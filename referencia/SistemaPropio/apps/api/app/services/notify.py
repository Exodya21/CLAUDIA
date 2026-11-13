"""Envíos salientes (correo; SMS cuando haya proveedor) mediante cola con idempotencia y adaptador (regla 11).

1. `enqueue` añade el envío en la MISMA transacción que el cambio que lo provoca, con una clave única: repetir la
   operación no duplica el correo.
2. `dispatch_pending` lo entrega fuera de la petición (tarea en segundo plano tras responder, o
   `python -m app.ops.outbox` desde un programador de tareas) y reintenta los fallos hasta 5 veces.
3. Sin SMTP configurado, el envío queda «no configurado»: nada sale del servidor y se ve en la bandeja.

Los avisos NUNCA llevan el contenido del mensaje: solo que hay algo nuevo en el portal (secreto profesional).
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_sessionmaker
from ..models_comm import CommOutbox
from . import textcrypt

log = logging.getLogger("sistema.notify")
MAX_ATTEMPTS = 5


class EmailAdapter(Protocol):
    configured: bool

    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpEmail:
    configured = True

    def __init__(self) -> None:
        self.s = get_settings()

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.s.smtp_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=20) as smtp:
            if self.s.smtp_starttls:
                smtp.starttls()
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password or "")
            smtp.send_message(msg)


class NotConfigured:
    configured = False

    def send(self, to: str, subject: str, body: str) -> None:  # pragma: no cover - nunca se llama
        raise RuntimeError("Correo no configurado")


_override: EmailAdapter | None = None


def email_adapter() -> EmailAdapter:
    if _override is not None:
        return _override
    return SmtpEmail() if get_settings().smtp_host else NotConfigured()


def set_adapter_for_tests(a: EmailAdapter | None) -> None:
    global _override
    _override = a


def enqueue(db: Session, *, organization_id: uuid.UUID, purpose: str, to: str, subject: str, body: str,
            idem_key: str, message_id: uuid.UUID | None = None, portal_account_id: uuid.UUID | None = None) -> CommOutbox | None:
    """Añade un correo a la cola. Devuelve None si esa clave ya estaba (no se duplica)."""
    if db.execute(select(CommOutbox.id).where(CommOutbox.idem_key == idem_key)).first():
        return None
    row = CommOutbox(organization_id=organization_id, channel="email", purpose=purpose, to_address=to,
                     subject=subject, body_enc=textcrypt.enc(body), idem_key=idem_key, message_id=message_id,
                     portal_account_id=portal_account_id,
                     status="pendiente" if email_adapter().configured else "no_configurado")
    try:
        with db.begin_nested():
            db.add(row)
    except IntegrityError:
        return None
    return row


def dispatch_pending(limit: int = 50) -> dict:
    """Entrega lo pendiente con una sesión propia. Idempotente: un envío ya «enviado» no se repite."""
    adapter = email_adapter()
    out = {"enviados": 0, "errores": 0, "no_configurado": 0}
    db = get_sessionmaker()()
    try:
        rows = list(db.execute(select(CommOutbox).where(CommOutbox.status.in_(("pendiente", "error")),
                                                        CommOutbox.attempts < MAX_ATTEMPTS)
                               .order_by(CommOutbox.created_at).limit(limit).with_for_update(skip_locked=True)).scalars())
        for r in rows:
            if not adapter.configured:
                r.status = "no_configurado"
                out["no_configurado"] += 1
                continue
            r.attempts += 1
            try:
                adapter.send(r.to_address, r.subject, textcrypt.dec(r.body_enc))
                r.status, r.sent_at, r.last_error = "enviado", datetime.now(UTC), None
                out["enviados"] += 1
            except Exception as exc:  # noqa: BLE001 - el error se guarda y se reintenta
                r.status, r.last_error = "error", str(exc)[:300]
                out["errores"] += 1
                log.warning("Envío %s fallido (intento %s): %s", r.id, r.attempts, exc)
        db.commit()
    finally:
        db.close()
    return out
