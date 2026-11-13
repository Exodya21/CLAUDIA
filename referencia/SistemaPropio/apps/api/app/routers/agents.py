"""Agentes (motores de Dirección) y bandeja única de propuestas (F5.1).

- La bandeja muestra a cada persona SOLO lo que puede decidir: el permiso de la propuesta en su entidad y, si la
  propuesta es de un expediente y su efecto es hablar con el cliente, acceso completo a ese expediente.
- Decidir = aprobar (se aplica con los permisos de quien aprueba) o rechazar con motivo. Todo auditado.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..agents import engine
from ..agents.base import ApplyError, now, setting
from ..agents.registry import AGENTS, get
from ..comm import auto_templates
from ..db import get_db
from ..errors import api_error
from ..models import CaseFile, UserAccount
from ..models_agents import AgentProposal, AgentRun, AgentSetting, CommDispatch
from ..models_comm import CommMessage, CommThread
from ..security.auth import Principal, get_principal
from ..security.policy import case_level, load_case_scope
from ..services import notify
from .common import req_ctx

router = APIRouter(tags=["agentes"])
CLIENT_FACING = ("mensaje", "dato_falta", "invitar_portal")


def _deny(p: Principal, request: Request, action: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type="agent", resource_id=rid, organization_id=org,
                             outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


BRANCH_SCOPED = ("cierre_pendiente",)  # avisos de una sede: solo para quien trabaja en ella


def can_decide(db: Session, p: Principal, prop: AgentProposal, scope=None) -> bool:
    if prop.organization_id not in p.org_ids() or not p.has(prop.organization_id, prop.permission):
        return False
    if prop.kind in BRANCH_SCOPED and prop.branch_id:
        if not any(m.branch_id in (None, prop.branch_id) for m in p.memberships_with(prop.organization_id, prop.permission)):
            return False
    if prop.kind == "remesa_firma" and prop.ref_id:
        from ..models_accounting import PaymentBatch, PaymentBatchApproval
        b = db.get(PaymentBatch, prop.ref_id)
        if b is None or b.proposed_by == p.id or db.execute(select(PaymentBatchApproval.id).where(
                PaymentBatchApproval.batch_id == b.id, PaymentBatchApproval.approver_id == p.id)).first():
            return False
    if prop.kind in CLIENT_FACING and prop.case_id:
        cf = db.get(CaseFile, prop.case_id)
        return cf is not None and case_level(p, cf, scope or load_case_scope(db, p)) == "full"
    return True


def _proposal_out(db: Session, x: AgentProposal, cache: dict) -> dict:
    a = get(x.agent_code)

    def name(uid):
        if uid is None:
            return None
        if uid not in cache:
            u = db.get(UserAccount, uid)
            cache[uid] = u.full_name if u else "?"
        return cache[uid]
    cf = db.get(CaseFile, x.case_id) if x.case_id else None
    return {"id": str(x.id), "agent": x.agent_code, "agent_name": a.name if a else x.agent_code, "kind": x.kind,
            "title": x.title, "detail": x.detail, "priority": x.priority, "status": x.status,
            "organization_id": str(x.organization_id), "case_id": str(x.case_id) if x.case_id else None,
            "case_code": cf.code if cf else None, "ref_type": x.ref_type, "ref_id": str(x.ref_id) if x.ref_id else None,
            "payload": x.payload, "assignee": name(x.assignee_id), "created_at": x.created_at.isoformat(),
            "decided_by": name(x.decided_by), "decided_at": x.decided_at.isoformat() if x.decided_at else None,
            "decision_note": x.decision_note, "result": x.result,
            "approvable": x.kind not in ("dato_falta", "invitar_portal", "cierre_pendiente", "factura_validar",
                                         "factura_vence", "factura_falta")
            and not (x.kind == "excepcion_banco" and not (x.payload or {}).get("aprobable"))}


# ------------------------------------------------------------------ bandeja única
@router.get("/proposals")
def list_proposals(request: Request, status: Literal["pendiente", "aprobada", "rechazada", "caducada"] = "pendiente",
                   agent: str | None = Query(default=None, max_length=40), mine: bool = False,
                   case_id: uuid.UUID | None = None, kind: str | None = Query(default=None, max_length=120),
                   p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Pendientes que la persona puede decidir. Cada pantalla los pide filtrados por su función: Contabilidad
    (agent=conciliacion), Comunicaciones (agent=mensajes), un expediente (case_id) o el resumen de Inicio."""
    orgs = p.org_ids()
    stmt = select(AgentProposal).where(AgentProposal.organization_id.in_(orgs), AgentProposal.status == status)
    if agent:
        stmt = stmt.where(AgentProposal.agent_code == agent)
    if case_id:
        stmt = stmt.where(AgentProposal.case_id == case_id)
    if kind:
        stmt = stmt.where(AgentProposal.kind.in_([k.strip() for k in kind.split(",") if k.strip()]))
    if mine:
        stmt = stmt.where(AgentProposal.assignee_id == p.id)
    order = (case({"alta": 0, "media": 1}, value=AgentProposal.priority, else_=2), AgentProposal.created_at)
    rows = db.execute(stmt.order_by(*order) if status == "pendiente" else
                      stmt.order_by(AgentProposal.decided_at.desc().nulls_last())).scalars()
    scope = load_case_scope(db, p)
    cache: dict = {}
    items = []
    for x in rows:
        if can_decide(db, p, x, scope):
            items.append(_proposal_out(db, x, cache))
            if len(items) >= 300:
                break
    counts: dict = {}
    for x in db.execute(select(AgentProposal).where(AgentProposal.organization_id.in_(orgs),
                                                    AgentProposal.status == "pendiente")).scalars():
        if can_decide(db, p, x, scope):
            counts[x.agent_code] = counts.get(x.agent_code, 0) + 1
    return {"items": items, "pending_by_agent": counts, "pending_total": sum(counts.values())}


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


@router.post("/proposals/{proposal_id}/decide")
def decide(proposal_id: uuid.UUID, body: DecisionIn, request: Request, background: BackgroundTasks,
           p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    x = db.get(AgentProposal, proposal_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Propuesta no encontrada.")
    db.execute(select(AgentProposal).where(AgentProposal.id == x.id).with_for_update())
    db.refresh(x)
    if not can_decide(db, p, x):
        _deny(p, request, "agent.proposal.decide", x.id, x.organization_id, f"sin {x.permission} o sin acceso al expediente")
        raise api_error(403, "prohibido", "Esta propuesta la decide otro perfil.")
    if not body.approve and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Indique el motivo del rechazo (mín. 5 caracteres).")
    try:
        engine.decide(db, x, p, body.approve, body.note, req_ctx(request))
    except ApplyError as exc:
        db.rollback()
        code = "conflicto" if exc.status == 409 else ("prohibido" if exc.status == 403 else "validacion")
        raise api_error(exc.status, code, exc.message) from exc
    db.commit()
    background.add_task(notify.dispatch_pending)
    return _proposal_out(db, x, {})


# ------------------------------------------------------------------ agentes
def _view_orgs(p: Principal, request: Request) -> set:
    orgs = p.orgs_with("agents.view")
    if not orgs:
        _deny(p, request, "agents.view", None, None, "sin agents.view")
        raise api_error(403, "prohibido", "No tiene acceso al panel de agentes.")
    return orgs


@router.get("/agents")
def list_agents(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = _view_orgs(p, request)
    out = []
    for a in AGENTS:
        per_org = []
        for org in sorted(orgs, key=str):
            st = db.execute(select(AgentSetting).where(AgentSetting.organization_id == org,
                                                       AgentSetting.agent_code == a.code)).scalar_one_or_none()
            last = db.execute(select(AgentRun).where(AgentRun.organization_id == org, AgentRun.agent_code == a.code)
                              .order_by(AgentRun.started_at.desc()).limit(1)).scalar_one_or_none()
            pending = db.execute(select(func.count()).select_from(AgentProposal).where(
                AgentProposal.organization_id == org, AgentProposal.agent_code == a.code,
                AgentProposal.status == "pendiente")).scalar()
            errors_24h = db.execute(select(func.count()).select_from(AgentRun).where(
                AgentRun.organization_id == org, AgentRun.agent_code == a.code, AgentRun.status == "error",
                AgentRun.started_at > now() - timedelta(hours=24))).scalar()
            per_org.append({"organization_id": str(org), "enabled": st.enabled if st else True,
                            "mode": st.mode if st else "propone", "version": st.version if st else 0,
                            "can_manage": p.has(org, "agents.manage"), "pending": pending, "errors_24h": errors_24h,
                            "last_run": {"at": last.started_at.isoformat(), "status": last.status,
                                         "trigger": last.trigger, "summary": last.summary, "error": last.error}
                            if last else None})
        out.append({"code": a.code, "name": a.name, "area": a.area, "description": a.description,
                    "covers": list(a.covers), "requirements": list(a.requirements), "events": list(a.events),
                    "every_min": a.scheduled_every_min, "can_be_automatic": a.can_be_automatic,
                    "limits": list(a.limits), "orgs": per_org})
    return out


class SettingIn(BaseModel):
    organization_id: uuid.UUID
    enabled: bool
    mode: Literal["propone", "automatico"]
    reason: str = Field(min_length=5, max_length=300)


@router.post("/agents/{code}/settings")
def update_setting(code: str, body: SettingIn, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    a = get(code)
    if a is None or body.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Agente no encontrado.")
    if not p.has(body.organization_id, "agents.manage"):
        _deny(p, request, "agents.manage", None, body.organization_id, f"sin agents.manage ({code})")
        raise api_error(403, "prohibido", "Solo Dirección configura los agentes.")
    if body.mode == "automatico" and not a.can_be_automatic:
        raise api_error(422, "validacion", "Este agente solo propone: lo que hace siempre lo valida una persona.")
    st = setting(db, body.organization_id, a)
    before = {"activo": st.enabled, "modo": st.mode}
    st.enabled, st.mode, st.updated_by, st.updated_at = body.enabled, body.mode, p.id, now()
    st.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="agent.setting", resource_type="agent", resource_id=None,
                 organization_id=body.organization_id, reason=body.reason, before=before,
                 after={"agente": code, "activo": st.enabled, "modo": st.mode}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"code": code, "enabled": st.enabled, "mode": st.mode, "version": st.version}


@router.get("/agents/{code}/runs")
def list_runs(code: str, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = _view_orgs(p, request)
    if get(code) is None:
        raise api_error(404, "no_encontrado", "Agente no encontrado.")
    rows = db.execute(select(AgentRun).where(AgentRun.agent_code == code, AgentRun.organization_id.in_(orgs))
                      .order_by(AgentRun.started_at.desc()).limit(100)).scalars()
    return [{"id": str(r.id), "organization_id": str(r.organization_id), "trigger": r.trigger, "status": r.status,
             "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None,
             "summary": r.summary, "error": r.error} for r in rows]


@router.post("/agents/{code}/run")
def run_agent(code: str, request: Request, organization_id: uuid.UUID = Query(...),
              p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    a = get(code)
    if a is None or organization_id not in p.org_ids() or a.scheduled_every_min is None:
        raise api_error(404, "no_encontrado", "Agente no encontrado.")
    if not p.has(organization_id, "agents.manage"):
        _deny(p, request, "agent.run", None, organization_id, f"sin agents.manage ({code})")
        raise api_error(403, "prohibido", "Solo Dirección lanza agentes a mano.")
    runs = engine.run_scheduled(db, only=code, user_id=p.id, org_ids={organization_id})
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="agent.run", resource_type="agent", resource_id=None,
                 organization_id=organization_id, after={"agente": code}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"runs": [{"id": str(r.id), "status": r.status, "summary": r.summary, "error": r.error} for r in runs]}


# ------------------------------------------------------------------ mensajes automáticos: plantillas y métricas
@router.get("/agents/mensajes/templates")
def message_templates(request: Request, p: Principal = Depends(get_principal)) -> list[dict]:
    _view_orgs(p, request)
    return auto_templates.catalog()


@router.get("/agents/mensajes/metrics")
def message_metrics(request: Request, days: int = Query(default=7, ge=1, le=92), p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    """Medición semanal del piloto (DR-MSG): programados, enviados, cancelados, fallidos, respuestas, derivados."""
    orgs = _view_orgs(p, request)
    since = now() - timedelta(days=days)
    rows = list(db.execute(select(CommDispatch).where(CommDispatch.organization_id.in_(orgs),
                                                      CommDispatch.created_at > since)).scalars())
    by_status: dict = {}
    by_template: dict = {}
    for d in rows:
        by_status[d.status] = by_status.get(d.status, 0) + 1
        t = by_template.setdefault(d.template, {"programados": 0, "enviados": 0, "cancelados": 0})
        t["programados"] += 1
        if d.status == "enviado":
            t["enviados"] += 1
        elif d.status == "cancelado":
            t["cancelados"] += 1
    replies = 0
    for d in rows:
        if d.status == "enviado" and d.sent_at:
            replies += db.execute(select(func.count()).select_from(CommMessage).join(
                CommThread, CommThread.id == CommMessage.thread_id).where(
                CommThread.case_id == d.case_id, CommMessage.author_portal_id.is_not(None),
                CommMessage.created_at > d.sent_at, CommMessage.created_at < d.sent_at + timedelta(days=3))).scalar() > 0
    dup = 0
    for r in db.execute(select(AgentRun.summary).where(AgentRun.organization_id.in_(orgs), AgentRun.agent_code == "mensajes",
                                                       AgentRun.started_at > since)).scalars():
        dup += (r or {}).get("duplicados_evitados", 0)
    derived = db.execute(select(func.count()).select_from(AgentProposal).where(
        AgentProposal.organization_id.in_(orgs), AgentProposal.agent_code == "mensajes",
        AgentProposal.kind.in_(("dato_falta", "invitar_portal")), AgentProposal.created_at > since)).scalar()
    return {"days": days, "programados": len(rows), "por_estado": by_status, "por_plantilla": by_template,
            "con_respuesta_3_dias": replies, "duplicados_evitados": dup, "derivados_al_equipo": derived,
            "plantillas_version": auto_templates.VERSION}
