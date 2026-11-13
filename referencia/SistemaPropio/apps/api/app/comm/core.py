"""Reglas comunes de las conversaciones: hilos, lectura, avisos y escalado de urgentes."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..models import CaseAssignment, CaseFile, Contact, UserAccount
from ..models_comm import (
    CommAttachment,
    CommConfirmation,
    CommMessage,
    CommReadMark,
    CommThread,
    PortalAccount,
)
from ..models_work import Task, TaskEvent
from ..services import notify, textcrypt

URGENT_ESCALATE_AFTER = timedelta(hours=24)   # aviso urgente sin confirmar → tarea de llamada
IMPORTANT_UNOPENED_AFTER = timedelta(hours=48)  # aviso importante sin abrir → se marca
EDIT_WINDOW = timedelta(minutes=15)
MAX_TEXT = 5000


def now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ hilos
def case_thread(db: Session, cf: CaseFile) -> CommThread:
    """Hilo del expediente: se crea la primera vez que alguien lo abre (equipo o cliente)."""
    t = db.execute(select(CommThread).where(CommThread.case_id == cf.id)).scalar_one_or_none()
    if t is None:
        t = CommThread(organization_id=cf.organization_id, kind="expediente", case_id=cf.id, contact_id=cf.contact_id)
        db.add(t)
        db.flush()
    return t


def general_thread(db: Session, contact: Contact) -> CommThread:
    t = db.execute(select(CommThread).where(CommThread.contact_id == contact.id, CommThread.kind == "general")).scalar_one_or_none()
    if t is None:
        t = CommThread(organization_id=contact.organization_id, kind="general", contact_id=contact.id)
        db.add(t)
        db.flush()
    return t


def read_mark(db: Session, thread_id: uuid.UUID, reader_type: str, reader_id: uuid.UUID) -> datetime | None:
    return db.execute(select(CommReadMark.last_read_at).where(
        CommReadMark.thread_id == thread_id, CommReadMark.reader_type == reader_type,
        CommReadMark.reader_id == reader_id)).scalar()


def mark_read(db: Session, thread_id: uuid.UUID, reader_type: str, reader_id: uuid.UUID) -> None:
    m = db.get(CommReadMark, (thread_id, reader_type, reader_id))
    if m is None:
        db.add(CommReadMark(thread_id=thread_id, reader_type=reader_type, reader_id=reader_id, last_read_at=now()))
    else:
        m.last_read_at = now()


def client_read_at(db: Session, t: CommThread) -> datetime | None:
    acc = portal_account_for(db, t.contact_id)
    return read_mark(db, t.id, "portal", acc.id) if acc else None


def portal_account_for(db: Session, contact_id: uuid.UUID) -> PortalAccount | None:
    return db.execute(select(PortalAccount).where(PortalAccount.contact_id == contact_id)).scalar_one_or_none()


# ------------------------------------------------------------------ salida
def _author(db: Session, m: CommMessage, cache: dict) -> dict:
    if m.kind == "sistema":
        return {"type": "sistema", "name": "Despacho"}
    if m.author_user_id:
        if m.author_user_id not in cache:
            u = db.get(UserAccount, m.author_user_id)
            cache[m.author_user_id] = u.full_name if u else "Equipo"
        return {"type": "equipo", "name": cache[m.author_user_id], "id": str(m.author_user_id)}
    acc = db.get(PortalAccount, m.author_portal_id)
    c = db.get(Contact, acc.contact_id) if acc else None
    return {"type": "cliente", "name": f"{c.given_name} {c.family_names}" if c else "Cliente"}


def message_out(db: Session, m: CommMessage, *, viewer: str, client_read: datetime | None = None,
                cache: dict | None = None, viewer_portal_id: uuid.UUID | None = None) -> dict:
    """Vista de un mensaje. El cliente nunca recibe notas internas ni mensajes ocultos (se filtran antes)."""
    cache = cache if cache is not None else {}
    atts = list(db.execute(select(CommAttachment).where(CommAttachment.message_id == m.id)).scalars())
    confirmed = db.execute(select(CommConfirmation.confirmed_at).where(CommConfirmation.message_id == m.id)
                           .order_by(CommConfirmation.confirmed_at).limit(1)).scalar()
    out = {
        "id": str(m.id), "kind": m.kind, "visibility": m.visibility, "level": m.level,
        "text": textcrypt.dec(m.body_enc), "author": _author(db, m, cache), "created_at": m.created_at.isoformat(),
        "edited_at": m.edited_at.isoformat() if m.edited_at else None, "version": m.version,
        "reply_to": str(m.reply_to_id) if m.reply_to_id else None,
        "requires_confirmation": m.requires_confirmation,
        "confirmed_at": confirmed.isoformat() if confirmed else None,
        "attachments": [{"id": str(a.id), "name": a.original_name, "mime": a.mime, "size": a.size_bytes,
                         "requirement_index": a.requirement_index,
                         **({"incorporated": bool(a.incorporated_doc_id)} if viewer == "staff" else {})} for a in atts],
    }
    mine = (viewer == "portal" and m.author_portal_id == viewer_portal_id) or False
    out["can_edit"] = bool(mine and m.created_at > now() - EDIT_WINDOW)
    if viewer == "staff":
        from_staff = m.author_user_id is not None or m.kind == "sistema"
        out["read_by_client"] = bool(from_staff and m.visibility == "cliente" and client_read and client_read >= m.created_at)
        out["hidden"] = m.hidden_at is not None
        out["hidden_reason"] = m.hidden_reason
        out["template"] = m.template
        out["escalated_task_id"] = str(m.escalated_task_id) if m.escalated_task_id else None
        out["unopened_48h"] = bool(m.level == "importante" and m.visibility == "cliente" and not out["read_by_client"]
                                   and m.created_at < now() - IMPORTANT_UNOPENED_AFTER)
        out["can_edit"] = bool(m.author_user_id is not None and not m.template and m.created_at > now() - EDIT_WINDOW)
    return out


# ------------------------------------------------------------------ avisos al cliente (sin contenido)
def notify_client(db: Session, t: CommThread, m: CommMessage, case_code: str | None) -> None:
    acc = portal_account_for(db, t.contact_id)
    if not acc or acc.status == "bloqueada" or m.visibility != "cliente" or m.hidden_at:
        return
    portal = get_settings().web_origin.rstrip("/") + "/portal"
    where = f" sobre su expediente {case_code}" if case_code else ""
    if m.level == "urgente":
        subject, key = "Aviso urgente del despacho: entre en su portal", f"aviso:{m.id}"
        body = (f"Tiene un aviso URGENTE del despacho{where}. Por motivos de confidencialidad no lo incluimos en este "
                f"correo: entre en su portal para leerlo y confirmarlo.\n\n{portal}\n\nSi no ha solicitado este acceso, "
                "ignore este mensaje.")
    elif m.level == "importante":
        subject, key = "Aviso importante del despacho", f"aviso:{m.id}"
        body = (f"Tiene un aviso importante del despacho{where}. Entre en su portal para leerlo.\n\n{portal}")
    else:
        # Mensajes del día a día: como mucho un correo por conversación y hora.
        bucket = now().strftime("%Y%m%d%H")
        subject, key = "Tiene un mensaje nuevo del despacho", f"mensaje:{t.id}:{bucket}"
        body = f"Tiene un mensaje nuevo del despacho{where}. Entre en su portal para leerlo.\n\n{portal}"
    notify.enqueue(db, organization_id=t.organization_id, purpose="aviso", to=acc.email, subject=subject, body=body,
                   idem_key=key, message_id=m.id, portal_account_id=acc.id)


# ------------------------------------------------------------------ escalado de urgentes
def _responsible(db: Session, cf: CaseFile | None, fallback: uuid.UUID) -> uuid.UUID:
    if cf is None:
        return fallback
    a = db.execute(select(CaseAssignment.user_id).where(
        CaseAssignment.case_id == cf.id, CaseAssignment.end_at.is_(None)).order_by(CaseAssignment.start_at)).first()
    return a[0] if a else fallback


def sweep_urgent(db: Session, org_ids: set[uuid.UUID] | None = None) -> int:
    """Avisos urgentes sin confirmar tras 24 h → una tarea de llamada (una sola vez por aviso)."""
    limit = now() - URGENT_ESCALATE_AFTER
    q = select(CommMessage).where(
        CommMessage.requires_confirmation.is_(True), CommMessage.escalated_task_id.is_(None),
        CommMessage.hidden_at.is_(None), CommMessage.created_at < limit,
        ~select(CommConfirmation.id).where(CommConfirmation.message_id == CommMessage.id).exists())
    if org_ids is not None:
        q = q.where(CommMessage.organization_id.in_(org_ids or {uuid.uuid4()}))
    n = 0
    for m in db.execute(q.with_for_update(skip_locked=True)).scalars():
        t = db.get(CommThread, m.thread_id)
        cf = db.get(CaseFile, t.case_id) if t.case_id else None
        who = m.author_user_id or _responsible(db, cf, m.author_user_id)
        if who is None:
            continue
        task = Task(organization_id=m.organization_id, case_id=t.case_id, kind="llamada", priority="alta",
                    title="Llamar al cliente: aviso urgente sin confirmar",
                    description=("El cliente no ha confirmado en 24 h la lectura de un aviso urgente del portal. "
                                 "Llámele para asegurarse de que lo conoce."),
                    assignee_id=_responsible(db, cf, who), due_at=now() + timedelta(hours=4), created_by=who)
        db.add(task)
        db.flush()
        db.add(TaskEvent(task_id=task.id, actor_user_id=who, kind="creada",
                         reason="Escalado automático de aviso urgente sin confirmar"))
        m.escalated_task_id = task.id
        audit.record(db, actor_id=None, action="comm.urgent.escalated", resource_type="comm_thread", resource_id=t.id,
                     organization_id=m.organization_id, after={"mensaje": str(m.id), "tarea": str(task.id)})
        n += 1
    return n


def unread_for_user(db: Session, thread_ids: list[uuid.UUID], user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Mensajes del cliente que esta persona aún no ha leído, por hilo."""
    if not thread_ids:
        return {}
    marks = dict(db.execute(select(CommReadMark.thread_id, CommReadMark.last_read_at).where(
        CommReadMark.thread_id.in_(thread_ids), CommReadMark.reader_type == "user",
        CommReadMark.reader_id == user_id)).all())
    out: dict[uuid.UUID, int] = {}
    rows = db.execute(select(CommMessage.thread_id, CommMessage.created_at).where(
        CommMessage.thread_id.in_(thread_ids), CommMessage.author_portal_id.is_not(None))).all()
    for tid, at in rows:
        if marks.get(tid) is None or at > marks[tid]:
            out[tid] = out.get(tid, 0) + 1
    return out


def clean_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").strip()
    return t[:MAX_TEXT]


def today() -> date:
    return date.today()


__all__ = ["case_thread", "general_thread", "message_out", "notify_client", "sweep_urgent", "func"]
