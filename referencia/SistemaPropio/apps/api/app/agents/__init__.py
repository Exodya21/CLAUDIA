"""Agentes del sistema (los «motores» de Dirección). Ver `engine.py` y `registry.py`.

Desde los routers solo se usa `emit` (dentro de la transacción del cambio) y `dispatch_events` (tras responder).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..models_agents import AgentEvent

DATED_TASK_KINDS = ("conciliacion", "senalamiento")


def emit(db: Session, org_id: uuid.UUID, kind: str, ref_type: str | None = None, ref_id=None,
         payload: dict | None = None) -> None:
    db.add(AgentEvent(organization_id=org_id, kind=kind, ref_type=ref_type, ref_id=ref_id, payload=payload))


def dispatch_events() -> int:
    from .engine import dispatch_events as _d

    return _d()
