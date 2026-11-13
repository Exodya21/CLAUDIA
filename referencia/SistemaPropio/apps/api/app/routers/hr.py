"""RRHH (F5.3; DR-RH-1, 2, 4, 5, 6): plantilla, ficha única, carpeta documental, vacaciones y ausencias,
resumen de nóminas para la gestoría e importación desde una hoja de cálculo.

Datos de personal aislados de los de clientes: tablas y permisos propios (`hr.*`). Salario y nóminas solo con
`hr.salary` (o la propia persona); bajas médicas solo RRHH. Todo cambio y toda descarga quedan auditados.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import agents, audit
from ..db import get_db
from ..errors import api_error
from ..hr import service as hs
from ..models import Branch, Department, Organization, UserAccount
from ..models_hr import Employee, EmployeeDocument, LeaveRequest
from ..security.auth import Principal, get_principal
from ..services import receipts, textcrypt, vault
from ..validation import ValidationFailure, fold, validate_identifier
from .common import req_ctx

router = APIRouter(prefix="/hr", tags=["rrhh"])
MAX_FILE = 20 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _deny(p: Principal, request: Request, action: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type="employee", resource_id=rid,
                             organization_id=org, outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _uname(db: Session, uid) -> str | None:
    return db.get(UserAccount, uid).full_name if uid else None


def _employee(db: Session, p: Principal, employee_id: uuid.UUID, request: Request, need: str, action: str) -> tuple[Employee, set]:
    e = db.get(Employee, employee_id)
    if e is None or e.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Ficha no encontrada.")
    acc = hs.access(p, e)
    ok = {"view": bool(acc & {"self", "read", "team"}), "manage": "manage" in acc, "salary": "salary" in acc,
          "leave": "leave" in acc}[need]
    if not ok:
        _deny(p, request, action, e.id, e.organization_id, f"sin acceso ({need})")
        raise api_error(403, "prohibido", "No tiene permiso para esta ficha.")
    return e, acc


# ------------------------------------------------------------------ salidas
def _emp_out(db: Session, e: Employee, acc: set, detail: bool = False) -> dict:
    b = db.get(Branch, e.branch_id)
    dpt = db.get(Department, e.department_id) if e.department_id else None
    see_salary = bool(acc & {"salary", "self"})
    see_private = bool(acc & {"manage", "self"})
    d = {"id": str(e.id), "organization_id": str(e.organization_id),
         "organization": db.get(Organization, e.organization_id).name, "code": e.code,
         "name": f"{e.given_name} {e.family_names}", "given_name": e.given_name, "family_names": e.family_names,
         "branch_id": str(e.branch_id), "branch": b.name, "department_id": str(e.department_id) if dpt else None,
         "department": dpt.name if dpt else None, "country": e.country, "category": e.category, "job_title": e.job_title,
         "contract_type": e.contract_type, "workday": e.workday, "weekly_hours": float(e.weekly_hours),
         "start_date": e.start_date.isoformat(),
         "contract_end_date": e.contract_end_date.isoformat() if e.contract_end_date else None,
         "trial_end_date": e.trial_end_date.isoformat() if e.trial_end_date else None,
         "status": e.status, "end_date": e.end_date.isoformat() if e.end_date else None, "version": e.version,
         "has_user": e.user_id is not None, "is_me": "self" in acc}
    if see_private:
        d |= {"email": e.email, "phone": e.phone, "national_id_masked": hs.mask_id(e.national_id_last),
              "vacation_days_year": e.vacation_days_year, "notes": e.notes if "manage" in acc else None}
    if see_salary:
        d["salary_annual_cents"] = e.salary_annual_cents
    d["can"] = {"manage": "manage" in acc, "salary": see_salary, "leave_decide": "leave" in acc}
    if detail:
        d["vacation"] = hs.vacation_balance(db, e)
        docs = db.execute(select(EmployeeDocument).where(EmployeeDocument.employee_id == e.id)
                          .order_by(EmployeeDocument.uploaded_at.desc())).scalars()
        d["documents"] = [_doc_out(db, x, acc) for x in docs if _can_see_doc(x, acc)]
        leaves = db.execute(select(LeaveRequest).where(LeaveRequest.employee_id == e.id)
                            .order_by(LeaveRequest.start_date.desc())).scalars()
        d["leaves"] = [_leave_out(db, x, e, acc) for x in leaves]
    return d


def _can_see_doc(x: EmployeeDocument, acc: set) -> bool:
    if x.kind in hs.RESTRICTED_DOCS:
        return "manage" in acc or "self" in acc
    if x.kind in hs.SALARY_DOCS:
        return bool(acc & {"salary", "self"})
    return bool(acc & {"manage", "self", "read"})


def _doc_out(db: Session, x: EmployeeDocument, acc: set) -> dict:
    return {"id": str(x.id), "kind": x.kind, "kind_label": hs.DOC_KINDS.get(x.kind, x.kind), "period": x.period,
            "name": x.original_name, "size": x.size_bytes, "status": x.status, "extracted": x.extracted,
            "confirmed": x.confirmed, "uploaded_by": _uname(db, x.uploaded_by), "uploaded_at": x.uploaded_at.isoformat(),
            "reviewed_by": _uname(db, x.reviewed_by), "version": x.version,
            "can_review": "manage" in acc and (x.kind not in hs.SALARY_DOCS or "salary" in acc)}


def _leave_out(db: Session, x: LeaveRequest, e: Employee, acc: set) -> dict:
    private = bool(acc & {"manage", "self"})
    kind = x.kind if (x.kind != "baja" or private) else "ausencia"
    return {"id": str(x.id), "employee_id": str(e.id), "employee": f"{e.given_name} {e.family_names}",
            "kind": kind, "kind_label": hs.LEAVE_KINDS.get(kind, "Ausencia"), "start_date": x.start_date.isoformat(),
            "end_date": x.end_date.isoformat(), "working_days": x.working_days,
            "note": x.note if private else None, "status": x.status, "requested_by": _uname(db, x.requested_by),
            "requested_at": x.requested_at.isoformat(), "decided_by": _uname(db, x.decided_by),
            "decision_note": x.decision_note, "version": x.version}


# ------------------------------------------------------------------ plantilla
def _visible(db: Session, p: Principal) -> list[tuple[Employee, set]]:
    out = []
    for e in db.execute(select(Employee).where(Employee.organization_id.in_(p.org_ids()))
                        .order_by(Employee.family_names, Employee.given_name)).scalars():
        acc = hs.access(p, e)
        if acc & {"read", "team", "self"}:
            out.append((e, acc))
    return out


@router.get("/employees")
def list_employees(request: Request, q: str | None = Query(default=None, max_length=60),
                   status: str | None = Query(default=None, max_length=12), branch_id: uuid.UUID | None = None,
                   p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    if not (p.orgs_with("hr.read") or p.orgs_with("hr.leave.decide")):
        _deny(p, request, "hr.read", None, None, "sin hr.read")
        raise api_error(403, "prohibido", "Su perfil no consulta la plantilla.")
    rows = []
    for e, acc in _visible(db, p):
        if not (acc & {"read", "team"}):
            continue
        if q and fold(q) not in fold(f"{e.given_name} {e.family_names} {e.code} {e.job_title}"):
            continue
        if status and e.status != status:
            continue
        if branch_id and e.branch_id != branch_id:
            continue
        rows.append(_emp_out(db, e, acc))
    return {"items": rows, "can_manage": bool(p.orgs_with("hr.manage")), "can_salary": bool(p.orgs_with("hr.salary"))}


@router.get("/me")
def me(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    e = db.execute(select(Employee).where(Employee.user_id == p.id, Employee.organization_id.in_(p.org_ids()))).scalars().first()
    if e is None or "self" not in hs.access(p, e):
        raise api_error(404, "no_encontrado", "Su ficha de empleado aún no está en el sistema. Consulte con RRHH.")
    return _emp_out(db, e, hs.access(p, e), detail=True)


@router.get("/employees/{employee_id}")
def get_employee(employee_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    e, acc = _employee(db, p, employee_id, request, "view", "hr.employee.read")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="hr.employee.read", resource_type="employee", resource_id=e.id,
                             organization_id=e.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    return _emp_out(db, e, acc, detail=True)


class EmployeeIn(BaseModel):
    organization_id: uuid.UUID
    given_name: str = Field(min_length=1, max_length=120)
    family_names: str = Field(min_length=1, max_length=200)
    id_kind: Literal["DNI", "NIE", "PASAPORTE", "OTRO"] | None = None
    id_number: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    country: Literal["ES", "CO"] = "ES"
    branch_id: uuid.UUID
    department_id: uuid.UUID | None = None
    category: str = Field(min_length=2, max_length=80)
    job_title: str = Field(min_length=2, max_length=80)
    contract_type: Literal["indefinido", "temporal", "practicas", "fijo_discontinuo", "otro"]
    workday: Literal["completa", "parcial"]
    weekly_hours: Decimal = Field(gt=0, le=60)
    start_date: date
    contract_end_date: date | None = None
    trial_end_date: date | None = None
    salary_annual_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)
    vacation_days_year: int | None = Field(default=None, ge=0, le=60)
    user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class EmployeePatch(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=300)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    job_title: str | None = Field(default=None, min_length=2, max_length=80)
    branch_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    contract_type: Literal["indefinido", "temporal", "practicas", "fijo_discontinuo", "otro"] | None = None
    workday: Literal["completa", "parcial"] | None = None
    weekly_hours: Decimal | None = Field(default=None, gt=0, le=60)
    contract_end_date: date | None = None
    trial_end_date: date | None = None
    salary_annual_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)
    vacation_days_year: int | None = Field(default=None, ge=0, le=60)
    status: Literal["activo", "baja", "excedencia", "finalizado"] | None = None
    end_date: date | None = None
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    clear: list[Literal["contract_end_date", "trial_end_date", "end_date"]] = []


def _check_dates(start: date, end: date | None, trial: date | None, contract_type: str) -> None:
    errs = []
    if end and end < start:
        errs.append({"field": "contract_end_date", "message": "No puede ser anterior al inicio"})
    if trial and trial < start:
        errs.append({"field": "trial_end_date", "message": "No puede ser anterior al inicio"})
    if contract_type == "temporal" and not end:
        errs.append({"field": "contract_end_date", "message": "Un contrato temporal necesita fecha de fin"})
    if errs:
        raise api_error(422, "validacion", "Revise las fechas.", errs)


def _check_place(db: Session, org, branch_id, department_id) -> None:
    b = db.get(Branch, branch_id)
    if b is None or b.organization_id != org:
        raise api_error(422, "validacion", "Sede no válida.", [{"field": "branch_id", "message": "No válida"}])
    if department_id:
        dp = db.get(Department, department_id)
        if dp is None or dp.organization_id != org:
            raise api_error(422, "validacion", "Departamento no válido.", [{"field": "department_id", "message": "No válido"}])


def _next_code(db: Session, org) -> str:
    n = db.execute(select(func.count()).select_from(Employee).where(Employee.organization_id == org)).scalar_one()
    while True:
        n += 1
        code = f"EMP-{n:04d}"
        if not db.execute(select(Employee.id).where(Employee.organization_id == org, Employee.code == code)).first():
            return code


def _duplicates(db: Session, org, given: str, family: str, email: str | None, id_last: str | None) -> list[Employee]:
    cond = [func.lower(Employee.family_names) == family.strip().lower()]
    rows = list(db.execute(select(Employee).where(Employee.organization_id == org, or_(*cond))).scalars())
    out = [e for e in rows if fold(e.given_name) == fold(given)]
    if email:
        out += [e for e in db.execute(select(Employee).where(Employee.organization_id == org,
                                                             func.lower(Employee.email) == email.strip().lower())).scalars()
                if e not in out]
    if id_last:
        out += [e for e in db.execute(select(Employee).where(Employee.organization_id == org,
                                                             Employee.national_id_last == id_last)).scalars()
                if e not in out and fold(e.family_names) == fold(family)]
    return out


def create_employee(db: Session, p: Principal, body: EmployeeIn, ctx, force: bool = False) -> Employee:
    org = body.organization_id
    _check_place(db, org, body.branch_id, body.department_id)
    _check_dates(body.start_date, body.contract_end_date, body.trial_end_date, body.contract_type)
    id_norm = None
    if body.id_number:
        try:
            id_norm = validate_identifier(body.id_kind or "OTRO", body.id_number, "ES" if body.id_kind in ("DNI", "NIE") else body.country)
        except ValidationFailure as exc:
            raise api_error(422, "validacion", exc.message, [{"field": "id_number", "message": exc.message}]) from exc
    if body.user_id:
        from ..models import Membership
        u = db.get(UserAccount, body.user_id)
        if u is None or not db.execute(select(Membership.id).where(Membership.user_id == u.id,
                                                                    Membership.organization_id == org)).first():
            raise api_error(422, "validacion", "El usuario no trabaja en esta entidad.", [{"field": "user_id", "message": "No válido"}])
        if db.execute(select(Employee.id).where(Employee.organization_id == org, Employee.user_id == u.id)).first():
            raise api_error(409, "conflicto", "Ese usuario ya tiene ficha de empleado.")
    dups = _duplicates(db, org, body.given_name, body.family_names, body.email, id_norm[-4:] if id_norm else None)
    if dups and not force:
        raise api_error(409, "posible_duplicado", "Ya hay una ficha que parece de la misma persona. Revísela antes de crear otra.",
                        [{"id": str(x.id), "code": x.code, "name": f"{x.given_name} {x.family_names}"} for x in dups])
    e = Employee(organization_id=org, code=_next_code(db, org), user_id=body.user_id, given_name=body.given_name.strip(),
                 family_names=body.family_names.strip(), national_id_enc=textcrypt.enc(id_norm) if id_norm else None,
                 national_id_last=id_norm[-4:] if id_norm else None, email=(body.email or "").strip() or None,
                 phone=(body.phone or "").strip() or None, country=body.country, branch_id=body.branch_id,
                 department_id=body.department_id, category=body.category.strip(), job_title=body.job_title.strip(),
                 contract_type=body.contract_type, workday=body.workday, weekly_hours=body.weekly_hours,
                 start_date=body.start_date, contract_end_date=body.contract_end_date, trial_end_date=body.trial_end_date,
                 salary_annual_cents=body.salary_annual_cents, vacation_days_year=body.vacation_days_year,
                 notes=body.notes, created_by=p.id)
    db.add(e)
    db.flush()
    audit.record(db, actor_id=p.id, action="hr.employee.create", resource_type="employee", resource_id=e.id,
                 organization_id=org, after={"codigo": e.code, "sede": str(e.branch_id), "categoria": e.category,
                                             "contrato": e.contract_type, "salario": "informado" if e.salary_annual_cents else None,
                                             "documento": hs.mask_id(e.national_id_last)},
                 ip=ctx.ip, request_id=ctx.request_id)
    return e


@router.post("/employees", status_code=201)
def add_employee(body: EmployeeIn, request: Request, force: bool = False, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    if body.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(body.organization_id, "hr.manage"):
        _deny(p, request, "hr.employee.create", None, body.organization_id, "sin hr.manage")
        raise api_error(403, "prohibido", "Solo RRHH da de alta fichas.")
    if body.salary_annual_cents is not None and not p.has(body.organization_id, "hr.salary"):
        raise api_error(403, "prohibido", "Su perfil no puede informar salarios.")
    e = create_employee(db, p, body, req_ctx(request), force=force)
    db.commit()
    return _emp_out(db, e, hs.access(p, e), detail=True)


SENSITIVE_FIELDS = {"salary_annual_cents"}


@router.patch("/employees/{employee_id}")
def update_employee(employee_id: uuid.UUID, body: EmployeePatch, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    e, acc = _employee(db, p, employee_id, request, "manage", "hr.employee.update")
    db.execute(select(Employee).where(Employee.id == e.id).with_for_update())
    db.refresh(e)
    if e.version != body.version:
        raise api_error(409, "conflicto_version", "La ficha ha cambiado desde que la abrió. Recargue.")
    data = body.model_dump(exclude_unset=True, exclude={"version", "reason", "clear"})
    if "salary_annual_cents" in data and "salary" not in acc:
        raise api_error(403, "prohibido", "Su perfil no puede cambiar salarios.")
    before, after = {}, {}
    for k, v in data.items():
        if v is None:
            continue
        old = getattr(e, k)
        if old != v:
            before[k] = "•••" if k in SENSITIVE_FIELDS else (str(old) if old is not None else None)
            after[k] = "•••" if k in SENSITIVE_FIELDS else str(v)
            setattr(e, k, v)
    for k in body.clear:
        if getattr(e, k) is not None:
            before[k], after[k] = str(getattr(e, k)), None
            setattr(e, k, None)
    if not after and not body.clear:
        raise api_error(422, "validacion", "No ha cambiado nada.")
    _check_place(db, e.organization_id, e.branch_id, e.department_id)
    _check_dates(e.start_date, e.contract_end_date, e.trial_end_date, e.contract_type)
    if e.status == "finalizado" and not e.end_date:
        raise api_error(422, "validacion", "Indique la fecha de fin de la relación laboral.", [{"field": "end_date", "message": "Obligatoria"}])
    e.version += 1
    e.updated_at = _now()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="hr.employee.update", resource_type="employee", resource_id=e.id,
                 organization_id=e.organization_id, reason=body.reason, before=before, after=after,
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _emp_out(db, e, acc, detail=True)


# ------------------------------------------------------------------ carpeta documental (DR-RH-2)
@router.post("/employees/{employee_id}/documents", status_code=201)
async def upload_document(employee_id: uuid.UUID, request: Request,
                          kind: Literal["contrato", "anexo", "nomina", "certificado", "solicitud", "baja", "otro"] = Form(...),
                          period: str | None = Form(None), file: UploadFile = File(...),
                          p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    e, acc = _employee(db, p, employee_id, request, "manage", "hr.document.upload")
    if kind in hs.SALARY_DOCS and "salary" not in acc:
        raise api_error(403, "prohibido", "Su perfil no gestiona nóminas.")
    data = await file.read(MAX_FILE + 1)
    try:
        mime = vault.sniff(data)
    except vault.VaultError as exc:
        raise api_error(422, "validacion", exc.message) from exc
    if period and not (len(period) == 7 and period[4] == "-" and period[:4].isdigit() and period[5:].isdigit()
                       and 1 <= int(period[5:]) <= 12):
        raise api_error(422, "validacion", "Periodo con formato AAAA-MM.", [{"field": "period", "message": "Formato AAAA-MM"}])
    import hashlib
    sha = hashlib.sha256(data).hexdigest()
    if db.execute(select(EmployeeDocument.id).where(EmployeeDocument.employee_id == e.id,
                                                    EmployeeDocument.sha256 == sha)).first():
        raise api_error(409, "conflicto", "Ese archivo ya está en la carpeta de esta persona.")
    extracted = None
    if kind == "nomina":
        ex = receipts.extractor()
        text = ex.text(data, mime) if ex else ""
        extracted = hs.read_payslip(text, e) if text else {"confianza": "baja", "aviso": "sin lector de texto"}
        period = period or extracted.get("periodo")
    path, _ = vault.store(data)
    d = EmployeeDocument(organization_id=e.organization_id, employee_id=e.id, kind=kind, period=period,
                         original_name=(file.filename or "documento")[:200], mime=mime, size_bytes=len(data), sha256=sha,
                         file_path=path, extracted=extracted, uploaded_by=p.id)
    db.add(d)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="hr.document.upload", resource_type="employee", resource_id=e.id,
                 organization_id=e.organization_id, after={"documento": str(d.id), "tipo": kind, "periodo": period},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _doc_out(db, d, acc)


def _document(db: Session, p: Principal, doc_id: uuid.UUID, request: Request, action: str):
    d = db.get(EmployeeDocument, doc_id)
    if d is None or d.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Documento no encontrado.")
    e = db.get(Employee, d.employee_id)
    acc = hs.access(p, e)
    if not _can_see_doc(d, acc):
        _deny(p, request, action, e.id, e.organization_id, f"documento {d.kind} restringido")
        raise api_error(403, "prohibido", "Este documento tiene acceso restringido.")
    return d, e, acc


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> Response:
    d, e, _ = _document(db, p, doc_id, request, "hr.document.download")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="hr.document.download", resource_type="employee", resource_id=e.id,
                             organization_id=e.organization_id, after={"documento": str(d.id), "tipo": d.kind},
                             ip=ctx.ip, request_id=ctx.request_id)
    safe = "".join(ch for ch in d.original_name if ch.isalnum() or ch in "._-") or "documento"
    return Response(vault.load(d.file_path), media_type=d.mime, headers={"Content-Disposition": f'inline; filename="{safe}"'})


class ReviewIn(BaseModel):
    version: int = Field(ge=1)
    status: Literal["valido", "rechazado"]
    period: str | None = Field(default=None, max_length=7)
    devengado_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    deducciones_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    liquido_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    note: str | None = Field(default=None, max_length=300)


@router.post("/documents/{doc_id}/review")
def review_document(doc_id: uuid.UUID, body: ReviewIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    d, e, acc = _document(db, p, doc_id, request, "hr.document.review")
    if "manage" not in acc or (d.kind in hs.SALARY_DOCS and "salary" not in acc):
        _deny(p, request, "hr.document.review", e.id, e.organization_id, "sin hr.manage/hr.salary")
        raise api_error(403, "prohibido", "Solo RRHH confirma documentos.")
    db.execute(select(EmployeeDocument).where(EmployeeDocument.id == d.id).with_for_update())
    db.refresh(d)
    if d.version != body.version:
        raise api_error(409, "conflicto_version", "El documento ha cambiado. Recargue.")
    if body.status == "rechazado" and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Indique por qué no es válido.")
    if body.status == "valido" and d.kind == "nomina":
        missing = [f for f in ("period", "devengado_cents", "deducciones_cents", "liquido_cents") if getattr(body, f) is None]
        if missing:
            raise api_error(422, "validacion", "Confirme periodo, devengado, deducciones y líquido de la nómina.",
                            [{"field": f, "message": "Obligatorio"} for f in missing])
        if body.devengado_cents - body.deducciones_cents != body.liquido_cents:
            raise api_error(422, "validacion", "Devengado − deducciones no coincide con el líquido. Revise las cifras de la nómina.")
        if not (len(body.period) == 7 and body.period[4] == "-"):
            raise api_error(422, "validacion", "Periodo con formato AAAA-MM.")
        d.period = body.period
        d.confirmed = {"periodo": body.period, "devengado_cents": body.devengado_cents,
                       "deducciones_cents": body.deducciones_cents, "liquido_cents": body.liquido_cents}
    d.status, d.reviewed_by, d.reviewed_at = body.status, p.id, _now()
    d.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="hr.document.review", resource_type="employee", resource_id=e.id,
                 organization_id=e.organization_id, reason=body.note,
                 after={"documento": str(d.id), "estado": d.status, "tipo": d.kind, "periodo": d.period},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _doc_out(db, d, acc)


# ------------------------------------------------------------------ vacaciones y ausencias (DR-RH-4)
class LeaveIn(BaseModel):
    kind: Literal["vacaciones", "asuntos_propios", "permiso", "baja", "otro"]
    start_date: date
    end_date: date
    note: str | None = Field(default=None, max_length=500)


@router.post("/employees/{employee_id}/leaves", status_code=201)
def request_leave(employee_id: uuid.UUID, body: LeaveIn, request: Request, background: BackgroundTasks,
                  p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    e, acc = _employee(db, p, employee_id, request, "view", "hr.leave.request")
    if not (acc & {"self", "manage"}):
        _deny(p, request, "hr.leave.request", e.id, e.organization_id, "ni propia ni RRHH")
        raise api_error(403, "prohibido", "Solo puede pedir sus propias ausencias (o RRHH por otra persona).")
    if body.kind == "baja" and "manage" not in acc:
        raise api_error(403, "prohibido", "Las bajas médicas las registra RRHH con el parte.")
    if body.end_date < body.start_date:
        raise api_error(422, "validacion", "La fecha de fin no puede ser anterior a la de inicio.",
                        [{"field": "end_date", "message": "Anterior al inicio"}])
    if (body.end_date - body.start_date).days > 366:
        raise api_error(422, "validacion", "Periodo demasiado largo.")
    if e.status == "finalizado":
        raise api_error(409, "conflicto", "La relación laboral ha finalizado.")
    days = hs.working_days(body.start_date, body.end_date)
    if days == 0 and body.kind != "baja":
        raise api_error(422, "validacion", "El periodo no tiene días laborables (lunes a viernes).")
    clash = db.execute(select(LeaveRequest).where(LeaveRequest.employee_id == e.id,
                                                  LeaveRequest.status.in_(("aprobada", "solicitada")),
                                                  LeaveRequest.start_date <= body.end_date,
                                                  LeaveRequest.end_date >= body.start_date)).scalars().first()
    if clash:
        raise api_error(409, "conflicto", f"Ya tiene una ausencia en esas fechas ({clash.start_date:%d/%m} – {clash.end_date:%d/%m}).")
    if body.kind == "vacaciones":
        bal = hs.vacation_balance(db, e, body.start_date.year)
        if bal["remaining"] is not None and days > bal["remaining"]:
            raise api_error(422, "validacion", f"Pide {days} días laborables y le quedan {bal['remaining']} de "
                            f"{bal['total']} en {bal['year']} (contando lo ya solicitado).")
    auto_ok = body.kind == "baja"  # la baja la registra RRHH con el parte: no se «aprueba»
    x = LeaveRequest(organization_id=e.organization_id, employee_id=e.id, kind=body.kind, start_date=body.start_date,
                     end_date=body.end_date, working_days=days, note=(body.note or "").strip() or None,
                     status="aprobada" if auto_ok else "solicitada", requested_by=p.id)
    db.add(x)
    db.flush()
    warn = [_leave_out(db, o, db.get(Employee, o.employee_id), set()) for o in hs.overlaps(db, e, body.start_date, body.end_date, x.id)]
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="hr.leave.request", resource_type="employee", resource_id=e.id,
                 organization_id=e.organization_id,
                 after={"ausencia": str(x.id), "tipo": "ausencia" if x.kind == "baja" else x.kind,
                        "desde": x.start_date.isoformat(), "hasta": x.end_date.isoformat(), "dias": days},
                 ip=ctx.ip, request_id=ctx.request_id)
    if not auto_ok:
        agents.emit(db, e.organization_id, "hr.leave.requested", "leave_request", x.id)
    db.commit()
    background.add_task(agents.dispatch_events)
    out = _leave_out(db, x, e, acc)
    out["coincidencias"] = warn
    return out


@router.get("/leaves")
def list_leaves(status: Literal["solicitada", "aprobada", "rechazada", "anulada"] = "solicitada",
                p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    out = []
    for x in db.execute(select(LeaveRequest).where(LeaveRequest.organization_id.in_(p.org_ids()),
                                                   LeaveRequest.status == status)
                        .order_by(LeaveRequest.start_date).limit(300)).scalars():
        e = db.get(Employee, x.employee_id)
        acc = hs.access(p, e)
        if acc & {"leave", "manage", "read", "team"}:
            d = _leave_out(db, x, e, acc)
            d["can_decide"] = ("leave" in acc and x.status == "solicitada" and e.user_id != p.id
                               and x.requested_by != p.id)
            d["coincidencias"] = len(hs.overlaps(db, e, x.start_date, x.end_date, x.id))
            d["branch"] = db.get(Branch, e.branch_id).name
            out.append(d)
    return out


class LeaveDecision(BaseModel):
    version: int = Field(ge=1)
    approve: bool
    note: str | None = Field(default=None, max_length=500)


def decide_leave(db: Session, p: Principal, x: LeaveRequest, approve: bool, note: str | None, ctx) -> LeaveRequest:
    e = db.get(Employee, x.employee_id)
    acc = hs.access(p, e)
    if "leave" not in acc:
        raise PermissionError("Solo su responsable o RRHH deciden esta ausencia.")
    if x.status != "solicitada":
        raise ValueError(f"La solicitud ya está {x.status}.")
    if e.user_id == p.id or x.requested_by == p.id:
        raise PermissionError("Nadie aprueba sus propias ausencias.")
    note = (note or "").strip()
    if not approve and len(note) < 5:
        raise ValueError("Indique el motivo del rechazo.")
    x.status = "aprobada" if approve else "rechazada"
    x.decided_by, x.decided_at, x.decision_note = p.id, _now(), note or None
    x.version += 1
    audit.record(db, actor_id=p.id, action="hr.leave.approve" if approve else "hr.leave.reject", resource_type="employee",
                 resource_id=e.id, organization_id=e.organization_id, reason=note or None,
                 after={"ausencia": str(x.id), "estado": x.status}, ip=ctx.ip, request_id=ctx.request_id)
    from ..models_agents import AgentProposal
    for prop in db.execute(select(AgentProposal).where(AgentProposal.ref_type == "leave_request",
                                                       AgentProposal.ref_id == x.id,
                                                       AgentProposal.status == "pendiente")).scalars():
        prop.status, prop.decided_by, prop.decided_at = "caducada", p.id, _now()
        prop.decision_note = "Solicitud decidida."
    return x


@router.post("/leaves/{leave_id}/decide")
def decide(leave_id: uuid.UUID, body: LeaveDecision, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    x = db.get(LeaveRequest, leave_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Solicitud no encontrada.")
    db.execute(select(LeaveRequest).where(LeaveRequest.id == x.id).with_for_update())
    db.refresh(x)
    if x.version != body.version:
        raise api_error(409, "conflicto_version", "La solicitud ha cambiado. Recargue.")
    try:
        decide_leave(db, p, x, body.approve, body.note, req_ctx(request))
    except PermissionError as exc:
        _deny(p, request, "hr.leave.decide", x.employee_id, x.organization_id, str(exc))
        raise api_error(403, "prohibido", str(exc)) from exc
    except ValueError as exc:
        raise api_error(422 if "motivo" in str(exc) else 409, "validacion" if "motivo" in str(exc) else "conflicto", str(exc)) from exc
    db.commit()
    e = db.get(Employee, x.employee_id)
    return _leave_out(db, x, e, hs.access(p, e))


class CancelIn(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=300)


@router.post("/leaves/{leave_id}/cancel")
def cancel_leave(leave_id: uuid.UUID, body: CancelIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    x = db.get(LeaveRequest, leave_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Solicitud no encontrada.")
    e = db.get(Employee, x.employee_id)
    acc = hs.access(p, e)
    if not (acc & {"self", "manage"}):
        _deny(p, request, "hr.leave.cancel", e.id, e.organization_id, "ni propia ni RRHH")
        raise api_error(403, "prohibido", "No puede anular esta solicitud.")
    if x.version != body.version:
        raise api_error(409, "conflicto_version", "La solicitud ha cambiado. Recargue.")
    if x.status not in ("solicitada", "aprobada") or (x.status == "aprobada" and x.start_date <= date.today() and "manage" not in acc):
        raise api_error(409, "conflicto", "Ya no se puede anular: hable con RRHH.")
    before = x.status
    x.status, x.decision_note = "anulada", body.reason
    x.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="hr.leave.cancel", resource_type="employee", resource_id=e.id,
                 organization_id=e.organization_id, reason=body.reason, before={"estado": before},
                 after={"estado": x.status, "ausencia": str(x.id)}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _leave_out(db, x, e, acc)


@router.get("/calendar")
def calendar(month: str = Query(pattern=r"^\d{4}-\d{2}$"), p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)) -> list[dict]:
    y, m = int(month[:4]), int(month[5:])
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    out = []
    for x in db.execute(select(LeaveRequest).where(LeaveRequest.organization_id.in_(p.org_ids()),
                                                   LeaveRequest.status.in_(("aprobada", "solicitada")),
                                                   LeaveRequest.start_date < end, LeaveRequest.end_date >= start)
                        .order_by(LeaveRequest.start_date)).scalars():
        e = db.get(Employee, x.employee_id)
        acc = hs.access(p, e)
        if acc & {"read", "team", "self", "manage"}:
            d = _leave_out(db, x, e, acc)
            d["branch"] = db.get(Branch, e.branch_id).name
            out.append(d)
    return out


# ------------------------------------------------------------------ nóminas para la gestoría (DR-RH-5; no calcula)
@router.get("/payroll")
def payroll(request: Request, month: str = Query(pattern=r"^\d{4}-\d{2}$"), p: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> dict:
    orgs = p.orgs_with("hr.salary")
    if not orgs:
        _deny(p, request, "hr.payroll", None, None, "sin hr.salary")
        raise api_error(403, "prohibido", "Solo RRHH y Dirección ven las nóminas.")
    y, m = int(month[:4]), int(month[5:])
    prev = f"{y - (m == 1)}-{(m - 2) % 12 + 1:02d}"
    rows = []
    for e in db.execute(select(Employee).where(Employee.organization_id.in_(orgs)).order_by(Employee.family_names)).scalars():
        if e.status == "finalizado" and e.end_date and e.end_date < date(y, m, 1):
            continue
        if e.start_date > date(y + (m == 12), m % 12 + 1, 1):
            continue

        def slip(period: str, emp=e):
            return db.execute(select(EmployeeDocument).where(EmployeeDocument.employee_id == emp.id,
                                                             EmployeeDocument.kind == "nomina",
                                                             EmployeeDocument.period == period,
                                                             EmployeeDocument.status != "rechazado")
                              .order_by(EmployeeDocument.uploaded_at.desc())).scalars().first()
        cur, before = slip(month), slip(prev)
        c = (cur.confirmed or {}) if cur and cur.status == "valido" else {}
        b = (before.confirmed or {}) if before and before.status == "valido" else {}
        diff = None
        if c.get("devengado_cents") and b.get("devengado_cents"):
            diff = round((c["devengado_cents"] - b["devengado_cents"]) * 100 / b["devengado_cents"], 1)
        rows.append({"employee_id": str(e.id), "code": e.code, "name": f"{e.given_name} {e.family_names}",
                     "branch": db.get(Branch, e.branch_id).name, "country": e.country,
                     "currency": db.get(Organization, e.organization_id).currency,
                     "estado": "confirmada" if c else ("por_revisar" if cur else "falta"),
                     "devengado_cents": c.get("devengado_cents"), "deducciones_cents": c.get("deducciones_cents"),
                     "liquido_cents": c.get("liquido_cents"), "devengado_anterior_cents": b.get("devengado_cents"),
                     "diferencia_pct": diff, "revisar": diff is not None and abs(diff) >= 10})
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="hr.payroll.read", resource_type="organization", resource_id=None,
                             organization_id=sorted(orgs, key=str)[0], after={"mes": month}, ip=ctx.ip,
                             request_id=ctx.request_id)
    return {"month": month, "previous": prev, "rows": rows,
            "aviso": "Resumen de las nóminas confirmadas por RRHH para la gestoría. El sistema no calcula nóminas."}


# ------------------------------------------------------------------ importación (DR-RH-1)
IMPORT_COLS = ["nombre", "apellidos", "tipo_documento", "documento", "email", "telefono", "pais", "sede",
               "departamento", "categoria", "puesto", "contrato", "jornada", "horas_semana", "fecha_alta",
               "fecha_fin_contrato", "fin_periodo_prueba", "salario_anual", "vacaciones_dias"]
REQUIRED = ["nombre", "apellidos", "sede", "categoria", "puesto", "contrato", "jornada", "horas_semana", "fecha_alta"]


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for f in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(f"fecha «{s}»")


def _parse_rows(db: Session, org, data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    delim = ";" if text[:2000].count(";") >= text[:2000].count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    if not rows:
        raise api_error(422, "validacion", "El archivo no tiene filas.")
    header = {(k or "").strip().lower() for k in rows[0].keys()}
    if not set(REQUIRED) <= header:
        raise api_error(422, "validacion", "Faltan columnas obligatorias: " + ", ".join(sorted(set(REQUIRED) - header)),
                        [{"field": "file", "message": "Columnas: " + ";".join(IMPORT_COLS)}])
    branches = {fold(b.name): b for b in db.execute(select(Branch).where(Branch.organization_id == org)).scalars()}
    depts = {fold(d.name): d for d in db.execute(select(Department).where(Department.organization_id == org)).scalars()}
    depts |= {fold(d.code): d for d in depts.values()}
    out = []
    seen: set[str] = set()
    for i, raw in enumerate(rows, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        problems, missing = [], [c for c in REQUIRED if not r.get(c)]
        parsed: dict = {}
        try:
            b = branches.get(fold(r.get("sede", "")))
            if r.get("sede") and b is None:
                problems.append(f"sede «{r['sede']}» no existe")
            d = depts.get(fold(r.get("departamento", ""))) if r.get("departamento") else None
            if r.get("departamento") and d is None:
                problems.append(f"departamento «{r['departamento']}» no existe")
            contract = r.get("contrato", "").lower().replace(" ", "_")
            if contract and contract not in ("indefinido", "temporal", "practicas", "fijo_discontinuo", "otro"):
                problems.append(f"contrato «{r['contrato']}» no reconocido")
            jornada = r.get("jornada", "").lower()
            if jornada and jornada not in ("completa", "parcial"):
                problems.append(f"jornada «{r['jornada']}» no reconocida")
            parsed = {"given_name": r.get("nombre"), "family_names": r.get("apellidos"), "branch_id": b.id if b else None,
                      "department_id": d.id if d else None, "category": r.get("categoria"), "job_title": r.get("puesto"),
                      "contract_type": contract, "workday": jornada,
                      "weekly_hours": Decimal(r["horas_semana"].replace(",", ".")) if r.get("horas_semana") else None,
                      "start_date": _parse_date(r.get("fecha_alta", "")),
                      "contract_end_date": _parse_date(r.get("fecha_fin_contrato", "")),
                      "trial_end_date": _parse_date(r.get("fin_periodo_prueba", "")),
                      "salary_annual_cents": int(round(float(r["salario_anual"].replace(".", "").replace(",", ".")) * 100))
                      if r.get("salario_anual") else None,
                      "vacation_days_year": int(r["vacaciones_dias"]) if r.get("vacaciones_dias") else None,
                      "email": r.get("email") or None, "phone": r.get("telefono") or None,
                      "country": (r.get("pais") or "ES").upper()[:2], "id_kind": (r.get("tipo_documento") or "").upper() or None,
                      "id_number": r.get("documento") or None}
            if parsed["contract_type"] == "temporal" and not parsed["contract_end_date"]:
                problems.append("contrato temporal sin fecha de fin")
            if parsed["id_number"]:
                try:
                    validate_identifier(parsed["id_kind"] or "OTRO", parsed["id_number"],
                                        "ES" if parsed["id_kind"] in ("DNI", "NIE") else parsed["country"])
                except ValidationFailure as exc:
                    problems.append(exc.message)
        except (ValueError, ArithmeticError) as exc:
            problems.append(f"valor no válido: {exc}")
        key = fold(f"{r.get('nombre', '')} {r.get('apellidos', '')}")
        dups = _duplicates(db, org, r.get("nombre", ""), r.get("apellidos", ""), r.get("email"), None) if r.get("apellidos") else []
        status = "error" if (missing or problems) else ("duplicado" if dups or key in seen else "nuevo")
        seen.add(key)
        out.append({"line": i, "name": f"{r.get('nombre', '')} {r.get('apellidos', '')}".strip(), "status": status,
                    "missing": missing, "problems": problems,
                    "duplicate_of": [f"{x.code} {x.given_name} {x.family_names}" for x in dups], "_parsed": parsed})
    return out


@router.post("/import")
async def import_employees(request: Request, organization_id: uuid.UUID = Form(...), confirm: bool = Form(False),
                           file: UploadFile = File(...), p: Principal = Depends(get_principal),
                           db: Session = Depends(get_db)) -> dict:
    """Importación desde una hoja (CSV exportado de MN Program u otra). Primero se previsualiza: nuevas, duplicadas y
    con errores. Al confirmar SOLO se crean las nuevas sin errores; nada se sobrescribe ni se borra."""
    if organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not (p.has(organization_id, "hr.manage") and p.has(organization_id, "hr.salary")):
        _deny(p, request, "hr.import", None, organization_id, "sin hr.manage/hr.salary")
        raise api_error(403, "prohibido", "Solo RRHH importa la plantilla.")
    data = await file.read(MAX_FILE + 1)
    if len(data) > 2 * 1024 * 1024:
        raise api_error(422, "validacion", "El archivo supera 2 MB.")
    rows = _parse_rows(db, organization_id, data)
    created = []
    if confirm:
        ctx = req_ctx(request)
        for r in rows:
            if r["status"] != "nuevo":
                continue
            body = EmployeeIn(organization_id=organization_id, **{k: v for k, v in r["_parsed"].items() if v is not None})
            e = create_employee(db, p, body, ctx, force=False)
            created.append(e.code)
        audit.record(db, actor_id=p.id, action="hr.import", resource_type="organization", resource_id=organization_id,
                     organization_id=organization_id,
                     after={"filas": len(rows), "creadas": len(created),
                            "duplicadas": sum(1 for r in rows if r["status"] == "duplicado"),
                            "errores": sum(1 for r in rows if r["status"] == "error")},
                     ip=ctx.ip, request_id=ctx.request_id)
        db.commit()
    return {"rows": [{k: v for k, v in r.items() if k != "_parsed"} for r in rows], "created": created,
            "columns": IMPORT_COLS, "required": REQUIRED, "confirmed": confirm}
