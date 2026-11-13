"""CRM de leads (M02, F1.2). Requisitos: Q-2.1, Q-2.7, Q-2.8, Q-3.1, I-099, I-102. Pruebas: AT-05, AT-06."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, CaseFile, Contact, UserAccount
from ..models_work import Lead, LeadEvent, LeadOrigin
from ..schemas import Page
from ..security.auth import Principal, get_principal
from ..security.policy import case_level, contact_level, contacts_with_full_case, load_case_scope
from ..validation import mask_phone
from .common import req_ctx

router = APIRouter(prefix="/leads", tags=["CRM"])

LeadStatus = Literal["nuevo", "contactado", "en_seguimiento", "cita_solicitada", "cita_pagada",
                     "convertido", "descartado", "no_convertido"]
OPEN = ("nuevo", "contactado", "en_seguimiento", "cita_solicitada")
# Transiciones manuales permitidas. 'convertido' solo lo pone el sistema al abrir expediente;
# 'cita_pagada' llegará con el módulo de Citas y su pasarela (F1.3).
FLOW: dict[str, set[str]] = {
    "nuevo": {"contactado", "en_seguimiento", "descartado"},
    "contactado": {"en_seguimiento", "cita_solicitada", "descartado"},
    "en_seguimiento": {"contactado", "cita_solicitada", "descartado"},
    "cita_solicitada": {"en_seguimiento", "no_convertido", "descartado"},
    "descartado": {"contactado"},
    "no_convertido": {"contactado"},
    "convertido": set(),
    "cita_pagada": set(),
}
NEEDS_NOTE = {"descartado", "no_convertido"}
FOLLOW_UP_HOURS = (24, 72, 24 * 7)  # Q-2.8: alertas de seguimiento a 24 h, 72 h y 7 días


# ---------------------------------------------------------------- esquemas
class LeadCreate(BaseModel):
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    origin_code: str = Field(min_length=2, max_length=40, description="Obligatorio (AT-05)")
    materia: Literal["laboral", "extranjeria", "nacionalidad", "otra"]
    branch_id: uuid.UUID | None = None
    summary: str = Field(default="", max_length=2000)
    campaign: str | None = Field(default=None, max_length=120)
    utm_source: str | None = Field(default=None, max_length=120)
    utm_medium: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=120)
    utm_content: str | None = Field(default=None, max_length=120)
    utm_term: str | None = Field(default=None, max_length=120)
    assigned_user_id: uuid.UUID | None = None


class LeadTransition(BaseModel):
    to: LeadStatus
    version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=1000)


class LeadAssign(BaseModel):
    version: int = Field(ge=1)
    assigned_user_id: uuid.UUID | None


class LeadOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str
    contact_phone_masked: str | None
    origin_code: str
    origin_name: str
    materia: str
    branch: str | None
    summary: str
    campaign: str | None
    utm: dict[str, str | None]
    assigned_user_id: uuid.UUID | None
    assigned_username: str | None
    status: str
    status_changed_at: datetime
    created_at: datetime
    version: int
    case_file_id: uuid.UUID | None
    case_code: str | None
    case_access: str | None
    follow_up_level: int  # 0 = al día; 1/2/3 = superado 24 h / 72 h / 7 días sin avanzar
    allowed_transitions: list[str]


class LeadEventOut(BaseModel):
    occurred_at: datetime
    actor: str
    from_status: str | None
    to_status: str
    note: str | None


class LeadDetail(LeadOut):
    events: list[LeadEventOut]


# ---------------------------------------------------------------- política
def _visibility(p: Principal) -> ColumnElement[bool]:
    conds: list[ColumnElement[bool]] = []
    for org in p.org_ids():
        if p.has(org, "lead.read.all"):
            conds.append(Lead.organization_id == org)
        elif p.has(org, "lead.read.own"):
            conds.append(and_(Lead.organization_id == org,
                              or_(Lead.assigned_user_id == p.id, Lead.created_by == p.id)))
    return or_(*conds) if conds else false()


def _can_see(p: Principal, lead: Lead) -> bool:
    org = lead.organization_id
    if org not in p.org_ids():
        return False
    if p.has(org, "lead.read.all"):
        return True
    return p.has(org, "lead.read.own") and p.id in (lead.assigned_user_id, lead.created_by)


def follow_up_level(lead: Lead, now: datetime | None = None) -> int:
    if lead.status not in OPEN or lead.status == "cita_solicitada":
        return 0
    hours = ((now or datetime.now(UTC)) - lead.status_changed_at).total_seconds() / 3600
    return sum(1 for h in FOLLOW_UP_HOURS if hours >= h)


def _out(db: Session, p: Principal, lead: Lead, scope=None) -> LeadOut:
    ct = db.get(Contact, lead.contact_id)
    origin = db.get(LeadOrigin, lead.origin_code)
    phone = next((pt.value_normalized for pt in ct.points if pt.kind == "phone"), None)
    case_code = case_access = None
    if lead.case_file_id:
        cf = db.get(CaseFile, lead.case_file_id)
        scope = scope or load_case_scope(db, p)
        case_access = case_level(p, cf, scope)
        case_code = cf.code if case_access else None
    assigned = db.get(UserAccount, lead.assigned_user_id) if lead.assigned_user_id else None
    br = db.get(Branch, lead.branch_id) if lead.branch_id else None
    allowed = sorted(FLOW[lead.status]) if p.has(lead.organization_id, "lead.transition") else []
    return LeadOut(
        id=lead.id, organization_id=lead.organization_id, contact_id=lead.contact_id,
        contact_name=f"{ct.given_name} {ct.family_names}", contact_phone_masked=mask_phone(phone) if phone else None,
        origin_code=lead.origin_code, origin_name=origin.name, materia=lead.materia, branch=br.name if br else None,
        summary=lead.summary, campaign=lead.campaign,
        utm={k: getattr(lead, f"utm_{k}") for k in ("source", "medium", "campaign", "content", "term")},
        assigned_user_id=lead.assigned_user_id, assigned_username=assigned.username if assigned else None,
        status=lead.status, status_changed_at=lead.status_changed_at, created_at=lead.created_at, version=lead.version,
        case_file_id=lead.case_file_id, case_code=case_code, case_access=case_access,
        follow_up_level=follow_up_level(lead), allowed_transitions=allowed,
    )


def _get_visible(db: Session, p: Principal, lead_id: uuid.UUID, request: Request) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or not _can_see(p, lead):
        ctx = req_ctx(request)
        audit.record_independent(actor_id=p.id, action="lead.read", resource_type="lead", resource_id=lead_id,
                                 organization_id=lead.organization_id if lead else None, outcome="denied",
                                 reason="fuera de ámbito o inexistente", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(404, "no_encontrado", "Lead no encontrado.")
    return lead


def _check_assignee(db: Session, org: uuid.UUID, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    from ..security.auth import load_principal

    ap = load_principal(db, user_id)
    if ap is None or not (ap.has(org, "lead.read.all") or ap.has(org, "lead.read.own")):
        raise api_error(422, "validacion", "La persona asignada no puede trabajar leads en esta entidad.",
                        [{"field": "assigned_user_id", "message": "Usuario no válido"}])


# ---------------------------------------------------------------- endpoints
@router.get("/origins", tags=["CRM"])
def origins(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(LeadOrigin).where(LeadOrigin.active.is_(True)).order_by(LeadOrigin.name)).scalars()
    return [{"code": o.code, "name": o.name, "requires_campaign": o.requires_campaign} for o in rows]


@router.get("", response_model=Page[LeadOut])
def list_leads(
    status: LeadStatus | None = None,
    origin: str | None = Query(default=None, max_length=40),
    materia: str | None = Query(default=None, max_length=20),
    mine: bool = False,
    follow_up: bool = Query(default=False, description="Solo leads abiertos que han superado 24 h sin avanzar"),
    contact_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=100),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not (p.orgs_with("lead.read.all") or p.orgs_with("lead.read.own")):
        raise api_error(403, "prohibido", "Su rol no tiene acceso al CRM.")
    where = _visibility(p)
    if status:
        where = and_(where, Lead.status == status)
    if origin:
        where = and_(where, Lead.origin_code == origin)
    if materia:
        where = and_(where, Lead.materia == materia)
    if mine:
        where = and_(where, Lead.assigned_user_id == p.id)
    if contact_id:
        where = and_(where, Lead.contact_id == contact_id)
    if follow_up:
        where = and_(where, Lead.status.in_(("nuevo", "contactado", "en_seguimiento")),
                     Lead.status_changed_at <= datetime.now(UTC) - timedelta(hours=FOLLOW_UP_HOURS[0]))
    total = db.execute(select(func.count()).select_from(Lead).where(where)).scalar_one()
    order = Lead.status_changed_at.asc() if follow_up else Lead.created_at.desc()
    rows = db.execute(select(Lead).where(where).order_by(order, Lead.id)
                      .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    scope = load_case_scope(db, p)
    return Page(items=[_out(db, p, x, scope) for x in rows], page=page, page_size=page_size, total=total)


@router.get("/funnel")
def funnel(
    desde: date | None = None,
    hasta: date | None = None,
    branch_id: uuid.UUID | None = None,
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Embudo (I-102, base de AT-27): mismos registros que la bandeja, sin tablas paralelas."""
    orgs = p.orgs_with("lead.funnel")
    if not orgs:
        raise api_error(403, "prohibido", "Su rol no puede consultar el embudo comercial.")
    where = Lead.organization_id.in_(orgs)
    if desde:
        where = and_(where, Lead.created_at >= datetime.combine(desde, time.min, UTC))
    if hasta:
        where = and_(where, Lead.created_at < datetime.combine(hasta + timedelta(days=1), time.min, UTC))
    if branch_id:
        where = and_(where, Lead.branch_id == branch_id)
    by_status = dict(db.execute(select(Lead.status, func.count()).where(where).group_by(Lead.status)).all())
    by_origin = []
    for code, name, total, conv in db.execute(
        select(Lead.origin_code, LeadOrigin.name, func.count(), func.count().filter(Lead.status == "convertido"))
        .join(LeadOrigin, LeadOrigin.code == Lead.origin_code).where(where)
        .group_by(Lead.origin_code, LeadOrigin.name).order_by(func.count().desc())
    ).all():
        by_origin.append({"origin": code, "name": name, "total": total, "convertidos": conv,
                          "conversion": round(conv / total, 4) if total else 0})
    total = sum(by_status.values())
    conv = by_status.get("convertido", 0)
    return {"total": total, "convertidos": conv, "conversion": round(conv / total, 4) if total else 0,
            "por_estado": by_status, "por_origen": by_origin,
            "nota": "Cita pagada e ingresos se incorporarán con Citas (F1.3) y Facturación (F5)."}


@router.post("", response_model=LeadOut, status_code=201)
def create_lead(body: LeadCreate, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    org = body.organization_id
    if org not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(org, "lead.create"):
        audit.record_independent(actor_id=p.id, action="lead.create", resource_type="lead", organization_id=org,
                                 outcome="denied", reason="sin lead.create", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Su rol no permite registrar leads.")
    origin = db.get(LeadOrigin, body.origin_code)
    if origin is None or not origin.active:
        raise api_error(422, "validacion", "Indique un origen válido: es obligatorio para todo lead.",
                        [{"field": "origin_code", "message": "Origen obligatorio"}])
    if origin.requires_campaign and not (body.campaign or body.utm_campaign):
        raise api_error(422, "validacion", f"El origen «{origin.name}» exige indicar la campaña.",
                        [{"field": "campaign", "message": "Campaña obligatoria para este origen"}])
    ct = db.get(Contact, body.contact_id)
    scope = load_case_scope(db, p)
    if ct is None or ct.organization_id != org or contact_level(p, ct, contacts_with_full_case(db, p, scope)) is None:
        raise api_error(422, "validacion", "El contacto no existe en esta entidad.",
                        [{"field": "contact_id", "message": "Contacto no válido"}])
    if body.branch_id:
        br = db.get(Branch, body.branch_id)
        if br is None or br.organization_id != org:
            raise api_error(422, "validacion", "La sede no pertenece a la entidad.")
    _check_assignee(db, org, body.assigned_user_id)
    lead = Lead(organization_id=org, contact_id=ct.id, origin_code=origin.code, materia=body.materia,
                branch_id=body.branch_id, summary=body.summary.strip(), campaign=body.campaign,
                utm_source=body.utm_source, utm_medium=body.utm_medium, utm_campaign=body.utm_campaign,
                utm_content=body.utm_content, utm_term=body.utm_term, assigned_user_id=body.assigned_user_id,
                created_by=p.id)
    db.add(lead)
    db.flush()
    db.add(LeadEvent(lead_id=lead.id, actor_user_id=p.id, from_status=None, to_status="nuevo", note="Alta"))
    audit.record(db, actor_id=p.id, action="lead.create", resource_type="lead", resource_id=lead.id,
                 organization_id=org, after={"contacto": str(ct.id), "origen": origin.code, "materia": body.materia,
                                             "campana": body.campaign, "utm_source": body.utm_source},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    db.refresh(lead)
    return _out(db, p, lead)


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    lead = _get_visible(db, p, lead_id, request)
    evs = db.execute(select(LeadEvent, UserAccount.username).join(UserAccount, UserAccount.id == LeadEvent.actor_user_id)
                     .where(LeadEvent.lead_id == lead.id).order_by(LeadEvent.occurred_at.desc())).all()
    return LeadDetail(**_out(db, p, lead).model_dump(), events=[
        LeadEventOut(occurred_at=e.occurred_at, actor=u, from_status=e.from_status, to_status=e.to_status, note=e.note)
        for e, u in evs])


@router.post("/{lead_id}/transition", response_model=LeadOut)
def transition(lead_id: uuid.UUID, body: LeadTransition, request: Request,
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    lead = _get_visible(db, p, lead_id, request)
    org = lead.organization_id
    if not p.has(org, "lead.transition"):
        audit.record_independent(actor_id=p.id, action="lead.transition", resource_type="lead", resource_id=lead.id,
                                 organization_id=org, outcome="denied", reason="sin lead.transition",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Su rol no permite cambiar el estado de los leads.")
    db.execute(select(Lead).where(Lead.id == lead.id).with_for_update())
    db.refresh(lead)
    if lead.version != body.version:
        raise api_error(409, "conflicto_version", "El lead ha cambiado desde que lo abrió. Recargue.")
    if body.to == "cita_pagada":
        raise api_error(422, "no_disponible_aun", "No disponible aún: la cita pagada llegará con el módulo de Citas (F1.3).")
    if body.to == "convertido":
        raise api_error(422, "validacion", "Un lead se convierte al abrir su expediente desde la ficha del lead.")
    if body.to not in FLOW[lead.status]:
        raise api_error(409, "transicion_no_permitida", f"No se puede pasar de «{lead.status}» a «{body.to}».")
    reopening = lead.status in ("descartado", "no_convertido")
    if (body.to in NEEDS_NOTE or reopening) and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Indique el motivo (mín. 5 caracteres).", [{"field": "note", "message": "Motivo obligatorio"}])
    prev = lead.status
    lead.status = body.to
    lead.status_changed_at = datetime.now(UTC)
    lead.version += 1
    db.add(LeadEvent(lead_id=lead.id, actor_user_id=p.id, from_status=prev, to_status=body.to, note=body.note))
    audit.record(db, actor_id=p.id, action="lead.transition", resource_type="lead", resource_id=lead.id,
                 organization_id=org, before={"estado": prev}, after={"estado": body.to}, reason=body.note,
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, lead)


@router.patch("/{lead_id}", response_model=LeadOut)
def assign(lead_id: uuid.UUID, body: LeadAssign, request: Request,
           p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    lead = _get_visible(db, p, lead_id, request)
    if not p.has(lead.organization_id, "lead.transition"):
        raise api_error(403, "prohibido", "Su rol no permite reasignar leads.")
    if lead.version != body.version:
        raise api_error(409, "conflicto_version", "El lead ha cambiado desde que lo abrió. Recargue.")
    _check_assignee(db, lead.organization_id, body.assigned_user_id)
    before = str(lead.assigned_user_id) if lead.assigned_user_id else None
    lead.assigned_user_id = body.assigned_user_id
    lead.version += 1
    audit.record(db, actor_id=p.id, action="lead.assign", resource_type="lead", resource_id=lead.id,
                 organization_id=lead.organization_id, before={"asignado": before},
                 after={"asignado": str(body.assigned_user_id) if body.assigned_user_id else None},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, lead)


def convert_on_case_open(db: Session, p: Principal, lead: Lead, case: CaseFile) -> None:
    """Usado por la apertura de expediente (AT-06): enlaza y convierte el lead en la misma transacción."""
    prev = lead.status
    lead.status = "convertido"
    lead.case_file_id = case.id
    lead.status_changed_at = datetime.now(UTC)
    lead.version += 1
    db.add(LeadEvent(lead_id=lead.id, actor_user_id=p.id, from_status=prev, to_status="convertido",
                     note=f"Expediente {case.code} abierto"))
