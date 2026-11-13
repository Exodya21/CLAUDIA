"""Auditoría inmutable (Q-6.17, AT-03).

Cada evento guarda el hash del anterior (cadena SHA-256). Un bloqueo consultivo de
transacción serializa la escritura de la cadena. La base de datos impide UPDATE,
DELETE y TRUNCATE sobre audit_event mediante triggers (ver migración 0001).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import get_sessionmaker
from .models import AuditEvent

GENESIS = "0" * 64
_LOCK_KEY = 815_200_001  # constante del bloqueo consultivo de la cadena de auditoría


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def record(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: Any = None,
    organization_id: uuid.UUID | None = None,
    outcome: str = "ok",
    reason: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Añade un evento dentro de la transacción en curso (atómico con el cambio auditado)."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    prev = db.execute(select(AuditEvent.hash).order_by(AuditEvent.id.desc()).limit(1)).scalar()
    prev_hash = prev or GENESIS
    occurred = datetime.now(UTC)
    payload = {
        "occurred_at": occurred.isoformat(),
        "actor_user_id": str(actor_id) if actor_id else None,
        "organization_id": str(organization_id) if organization_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "outcome": outcome,
        "reason": reason,
        "before": before,
        "after": after,
    }
    ev = AuditEvent(
        occurred_at=occurred,
        actor_user_id=actor_id,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=payload["resource_id"],
        outcome=outcome,
        reason=reason,
        before=before,
        after=after,
        ip=ip,
        request_id=request_id,
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, payload),
    )
    db.add(ev)
    db.flush()
    return ev


def record_independent(**kwargs: Any) -> None:
    """Registra en una transacción propia: las denegaciones deben persistir aunque la petición falle."""
    s = get_sessionmaker()()
    try:
        record(s, **kwargs)
        s.commit()
    finally:
        s.close()


def verify_chain(db: Session) -> tuple[bool, int, int | None]:
    """Recalcula la cadena completa. Devuelve (íntegra, eventos revisados, primer id roto)."""
    prev_hash = GENESIS
    n = 0
    for ev in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        payload = {
            "occurred_at": ev.occurred_at.astimezone(UTC).isoformat(),
            "actor_user_id": str(ev.actor_user_id) if ev.actor_user_id else None,
            "organization_id": str(ev.organization_id) if ev.organization_id else None,
            "action": ev.action,
            "resource_type": ev.resource_type,
            "resource_id": ev.resource_id,
            "outcome": ev.outcome,
            "reason": ev.reason,
            "before": ev.before,
            "after": ev.after,
        }
        if ev.prev_hash != prev_hash or compute_hash(prev_hash, payload) != ev.hash:
            return False, n, ev.id
        prev_hash = ev.hash
        n += 1
    return True, n, None
