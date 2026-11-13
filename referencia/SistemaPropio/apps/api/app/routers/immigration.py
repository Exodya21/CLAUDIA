"""Expediente de extranjería (F4.1): trámite, fases del flujo, documentos leídos y paquete para Mercurio.

Límites deliberados:
- No se presenta nada en Mercurio ni se descarga nada de DEHú automáticamente (A-11, D-09). El paquete se prepara
  aquí; el profesional presenta con su certificado y sube el resguardo.
- No se calcula ningún plazo legal (D-01, D-03): un requerimiento crea una tarea para que el letrado proponga el
  plazo con su fuente y otro lo valide.
- La lectura de documentos propone tipo y fechas; una persona los confirma.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from datetime import date as Day
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..immigration import extract, reader
from ..immigration.catalog import (
    DOC_TYPES,
    LEGAL_STAGES,
    MERCURIO_FORMATS,
    MERCURIO_MAX_BYTES,
    MERCURIO_SOURCE,
    STAGE_FLOW,
    STAGES,
)
from ..immigration.sync import current
from ..models import CaseAssignment, CaseFile, Contact, UserAccount
from ..models_immigration import ImmigCase, ImmigDocument, ImmigProcedure, ImmigStageEvent
from ..models_work import Task, TaskEvent
from ..security.auth import Principal, get_principal
from ..security.policy import case_level, case_visibility_filter, load_case_scope
from ..services import vault
from .common import ReqCtx, req_ctx

router = APIRouter(prefix="/immigration", tags=["extranjería"])
PASSPORT_WARN_DAYS = 90  # propuesta (T-22): aviso de pasaporte que caduca pronto; configurable cuando se valide
MATERIAS = {"extranjeria", "nacionalidad"}


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ esquemas
class CaseSetup(BaseModel):
    procedure_code: str = Field(min_length=2, max_length=40)
    province: str | None = Field(default=None, max_length=60)


class CaseUpdate(BaseModel):
    province: str | None = Field(default=None, max_length=60)
    mercurio_identifier: str | None = Field(default=None, max_length=60)
    registry_number: str | None = Field(default=None, max_length=60)
    office_file_number: str | None = Field(default=None, max_length=60)
    version: int


class StageIn(BaseModel):
    to: str
    note: str | None = Field(default=None, max_length=2000)
    date: Day | None = None                        # presentación, notificación o resolución
    registry_number: str | None = Field(default=None, max_length=60)
    version: int | None = None


class ReviewIn(BaseModel):
    doc_type: str
    status: Literal["valido", "rechazado"]
    label: str | None = Field(default=None, max_length=200)
    issued_on: date | None = None
    expires_on: date | None = None
    in_package: bool = True
    note: str | None = Field(default=None, max_length=500)
    version: int


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ApproveIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


# ------------------------------------------------------------------ acceso
def _deny(p: Principal, ctx: ReqCtx, action: str, rid, org, reason: str) -> None:
    audit.record_independent(actor_id=p.id, action=action, resource_type="case_file", resource_id=rid,
                             organization_id=org, outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _case(db: Session, p: Principal, case_id: uuid.UUID, request: Request, action: str, need: str = "full",
          perm: str | None = None) -> CaseFile:
    ctx = req_ctx(request)
    cf = db.get(CaseFile, case_id)
    if cf is None or cf.organization_id not in p.org_ids():
        _deny(p, ctx, action, case_id, cf.organization_id if cf else None, "fuera de entidad o inexistente")
        raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    level = case_level(p, cf, load_case_scope(db, p))
    ok = level == "full" if need == "full" else level is not None
    if perm and not p.has(cf.organization_id, perm):
        ok = False
    if not ok:
        _deny(p, ctx, action, cf.id, cf.organization_id, f"sin acceso ({perm or need})")
        raise api_error(403, "prohibido", "Su rol no permite esta operación en este expediente. Queda registrado.")
    return cf


def _immig(db: Session, cf: CaseFile) -> ImmigCase:
    ic = db.get(ImmigCase, cf.id)
    if ic is None:
        raise api_error(409, "sin_tramite", "Elija primero el trámite de extranjería del expediente.")
    return ic


def _touch(cf: CaseFile) -> None:
    cf.last_activity_at = _now()


def _uname(db: Session, uid) -> str | None:
    return db.get(UserAccount, uid).full_name if uid else None


# ------------------------------------------------------------------ catálogo
def _proc_out(pr: ImmigProcedure, db: Session) -> dict:
    return {"id": str(pr.id), "code": pr.code, "version": pr.version, "name": pr.name, "family": pr.family,
            "materia": pr.materia, "status": pr.status, "approved_by": _uname(db, pr.approved_by),
            "approved_at": pr.approved_at.isoformat() if pr.approved_at else None, **{
                k: pr.data.get(k) for k in ("sheet", "source_url", "source_updated", "legal_basis", "ex_form", "fee",
                                            "mercurio", "resolution", "silence", "window", "note", "requirements")}}


@router.get("/procedures")
def procedures(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(ImmigProcedure).where(ImmigProcedure.status != "sustituido")
                      .order_by(ImmigProcedure.family, ImmigProcedure.name)).scalars()
    return {"procedures": [_proc_out(r, db) for r in rows], "doc_types": DOC_TYPES, "stages": STAGES,
            "can_approve": bool(p.orgs_with("immig.catalog.approve")),
            "mercurio": {"max_mb": MERCURIO_MAX_BYTES // (1024 * 1024), "formats": sorted(set(MERCURIO_FORMATS.values())),
                         "source": MERCURIO_SOURCE}}


@router.post("/procedures/{proc_id}/approve")
def approve_procedure(proc_id: uuid.UUID, body: ApproveIn, request: Request, p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> dict:
    ctx = req_ctx(request)
    if not p.orgs_with("immig.catalog.approve"):
        _deny(p, ctx, "immig.catalog.approve", proc_id, None, "sin immig.catalog.approve")
        raise api_error(403, "prohibido", "Solo Legal Extranjería o Dirección validan el catálogo.")
    pr = db.get(ImmigProcedure, proc_id)
    if pr is None or pr.status == "sustituido":
        raise api_error(404, "no_encontrado", "Versión no encontrada o ya sustituida.")
    pr.status, pr.approved_by, pr.approved_at, pr.approval_note = "aprobado", p.id, _now(), body.note
    audit.record(db, actor_id=p.id, action="immig.catalog.approve", resource_type="immig_procedure",
                 resource_id=pr.id, reason=body.note, after={"tramite": pr.code, "version": pr.version},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _proc_out(pr, db)


# ------------------------------------------------------------------ comprobaciones del expediente
def _doc_out(db: Session, d: ImmigDocument, warnings: list[str] | None = None) -> dict:
    mrz_data = (d.extracted or {}).get("mrz")
    return {"id": str(d.id), "status": d.status, "doc_type": d.doc_type, "suggested_type": d.suggested_type,
            "suggested_confidence": d.suggested_confidence, "label": d.label, "original_name": d.original_name,
            "mime": d.mime, "size_bytes": d.size_bytes, "issued_on": d.issued_on.isoformat() if d.issued_on else None,
            "expires_on": d.expires_on.isoformat() if d.expires_on else None, "review_note": d.review_note,
            "uploaded_by": _uname(db, d.uploaded_by), "uploaded_at": d.uploaded_at.isoformat(),
            "reviewed_by": _uname(db, d.reviewed_by), "in_package": d.in_package, "version": d.version,
            "extracted": {k: v for k, v in (d.extracted or {}).items() if k != "mrz_lines"},
            "mrz": mrz_data, "warnings": warnings or [], "ocr_engine": d.ocr_engine}


def _doc_warnings(d: ImmigDocument, contact: Contact, today: date, dup_shas: set[str]) -> list[str]:
    w = []
    if d.status == "pendiente_revision":
        w.append("Pendiente de revisar y confirmar")
    if d.expires_on and d.expires_on < today:
        w.append(f"Caducado el {d.expires_on.strftime('%d/%m/%Y')}")
    elif d.expires_on and (d.doc_type or d.suggested_type) == "pasaporte" and d.expires_on < today + timedelta(days=PASSPORT_WARN_DAYS):
        w.append(f"El pasaporte caduca el {d.expires_on.strftime('%d/%m/%Y')} (menos de {PASSPORT_WARN_DAYS} días)")
    mrz_data = (d.extracted or {}).get("mrz")
    if mrz_data and reader.name_matches(contact.given_name, contact.family_names, mrz_data) is False:
        w.append("El titular del documento no coincide con el cliente del expediente")
    if mrz_data and not mrz_data.get("valid"):
        w.append("La zona MRZ no supera los dígitos de control: compruebe los datos a mano")
    if (d.doc_type or d.suggested_type) == "tasa_790" and not ((d.extracted or {}).get("info") or {}).get("nrc"):
        w.append("No se ve el NRC del pago: compruebe que la tasa está pagada")
    if d.sha256 in dup_shas:
        w.append("Este mismo archivo está subido más de una vez")
    if d.mime not in MERCURIO_FORMATS and d.mime != "image/png":
        w.append("Formato no admitido por Mercurio")
    if d.mime == "application/pdf" and d.size_bytes > MERCURIO_MAX_BYTES:
        w.append("Supera 6 MB: Mercurio no lo admite; divídalo o comprímalo antes de presentar")
    return w


def _checklist(proc: ImmigProcedure, docs: list[ImmigDocument], today: date) -> list[dict]:
    valid = [d for d in docs if d.status == "valido" and d.doc_type]
    used: set[uuid.UUID] = set()
    out = []
    for i, r in enumerate(proc.data["requirements"]):
        matches = [d for d in valid if d.doc_type == r["doc_type"] and d.id not in used]
        # Un requisito que se repite (p. ej. dos pasaportes en reagrupación) consume un documento cada vez.
        repeat = sum(1 for x in proc.data["requirements"][:i] if x["doc_type"] == r["doc_type"])
        if repeat and len(matches) > 0:
            matches = matches[:1]
        live = [d for d in matches if not d.expires_on or d.expires_on >= today]
        if live:
            used.add(live[0].id)
        pending = [d for d in docs if d.status == "pendiente_revision" and (d.doc_type or d.suggested_type) == r["doc_type"]]
        state = "cumplido" if live else ("caducado" if matches else ("por_revisar" if pending else "falta"))
        out.append({"index": i, **r, "state": state, "documents": [str(d.id) for d in (live or matches)]})
    return out


def _detail(db: Session, p: Principal, cf: CaseFile, ic: ImmigCase) -> dict:
    proc = db.get(ImmigProcedure, ic.procedure_id)
    contact = db.get(Contact, cf.contact_id)
    today = date.today()
    docs = list(db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id, ImmigDocument.status != "retirado")
                           .order_by(ImmigDocument.uploaded_at)).scalars())
    shas = [d.sha256 for d in docs]
    dup = {s for s in shas if shas.count(s) > 1}
    checklist = _checklist(proc, docs, today)
    alerts: list[dict] = []
    if proc.status != "aprobado":
        alerts.append({"level": "info", "text": "La lista de documentos de este trámite está pendiente de validar por Legal Extranjería."})
    missing = [c for c in checklist if c["kind"] == "obligatorio" and c["state"] != "cumplido"]
    if missing and ic.stage in ("preparacion", "lista_presentar"):
        alerts.append({"level": "warn", "text": f"Faltan {len(missing)} documentos obligatorios para presentar."})
    if dup:
        n = sum(1 for d in docs if d.sha256 in dup) - len(dup)
        alerts.append({"level": "warn", "text": f"Hay {n} archivo(s) repetido(s): retire las copias sobrantes (botón «Retirar» del documento)."})
    for d in docs:
        for w in _doc_warnings(d, contact, today, dup):
            if not w.startswith("Pendiente") and not w.startswith("Este mismo archivo"):
                alerts.append({"level": "warn", "text": f"{d.label or DOC_TYPES.get(d.doc_type or d.suggested_type or 'otros')}: {w}",
                               "document_id": str(d.id)})
    pend = sum(1 for d in docs if d.status == "pendiente_revision")
    if pend:
        alerts.append({"level": "info", "text": f"{pend} documento(s) pendientes de revisar."})
    if ic.stage == "presentado" and not ic.registry_number and not any(d.doc_type == "resguardo_presentacion" for d in docs):
        alerts.append({"level": "warn", "text": "Presentado sin número de registro ni resguardo: súbalo."})
    org = cf.organization_id
    events = db.execute(select(ImmigStageEvent).where(ImmigStageEvent.case_id == cf.id).order_by(ImmigStageEvent.at)).scalars()
    nexts = sorted(STAGE_FLOW.get(ic.stage, set()), key=list(STAGES).index)
    allowed = [s for s in nexts if p.has(org, "case.transition.legal" if s in LEGAL_STAGES else "case.transition")]
    return {
        "case_id": str(cf.id), "code": cf.code, "materia": cf.materia, "stage": ic.stage,
        "stage_label": STAGES[ic.stage], "stage_since": ic.stage_changed_at.isoformat(),
        "days_in_stage": (_now() - ic.stage_changed_at).days, "province": ic.province,
        "mercurio_identifier": ic.mercurio_identifier, "registry_number": ic.registry_number,
        "presented_at": ic.presented_at.isoformat() if ic.presented_at else None,
        "office_file_number": ic.office_file_number,
        "resolution_at": ic.resolution_at.isoformat() if ic.resolution_at else None, "version": ic.version,
        "procedure": _proc_out(proc, db),
        "client": {"name": f"{contact.given_name} {contact.family_names}", "nationality": contact.nationality,
                   "birth_date": contact.birth_date.isoformat() if contact.birth_date else None},
        "documents": [_doc_out(db, d, _doc_warnings(d, contact, today, dup)) for d in docs],
        "checklist": checklist, "alerts": alerts, "next_stages": allowed, "all_next": nexts,
        "events": [{"from": e.from_stage, "to": e.to_stage, "note": e.note, "data": e.data,
                    "actor": _uname(db, e.actor_user_id), "at": e.at.isoformat()} for e in events],
        "can": {"upload": p.has(org, "immig.document.upload"), "review": p.has(org, "immig.document.review"),
                "package": p.has(org, "immig.package"), "edit": p.has(org, "case.transition")},
    }


# ------------------------------------------------------------------ expediente
@router.get("/cases/{case_id}")
def get_case(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.read")
    ic = db.get(ImmigCase, cf.id)
    if ic is None:
        options = db.execute(select(ImmigProcedure).where(ImmigProcedure.status != "sustituido",
                                                          ImmigProcedure.materia == cf.materia)
                             .order_by(ImmigProcedure.family, ImmigProcedure.name)).scalars()
        return {"case_id": str(cf.id), "configured": False, "materia": cf.materia,
                "options": [{"code": o.code, "name": o.name, "family": o.family, "status": o.status} for o in options],
                "can": {"edit": p.has(cf.organization_id, "case.transition")}}
    return {"configured": True, **_detail(db, p, cf, ic)}


@router.post("/cases/{case_id}", status_code=201)
def setup_case(case_id: uuid.UUID, body: CaseSetup, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.setup", perm="case.transition")
    if cf.materia not in MATERIAS:
        raise api_error(422, "validacion", "Este expediente no es de extranjería ni de nacionalidad.")
    if db.get(ImmigCase, cf.id):
        raise api_error(409, "conflicto", "El expediente ya tiene trámite.")
    pr = current(db, body.procedure_code)
    if pr is None or pr.materia != cf.materia:
        raise api_error(422, "validacion", "Trámite no disponible para esta materia.",
                        [{"field": "procedure_code", "message": "No válido"}])
    ic = ImmigCase(case_id=cf.id, organization_id=cf.organization_id, procedure_id=pr.id, stage="documentacion",
                   province=body.province, created_by=p.id)
    db.add(ic)
    db.add(ImmigStageEvent(case_id=cf.id, actor_user_id=p.id, from_stage=None, to_stage="documentacion",
                           note=f"Trámite: {pr.name} (versión {pr.version})"))
    _touch(cf)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.setup", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after={"tramite": pr.code, "version": pr.version},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"configured": True, **_detail(db, p, cf, ic)}


@router.patch("/cases/{case_id}")
def update_case(case_id: uuid.UUID, body: CaseUpdate, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.update", perm="case.transition")
    ic = _immig(db, cf)
    if body.version != ic.version:
        raise api_error(409, "conflicto_version", "Otra persona ha cambiado el expediente. Recargue la página.")
    data = body.model_dump(exclude_unset=True, exclude={"version"})
    before = {k: getattr(ic, k) for k in data}
    for k, v in data.items():
        setattr(ic, k, (v or "").strip() or None)
    ic.version += 1
    _touch(cf)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.update", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, before=before, after=data, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"configured": True, **_detail(db, p, cf, ic)}


def _responsible(db: Session, cf: CaseFile, fallback: uuid.UUID) -> uuid.UUID:
    a = db.execute(select(CaseAssignment).where(CaseAssignment.case_id == cf.id, CaseAssignment.end_at.is_(None))
                   .order_by(CaseAssignment.start_at)).scalars().first()
    return a.user_id if a else fallback


@router.post("/cases/{case_id}/stage")
def change_stage(case_id: uuid.UUID, body: StageIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.stage")
    ic = _immig(db, cf)
    ctx = req_ctx(request)
    if body.version is not None and body.version != ic.version:
        raise api_error(409, "conflicto_version", "Otra persona ha cambiado el expediente. Recargue la página.")
    if body.to not in STAGE_FLOW.get(ic.stage, set()):
        raise api_error(422, "transicion_no_valida", f"No se puede pasar de «{STAGES[ic.stage]}» a «{STAGES.get(body.to, body.to)}».")
    perm = "case.transition.legal" if body.to in LEGAL_STAGES else "case.transition"
    if not p.has(cf.organization_id, perm):
        _deny(p, ctx, f"immig.stage.{body.to}", cf.id, cf.organization_id, f"sin {perm}")
        raise api_error(403, "prohibido", "Esta fase solo la registra un letrado autorizado o Dirección.")
    note = (body.note or "").strip()
    data: dict = {}
    today = date.today()
    if body.date and body.date > today:
        raise api_error(422, "validacion", "La fecha no puede ser futura.", [{"field": "date", "message": "Futura"}])
    if body.to == "presentado":
        docs = list(db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id,
                                                           ImmigDocument.status != "retirado")).scalars())
        proc = db.get(ImmigProcedure, ic.procedure_id)
        missing = [c["label"] for c in _checklist(proc, docs, today) if c["kind"] == "obligatorio" and c["state"] != "cumplido"]
        if missing and len(note) < 10:
            raise api_error(422, "faltan_documentos",
                            f"Faltan documentos obligatorios ({', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}). "
                            "Si se presenta igualmente, explique el motivo.", {"missing": missing})
        ic.presented_at = datetime.combine(body.date or today, datetime.min.time(), UTC)
        if body.registry_number:
            ic.registry_number = body.registry_number.strip()
        data = {"fecha_presentacion": (body.date or today).isoformat(), "registro": ic.registry_number,
                "faltaban": missing}
    if body.to in ("resolucion_favorable", "resolucion_desfavorable"):
        if not body.date:
            raise api_error(422, "validacion", "Indique la fecha de la resolución.", [{"field": "date", "message": "Obligatoria"}])
        ic.resolution_at = body.date
        data = {"fecha_resolucion": body.date.isoformat()}
    if body.to in ("requerimiento", "recurso", "cerrado", "resolucion_desfavorable") and len(note) < 5:
        raise api_error(422, "validacion", "Añada una nota (qué se pide, motivo o decisión).", [{"field": "note", "message": "Obligatoria"}])
    if body.to == "requerimiento":
        notified = body.date or today
        data = {"fecha_notificacion": notified.isoformat()}
        # La fecha legal NO se calcula (D-01, D-03): la propone un letrado con su fuente y otro la valida.
        t = Task(organization_id=cf.organization_id, case_id=cf.id, kind="plazo", priority="alta",
                 title=f"Requerimiento {cf.code}: fijar plazo legal y responder",
                 description=(f"Requerimiento notificado el {notified.strftime('%d/%m/%Y')}. {note}\n\n"
                              "El sistema no calcula el plazo legal: propóngalo con su fuente (norma y forma de "
                              "cómputo) y que lo valide otro letrado."),
                 assignee_id=_responsible(db, cf, p.id), due_at=_now() + timedelta(days=1), created_by=p.id)
        db.add(t)
        db.flush()
        db.add(TaskEvent(task_id=t.id, actor_user_id=p.id, kind="creada", to_status="pendiente", new_due_at=t.due_at,
                         reason="Creada al registrar el requerimiento"))
        data["tarea"] = str(t.id)
    db.add(ImmigStageEvent(case_id=cf.id, actor_user_id=p.id, from_stage=ic.stage, to_stage=body.to,
                           note=note or None, data=data or None))
    before = ic.stage
    ic.stage, ic.stage_changed_at = body.to, _now()
    ic.version += 1
    _touch(cf)
    audit.record(db, actor_id=p.id, action=f"immig.stage.{body.to}", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, reason=note or None, before={"fase": before},
                 after={"fase": body.to, **data}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"configured": True, **_detail(db, p, cf, ic)}


# ------------------------------------------------------------------ documentos
def ingest_document(db: Session, cf: CaseFile, data: bytes, mime: str, name: str, by: uuid.UUID, ctx: ReqCtx,
                    source: str | None = None) -> tuple[ImmigDocument | None, str | None, dict]:
    """Lee, cifra y registra un documento del expediente (subida directa o traído del portal del cliente)."""
    if db.execute(select(ImmigDocument.id).where(ImmigDocument.case_id == cf.id, ImmigDocument.status != "retirado",
                                                 ImmigDocument.sha256 == hashlib.sha256(data).hexdigest())).first():
        return None, "Ya estaba subido en este expediente: no se ha duplicado.", {}
    r = reader.read(data, mime)
    path, sha = vault.store(data)
    fields = r["fields"]
    d = ImmigDocument(organization_id=cf.organization_id, case_id=cf.id, suggested_type=r["suggested_type"],
                      suggested_confidence=r["confidence"], original_name=name, mime=mime, size_bytes=len(data),
                      sha256=sha, file_path=path, extracted=fields or None, ocr_engine=r["engine"],
                      ocr_text=r["text"] or None,
                      expires_on=date.fromisoformat(fields["expires_on"]) if fields.get("expires_on") else None,
                      issued_on=date.fromisoformat(fields["issued_on"]) if fields.get("issued_on") else None,
                      uploaded_by=by)
    db.add(d)
    db.flush()
    audit.record(db, actor_id=by, action="immig.document.upload", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id,
                 after={"documento": str(d.id), "archivo": name, "sha256": sha, "tipo_propuesto": r["suggested_type"],
                        **({"origen": source} if source else {})},
                 ip=ctx.ip, request_id=ctx.request_id)
    _touch(cf)
    return d, None, r


@router.post("/cases/{case_id}/documents", status_code=201)
async def upload(case_id: uuid.UUID, request: Request, files: list[UploadFile] = File(...),
                 p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.upload", need="meta", perm="immig.document.upload")
    _immig(db, cf)
    if len(files) > 20:
        raise api_error(422, "validacion", "Máximo 20 archivos por subida.")
    ctx = req_ctx(request)
    results = []
    for f in files:
        data = await f.read(vault.MAX_BYTES + 1)
        name = (f.filename or "documento")[:200]
        try:
            mime = vault.sniff(data)
        except vault.VaultError as exc:
            results.append({"name": name, "ok": False, "error": exc.message})
            continue
        d, err, r = ingest_document(db, cf, data, mime, name, p.id, ctx)
        if err:
            results.append({"name": name, "ok": False, "error": err})
            continue
        results.append({"name": name, "ok": True, "id": str(d.id), "suggested_type": r["suggested_type"],
                        "confidence": r["confidence"], "message": r.get("message")})
    _touch(cf)
    db.commit()
    level = case_level(p, cf, load_case_scope(db, p))
    out = {"results": results}
    if level == "full":
        ic = db.get(ImmigCase, cf.id)
        out["case"] = {"configured": True, **_detail(db, p, cf, ic)}
    return out


def _doc(db: Session, p: Principal, doc_id: uuid.UUID, request: Request, action: str, perm: str | None = None) -> tuple[ImmigDocument, CaseFile]:
    d = db.get(ImmigDocument, doc_id)
    if d is None or d.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Documento no encontrado.")
    cf = _case(db, p, d.case_id, request, action, perm=perm)
    return d, cf


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> Response:
    d, cf = _doc(db, p, doc_id, request, "immig.document.read")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="immig.document.read", resource_type="case_file", resource_id=cf.id,
                             organization_id=cf.organization_id, after={"documento": str(d.id)}, ip=ctx.ip,
                             request_id=ctx.request_id)
    ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[d.mime]
    return Response(vault.load(d.file_path), media_type=d.mime,
                    headers={"Content-Disposition": f'inline; filename="{reader.safe_name(d.label or d.doc_type or "documento")}.{ext}"',
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
                             "Cache-Control": "no-store"})


@router.post("/documents/{doc_id}/reread")
def reread_document(doc_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    """Vuelve a leer un documento ya subido con la versión actual de la lectura. No cambia su estado ni su tipo
    confirmado; si ya estaba validado, sus datos nuevos se proponen en la ficha (nunca pisan lo guardado)."""
    d, cf = _doc(db, p, doc_id, request, "immig.document.reread", perm="immig.document.review")
    if d.status == "retirado":
        raise api_error(409, "conflicto", "El documento está retirado.")
    r = reader.read(vault.load(d.file_path), d.mime)
    fields = dict(r["fields"])
    if d.doc_type and d.doc_type != r["suggested_type"]:
        ficha, info = extract.for_document(d.doc_type, r["text"] or "", fields.get("mrz"))
        fields.pop("ficha", None)
        fields.pop("info", None)
        fields.update({k: v for k, v in (("ficha", ficha), ("info", info)) if v})
    d.extracted, d.ocr_text, d.ocr_engine = fields or None, r["text"] or None, r["engine"]
    d.suggested_type, d.suggested_confidence = r["suggested_type"], r["confidence"]
    if fields.get("expires_on") and not d.expires_on:
        d.expires_on = date.fromisoformat(fields["expires_on"])
    d.version += 1
    _touch(cf)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.document.reread", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id,
                 after={"documento": str(d.id), "tipo_propuesto": r["suggested_type"], "datos_leidos": len(fields.get("ficha") or {})},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"configured": True, **_detail(db, p, cf, db.get(ImmigCase, cf.id))}


@router.get("/documents/{doc_id}/diagnostic")
def document_diagnostic(doc_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                        db: Session = Depends(get_db)) -> dict:
    """Estructura del texto leído SIN datos: etiquetas del formulario visibles, todo lo demás enmascarado."""
    d, cf = _doc(db, p, doc_id, request, "immig.document.diagnostic", perm="immig.document.review")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="immig.document.diagnostic", resource_type="case_file",
                             resource_id=cf.id, organization_id=cf.organization_id, after={"documento": str(d.id)},
                             ip=ctx.ip, request_id=ctx.request_id)
    mz = (d.extracted or {}).get("mrz") or {}
    return {"tipo": d.doc_type or d.suggested_type, "motor": d.ocr_engine, "paginas_texto": (d.ocr_text or "").count("\f") + 1,
            "mrz": {"formato": mz.get("format"), "controles": mz.get("checks")} if mz else None,
            "campos_leidos": sorted((d.extracted or {}).get("ficha", {}).keys()),
            "texto": extract.mask_text(d.ocr_text or "")[:20000]}


@router.post("/documents/{doc_id}/review")
def review_document(doc_id: uuid.UUID, body: ReviewIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    d, cf = _doc(db, p, doc_id, request, "immig.document.review", perm="immig.document.review")
    if body.doc_type not in DOC_TYPES:
        raise api_error(422, "validacion", "Tipo de documento no válido.", [{"field": "doc_type", "message": "No válido"}])
    if d.status == "retirado":
        raise api_error(409, "conflicto", "El documento está retirado.")
    if body.version != d.version:
        raise api_error(409, "conflicto_version", "El documento ha cambiado. Recargue la página.")
    if body.status == "rechazado" and len((body.note or "").strip()) < 5:
        raise api_error(422, "validacion", "Indique por qué no es válido.", [{"field": "note", "message": "Obligatorio"}])
    if body.issued_on and body.issued_on > date.today():
        raise api_error(422, "validacion", "La fecha de expedición no puede ser futura.", [{"field": "issued_on", "message": "Futura"}])
    before = {"estado": d.status, "tipo": d.doc_type, "expedicion": str(d.issued_on), "caducidad": str(d.expires_on)}
    if body.doc_type != (d.doc_type or d.suggested_type) or "ficha" not in (d.extracted or {}):
        # Tipo confirmado distinto del propuesto: volver a sacar los datos con las reglas de ese tipo (sin releer)
        ficha, info = extract.for_document(body.doc_type, d.ocr_text or "", (d.extracted or {}).get("mrz"))
        ext = {k: v for k, v in (d.extracted or {}).items() if k not in ("ficha", "info")}
        if ficha:
            ext["ficha"] = ficha
        if info:
            ext["info"] = info
        d.extracted = ext or None
    d.doc_type, d.status, d.label = body.doc_type, body.status, (body.label or "").strip() or None
    d.issued_on, d.expires_on, d.in_package = body.issued_on, body.expires_on, body.in_package
    d.review_note = (body.note or "").strip() or None
    d.reviewed_by, d.reviewed_at = p.id, _now()
    d.version += 1
    _touch(cf)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.document.review", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, reason=d.review_note, before=before,
                 after={"documento": str(d.id), "estado": d.status, "tipo": d.doc_type,
                        "tipo_propuesto": d.suggested_type, "expedicion": str(d.issued_on), "caducidad": str(d.expires_on)},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"configured": True, **_detail(db, p, cf, db.get(ImmigCase, cf.id))}


@router.post("/documents/{doc_id}/retire")
def retire_document(doc_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    d, cf = _doc(db, p, doc_id, request, "immig.document.retire", perm="immig.document.review")
    if d.status != "retirado":
        before = d.status
        d.status, d.review_note, d.reviewed_by, d.reviewed_at = "retirado", body.reason, p.id, _now()
        d.version += 1
        ctx = req_ctx(request)
        audit.record(db, actor_id=p.id, action="immig.document.retire", resource_type="case_file", resource_id=cf.id,
                     organization_id=cf.organization_id, reason=body.reason, before={"estado": before},
                     after={"documento": str(d.id), "estado": "retirado"}, ip=ctx.ip, request_id=ctx.request_id)
        db.commit()
    return {"configured": True, **_detail(db, p, cf, db.get(ImmigCase, cf.id))}


# ------------------------------------------------------------------ paquete para Mercurio
def _to_mercurio(data: bytes, mime: str) -> tuple[bytes, str, str | None]:
    """Convierte al formato que admite Mercurio. Devuelve (bytes, extensión, problema o None)."""
    if mime == "application/pdf":
        return data, "pdf", None if len(data) <= MERCURIO_MAX_BYTES else "PDF de más de 6 MB: divídalo o comprímalo"
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = data
    if mime != "image/jpeg" or len(data) > MERCURIO_MAX_BYTES:
        for quality, scale in ((90, 1.0), (80, 1.0), (75, 0.8), (70, 0.6), (65, 0.45)):
            im = img if scale == 1.0 else img.resize((int(img.width * scale), int(img.height * scale)))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=quality, optimize=True)
            out = buf.getvalue()
            if len(out) <= MERCURIO_MAX_BYTES:
                break
    problem = None if len(out) <= MERCURIO_MAX_BYTES else "Imagen de más de 6 MB incluso comprimida"
    return out, "jpg", problem


def _package_plan(db: Session, cf: CaseFile, ic: ImmigCase) -> dict:
    proc = db.get(ImmigProcedure, ic.procedure_id)
    today = date.today()
    docs = list(db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id,
                                                       ImmigDocument.status != "retirado")
                           .order_by(ImmigDocument.uploaded_at)).scalars())
    checklist = _checklist(proc, docs, today)
    order = {r["doc_type"]: i for i, r in reversed(list(enumerate(proc.data["requirements"])))}
    include = sorted([d for d in docs if d.status == "valido" and d.in_package],
                     key=lambda d: (order.get(d.doc_type, 99), d.uploaded_at))
    blocking, warnings = [], []
    for c in checklist:
        if c["kind"] == "obligatorio" and c["state"] != "cumplido":
            blocking.append(f"Falta: {c['label']} ({c['state'].replace('_', ' ')})")
    pend = [d for d in docs if d.status == "pendiente_revision"]
    if pend:
        warnings.append(f"{len(pend)} documento(s) sin revisar no se incluyen.")
    for d in include:
        if d.expires_on and d.expires_on < today:
            blocking.append(f"Caducado: {d.label or DOC_TYPES[d.doc_type]}")
        if d.mime == "application/pdf" and d.size_bytes > MERCURIO_MAX_BYTES:
            blocking.append(f"Más de 6 MB: {d.label or DOC_TYPES[d.doc_type]}")
    if proc.status != "aprobado":
        warnings.append("La lista de documentos del trámite está pendiente de validar por Legal Extranjería.")
    if not proc.data.get("mercurio"):
        warnings.append("Según la hoja oficial, este trámite no se presenta por Mercurio.")
    return {"procedure": proc, "include": include, "blocking": blocking, "warnings": warnings, "checklist": checklist}


@router.get("/cases/{case_id}/package/check")
def package_check(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.package", perm="immig.package")
    plan = _package_plan(db, cf, _immig(db, cf))
    return {"ready": not plan["blocking"], "blocking": plan["blocking"], "warnings": plan["warnings"],
            "files": [{"id": str(d.id), "type": d.doc_type, "label": d.label or DOC_TYPES[d.doc_type],
                       "size_bytes": d.size_bytes, "mime": d.mime} for d in plan["include"]]}


@router.get("/cases/{case_id}/package.zip")
def package_zip(case_id: uuid.UUID, request: Request, force: bool = Query(False), p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> Response:
    cf = _case(db, p, case_id, request, "immig.package", perm="immig.package")
    ic = _immig(db, cf)
    plan = _package_plan(db, cf, ic)
    if plan["blocking"] and not force:
        raise api_error(422, "paquete_incompleto", "El paquete tiene problemas que impiden presentarlo.",
                        {"blocking": plan["blocking"]})
    contact = db.get(Contact, cf.contact_id)
    proc = plan["procedure"]
    buf = io.BytesIO()
    index = [f"Expediente {cf.code} · {proc.name} ({proc.data.get('ex_form')})",
             f"Generado el {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC. Revise cada archivo antes de adjuntarlo en Mercurio.", ""]
    problems = list(plan["blocking"])
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in enumerate(plan["include"], start=1):
            data, ext, problem = _to_mercurio(vault.load(d.file_path), d.mime)
            fname = f"{n:02d}_{reader.safe_name(d.label or DOC_TYPES[d.doc_type])}.{ext}"
            z.writestr(fname, data)
            index.append(f"{fname}  ->  tipo en Mercurio: {DOC_TYPES[d.doc_type]}  ({len(data) / 1024:.0f} KB)")
            if problem:
                problems.append(f"{fname}: {problem}")
        mrz_data = next(((d.extracted or {}).get("mrz") for d in plan["include"] if d.doc_type == "pasaporte"
                         and (d.extracted or {}).get("mrz")), None)
        ficha = [
            "DATOS PARA EL FORMULARIO (verifíquelos con el pasaporte)",
            f"Nombre: {contact.given_name}", f"Apellidos: {contact.family_names}",
            f"Fecha de nacimiento: {contact.birth_date.strftime('%d/%m/%Y') if contact.birth_date else '—'}",
            f"Nacionalidad (ficha del cliente): {contact.nationality or '—'}",
        ]
        if mrz_data:
            ficha += [f"Pasaporte nº: {mrz_data.get('document_number')}", f"Nacionalidad (pasaporte): {mrz_data.get('nationality')}",
                      f"Sexo: {mrz_data.get('sex')}", f"Caducidad del pasaporte: {mrz_data.get('expiry_date')}"]
        ficha += ["", f"Trámite: {proc.name}", f"Modelo: {proc.data.get('ex_form')}", f"Tasa: {proc.data.get('fee')}",
                  f"Provincia: {ic.province or '—'}", f"Fuente oficial: {proc.data.get('source_url')}"]
        z.writestr("00_DATOS_FORMULARIO.txt", "\n".join(ficha))
        if problems:
            index += ["", "ATENCIÓN — resolver antes de presentar:"] + [f"- {x}" for x in problems]
        z.writestr("00_INDICE.txt", "\n".join(index))
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.package", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, reason="forzado con problemas" if plan["blocking"] else None,
                 after={"archivos": len(plan["include"]), "problemas": len(problems)}, ip=ctx.ip, request_id=ctx.request_id)
    if ic.stage == "preparacion":
        pass  # la fase la cambia una persona; el paquete no presenta nada
    db.commit()
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="mercurio_{cf.code}.zip"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ bandeja
@router.get("/inbox")
def inbox(stage: str | None = None, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    scope = load_case_scope(db, p)
    q = (select(CaseFile, ImmigCase).join(ImmigCase, ImmigCase.case_id == CaseFile.id)
         .where(case_visibility_filter(p, scope, full_only=True)))
    if stage:
        q = q.where(ImmigCase.stage == stage)
    rows = db.execute(q.order_by(ImmigCase.stage_changed_at).limit(300)).all()
    ids = [cf.id for cf, _ in rows]
    pend = dict(db.execute(select(ImmigDocument.case_id, func.count()).where(
        ImmigDocument.case_id.in_(ids or [uuid.uuid4()]), ImmigDocument.status == "pendiente_revision")
        .group_by(ImmigDocument.case_id)).all())
    today = date.today()
    expiring = dict(db.execute(select(ImmigDocument.case_id, func.min(ImmigDocument.expires_on)).where(
        ImmigDocument.case_id.in_(ids or [uuid.uuid4()]), ImmigDocument.status.in_(("valido", "pendiente_revision")),
        ImmigDocument.expires_on.is_not(None)).group_by(ImmigDocument.case_id)).all())
    counts = dict(db.execute(select(ImmigCase.stage, func.count()).join(CaseFile, CaseFile.id == ImmigCase.case_id)
                             .where(case_visibility_filter(p, scope, full_only=True)).group_by(ImmigCase.stage)).all())
    out = []
    for cf, ic in rows:
        c = db.get(Contact, cf.contact_id)
        exp = expiring.get(cf.id)
        out.append({"case_id": str(cf.id), "code": cf.code, "client": f"{c.given_name} {c.family_names}",
                    "procedure": db.get(ImmigProcedure, ic.procedure_id).name, "stage": ic.stage,
                    "stage_label": STAGES[ic.stage], "days_in_stage": (_now() - ic.stage_changed_at).days,
                    "days_inactive": (_now() - cf.last_activity_at).days, "pending_review": pend.get(cf.id, 0),
                    "first_expiry": exp.isoformat() if exp else None,
                    "expiry_alert": bool(exp and exp < today + timedelta(days=PASSPORT_WARN_DAYS))})
    return {"stages": STAGES, "counts": counts, "cases": out}
