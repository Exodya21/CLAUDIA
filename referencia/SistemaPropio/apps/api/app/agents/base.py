"""Base de los agentes (los «motores» de los documentos de Dirección).

Un agente:
- tiene un código, un nombre, el área, los motores de Dirección que cubre (DR-…) y los requisitos de la matriz;
- escucha eventos (`events`) y/o trabaja por calendario (`scheduled`);
- deja propuestas en la bandeja única (`propose`) o, solo donde se permite y Dirección lo activa, actúa solo;
- sabe aplicar una propuesta aprobada (`apply`) con los permisos de la persona que la aprueba.
Todo queda en `agent_run`, en la propia propuesta y en la auditoría.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models_agents import AgentEvent, AgentProposal, AgentRun, AgentSetting


def now() -> datetime:
    return datetime.now(UTC)


class ApplyError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.message, self.status = message, status


@dataclass
class RunContext:
    db: Session
    org_id: uuid.UUID
    run: AgentRun
    mode: str
    counts: dict = field(default_factory=dict)

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


class Agent:
    code: str = ""
    name: str = ""
    area: str = ""
    description: str = ""
    covers: tuple[str, ...] = ()        # motores de Dirección (DR-…)
    requirements: tuple[str, ...] = ()  # requisitos de la matriz
    events: tuple[str, ...] = ()
    scheduled_every_min: int | None = None
    can_be_automatic: bool = False      # solo algunos pueden actuar sin aprobación (T-47)
    view_permission: str = "agents.view"
    limits: tuple[str, ...] = ()        # lo que el agente NUNCA hace (se muestra en la pantalla)

    def handle(self, ctx: RunContext, event: AgentEvent) -> None:  # pragma: no cover - lo implementa cada agente
        pass

    def scheduled(self, ctx: RunContext) -> None:  # pragma: no cover
        pass

    def apply(self, db: Session, proposal: AgentProposal, user, request_ctx) -> dict:  # pragma: no cover
        raise ApplyError("Este agente no aplica propuestas.")

    def reject(self, db: Session, proposal: AgentProposal, user) -> None:
        """Gancho opcional al rechazar (p. ej. liberar un emparejamiento)."""


def setting(db: Session, org_id: uuid.UUID, agent: Agent) -> AgentSetting:
    s = db.execute(select(AgentSetting).where(AgentSetting.organization_id == org_id,
                                              AgentSetting.agent_code == agent.code)).scalar_one_or_none()
    if s is None:
        s = AgentSetting(organization_id=org_id, agent_code=agent.code, enabled=True, mode="propone")
        db.add(s)
        db.flush()
    return s


def propose(ctx: RunContext, agent: Agent, *, kind: str, title: str, permission: str, dedupe_key: str,
            detail: str | None = None, priority: str = "media", case_id=None, branch_id=None, assignee_id=None,
            ref_type: str | None = None, ref_id=None, payload: dict | None = None) -> AgentProposal | None:
    """Añade una propuesta a la bandeja. Si ya existe la misma (clave), no se duplica y devuelve None."""
    db = ctx.db
    if db.execute(select(AgentProposal.id).where(AgentProposal.dedupe_key == dedupe_key)).first():
        ctx.count("duplicados_evitados")
        return None
    p = AgentProposal(organization_id=ctx.org_id, agent_code=agent.code, kind=kind, title=title[:200],
                      detail=detail, priority=priority, permission=permission, dedupe_key=dedupe_key[:160],
                      case_id=case_id, branch_id=branch_id, assignee_id=assignee_id, ref_type=ref_type,
                      ref_id=ref_id, payload=payload, run_id=ctx.run.id)
    try:
        with db.begin_nested():
            db.add(p)
    except IntegrityError:
        ctx.count("duplicados_evitados")
        return None
    ctx.count("propuestas")
    return p
