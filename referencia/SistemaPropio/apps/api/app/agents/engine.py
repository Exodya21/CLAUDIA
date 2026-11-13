"""Motor que coordina los agentes: emite eventos, los reparte, lanza el calendario y aplica decisiones.

- `emit` se llama DENTRO de la transacción del cambio (si el cambio no se guarda, el evento tampoco).
- `dispatch_events` y `run_scheduled` trabajan después (tras la respuesta o con `python -m app.ops.agents`).
- Cada ejecución de un agente usa su propio punto de guardado: si un agente falla, los demás siguen y el fallo
  queda registrado en `agent_run` (con reintentos del evento hasta 5 veces).
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_sessionmaker
from ..models import Organization
from ..models_agents import AgentEvent, AgentProposal, AgentRun
from . import emit  # noqa: F401 - reexportado
from .base import Agent, ApplyError, RunContext, now, setting
from .registry import AGENTS, by_code

log = logging.getLogger("sistema.agents")
MAX_ATTEMPTS = 5


def _run(db: Session, agent: Agent, org_id: uuid.UUID, trigger: str, fn, event: AgentEvent | None = None,
         user_id=None) -> AgentRun | None:
    st = setting(db, org_id, agent)
    if not st.enabled:
        return None
    run = AgentRun(organization_id=org_id, agent_code=agent.code, trigger=trigger,
                   event_id=event.id if event else None, started_by=user_id)
    db.add(run)
    db.flush()
    ctx = RunContext(db=db, org_id=org_id, run=run, mode=st.mode)
    try:
        with db.begin_nested():
            fn(ctx)
        run.status = "ok"
    except Exception as exc:  # noqa: BLE001 - se registra y se sigue con los demás agentes
        log.exception("Agente %s falló", agent.code)
        run.status, run.error = "error", str(exc)[:500]
        if event is not None:
            raise
    finally:
        run.finished_at = now()
        run.summary = ctx.counts or None
    return run


def dispatch_events(limit: int = 200) -> int:
    """Reparte los eventos pendientes entre los agentes que los escuchan (sesión propia)."""
    db = get_sessionmaker()()
    n = 0
    try:
        events = list(db.execute(select(AgentEvent).where(AgentEvent.processed_at.is_(None),
                                                          AgentEvent.attempts < MAX_ATTEMPTS)
                                 .order_by(AgentEvent.created_at).limit(limit).with_for_update(skip_locked=True)).scalars())
        for ev in events:
            ev.attempts += 1
            try:
                with db.begin_nested():
                    for agent in AGENTS:
                        if ev.kind in agent.events:
                            _run(db, agent, ev.organization_id, f"evento:{ev.kind}",
                                 lambda ctx, a=agent, e=ev: a.handle(ctx, e), event=ev)
                ev.processed_at, ev.last_error = now(), None
                n += 1
            except Exception as exc:  # noqa: BLE001
                ev.last_error = str(exc)[:300]
                db.add(AgentRun(organization_id=ev.organization_id, agent_code="motor", trigger=f"evento:{ev.kind}",
                                event_id=ev.id, status="error", finished_at=now(), error=str(exc)[:500]))
        db.commit()
    finally:
        db.close()
    return n


def run_scheduled(db: Session, only: str | None = None, user_id=None, org_ids: set | None = None) -> list[AgentRun]:
    """Trabajo por calendario de cada agente y entidad (idempotente: las claves evitan duplicados)."""
    runs = []
    orgs = [o.id for o in db.execute(select(Organization)).scalars() if org_ids is None or o.id in org_ids]
    for agent in AGENTS:
        if agent.scheduled_every_min is None or (only and agent.code != only):
            continue
        for org_id in orgs:
            if only is None and _ran_recently(db, agent, org_id):
                continue
            r = _run(db, agent, org_id, "manual" if user_id else "calendario", agent.scheduled, user_id=user_id)
            if r:
                runs.append(r)
    return runs


def _ran_recently(db: Session, agent: Agent, org_id) -> bool:
    last = db.execute(select(AgentRun.started_at).where(AgentRun.agent_code == agent.code,
                                                        AgentRun.organization_id == org_id,
                                                        AgentRun.trigger == "calendario")
                      .order_by(AgentRun.started_at.desc()).limit(1)).scalar()
    return bool(last and last > now() - timedelta(minutes=agent.scheduled_every_min or 0))


def decide(db: Session, proposal: AgentProposal, user, approve: bool, note: str | None, request_ctx) -> AgentProposal:
    """Una persona aprueba (y se aplica) o rechaza una propuesta. El permiso lo comprueba el router."""
    agent = by_code(proposal.agent_code)
    if proposal.status != "pendiente":
        raise ApplyError(f"La propuesta ya está {proposal.status}.")
    before = {"estado": proposal.status}
    proposal.decision_note = (note or "").strip()[:500] or None
    if approve:
        try:
            with db.begin_nested():
                proposal.result = agent.apply(db, proposal, user, request_ctx) or None
        except ApplyError:
            raise
        proposal.status, proposal.applied_at = "aprobada", now()
    else:
        agent.reject(db, proposal, user)
        proposal.status = "rechazada"
    proposal.decided_by, proposal.decided_at = user.id, now()
    audit.record(db, actor_id=user.id, action=f"agent.proposal.{'approve' if approve else 'reject'}",
                 resource_type="agent_proposal", resource_id=proposal.id, organization_id=proposal.organization_id,
                 before=before, after={"estado": proposal.status, "agente": agent.code, "tipo": proposal.kind,
                                       "resultado": proposal.result},
                 reason=note or None, ip=request_ctx.ip, request_id=request_ctx.request_id)
    return proposal
