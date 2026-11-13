"""Expedientes (M05). F0.1: consulta con aislamiento (AT-01). F2.1: apertura, fases, responsables,
relaciones e inactividad. Requisitos: Q-6.2, Q-6.4, I-007, I-008, I-009, I-010, I-088, I-092. Pruebas: AT-15, AT-16.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import agents, audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, CaseAssignment, CaseFile, Contact, Department, Membership, UserAccount
from ..models_work import CasePhaseEvent, CaseRelation, Lead
from ..schemas import CaseFull, CaseMeta, Materia, Page
from ..security.auth import Principal, get_principal, load_principal
from ..security.policy import (
    case_level,
    case_visibility_filter,
    contact_level,
    contacts_with_full_case,
    load_case_scope,
)
from .common import req_ctx
from .contacts import case_meta

router = APIRouter(prefix="/cases", tags=["expedientes"])

DEPT_BY_MATERIA = {"laboral": "LAB", "extranjeria": "EXT", "nacionalidad": "NAC"}
PREFIX_BY_MATERIA = {"laboral": "LAB", "extranjeria": "EXT", "nacionalidad": "NAC"}
CaseStatus = Literal["preapertura", "abierto", "en_tramite", "suspendido", "resuelto", "en_ejecucion",
                     "desistido", "archivado"]
# Transición -> permiso necesario. Las fases con efecto jurídico exigen case.transition.legal (AT-16).
FLOW: dict[str, dict[str, str]] = {
    "preapertura": {"abierto": "case.transition", "desistido": "case.transition.legal"},
    "abierto": {"en_tramite": "case.transition", "suspendido": "case.transition", "desistido": "case.transition.legal"},
    "en_tramite": {"suspendido": "case.transition", "resuelto": "case.transition.legal"},
    "suspendido": {"en_tramite": "case.transition"},
    "resuelto": {"en_ejecucion": "case.transition.legal", "archivado": "case.transition.legal"},
    "en_ejecucion": {"resuelto": "case.transition.legal"},
    "desistido": {"archivado": "case.transition.legal"},
    "archivado": {},
}
NEEDS_NOTE = {"suspendido", "desistido", "resuelto", "archivado", "en_ejecucion"}
INACTIVITY_DAYS = 30  # Umbral del indicador visual (Q-6.4). Propuesta pendiente de Dirección (T-11).


# ---------------------------------------------------------------- esquemas
class CaseCreate(BaseModel):
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    materia: Materia
    branch_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(default="", max_length=5000)
    lead_id: uuid.UUID | None = None
    responsible_user_id: uuid.UUID | None = None


class CaseTransitionIn(BaseModel):
    to: CaseStatus
    note: str | None = Field(default=None, max_length=2000)
    engagement_confirmed: bool = False


class AssignmentIn(BaseModel):
    user_id: uuid.UUID
    role_in_case: Literal["responsable", "letrado", "gestor", "apoyo"] = "responsable"
    reason: str = Field(min_length=5, max_length=500)


class RelationIn(BaseModel):
    related_case_id: uuid.UUID
    kind: Literal["mismo_cliente", "conexo", "derivado"]
    note: str | None = Field(default=None, max_length=500)


class CaseDetail(CaseFull):
    status_allowed: list[str]
    engagement_confirmed_at: datetime | None
    phase_events: list[dict]
    relations: list[dict]
    lead_id: uuid.UUID | None
    can_assign: bool
    inactive: bool


# ---------------------------------------------------------------- utilidades
def eligible(db: Session, user_id: uuid.UUID, org: uuid.UUID, dept_id: uuid.UUID) -> bool:
    """¿Puede esta persona trabajar un expediente de ese departamento? Respeta la separación entre ramas."""
    up = load_principal(db, user_id)
    if up is None or org not in up.org_ids():
        return False
    if up.has(org, "case.read.all"):
        return True
    for m in up.memberships_with(org, "case.read.department") + up.memberships_with(org, "case.read.assigned"):
        if m.department_id in (None, dept_id):
            return True
    return False


def _load_full(db: Session, p: Principal, case_id: uuid.UUID, request: Request, action: str) -> CaseFile:
    ctx = req_ctx(request)
    cf = db.get(CaseFile, case_id)
    if cf is None or cf.organization_id not in p.org_ids():
        audit.record_independent(actor_id=p.id, action=action, resource_type="case_file", resource_id=case_id,
                                 organization_id=cf.organization_id if cf else None, outcome="denied",
                                 reason="fuera de entidad o inexistente", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    if case_level(p, cf, load_case_scope(db, p)) != "full":
        audit.record_independent(actor_id=p.id, action=action, resource_type="case_file", resource_id=cf.id,
                                 organization_id=cf.organization_id, outcome="denied",
                                 reason=f"sin acceso a materia {cf.materia}", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "acceso_denegado",
                        "No tiene autorización para consultar este expediente. El intento ha quedado registrado.")
    return cf


def touch(cf: CaseFile) -> None:
    cf.last_activity_at = datetime.now(UTC)


def next_code(db: Session, org: uuid.UUID, prefix: str) -> str:
    from ..seed import next_case_code

    return next_case_code(db, org, prefix, datetime.now(UTC).year)


# ---------------------------------------------------------------- consulta
@router.get("", response_model=Page[CaseMeta])
def list_cases(
    request: Request,
    materia: Materia | None = None,
    status: CaseStatus | None = None,
    inactive: bool = False,
    mine: bool = False,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=50),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    scope = load_case_scope(db, p)
    where = case_visibility_filter(p, scope)
    if materia:
        where = where & (CaseFile.materia == materia)
    if status:
        where = where & (CaseFile.status == status)
    if inactive:
        # Solo sobre expedientes con acceso completo: los metadatos no revelan actividad.
        where = where & case_visibility_filter(p, scope, full_only=True) & (
            CaseFile.last_activity_at < func.now() - func.make_interval(0, 0, 0, INACTIVITY_DAYS)
        ) & CaseFile.status.notin_(("archivado", "desistido"))
    if mine:
        where = where & CaseFile.id.in_(scope.assigned_ids or [uuid.uuid4()])
    total = db.execute(select(func.count()).select_from(CaseFile).where(where)).scalar_one()
    rows = db.execute(
        select(CaseFile, Contact).join(Contact, Contact.id == CaseFile.contact_id).where(where)
        .order_by(CaseFile.created_at.desc(), CaseFile.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for cf, ct in rows:
        lvl = case_level(p, cf, scope)
        name = f"{ct.given_name} {ct.family_names}" if lvl == "full" else None
        items.append(case_meta(db, cf, lvl, name))
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/eligible-users")
def eligible_users(
    organization_id: uuid.UUID,
    materia: Materia,
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Personas que pueden ser responsables de un expediente de esa materia (para formularios)."""
    if organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not (p.has(organization_id, "case.create") or p.has(organization_id, "case.assign")
            or p.has(organization_id, "task.create")):
        raise api_error(403, "prohibido", "Su rol no gestiona expedientes.")
    dept = db.execute(select(Department).where(Department.organization_id == organization_id,
                                               Department.code == DEPT_BY_MATERIA[materia])).scalar_one()
    users = db.execute(select(UserAccount).join(Membership, Membership.user_id == UserAccount.id)
                       .where(Membership.organization_id == organization_id, UserAccount.status == "activo")
                       .distinct().order_by(UserAccount.full_name)).scalars().all()
    return [{"id": str(u.id), "username": u.username, "full_name": u.full_name}
            for u in users if eligible(db, u.id, organization_id, dept.id)]


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    cf = _load_full(db, p, case_id, request, "case.read")
    ct = db.get(Contact, cf.contact_id)
    assigns = db.execute(
        select(CaseAssignment, UserAccount.full_name).join(UserAccount, UserAccount.id == CaseAssignment.user_id)
        .where(CaseAssignment.case_id == cf.id).order_by(CaseAssignment.start_at)
    ).all()
    events = db.execute(select(CasePhaseEvent, UserAccount.username)
                        .join(UserAccount, UserAccount.id == CasePhaseEvent.actor_user_id)
                        .where(CasePhaseEvent.case_id == cf.id).order_by(CasePhaseEvent.occurred_at.desc())).all()
    scope = load_case_scope(db, p)
    rels = []
    for r in db.execute(select(CaseRelation).where(or_(CaseRelation.case_id == cf.id,
                                                       CaseRelation.related_case_id == cf.id))).scalars():
        other = db.get(CaseFile, r.related_case_id if r.case_id == cf.id else r.case_id)
        lvl = case_level(p, other, scope)
        if lvl:  # una relación no revela expedientes que el usuario no puede ver
            rels.append({"id": str(other.id), "code": other.code, "materia": other.materia, "kind": r.kind,
                         "note": r.note, "access_level": lvl})
    lead = db.execute(select(Lead.id).where(Lead.case_file_id == cf.id)).scalar()
    audit.record(db, actor_id=p.id, action="case.read", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    meta = case_meta(db, cf, "full", f"{ct.given_name} {ct.family_names}")
    allowed = [to for to, perm in FLOW[cf.status].items() if p.has(cf.organization_id, perm)]
    return CaseDetail(
        **meta.model_dump(), title=cf.title, confidential_summary=cf.confidential_summary,
        assignments=[{"id": str(a.id), "user_id": str(a.user_id), "user": n, "role": a.role_in_case,
                      "since": a.start_at.isoformat(), "until": a.end_at.isoformat() if a.end_at else None}
                     for a, n in assigns],
        status_allowed=allowed, engagement_confirmed_at=cf.engagement_confirmed_at,
        phase_events=[{"at": e.occurred_at.isoformat(), "actor": u, "from": e.from_status, "to": e.to_status,
                       "note": e.note} for e, u in events],
        relations=rels, lead_id=lead, can_assign=p.has(cf.organization_id, "case.assign"),
        inactive=(meta.inactive_days or 0) >= INACTIVITY_DAYS and cf.status not in ("archivado", "desistido"),
    )


# ---------------------------------------------------------------- apertura (I-007, Q-6.2, AT-06, AT-15)
@router.post("", response_model=CaseMeta, status_code=201)
def create_case(body: CaseCreate, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    org = body.organization_id
    if org not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    dept = db.execute(select(Department).where(Department.organization_id == org,
                                               Department.code == DEPT_BY_MATERIA[body.materia])).scalar_one_or_none()
    branch = db.get(Branch, body.branch_id)
    if dept is None or branch is None or branch.organization_id != org:
        raise api_error(422, "validacion", "Materia o sede no disponibles en esta entidad.")
    # Alcance de entidad (case.read.all): no queda acotado a un departamento. Resto: su rama y su sede.
    org_wide = p.has(org, "case.create") and p.has(org, "case.read.all")
    allowed = org_wide or [m for m in p.memberships_with(org, "case.create")
                           if m.department_id in (None, dept.id) and m.branch_id in (None, branch.id)]
    if not allowed:
        audit.record_independent(actor_id=p.id, action="case.create", resource_type="case_file", organization_id=org,
                                 outcome="denied", reason=f"sin case.create para {body.materia}",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", f"Su rol no permite abrir expedientes de {dept.name} en {branch.name}.")
    ct = db.get(Contact, body.contact_id)
    scope = load_case_scope(db, p)
    if ct is None or ct.organization_id != org or contact_level(p, ct, contacts_with_full_case(db, p, scope)) is None:
        raise api_error(422, "validacion", "El cliente no existe en esta entidad.",
                        [{"field": "contact_id", "message": "Cliente no válido"}])
    lead = None
    if body.lead_id:
        lead = db.get(Lead, body.lead_id)
        if lead is None or lead.organization_id != org or lead.contact_id != ct.id:
            raise api_error(422, "validacion", "El lead no corresponde a este cliente.")
        if lead.status in ("convertido", "descartado"):
            raise api_error(409, "conflicto", f"El lead está «{lead.status}»: no puede abrir otro expediente con él.")
    responsible = body.responsible_user_id or p.id
    if not eligible(db, responsible, org, dept.id):
        raise api_error(422, "validacion", "La persona responsable no trabaja en esta rama o entidad.",
                        [{"field": "responsible_user_id", "message": "Responsable no válido"}])
    cf = CaseFile(organization_id=org, branch_id=branch.id, department_id=dept.id, contact_id=ct.id,
                  code=next_code(db, org, PREFIX_BY_MATERIA[body.materia]), materia=body.materia,
                  title=body.title.strip(), status="preapertura", confidential_summary=body.summary.strip(),
                  created_by=p.id)
    db.add(cf)
    db.flush()
    db.add(CaseAssignment(case_id=cf.id, user_id=responsible, role_in_case="responsable"))
    db.add(CasePhaseEvent(case_id=cf.id, actor_user_id=p.id, from_status=None, to_status="preapertura",
                          note="Apertura" + (" desde lead" if lead else "")))
    if lead:
        from .leads import convert_on_case_open

        convert_on_case_open(db, p, lead, cf)
        audit.record(db, actor_id=p.id, action="lead.transition", resource_type="lead", resource_id=lead.id,
                     organization_id=org, after={"estado": "convertido", "expediente": cf.code},
                     ip=ctx.ip, request_id=ctx.request_id)
    audit.record(db, actor_id=p.id, action="case.create", resource_type="case_file", resource_id=cf.id,
                 organization_id=org, after={"codigo": cf.code, "materia": cf.materia, "cliente": str(ct.id),
                                             "responsable": str(responsible), "lead": str(lead.id) if lead else None},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    db.refresh(cf)
    return case_meta(db, cf, case_level(p, cf, load_case_scope(db, p)) or "metadata", f"{ct.given_name} {ct.family_names}")


# ---------------------------------------------------------------- fases (AT-16)
@router.post("/{case_id}/transition", response_model=CaseMeta)
def transition(case_id: uuid.UUID, body: CaseTransitionIn, request: Request, background: BackgroundTasks,
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    cf = _load_full(db, p, case_id, request, "case.transition")
    db.execute(select(CaseFile).where(CaseFile.id == cf.id).with_for_update())
    db.refresh(cf)
    perm = FLOW[cf.status].get(body.to)
    if perm is None:
        raise api_error(409, "transicion_no_permitida", f"No se puede pasar de «{cf.status}» a «{body.to}».")
    if not p.has(cf.organization_id, perm):
        audit.record_independent(actor_id=p.id, action="case.transition", resource_type="case_file", resource_id=cf.id,
                                 organization_id=cf.organization_id, outcome="denied",
                                 reason=f"{cf.status}->{body.to} requiere {perm}", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Este cambio de fase solo lo puede hacer un perfil autorizado (letrado o Dirección).")
    if body.to in NEEDS_NOTE and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Indique el motivo o resultado (mín. 5 caracteres).",
                        [{"field": "note", "message": "Obligatorio"}])
    if cf.status == "preapertura" and body.to == "abierto":
        if not body.engagement_confirmed:
            raise api_error(422, "validacion", "Para abrir el expediente confirme que consta el encargo firmado.",
                            [{"field": "engagement_confirmed", "message": "Confirmación obligatoria"}])
        cf.engagement_confirmed_at = datetime.now(UTC)
        cf.engagement_confirmed_by = p.id
    prev = cf.status
    cf.status = body.to
    touch(cf)
    db.add(CasePhaseEvent(case_id=cf.id, actor_user_id=p.id, from_status=prev, to_status=body.to, note=body.note))
    audit.record(db, actor_id=p.id, action="case.transition", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, before={"fase": prev}, after={"fase": body.to},
                 reason=body.note, ip=ctx.ip, request_id=ctx.request_id)
    # Hechos para los agentes (en la misma transacción: si no se guarda el cambio, tampoco el evento)
    if prev == "preapertura" and body.to == "abierto":
        agents.emit(db, cf.organization_id, "case.opened", "case_file", cf.id)
    elif body.to in ("archivado", "desistido"):
        agents.emit(db, cf.organization_id, "case.closed", "case_file", cf.id, {"fase": body.to})
    db.commit()
    background.add_task(agents.dispatch_events)
    return case_meta(db, cf, "full", None)


# ---------------------------------------------------------------- responsables (I-008, I-088)
@router.post("/{case_id}/assignments", response_model=CaseMeta, status_code=201)
def assign(case_id: uuid.UUID, body: AssignmentIn, request: Request,
           p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    cf = _load_full(db, p, case_id, request, "case.assign")
    if not p.has(cf.organization_id, "case.assign"):
        raise api_error(403, "prohibido", "Su rol no permite asignar responsables.")
    if not eligible(db, body.user_id, cf.organization_id, cf.department_id):
        raise api_error(422, "validacion", "Esa persona no trabaja en esta rama o entidad. Use una autorización puntual si es una excepción.")
    now = datetime.now(UTC)
    ended = []
    if body.role_in_case == "responsable":
        for a in db.execute(select(CaseAssignment).where(CaseAssignment.case_id == cf.id,
                                                         CaseAssignment.role_in_case == "responsable",
                                                         CaseAssignment.end_at.is_(None))).scalars():
            if a.user_id == body.user_id:
                raise api_error(409, "conflicto", "Esa persona ya es la responsable.")
            a.end_at = now
            ended.append(str(a.user_id))
    db.add(CaseAssignment(case_id=cf.id, user_id=body.user_id, role_in_case=body.role_in_case))
    touch(cf)
    audit.record(db, actor_id=p.id, action="case.assign", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, reason=body.reason, before={"responsables_cesados": ended} if ended else None,
                 after={"usuario": str(body.user_id), "rol": body.role_in_case}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return case_meta(db, cf, "full", None)


@router.post("/{case_id}/assignments/{assignment_id}/end", response_model=CaseMeta)
def end_assignment(case_id: uuid.UUID, assignment_id: uuid.UUID, request: Request,
                   p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    cf = _load_full(db, p, case_id, request, "case.assign")
    if not p.has(cf.organization_id, "case.assign"):
        raise api_error(403, "prohibido", "Su rol no permite retirar responsables.")
    a = db.get(CaseAssignment, assignment_id)
    if a is None or a.case_id != cf.id or a.end_at is not None:
        raise api_error(404, "no_encontrado", "Asignación no encontrada o ya finalizada.")
    a.end_at = datetime.now(UTC)
    audit.record(db, actor_id=p.id, action="case.unassign", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, before={"usuario": str(a.user_id), "rol": a.role_in_case},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return case_meta(db, cf, "full", None)


# ---------------------------------------------------------------- relaciones (AT-15)
@router.post("/{case_id}/relations", status_code=201)
def relate(case_id: uuid.UUID, body: RelationIn, request: Request,
           p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    ctx = req_ctx(request)
    cf = _load_full(db, p, case_id, request, "case.relate")
    other = _load_full(db, p, body.related_case_id, request, "case.relate")
    if not p.has(cf.organization_id, "case.transition"):
        raise api_error(403, "prohibido", "Su rol no permite relacionar expedientes.")
    if other.id == cf.id or other.organization_id != cf.organization_id:
        raise api_error(422, "validacion", "Solo se relacionan expedientes distintos de la misma entidad.")
    exists = db.execute(select(CaseRelation).where(or_(
        (CaseRelation.case_id == cf.id) & (CaseRelation.related_case_id == other.id),
        (CaseRelation.case_id == other.id) & (CaseRelation.related_case_id == cf.id)))).first()
    if exists:
        raise api_error(409, "conflicto", "Los expedientes ya están relacionados.")
    db.add(CaseRelation(case_id=cf.id, related_case_id=other.id, kind=body.kind, note=body.note, created_by=p.id))
    touch(cf)
    audit.record(db, actor_id=p.id, action="case.relate", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after={"relacionado": other.code, "tipo": body.kind},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"case": cf.code, "related": other.code, "kind": body.kind}
