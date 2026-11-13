"""Tareas y agenda (M09, F2.2). Requisitos: I-067…I-077, Q-6.9, Q-6.10, Q-6.15, Q-6.16, Q-6.20, Q-6.20B,
Q-6.23, U-16. Pruebas: AT-19 (plazo legal pendiente hasta validación), AT-20 (aplazamiento con motivo y traza).

El sistema NO calcula plazos legales (D-02, D-03, D-04, D-21): una persona propone la fecha con su fuente y
otra con permiso de letrado la valida. La fecha objetivo interna (due_at) y el plazo legal se guardan aparte.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from .. import agents, audit
from ..db import get_db
from ..errors import api_error
from ..models import CaseFile, Contact, UserAccount
from ..models_work import Task, TaskEvent
from ..schemas import Page
from ..security.auth import Principal, get_principal, load_principal
from ..security.policy import case_level, case_visibility_filter, load_case_scope
from .common import req_ctx

router = APIRouter(prefix="/tasks", tags=["tareas y agenda"])

Kind = Literal["gestion", "senalamiento", "conciliacion", "plazo", "llamada", "otro"]
Status = Literal["pendiente", "en_curso", "completada", "pospuesta", "anulada"]
FLOW: dict[str, set[str]] = {
    "pendiente": {"en_curso", "completada", "pospuesta", "anulada"},
    "en_curso": {"completada", "pospuesta", "anulada"},
    "pospuesta": {"en_curso", "completada", "pospuesta", "anulada"},
    "completada": set(),
    "anulada": set(),
}
TIMED = {"senalamiento", "conciliacion"}  # requieren hora de inicio y fin (detección de solapes, I-074)


# ---------------------------------------------------------------- esquemas
class TaskCreate(BaseModel):
    organization_id: uuid.UUID
    case_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)
    kind: Kind = "gestion"
    priority: Literal["alta", "media", "baja"] = "media"
    assignee_id: uuid.UUID
    due_at: datetime = Field(description="Fecha objetivo INTERNA")
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    legal_deadline: date | None = Field(default=None, description="Propuesta; queda pendiente de validación")
    legal_source: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check(self) -> TaskCreate:
        if self.kind in TIMED and not (self.start_at and self.end_at):
            raise ValueError("Los señalamientos y conciliaciones requieren hora de inicio y de fin")
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        if self.legal_deadline and not (self.legal_source and len(self.legal_source.strip()) >= 5):
            raise ValueError("Toda fecha legal propuesta necesita su fuente (resolución, norma o notificación)")
        return self


class TaskTransition(BaseModel):
    to: Status
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)
    new_due_at: datetime | None = None
    new_assignee_id: uuid.UUID | None = None


class LegalProposal(BaseModel):
    version: int = Field(ge=1)
    legal_deadline: date
    legal_source: str = Field(min_length=5, max_length=1000)


class LegalDecision(BaseModel):
    version: int = Field(ge=1)
    decision: Literal["validar", "rechazar"]
    note: str | None = Field(default=None, max_length=1000)


class TaskOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    case_id: uuid.UUID | None
    case_code: str | None
    contact_name: str | None
    title: str
    description: str
    kind: str
    priority: str
    assignee_id: uuid.UUID
    assignee: str
    due_at: datetime
    start_at: datetime | None
    end_at: datetime | None
    location: str | None
    status: str
    overdue: bool
    overlaps: list[uuid.UUID]
    legal_deadline: date | None
    legal_status: str
    legal_source: str | None
    legal_validated_by: str | None
    legal_validated_at: datetime | None
    version: int
    allowed_transitions: list[str]
    can_validate_legal: bool
    can_edit: bool


class TaskDetail(TaskOut):
    events: list[dict]


# ---------------------------------------------------------------- política
def _visibility(p: Principal, scope) -> ColumnElement[bool]:
    """Tareas de expedientes con acceso completo + tareas propias (asignadas o creadas)."""
    cases = select(CaseFile.id).where(case_visibility_filter(p, scope, full_only=True))
    conds = [Task.case_id.in_(cases), Task.assignee_id == p.id, Task.created_by == p.id]
    orgs = p.org_ids()
    return and_(Task.organization_id.in_(orgs or [uuid.uuid4()]), or_(*conds)) if orgs else false()


def _can_see(db: Session, p: Principal, t: Task, scope) -> bool:
    if t.organization_id not in p.org_ids():
        return False
    if p.id in (t.assignee_id, t.created_by):
        return True
    return bool(t.case_id) and case_level(p, db.get(CaseFile, t.case_id), scope) == "full"


def _can_edit(p: Principal, t: Task, scope_ok: bool) -> bool:
    """Q-6.23: solo quien la tiene asignada, quien la creó, o un perfil con task.manage.others en su ámbito."""
    return p.id in (t.assignee_id, t.created_by) or (p.has(t.organization_id, "task.manage.others") and scope_ok)


def _assignee_ok(db: Session, user_id: uuid.UUID, org: uuid.UUID, case: CaseFile | None) -> bool:
    ap = load_principal(db, user_id)
    if ap is None or org not in ap.org_ids():
        return False
    return case is None or case_level(ap, case, load_case_scope(db, ap)) == "full"


def _get(db: Session, p: Principal, task_id: uuid.UUID, request: Request) -> tuple[Task, bool]:
    t = db.get(Task, task_id)
    scope = load_case_scope(db, p)
    if t is None or not _can_see(db, p, t, scope):
        ctx = req_ctx(request)
        audit.record_independent(actor_id=p.id, action="task.read", resource_type="task", resource_id=task_id,
                                 organization_id=t.organization_id if t else None, outcome="denied",
                                 reason="fuera de ámbito o inexistente", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(404, "no_encontrado", "Tarea no encontrada.")
    case_ok = bool(t.case_id) and case_level(p, db.get(CaseFile, t.case_id), scope) == "full"
    return t, case_ok


def _overlaps(db: Session, t: Task) -> list[uuid.UUID]:
    if not (t.start_at and t.end_at) or t.status in ("anulada", "completada"):
        return []
    return list(db.execute(select(Task.id).where(
        Task.assignee_id == t.assignee_id, Task.id != t.id, Task.status.notin_(("anulada", "completada")),
        Task.start_at < t.end_at, Task.end_at > t.start_at)).scalars())


def _out(db: Session, p: Principal, t: Task, case_ok: bool) -> TaskOut:
    cf = db.get(CaseFile, t.case_id) if t.case_id else None
    ct = db.get(Contact, cf.contact_id) if cf else None
    names = {u.id: u.username for u in db.execute(select(UserAccount).where(
        UserAccount.id.in_([x for x in (t.assignee_id, t.legal_validated_by) if x]))).scalars()}
    editable = _can_edit(p, t, case_ok)
    allowed = sorted(FLOW[t.status]) if editable else []
    if "anulada" in allowed and not p.has(t.organization_id, "task.cancel"):
        allowed.remove("anulada")
    return TaskOut(
        id=t.id, organization_id=t.organization_id, case_id=t.case_id, case_code=cf.code if cf else None,
        contact_name=f"{ct.given_name} {ct.family_names}" if ct and case_ok else None,
        title=t.title, description=t.description, kind=t.kind, priority=t.priority,
        assignee_id=t.assignee_id, assignee=names.get(t.assignee_id, "—"), due_at=t.due_at,
        start_at=t.start_at, end_at=t.end_at, location=t.location, status=t.status,
        overdue=t.status in ("pendiente", "en_curso", "pospuesta") and t.due_at < datetime.now(UTC),
        overlaps=_overlaps(db, t), legal_deadline=t.legal_deadline, legal_status=t.legal_status,
        legal_source=t.legal_source, legal_validated_by=names.get(t.legal_validated_by),
        legal_validated_at=t.legal_validated_at, version=t.version, allowed_transitions=allowed,
        can_validate_legal=(t.legal_status == "pendiente_validacion" and p.has(t.organization_id, "deadline.validate")
                            and case_ok and t.legal_proposed_by != p.id),
        can_edit=editable,
    )


def _touch_case(db: Session, t: Task) -> None:
    if t.case_id:
        db.get(CaseFile, t.case_id).last_activity_at = datetime.now(UTC)


def _lock(db: Session, t: Task, version: int) -> None:
    db.execute(select(Task).where(Task.id == t.id).with_for_update())
    db.refresh(t)
    if t.version != version:
        raise api_error(409, "conflicto_version", "La tarea ha cambiado desde que la abrió. Recargue.")


# ---------------------------------------------------------------- consulta / agenda
@router.get("", response_model=Page[TaskOut])
def list_tasks(
    scope_q: Literal["mine", "all"] = Query(default="mine", alias="scope"),
    case_id: uuid.UUID | None = None,
    status: Status | None = None,
    open_only: bool = True,
    legal_pending: bool = False,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    scope = load_case_scope(db, p)
    where = _visibility(p, scope)
    if scope_q == "mine":
        where = and_(where, Task.assignee_id == p.id)
    if case_id:
        where = and_(where, Task.case_id == case_id)
    if status:
        where = and_(where, Task.status == status)
    elif open_only:
        where = and_(where, Task.status.in_(("pendiente", "en_curso", "pospuesta")))
    if legal_pending:
        where = and_(where, Task.legal_status == "pendiente_validacion")
    if desde:
        where = and_(where, func.coalesce(Task.start_at, Task.due_at) >= desde)
    if hasta:
        where = and_(where, func.coalesce(Task.start_at, Task.due_at) < hasta)
    total = db.execute(select(func.count()).select_from(Task).where(where)).scalar_one()
    # Q-6.20B: orden prioritario por fecha límite (la legal validada manda si existe).
    rows = db.execute(select(Task).where(where).order_by(
        func.coalesce(Task.legal_deadline, func.date(Task.due_at)), Task.due_at, Task.id)
        .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    out = []
    for t in rows:
        case_ok = bool(t.case_id) and case_level(p, db.get(CaseFile, t.case_id), scope) == "full"
        out.append(_out(db, p, t, case_ok))
    return Page(items=out, page=page, page_size=page_size, total=total)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    t, case_ok = _get(db, p, task_id, request)
    evs = db.execute(select(TaskEvent, UserAccount.username).join(UserAccount, UserAccount.id == TaskEvent.actor_user_id)
                     .where(TaskEvent.task_id == t.id).order_by(TaskEvent.occurred_at.desc())).all()
    return TaskDetail(**_out(db, p, t, case_ok).model_dump(), events=[
        {"at": e.occurred_at.isoformat(), "actor": u, "kind": e.kind, "from": e.from_status, "to": e.to_status,
         "old_due_at": e.old_due_at.isoformat() if e.old_due_at else None,
         "new_due_at": e.new_due_at.isoformat() if e.new_due_at else None, "reason": e.reason} for e, u in evs])


# ---------------------------------------------------------------- alta
@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, request: Request, background: BackgroundTasks, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    org = body.organization_id
    if org not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(org, "task.create"):
        raise api_error(403, "prohibido", "Su rol no permite crear tareas.")
    cf = None
    if body.case_id:
        cf = db.get(CaseFile, body.case_id)
        if cf is None or cf.organization_id != org or case_level(p, cf, load_case_scope(db, p)) != "full":
            raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    if body.assignee_id != p.id and not p.has(org, "task.manage.others") and not cf:
        raise api_error(403, "prohibido", "Solo puede asignar a otras personas tareas de un expediente.")
    if not _assignee_ok(db, body.assignee_id, org, cf):
        raise api_error(422, "validacion", "La persona responsable no tiene acceso a ese expediente.",
                        [{"field": "assignee_id", "message": "Responsable no válido"}])
    t = Task(organization_id=org, case_id=cf.id if cf else None, title=body.title.strip(), description=body.description,
             kind=body.kind, priority=body.priority, assignee_id=body.assignee_id, due_at=body.due_at,
             start_at=body.start_at, end_at=body.end_at, location=body.location, created_by=p.id)
    if body.legal_deadline:
        t.legal_deadline, t.legal_source = body.legal_deadline, body.legal_source
        t.legal_status, t.legal_proposed_by = "pendiente_validacion", p.id
    db.add(t)
    db.flush()
    db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="creada", to_status="pendiente", new_due_at=t.due_at))
    if body.legal_deadline:
        db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="plazo_legal_propuesto",
                         reason=f"{body.legal_deadline.isoformat()} · {body.legal_source}"))
    _touch_case(db, t)
    audit.record(db, actor_id=p.id, action="task.create", resource_type="task", resource_id=t.id, organization_id=org,
                 after={"titulo": t.title, "tipo": t.kind, "expediente": cf.code if cf else None,
                        "responsable": str(t.assignee_id), "fecha_interna": t.due_at.isoformat(),
                        "plazo_legal_propuesto": body.legal_deadline.isoformat() if body.legal_deadline else None},
                 ip=ctx.ip, request_id=ctx.request_id)
    if t.case_id and t.kind in agents.DATED_TASK_KINDS:
        agents.emit(db, org, "task.created", "task", t.id)
    db.commit()
    background.add_task(agents.dispatch_events)
    db.refresh(t)
    return _out(db, p, t, cf is not None)


class LocationIn(BaseModel):
    version: int = Field(ge=1)
    location: str = Field(min_length=3, max_length=200)


@router.post("/{task_id}/location", response_model=TaskOut)
def set_location(task_id: uuid.UUID, body: LocationIn, request: Request, background: BackgroundTasks,
                 p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Completar o corregir el lugar de una cita, conciliación o juicio (los avisos al cliente lo necesitan)."""
    ctx = req_ctx(request)
    t, case_ok = _get(db, p, task_id, request)
    if not _can_edit(p, t, case_ok):
        audit.record_independent(actor_id=p.id, action="task.location", resource_type="task", resource_id=t.id,
                                 organization_id=t.organization_id, outcome="denied", reason="tarea ajena (Q-6.23)",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Solo la persona asignada, quien la creó o un responsable del área pueden modificar esta tarea.")
    _lock(db, t, body.version)
    if t.status in ("completada", "anulada"):
        raise api_error(409, "conflicto", f"La tarea está {t.status}.")
    before = t.location
    t.location = body.location.strip()
    t.version += 1
    db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="lugar", from_status=t.status, to_status=t.status,
                     reason=f"Lugar: {before or '(vacío)'} → {t.location}"[:500]))
    audit.record(db, actor_id=p.id, action="task.location", resource_type="task", resource_id=t.id,
                 organization_id=t.organization_id, before={"lugar": before}, after={"lugar": t.location},
                 ip=ctx.ip, request_id=ctx.request_id)
    if t.case_id and t.kind in agents.DATED_TASK_KINDS:
        agents.emit(db, t.organization_id, "task.changed", "task", t.id, {"lugar": True})
    db.commit()
    background.add_task(agents.dispatch_events)
    return _out(db, p, t, case_ok)


# ---------------------------------------------------------------- estados y aplazamientos (AT-20, U-16)
@router.post("/{task_id}/transition", response_model=TaskOut)
def transition(task_id: uuid.UUID, body: TaskTransition, request: Request, background: BackgroundTasks,
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    t, case_ok = _get(db, p, task_id, request)
    if not _can_edit(p, t, case_ok):
        audit.record_independent(actor_id=p.id, action="task.transition", resource_type="task", resource_id=t.id,
                                 organization_id=t.organization_id, outcome="denied", reason="tarea ajena (Q-6.23)",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Solo la persona asignada, quien la creó o un responsable del área pueden modificar esta tarea.")
    _lock(db, t, body.version)
    if body.to not in FLOW[t.status]:
        raise api_error(409, "transicion_no_permitida", f"No se puede pasar de «{t.status}» a «{body.to}».")
    reason = (body.reason or "").strip()
    old_due = t.due_at
    if body.to == "anulada":
        if not p.has(t.organization_id, "task.cancel"):
            raise api_error(403, "prohibido", "Solo un perfil autorizado puede anular tareas.")
        if len(reason) < 5:
            raise api_error(422, "validacion", "Indique el motivo de la anulación.", [{"field": "reason", "message": "Obligatorio"}])
    if body.to == "pospuesta":
        errs = []
        if len(reason) < 5:
            errs.append({"field": "reason", "message": "Motivo obligatorio"})
        if body.new_due_at is None or body.new_due_at <= datetime.now(UTC):
            errs.append({"field": "new_due_at", "message": "Indique una nueva fecha futura"})
        if errs:
            raise api_error(422, "validacion", "Para aplazar indique motivo y nueva fecha.", errs)
        if body.new_assignee_id and body.new_assignee_id != t.assignee_id:
            cf = db.get(CaseFile, t.case_id) if t.case_id else None
            if not (p.has(t.organization_id, "task.manage.others") or p.id == t.created_by):
                raise api_error(403, "prohibido", "No puede reasignar esta tarea.")
            if not _assignee_ok(db, body.new_assignee_id, t.organization_id, cf):
                raise api_error(422, "validacion", "La nueva persona responsable no tiene acceso al expediente.")
            t.assignee_id = body.new_assignee_id
        if t.start_at and t.end_at:
            shift = body.new_due_at - t.due_at
            t.start_at, t.end_at = t.start_at + shift, t.end_at + shift
        t.due_at = body.new_due_at
    prev = t.status
    t.status = body.to
    t.completed_at = datetime.now(UTC) if body.to == "completada" else None
    t.version += 1
    db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="aplazada" if body.to == "pospuesta" else "estado",
                     from_status=prev, to_status=body.to, old_due_at=old_due if body.to == "pospuesta" else None,
                     new_due_at=t.due_at if body.to == "pospuesta" else None, reason=reason or None))
    _touch_case(db, t)
    audit.record(db, actor_id=p.id, action="task.transition", resource_type="task", resource_id=t.id,
                 organization_id=t.organization_id, reason=reason or None,
                 before={"estado": prev, "fecha_interna": old_due.isoformat()},
                 after={"estado": body.to, "fecha_interna": t.due_at.isoformat(), "responsable": str(t.assignee_id)},
                 ip=ctx.ip, request_id=ctx.request_id)
    if t.case_id and t.kind in agents.DATED_TASK_KINDS:
        agents.emit(db, t.organization_id, "task.changed", "task", t.id, {"estado": body.to})
    db.commit()
    background.add_task(agents.dispatch_events)
    return _out(db, p, t, case_ok)


# ---------------------------------------------------------------- plazo legal (AT-19)
@router.post("/{task_id}/legal-deadline", response_model=TaskOut)
def propose_legal(task_id: uuid.UUID, body: LegalProposal, request: Request,
                  p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    t, case_ok = _get(db, p, task_id, request)
    if not t.case_id or not case_ok or not _can_edit(p, t, case_ok):
        raise api_error(403, "prohibido", "Solo se proponen plazos legales en tareas de expedientes que usted gestiona.")
    _lock(db, t, body.version)
    before = {"plazo_legal": t.legal_deadline.isoformat() if t.legal_deadline else None, "estado": t.legal_status}
    t.legal_deadline, t.legal_source = body.legal_deadline, body.legal_source.strip()
    t.legal_status, t.legal_proposed_by = "pendiente_validacion", p.id
    t.legal_validated_by = t.legal_validated_at = None
    t.version += 1
    db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="plazo_legal_propuesto",
                     reason=f"{body.legal_deadline.isoformat()} · {t.legal_source}"))
    audit.record(db, actor_id=p.id, action="deadline.propose", resource_type="task", resource_id=t.id,
                 organization_id=t.organization_id, before=before,
                 after={"plazo_legal": body.legal_deadline.isoformat(), "fuente": t.legal_source, "estado": "pendiente_validacion"},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, t, case_ok)


@router.post("/{task_id}/legal-deadline/decision", response_model=TaskOut)
def decide_legal(task_id: uuid.UUID, body: LegalDecision, request: Request,
                 p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    t, case_ok = _get(db, p, task_id, request)
    if not (case_ok and p.has(t.organization_id, "deadline.validate")):
        audit.record_independent(actor_id=p.id, action="deadline.validate", resource_type="task", resource_id=t.id,
                                 organization_id=t.organization_id, outcome="denied", reason="sin deadline.validate",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Solo un letrado autorizado valida plazos legales.")
    _lock(db, t, body.version)
    if t.legal_status != "pendiente_validacion":
        raise api_error(409, "conflicto", "No hay ningún plazo legal pendiente de validar.")
    if t.legal_proposed_by == p.id:
        raise api_error(403, "doble_validacion", "Quien propone un plazo legal no puede validarlo: debe hacerlo otra persona.")
    if body.decision == "rechazar" and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Explique por qué se rechaza el plazo propuesto.", [{"field": "note", "message": "Obligatorio"}])
    proposed = t.legal_deadline.isoformat()
    if body.decision == "validar":
        t.legal_status, t.legal_validated_by, t.legal_validated_at = "validado", p.id, datetime.now(UTC)
    else:
        t.legal_status, t.legal_deadline, t.legal_source = "no_aplica", None, None
        t.legal_proposed_by = t.legal_validated_by = t.legal_validated_at = None
    t.version += 1
    db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind=f"plazo_legal_{'validado' if body.decision == 'validar' else 'rechazado'}",
                     reason=f"{proposed}" + (f" · {body.note}" if body.note else "")))
    audit.record(db, actor_id=p.id, action=f"deadline.{'validate' if body.decision == 'validar' else 'reject'}",
                 resource_type="task", resource_id=t.id, organization_id=t.organization_id, reason=body.note,
                 before={"plazo_legal": proposed, "estado": "pendiente_validacion"},
                 after={"estado": t.legal_status}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, t, case_ok)


@router.get("/agenda/week")
def week(start: date | None = None, scope_q: Literal["mine", "all"] = Query(default="mine", alias="scope"),
         p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Agenda semanal (I-069, I-076): lunes a domingo, con tareas vencidas arrastradas al principio."""
    today = datetime.now(UTC).date()
    monday = (start or today) - timedelta(days=(start or today).weekday())
    lo = datetime.combine(monday, datetime.min.time(), UTC)
    hi = lo + timedelta(days=7)
    page = list_tasks(scope_q=scope_q, case_id=None, status=None, open_only=False, legal_pending=False,
                      desde=lo - timedelta(days=60), hasta=hi, page=1, page_size=200, p=p, db=db)
    items = [x for x in page.items
             if (lo <= (x.start_at or x.due_at) < hi) or (x.overdue and (x.start_at or x.due_at) < lo)]
    return {"week_start": monday.isoformat(), "items": [x.model_dump(mode="json") for x in items]}
