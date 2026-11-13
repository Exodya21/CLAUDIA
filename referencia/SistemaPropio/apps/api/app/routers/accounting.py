"""Contabilidad F5.4 (DR-CON-1, 4, 5, 7, 8): proveedores, facturas recibidas, tesorería con remesas de doble
autorización y cierre provisional del mes con cuadro de mando. Todo por entidad, auditado y sin borrar.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import agents, audit
from ..accounting import close as closing
from ..accounting import treasury
from ..accounting.invoices import (
    CATEGORIES,
    normalize_iban,
    normalize_tax_id,
    read_invoice,
    score,
    valid_iban,
    valid_tax_id,
)
from ..config import get_settings
from ..db import get_db
from ..errors import api_error
from ..models import Branch, Organization, UserAccount
from ..models_accounting import (
    MonthClose,
    PaymentBatch,
    PaymentBatchApproval,
    PaymentBatchItem,
    Supplier,
    SupplierInvoice,
)
from ..models_agents import AgentProposal
from ..models_bank import BankAccount
from ..security.auth import Principal, get_principal
from ..services import receipts, textcrypt, vault
from .common import req_ctx

router = APIRouter(prefix="/accounting", tags=["contabilidad"])
MAX_FILE = 15 * 1024 * 1024
ACTIVITY = Literal["laboral", "extranjeria", "compartida"]


def _now() -> datetime:
    return datetime.now(UTC)


def _uname(db: Session, uid) -> str | None:
    return db.get(UserAccount, uid).full_name if uid else None


def _deny(p: Principal, request: Request, action: str, rtype: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type=rtype, resource_id=rid, organization_id=org,
                             outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _need(p: Principal, request: Request, org, perm: str, rtype: str = "organization", rid=None) -> None:
    if org not in p.org_ids():
        raise api_error(404, "no_encontrado", "No encontrado.")
    if not p.has(org, perm):
        _deny(p, request, perm, rtype, rid if rid is not None else org, org, f"sin {perm}")
        raise api_error(403, "prohibido", "Su perfil no tiene permiso para esta operación de Contabilidad.")


def _close_props(db: Session, ref_type: str, ref_id, user_id, why: str) -> None:
    for x in db.execute(select(AgentProposal).where(AgentProposal.ref_type == ref_type, AgentProposal.ref_id == ref_id,
                                                    AgentProposal.status == "pendiente")).scalars():
        x.status, x.decided_by, x.decided_at, x.decision_note = "caducada", user_id, _now(), why[:500]


# ------------------------------------------------------------------ proveedores
def _supplier_out(db: Session, s: Supplier) -> dict:
    b = db.get(Branch, s.branch_id) if s.branch_id else None
    pending = db.execute(select(func.coalesce(func.sum(SupplierInvoice.total_cents), 0)).where(
        SupplierInvoice.supplier_id == s.id, SupplierInvoice.status.in_(("recibida", "validada", "programada")))).scalar_one()
    return {"id": str(s.id), "organization_id": str(s.organization_id), "name": s.name, "tax_id": s.tax_id,
            "iban_masked": f"•••• {s.iban_last4}" if s.iban_last4 else None, "email": s.email, "category": s.category,
            "category_label": CATEGORIES.get(s.category, s.category), "activity": s.activity,
            "branch_id": str(s.branch_id) if s.branch_id else None, "branch": b.name if b else None,
            "payment_terms_days": s.payment_terms_days, "recurring": s.recurring, "active": s.active,
            "pending_cents": int(pending), "version": s.version}


class SupplierIn(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    tax_id: str = Field(min_length=8, max_length=20)
    iban: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    category: str = Field(max_length=30)
    activity: ACTIVITY = "compartida"
    branch_id: uuid.UUID | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=180)
    recurring: bool = False


def _check_supplier(db: Session, org, body) -> None:
    errs = []
    if body.category not in CATEGORIES:
        errs.append({"field": "category", "message": "Categoría no válida"})
    if getattr(body, "tax_id", None) is not None and not valid_tax_id(body.tax_id):
        errs.append({"field": "tax_id", "message": "CIF/NIF con dígito de control incorrecto"})
    if getattr(body, "iban", None) and not valid_iban(body.iban):
        errs.append({"field": "iban", "message": "IBAN no válido (dígitos de control)"})
    if getattr(body, "branch_id", None):
        b = db.get(Branch, body.branch_id)
        if b is None or b.organization_id != org:
            errs.append({"field": "branch_id", "message": "Oficina no válida"})
    if errs:
        raise api_error(422, "validacion", "Revise los datos del proveedor.", errs)


@router.get("/suppliers")
def list_suppliers(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "treasury.read")
    return [_supplier_out(db, s) for s in db.execute(select(Supplier).where(Supplier.organization_id == organization_id)
                                                      .order_by(Supplier.name)).scalars()]


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    _need(p, request, body.organization_id, "supplier.manage")
    _check_supplier(db, body.organization_id, body)
    tax = normalize_tax_id(body.tax_id)
    if db.execute(select(Supplier.id).where(Supplier.organization_id == body.organization_id, Supplier.tax_id == tax)).first():
        raise api_error(409, "conflicto", "Ya existe un proveedor con ese CIF/NIF.")
    iban = normalize_iban(body.iban) if body.iban else None
    s = Supplier(organization_id=body.organization_id, name=body.name.strip(), tax_id=tax,
                 iban_enc=textcrypt.enc(iban) if iban else None, iban_last4=iban[-4:] if iban else None,
                 email=(body.email or "").strip() or None, category=body.category, activity=body.activity,
                 branch_id=body.branch_id, payment_terms_days=body.payment_terms_days, recurring=body.recurring,
                 created_by=p.id)
    db.add(s)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="supplier.create", resource_type="supplier", resource_id=s.id,
                 organization_id=s.organization_id, after={"nombre": s.name, "cif": s.tax_id,
                                                           "iban": f"•••• {s.iban_last4}" if s.iban_last4 else None},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _supplier_out(db, s)


class SupplierPatch(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=300)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    iban: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=30)
    activity: ACTIVITY | None = None
    branch_id: uuid.UUID | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=180)
    recurring: bool | None = None
    active: bool | None = None


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: uuid.UUID, body: SupplierPatch, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    s = db.get(Supplier, supplier_id)
    if s is None or s.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Proveedor no encontrado.")
    _need(p, request, s.organization_id, "supplier.manage", "supplier", s.id)
    if s.version != body.version:
        raise api_error(409, "conflicto_version", "El proveedor ha cambiado. Recargue.")
    if body.category is not None or body.iban or body.branch_id:
        _check_supplier(db, s.organization_id, type("B", (), {"category": body.category or s.category, "iban": body.iban,
                                                                "branch_id": body.branch_id})())
    before, after = {}, {}
    for k in ("name", "email", "category", "activity", "branch_id", "payment_terms_days", "recurring", "active"):
        v = getattr(body, k)
        if v is not None and getattr(s, k) != v:
            before[k], after[k] = str(getattr(s, k)), str(v)
            setattr(s, k, v)
    if body.iban:
        iban = normalize_iban(body.iban)
        before["iban"], after["iban"] = f"•••• {s.iban_last4}" if s.iban_last4 else None, f"•••• {iban[-4:]}"
        s.iban_enc, s.iban_last4 = textcrypt.enc(iban), iban[-4:]
    if not after:
        raise api_error(422, "validacion", "No ha cambiado nada.")
    s.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="supplier.update", resource_type="supplier", resource_id=s.id,
                 organization_id=s.organization_id, reason=body.reason, before=before, after=after,
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _supplier_out(db, s)


class IbanIn(BaseModel):
    iban: str = Field(max_length=40)
    reason: str = Field(min_length=5, max_length=300)


@router.post("/accounts/{account_id}/iban")
def set_account_iban(account_id: uuid.UUID, body: IbanIn, request: Request, p: Principal = Depends(get_principal),
                     db: Session = Depends(get_db)) -> dict:
    """IBAN completo de una cuenta propia (cifrado): necesario para generar el fichero de la remesa."""
    a = db.get(BankAccount, account_id)
    if a is None or a.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cuenta no encontrada.")
    _need(p, request, a.organization_id, "bank.accounts.manage", "bank_account", a.id)
    iban = normalize_iban(body.iban)
    if not valid_iban(iban):
        raise api_error(422, "validacion", "IBAN no válido (dígitos de control).", [{"field": "iban", "message": "No válido"}])
    if iban[-4:] != a.iban_last4:
        raise api_error(422, "validacion", f"El IBAN no termina en {a.iban_last4}, como la cuenta «{a.name}».")
    a.iban_enc = textcrypt.enc(iban)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="bank.account.iban", resource_type="bank_account", resource_id=a.id,
                 organization_id=a.organization_id, reason=body.reason, after={"iban": f"•••• {iban[-4:]}"},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"id": str(a.id), "has_iban": True}


# ------------------------------------------------------------------ facturas recibidas
def _invoice_out(db: Session, x: SupplierInvoice) -> dict:
    s = db.get(Supplier, x.supplier_id)
    b = db.get(Branch, x.branch_id) if x.branch_id else None
    batch = db.execute(select(PaymentBatch).join(PaymentBatchItem, PaymentBatchItem.batch_id == PaymentBatch.id)
                       .where(PaymentBatchItem.invoice_id == x.id, PaymentBatch.status.in_(("propuesta", "autorizada", "enviada")))
                       ).scalars().first()
    today = date.today()
    return {"id": str(x.id), "organization_id": str(x.organization_id), "supplier_id": str(s.id), "supplier": s.name,
            "supplier_tax_id": s.tax_id, "number": x.number, "issue_date": x.issue_date.isoformat(),
            "operation_date": x.operation_date.isoformat() if x.operation_date else None,
            "due_date": x.due_date.isoformat() if x.due_date else None, "base_cents": x.base_cents, "vat_cents": x.vat_cents,
            "withholding_cents": x.withholding_cents, "total_cents": x.total_cents, "currency": x.currency,
            "category": x.category, "category_label": CATEGORIES.get(x.category, x.category), "activity": x.activity,
            "branch_id": str(x.branch_id) if x.branch_id else None, "branch": b.name if b else None,
            "description": x.description, "status": x.status, "file_name": x.file_name, "extracted": x.extracted,
            "registered_by": _uname(db, x.registered_by), "registered_at": x.registered_at.isoformat(),
            "validated_by": _uname(db, x.validated_by), "rejected_reason": x.rejected_reason,
            "paid_at": x.paid_at.isoformat() if x.paid_at else None, "version": x.version,
            "overdue": x.status in ("validada", "programada") and x.due_date is not None and x.due_date < today,
            "batch": {"id": str(batch.id), "code": batch.code, "status": batch.status} if batch else None}


@router.post("/invoices/read")
async def read_upload(request: Request, organization_id: uuid.UUID = Form(...), file: UploadFile = File(...),
                      p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Lee una factura y PROPONE sus datos (no guarda nada): proveedor por CIF, importes y posibles duplicados."""
    _need(p, request, organization_id, "invoice.register")
    data = await file.read(MAX_FILE + 1)
    try:
        mime = vault.sniff(data)
    except vault.VaultError as exc:
        raise api_error(422, "validacion", exc.message) from exc
    ex = receipts.extractor()
    org = db.get(Organization, organization_id)
    own = {x.strip() for x in get_settings().own_tax_ids.split(",") if x.strip()}
    if ex is None:
        proposal = {"confianza": "baja", "aviso": "La lectura automática no está instalada en este servidor."}
    else:
        try:
            text = ex.text(data, mime)
            proposal = read_invoice(text, set(own), org.name)
            if mime == "application/pdf" and not proposal.get("cuadra") and hasattr(ex, "ocr_pdf"):
                second = read_invoice(ex.ocr_pdf(data), set(own), org.name)  # escaneado con capa de texto mala
                if score(second) > score(proposal):
                    proposal = second | {"origen": "ocr"}
        except (OSError, subprocess.SubprocessError):
            proposal = {"confianza": "baja", "aviso": "No se ha podido leer el archivo."}
    sup = None
    for cif in proposal.get("cif_candidatos") or ([proposal["cif"]] if proposal.get("cif") else []):
        sup = db.execute(select(Supplier).where(Supplier.organization_id == organization_id,
                                                Supplier.tax_id == cif)).scalar_one_or_none()
        if sup is not None:  # si uno de los CIF de la factura es de un proveedor ya dado de alta, es ese
            proposal["cif"] = cif
            break
    sha = hashlib.sha256(data).hexdigest()
    dup = db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id,
                                                   SupplierInvoice.file_sha256 == sha)).scalars().first()
    proposal.pop("iban", None) if sup and sup.iban_last4 else None
    return {"proposal": proposal, "supplier": _supplier_out(db, sup) if sup else None,
            "duplicate_file": _invoice_out(db, dup) if dup else None}


class InvoiceData(BaseModel):
    organization_id: uuid.UUID
    supplier_id: uuid.UUID
    number: str = Field(min_length=1, max_length=40)
    issue_date: date
    operation_date: date | None = None
    due_date: date | None = None
    base_cents: int = Field(ge=-100_000_000_00, le=100_000_000_00)
    vat_cents: int = Field(default=0, ge=-100_000_000_00, le=100_000_000_00)
    withholding_cents: int = Field(default=0, ge=0, le=100_000_000_00)
    total_cents: int = Field(ge=-100_000_000_00, le=100_000_000_00)
    category: str = Field(max_length=30)
    activity: ACTIVITY
    branch_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    validate_now: bool = False
    duplicate_reason: str | None = Field(default=None, max_length=300)


@router.post("/invoices", status_code=201)
async def register_invoice(request: Request, background: BackgroundTasks, data: str = Form(...),
                           file: UploadFile = File(...), p: Principal = Depends(get_principal),
                           db: Session = Depends(get_db)) -> dict:
    try:
        body = InvoiceData.model_validate(json.loads(data))
    except (ValueError, ValidationError) as exc:
        raise api_error(422, "validacion", "Datos de la factura no válidos.",
                        [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in
                         (exc.errors() if isinstance(exc, ValidationError) else [{"loc": ["data"], "msg": str(exc)}])]) from exc
    org = body.organization_id
    _need(p, request, org, "invoice.register")
    if body.validate_now and not p.has(org, "invoice.validate"):
        raise api_error(403, "prohibido", "Su perfil registra facturas pero no las valida.")
    s = db.get(Supplier, body.supplier_id)
    if s is None or s.organization_id != org:
        raise api_error(422, "validacion", "Proveedor no válido.", [{"field": "supplier_id", "message": "No válido"}])
    errs = []
    if body.base_cents + body.vat_cents - body.withholding_cents != body.total_cents:
        errs.append({"field": "total_cents", "message": "Base + IVA − retención no coincide con el total"})
    if body.category not in CATEGORIES:
        errs.append({"field": "category", "message": "Categoría no válida"})
    if body.due_date and body.due_date < body.issue_date:
        errs.append({"field": "due_date", "message": "El vencimiento no puede ser anterior a la factura"})
    if body.issue_date > date.today():
        errs.append({"field": "issue_date", "message": "Fecha futura"})
    if body.branch_id:
        b = db.get(Branch, body.branch_id)
        if b is None or b.organization_id != org:
            errs.append({"field": "branch_id", "message": "Oficina no válida"})
    if errs:
        raise api_error(422, "validacion", "Revise los datos de la factura.", errs)
    raw = await file.read(MAX_FILE + 1)
    try:
        mime = vault.sniff(raw)
    except vault.VaultError as exc:
        raise api_error(422, "validacion", exc.message) from exc
    sha = hashlib.sha256(raw).hexdigest()
    if db.execute(select(SupplierInvoice.id).where(SupplierInvoice.organization_id == org,
                                                   SupplierInvoice.file_sha256 == sha)).first():
        raise api_error(409, "conflicto", "Ese archivo ya está registrado como factura.")
    num = body.number.strip().upper()
    if db.execute(select(SupplierInvoice.id).where(SupplierInvoice.supplier_id == s.id, SupplierInvoice.number == num)).first():
        raise api_error(409, "conflicto", f"La factura {num} de {s.name} ya está registrada.")
    similar = list(db.execute(select(SupplierInvoice).where(
        SupplierInvoice.supplier_id == s.id, SupplierInvoice.total_cents == body.total_cents,
        SupplierInvoice.issue_date == body.issue_date, SupplierInvoice.status != "rechazada")).scalars())
    reason = (body.duplicate_reason or "").strip()
    if similar and len(reason) < 10:
        raise api_error(409, "posible_duplicado", "Hay una factura de este proveedor con el mismo importe y fecha. "
                        "Si es otra distinta, explique por qué.", [_invoice_out(db, x) for x in similar])
    ex = receipts.extractor()
    text = ex.text(raw, mime) if ex else ""
    extracted = read_invoice(text) if text else None
    path, _ = vault.store(raw)
    x = SupplierInvoice(organization_id=org, supplier_id=s.id, number=num, issue_date=body.issue_date,
                        operation_date=body.operation_date, due_date=body.due_date or (
                            date.fromordinal(body.issue_date.toordinal() + s.payment_terms_days) if s.payment_terms_days is not None else None),
                        base_cents=body.base_cents, vat_cents=body.vat_cents, withholding_cents=body.withholding_cents,
                        total_cents=body.total_cents, currency=db.get(Organization, org).currency, category=body.category,
                        activity=body.activity, branch_id=body.branch_id, description=(body.description or "").strip() or None,
                        file_name=(file.filename or "factura")[:200], file_mime=mime, file_sha256=sha, file_path=path,
                        extracted=extracted, registered_by=p.id)
    if body.validate_now:
        x.status, x.validated_by, x.validated_at = "validada", p.id, _now()
    db.add(x)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="invoice.register", resource_type="supplier_invoice", resource_id=x.id,
                 organization_id=org, reason=reason if similar else None,
                 after={"proveedor": s.name, "numero": num, "total": x.total_cents, "estado": x.status,
                        "parecidas": [str(y.id) for y in similar]}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    background.add_task(agents.dispatch_events)
    return _invoice_out(db, x)


@router.get("/invoices")
def list_invoices(request: Request, organization_id: uuid.UUID,
                  status: Literal["recibida", "validada", "programada", "pagada", "rechazada", "pendientes", "todas"] = "pendientes",
                  supplier_id: uuid.UUID | None = None, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "treasury.read")
    q = select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id)
    if status == "pendientes":
        q = q.where(SupplierInvoice.status.in_(("recibida", "validada", "programada")))
    elif status != "todas":
        q = q.where(SupplierInvoice.status == status)
    if supplier_id:
        q = q.where(SupplierInvoice.supplier_id == supplier_id)
    rows = db.execute(q.order_by(SupplierInvoice.due_date.asc().nulls_last(), SupplierInvoice.issue_date.desc()).limit(500)).scalars()
    return [_invoice_out(db, x) for x in rows]


def _invoice(db: Session, p: Principal, invoice_id: uuid.UUID, request: Request, perm: str) -> SupplierInvoice:
    x = db.get(SupplierInvoice, invoice_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Factura no encontrada.")
    _need(p, request, x.organization_id, perm, "supplier_invoice", x.id)
    return x


@router.get("/invoices/{invoice_id}/file")
def invoice_file(invoice_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> Response:
    x = _invoice(db, p, invoice_id, request, "treasury.read")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="invoice.download", resource_type="supplier_invoice", resource_id=x.id,
                             organization_id=x.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    safe = "".join(ch for ch in x.file_name if ch.isalnum() or ch in "._-") or "factura"
    return Response(vault.load(x.file_path), media_type=x.file_mime, headers={"Content-Disposition": f'inline; filename="{safe}"'})


class InvoiceDecision(BaseModel):
    version: int = Field(ge=1)
    approve: bool
    reason: str | None = Field(default=None, max_length=300)
    category: str | None = Field(default=None, max_length=30)
    activity: ACTIVITY | None = None
    branch_id: uuid.UUID | None = None
    due_date: date | None = None


@router.post("/invoices/{invoice_id}/decide")
def decide_invoice(invoice_id: uuid.UUID, body: InvoiceDecision, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    x = _invoice(db, p, invoice_id, request, "invoice.validate")
    db.execute(select(SupplierInvoice).where(SupplierInvoice.id == x.id).with_for_update())
    db.refresh(x)
    if x.version != body.version:
        raise api_error(409, "conflicto_version", "La factura ha cambiado. Recargue.")
    if x.status != "recibida":
        raise api_error(409, "conflicto", f"La factura ya está {x.status}.")
    before = {"estado": x.status}
    if body.approve:
        if body.category:
            if body.category not in CATEGORIES:
                raise api_error(422, "validacion", "Categoría no válida.")
            x.category = body.category
        if body.activity:
            x.activity = body.activity
        if body.branch_id:
            b = db.get(Branch, body.branch_id)
            if b is None or b.organization_id != x.organization_id:
                raise api_error(422, "validacion", "Oficina no válida.")
            x.branch_id = body.branch_id
        if body.due_date:
            x.due_date = body.due_date
        x.status, x.validated_by, x.validated_at = "validada", p.id, _now()
    else:
        if len((body.reason or "").strip()) < 5:
            raise api_error(422, "validacion", "Indique por qué se rechaza (p. ej. duplicada o no es del despacho).")
        x.status, x.rejected_reason = "rechazada", body.reason.strip()
    x.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="invoice.validate" if body.approve else "invoice.reject",
                 resource_type="supplier_invoice", resource_id=x.id, organization_id=x.organization_id,
                 reason=body.reason, before=before, after={"estado": x.status, "actividad": x.activity},
                 ip=ctx.ip, request_id=ctx.request_id)
    _close_props(db, "supplier_invoice", x.id, p.id, "Factura revisada.")
    db.commit()
    return _invoice_out(db, x)


# ------------------------------------------------------------------ tesorería y remesas (DR-CON-7)
@router.get("/treasury")
def treasury_view(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    _need(p, request, organization_id, "treasury.read")
    out = treasury.forecast(db, organization_id)
    out["can_propose"] = p.has(organization_id, "treasury.propose")
    out["can_approve"] = p.has(organization_id, "treasury.approve")
    out["can_manage_accounts"] = p.has(organization_id, "bank.accounts.manage")
    return out


def _batch_out(db: Session, b: PaymentBatch, p: Principal | None = None) -> dict:
    acc = db.get(BankAccount, b.account_id)
    items = list(db.execute(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == b.id)).scalars())
    sigs = list(db.execute(select(PaymentBatchApproval).where(PaymentBatchApproval.batch_id == b.id)
                           .order_by(PaymentBatchApproval.at)).scalars())
    invs = [db.get(SupplierInvoice, it.invoice_id) for it in items]
    d = {"id": str(b.id), "code": b.code, "organization_id": str(b.organization_id), "account": acc.name,
         "account_id": str(acc.id), "account_has_iban": bool(acc.iban_enc), "execution_date": b.execution_date.isoformat(),
         "total_cents": b.total_cents, "currency": b.currency, "status": b.status,
         "proposed_by": _uname(db, b.proposed_by), "proposed_at": b.proposed_at.isoformat(), "note": b.note,
         "sent_by": _uname(db, b.sent_by), "sent_at": b.sent_at.isoformat() if b.sent_at else None,
         "closed_reason": b.closed_reason, "version": b.version, "sepa_sha256": b.sepa_sha256,
         "items": [{"invoice_id": str(i.id), "number": i.number, "supplier": db.get(Supplier, i.supplier_id).name,
                    "amount_cents": it.amount_cents, "due_date": i.due_date.isoformat() if i.due_date else None,
                    "status": i.status} for it, i in zip(items, invs, strict=True)],
         "paid": sum(1 for i in invs if i.status == "pagada"),
         "signatures": [{"by": _uname(db, s.approver_id), "decision": s.decision, "note": s.note, "at": s.at.isoformat()}
                        for s in sigs],
         "signatures_needed": max(0, 2 - sum(1 for s in sigs if s.decision == "autoriza"))}
    if p is not None:
        signed = any(s.approver_id == p.id for s in sigs)
        d["can_sign"] = (b.status == "propuesta" and p.has(b.organization_id, "treasury.approve")
                         and b.proposed_by != p.id and not signed)
        d["can_download"] = b.status in ("autorizada", "enviada") and p.has(b.organization_id, "treasury.propose")
        d["can_mark_sent"] = b.status == "autorizada" and p.has(b.organization_id, "treasury.propose")
        d["can_cancel"] = b.status in ("propuesta", "autorizada") and (p.has(b.organization_id, "treasury.propose")
                                                                        or p.has(b.organization_id, "treasury.approve"))
    return d


class BatchIn(BaseModel):
    organization_id: uuid.UUID
    account_id: uuid.UUID
    execution_date: date
    invoice_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)


@router.post("/batches", status_code=201)
def propose_batch(body: BatchIn, request: Request, background: BackgroundTasks, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    org = body.organization_id
    _need(p, request, org, "treasury.propose")
    acc = db.get(BankAccount, body.account_id)
    if acc is None or acc.organization_id != org or not acc.active:
        raise api_error(422, "validacion", "Cuenta de cargo no válida.")
    if body.execution_date < date.today():
        raise api_error(422, "validacion", "La fecha de ejecución no puede ser pasada.")
    if len(set(body.invoice_ids)) != len(body.invoice_ids):
        raise api_error(422, "validacion", "Hay facturas repetidas en la remesa.")
    invs = []
    for iid in body.invoice_ids:
        inv = db.execute(select(SupplierInvoice).where(SupplierInvoice.id == iid).with_for_update()).scalar_one_or_none()
        if inv is None or inv.organization_id != org:
            raise api_error(422, "validacion", "Factura no válida.")
        if inv.status != "validada":
            raise api_error(409, "conflicto", f"La factura {inv.number} está {inv.status}: solo se pagan facturas validadas.")
        if inv.total_cents <= 0:
            raise api_error(422, "validacion", f"La factura {inv.number} no tiene importe a pagar (abono).")
        busy = db.execute(select(PaymentBatch.code).join(PaymentBatchItem, PaymentBatchItem.batch_id == PaymentBatch.id)
                          .where(PaymentBatchItem.invoice_id == inv.id, PaymentBatch.status.in_(("propuesta", "autorizada", "enviada")))).first()
        if busy:
            raise api_error(409, "conflicto", f"La factura {inv.number} ya está en la remesa {busy[0]}.")
        sup = db.get(Supplier, inv.supplier_id)
        if not sup.iban_enc:
            raise api_error(422, "validacion", f"El proveedor {sup.name} no tiene IBAN: no se le puede pagar por remesa.")
        invs.append(inv)
        _close_props(db, "supplier_invoice", inv.id, p.id, "Incluida en una remesa.")
    total = sum(i.total_cents for i in invs)
    b = PaymentBatch(organization_id=org, code=treasury.next_batch_code(db, body.execution_date.year), account_id=acc.id,
                     execution_date=body.execution_date, total_cents=total, currency=acc.currency, proposed_by=p.id,
                     note=(body.note or "").strip() or None)
    db.add(b)
    db.flush()
    for i in invs:
        db.add(PaymentBatchItem(organization_id=org, batch_id=b.id, invoice_id=i.id, amount_cents=i.total_cents))
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="treasury.batch.propose", resource_type="payment_batch", resource_id=b.id,
                 organization_id=org, after={"codigo": b.code, "facturas": len(invs), "total": total,
                                             "cuenta": acc.name, "fecha": b.execution_date.isoformat()},
                 ip=ctx.ip, request_id=ctx.request_id)
    agents.emit(db, org, "treasury.batch.proposed", "payment_batch", b.id)
    db.commit()
    background.add_task(agents.dispatch_events)
    return _batch_out(db, b, p)


@router.get("/batches")
def list_batches(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "treasury.read")
    return [_batch_out(db, b, p) for b in db.execute(select(PaymentBatch).where(PaymentBatch.organization_id == organization_id)
                                                     .order_by(PaymentBatch.proposed_at.desc()).limit(100)).scalars()]


def _batch(db: Session, p: Principal, batch_id: uuid.UUID, request: Request, perm: str) -> PaymentBatch:
    b = db.get(PaymentBatch, batch_id)
    if b is None or b.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Remesa no encontrada.")
    _need(p, request, b.organization_id, perm, "payment_batch", b.id)
    db.execute(select(PaymentBatch).where(PaymentBatch.id == b.id).with_for_update())
    db.refresh(b)
    return b


class SignIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=300)


def sign_batch(db: Session, b: PaymentBatch, p: Principal, approve: bool, note: str | None, ctx) -> PaymentBatch:
    """Una firma de la remesa. Con dos «autoriza» de personas distintas (y distintas de quien propone) queda
    autorizada y sus facturas pasan a programadas. Un «rechaza» la cierra."""
    if b.status != "propuesta":
        raise ValueError(f"La remesa ya está {b.status}.")
    if b.proposed_by == p.id:
        raise PermissionError("Quien propone la remesa no puede autorizarla.")
    if not p.has(b.organization_id, "treasury.approve"):
        raise PermissionError("Su perfil no autoriza remesas.")
    if db.execute(select(PaymentBatchApproval.id).where(PaymentBatchApproval.batch_id == b.id,
                                                        PaymentBatchApproval.approver_id == p.id)).first():
        raise ValueError("Ya ha firmado esta remesa: hace falta otra persona.")
    note = (note or "").strip()
    if not approve and len(note) < 5:
        raise ValueError("Indique por qué no autoriza la remesa.")
    db.add(PaymentBatchApproval(organization_id=b.organization_id, batch_id=b.id, approver_id=p.id,
                                decision="autoriza" if approve else "rechaza", note=note or None))
    db.flush()
    yes = db.execute(select(func.count()).select_from(PaymentBatchApproval).where(
        PaymentBatchApproval.batch_id == b.id, PaymentBatchApproval.decision == "autoriza")).scalar_one()
    before = b.status
    if not approve:
        b.status, b.closed_reason = "rechazada", note
    elif yes >= 2:
        b.status = "autorizada"
        for it in db.execute(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == b.id)).scalars():
            inv = db.get(SupplierInvoice, it.invoice_id)
            if inv.status == "validada":
                inv.status = "programada"
                inv.version += 1
    b.version += 1
    audit.record(db, actor_id=p.id, action="treasury.batch.sign", resource_type="payment_batch", resource_id=b.id,
                 organization_id=b.organization_id, reason=note or None, before={"estado": before},
                 after={"estado": b.status, "firma": "autoriza" if approve else "rechaza", "firmas": yes},
                 ip=ctx.ip, request_id=ctx.request_id)
    if b.status != "propuesta":
        _close_props(db, "payment_batch", b.id, p.id, f"Remesa {b.status}.")
    return b


@router.post("/batches/{batch_id}/sign")
def sign(batch_id: uuid.UUID, body: SignIn, request: Request, p: Principal = Depends(get_principal),
         db: Session = Depends(get_db)) -> dict:
    b = _batch(db, p, batch_id, request, "treasury.approve")
    try:
        sign_batch(db, b, p, body.approve, body.note, req_ctx(request))
    except PermissionError as exc:
        db.rollback()
        _deny(p, request, "treasury.batch.sign", "payment_batch", batch_id, b.organization_id, str(exc))
        raise api_error(403, "prohibido", str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise api_error(409 if "ya" in str(exc).lower() else 422, "conflicto" if "ya" in str(exc).lower() else "validacion",
                        str(exc)) from exc
    db.commit()
    return _batch_out(db, b, p)


@router.get("/batches/{batch_id}/sepa.xml")
def batch_file(batch_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> Response:
    b = _batch(db, p, batch_id, request, "treasury.propose")
    if b.status not in ("autorizada", "enviada"):
        raise api_error(409, "conflicto", "El fichero solo se genera con la remesa autorizada por dos personas.")
    try:
        data = treasury.sepa_xml(db, b)
    except ValueError as exc:
        raise api_error(422, "validacion", str(exc)) from exc
    digest = treasury.sha(data)
    if b.sepa_sha256 is None:
        b.sepa_sha256 = digest
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="treasury.batch.download", resource_type="payment_batch", resource_id=b.id,
                 organization_id=b.organization_id, after={"huella": digest}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return Response(data, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{b.code}.xml"'})


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


@router.post("/batches/{batch_id}/sent")
def mark_sent(batch_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Una persona confirma que ha subido el fichero a la banca electrónica (el sistema no lo envía)."""
    b = _batch(db, p, batch_id, request, "treasury.propose")
    if b.status != "autorizada":
        raise api_error(409, "conflicto", f"La remesa está {b.status}.")
    if b.sepa_sha256 is None:
        raise api_error(409, "conflicto", "Descargue primero el fichero de la remesa.")
    b.status, b.sent_by, b.sent_at = "enviada", p.id, _now()
    b.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="treasury.batch.sent", resource_type="payment_batch", resource_id=b.id,
                 organization_id=b.organization_id, after={"estado": "enviada"}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _batch_out(db, b, p)


@router.post("/batches/{batch_id}/cancel")
def cancel_batch(batch_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    b = db.get(PaymentBatch, batch_id)
    if b is None or b.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Remesa no encontrada.")
    if not (p.has(b.organization_id, "treasury.propose") or p.has(b.organization_id, "treasury.approve")):
        _deny(p, request, "treasury.batch.cancel", "payment_batch", b.id, b.organization_id, "sin permiso de tesorería")
        raise api_error(403, "prohibido", "Sin permiso.")
    if b.status not in ("propuesta", "autorizada"):
        raise api_error(409, "conflicto", f"La remesa está {b.status}: ya no se puede anular aquí.")
    before = b.status
    b.status, b.closed_reason = "anulada", body.reason
    b.version += 1
    for it in db.execute(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == b.id)).scalars():
        inv = db.get(SupplierInvoice, it.invoice_id)
        if inv.status == "programada":
            inv.status = "validada"
            inv.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="treasury.batch.cancel", resource_type="payment_batch", resource_id=b.id,
                 organization_id=b.organization_id, reason=body.reason, before={"estado": before},
                 after={"estado": "anulada"}, ip=ctx.ip, request_id=ctx.request_id)
    _close_props(db, "payment_batch", b.id, p.id, "Remesa anulada.")
    db.commit()
    return _batch_out(db, b, p)


# ------------------------------------------------------------------ cuadro de mando y cierre del mes (DR-CON-8)
def _month_ok(month: str) -> None:
    if len(month) != 7 or month[4] != "-" or not (month[:4].isdigit() and month[5:].isdigit()) or not 1 <= int(month[5:]) <= 12:
        raise api_error(422, "validacion", "Mes con formato AAAA-MM.")


@router.get("/dashboard")
def dashboard(request: Request, organization_id: uuid.UUID, month: str, p: Principal = Depends(get_principal),
              db: Session = Depends(get_db)) -> dict:
    _month_ok(month)
    _need(p, request, organization_id, "accounting.read")
    figures = closing.compute(db, organization_id, month)
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="accounting.dashboard", resource_type="organization",
                             resource_id=organization_id, organization_id=organization_id, after={"mes": month},
                             ip=ctx.ip, request_id=ctx.request_id)
    return closing.for_viewer(figures, p.has(organization_id, "hr.salary"))


def _close_out(db: Session, c: MonthClose, p: Principal) -> dict:
    return {"id": str(c.id), "organization_id": str(c.organization_id), "month": c.month, "revision": c.revision,
            "status": c.status, "figures": closing.for_viewer(c.figures, p.has(c.organization_id, "hr.salary")),
            "figures_sha256": c.figures_sha256, "prepared_by": _uname(db, c.prepared_by), "prepared_at": c.prepared_at.isoformat(),
            "reviewed_by": _uname(db, c.reviewed_by), "approved_by": _uname(db, c.approved_by),
            "approved_at": c.approved_at.isoformat() if c.approved_at else None, "note": c.note,
            "can_review": c.status == "borrador" and p.has(c.organization_id, "accounting.close"),
            "can_approve": c.status == "revisado" and p.has(c.organization_id, "accounting.close.approve") and c.prepared_by != p.id}


class CloseIn(BaseModel):
    organization_id: uuid.UUID
    month: str
    note: str | None = Field(default=None, max_length=1000)


def prepare_close(db: Session, org_id, month: str, user_id, note: str | None, ctx) -> MonthClose:
    last = db.execute(select(MonthClose).where(MonthClose.organization_id == org_id, MonthClose.month == month)
                      .order_by(MonthClose.revision.desc()).limit(1)).scalar_one_or_none()
    if last is not None and last.status == "aprobado":
        raise ValueError(f"El cierre de {month} ya está aprobado (revisión {last.revision}) y no se modifica.")
    first, nxt, _, _ = closing.month_bounds(month)
    if first > date.today():
        raise ValueError("No se puede cerrar un mes que no ha empezado.")
    figures = closing.compute(db, org_id, month)
    c = MonthClose(organization_id=org_id, month=month, revision=(last.revision + 1) if last else 1, status="borrador",
                   figures=figures, figures_sha256=closing.digest(figures), prepared_by=user_id, note=note)
    if last is not None and last.status in ("borrador", "revisado"):
        last.status = "sustituido"
    db.add(c)
    db.flush()
    audit.record(db, actor_id=user_id, action="accounting.close.prepare", resource_type="month_close", resource_id=c.id,
                 organization_id=org_id, after={"mes": month, "revision": c.revision, "huella": c.figures_sha256,
                                                "resultado": figures["total"]["resultado"],
                                                "fiabilidad": figures["reliability"]["level"]},
                 ip=ctx.ip, request_id=ctx.request_id)
    return c


@router.post("/closes", status_code=201)
def create_close(body: CloseIn, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    _month_ok(body.month)
    _need(p, request, body.organization_id, "accounting.close")
    try:
        c = prepare_close(db, body.organization_id, body.month, p.id, body.note, req_ctx(request))
    except ValueError as exc:
        db.rollback()
        raise api_error(409, "conflicto", str(exc)) from exc
    _close_props(db, "month_close_due", body.organization_id, p.id, f"Cierre {body.month} preparado.")
    db.commit()
    return _close_out(db, c, p)


@router.get("/closes")
def list_closes(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "accounting.read")
    return [_close_out(db, c, p) for c in db.execute(select(MonthClose).where(MonthClose.organization_id == organization_id)
                                                     .order_by(MonthClose.month.desc(), MonthClose.revision.desc()).limit(60)).scalars()]


class CloseDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.post("/closes/{close_id}/review")
def review_close(close_id: uuid.UUID, body: CloseDecision, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    c = db.get(MonthClose, close_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cierre no encontrado.")
    _need(p, request, c.organization_id, "accounting.close", "month_close", c.id)
    if c.status != "borrador":
        raise api_error(409, "conflicto", f"El cierre está {c.status}.")
    pend = c.figures.get("pending", {})
    blocking = {k: v for k, v in pend.items() if k != "accounts_sin_extracto" and v}
    if blocking and len((body.note or "").strip()) < 10:
        raise api_error(422, "validacion", "Hay pendientes en el mes: explique en la nota por qué se puede dar por revisado.",
                        [{"field": k, "message": str(v)} for k, v in blocking.items()])
    c.status, c.reviewed_by, c.reviewed_at = "revisado", p.id, _now()
    if body.note:
        c.note = ((c.note + "\n") if c.note else "") + f"Revisión: {body.note.strip()}"
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="accounting.close.review", resource_type="month_close", resource_id=c.id,
                 organization_id=c.organization_id, reason=body.note, after={"estado": c.status, "mes": c.month},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _close_out(db, c, p)


@router.post("/closes/{close_id}/approve")
def approve_close(close_id: uuid.UUID, body: CloseDecision, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    c = db.get(MonthClose, close_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cierre no encontrado.")
    _need(p, request, c.organization_id, "accounting.close.approve", "month_close", c.id)
    if c.status != "revisado":
        raise api_error(409, "conflicto", "Solo se aprueba un cierre revisado por Contabilidad.")
    if c.prepared_by == p.id:
        raise api_error(403, "prohibido", "Quien preparó el cierre no puede aprobarlo.")
    c.status, c.approved_by, c.approved_at = "aprobado", p.id, _now()
    if body.note:
        c.note = ((c.note + "\n") if c.note else "") + f"Aprobación: {body.note.strip()}"
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="accounting.close.approve", resource_type="month_close", resource_id=c.id,
                 organization_id=c.organization_id, reason=body.note,
                 after={"estado": "aprobado", "mes": c.month, "huella": c.figures_sha256}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _close_out(db, c, p)


LINE_LABELS = {"ingresos_devengados": "Ingresos devengados", "cobros": "Cobros", "gastos_proveedores": "Gastos de proveedores (base)",
               "gastos_empleados": "Gastos de empleados (sin IVA)", "coste_personal": "Coste de personal (devengado)",
               "pagos": "Pagos a proveedores", "resultado": "Resultado provisional"}


@router.get("/closes/{close_id}/export.csv")
def export_close(close_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> Response:
    c = db.get(MonthClose, close_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cierre no encontrado.")
    _need(p, request, c.organization_id, "accounting.read", "month_close", c.id)
    f = closing.for_viewer(c.figures, p.has(c.organization_id, "hr.salary"))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    acts = ["laboral", "extranjeria", "compartida", "sin_asignar"]
    w.writerow([f"Cierre provisional {c.month} · revisión {c.revision} · {c.status} · huella {c.figures_sha256[:16]}"])
    w.writerow(["Concepto", "Laboral", "Extranjería", "Compartida", "Sin asignar", "Total", "Mes anterior"])

    def eur(v):
        return "" if v is None else f"{v / 100:.2f}".replace(".", ",")
    for line, label in LINE_LABELS.items():
        w.writerow([label, *[eur(f["by_activity"][a][line]) for a in acts], eur(f["total"][line]),
                    eur(f.get("previous", {}).get("total", {}).get(line))])
    w.writerow([])
    w.writerow(["Oficina", *LINE_LABELS.values()])
    for bname, vals in f["by_branch"].items():
        w.writerow([bname, *[eur(vals[k]) for k in LINE_LABELS]])
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="accounting.close.export", resource_type="month_close", resource_id=c.id,
                             organization_id=c.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    return Response(("﻿" + buf.getvalue()).encode(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="cierre_{c.month}_r{c.revision}.csv"'})


# ------------------------------------------------------------------ rutina de trabajo (F5.4b)
from ..accounting import reports as reporting  # noqa: E402
from ..accounting import routine  # noqa: E402
from ..models_accounting import AccountingReport, RoutineItem, RoutineOwner  # noqa: E402

CADENCE_ORDER = {"diaria": 0, "semanal": 1, "quincenal": 2, "mensual": 3}


def _item_out(db: Session, x: RoutineItem, p: Principal, today: date) -> dict:
    step = routine.BY_CODE.get(x.step)
    state = x.status if x.status != "pendiente" else ("vencido" if x.due_date < today else "pendiente")
    return {"id": str(x.id), "step": x.step, "cadence": x.cadence, "title": step.title if step else x.step,
            "how": step.how if step else "", "period": x.period, "period_label": x.period_label,
            "due_date": x.due_date.isoformat(), "status": x.status, "state": state, "evidence": x.evidence,
            "owner": _uname(db, x.owner_id), "owner_id": str(x.owner_id) if x.owner_id else None,
            "done_at": x.done_at.isoformat() if x.done_at else None, "on_time": x.on_time,
            "na_reason": x.na_reason, "na_by": _uname(db, x.na_by), "task_id": str(x.task_id) if x.task_id else None,
            "can_na": x.status == "pendiente" and bool(step) and p.has(x.organization_id, step.perm)}


@router.get("/routine")
def get_routine(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    """Comprueba la rutina AHORA (crea los pasos del periodo y da por hechos los que ya lo están) y la devuelve."""
    _need(p, request, organization_id, "accounting.read")
    today = datetime.now(routine.MADRID).date()
    summary = routine.sync(db, organization_id, today)
    db.commit()
    rows = list(db.execute(select(RoutineItem).where(
        RoutineItem.organization_id == organization_id,
        (RoutineItem.status == "pendiente") | (RoutineItem.due_date >= today - timedelta(days=35))))
        .scalars())
    rows.sort(key=lambda x: (x.status != "pendiente", CADENCE_ORDER.get(x.cadence, 9), x.due_date))
    month_start = today.replace(day=1)
    return {"today": today.isoformat(), "sync": summary,
            "items": [_item_out(db, x, p, today) for x in rows],
            "compliance_month": routine.compliance(db, organization_id, month_start, today),
            "compliance_prev_month": routine.compliance(db, organization_id, (month_start - timedelta(days=1)).replace(day=1),
                                                        month_start - timedelta(days=1))}


class NaIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


@router.post("/routine/{item_id}/na")
def routine_na(item_id: uuid.UUID, body: NaIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    x = db.get(RoutineItem, item_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Paso no encontrado.")
    step = routine.BY_CODE[x.step]
    _need(p, request, x.organization_id, step.perm, "routine_item", x.id)
    if x.status != "pendiente":
        raise api_error(409, "conflicto", "Ese paso ya está cerrado.")
    routine.mark_na(db, x, p.id, body.reason.strip())
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="accounting.routine.na", resource_type="routine_item", resource_id=x.id,
                 organization_id=x.organization_id, reason=body.reason, after={"paso": x.step, "periodo": x.period},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _item_out(db, x, p, datetime.now(routine.MADRID).date())


@router.get("/routine/owners")
def routine_owners(request: Request, organization_id: uuid.UUID, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "accounting.read")
    out = []
    for s in routine.STEPS:
        owner = routine.owner_for(db, organization_id, s)
        out.append({"step": s.code, "cadence": s.cadence, "title": s.title, "how": s.how,
                    "owner_id": str(owner.id) if owner else None, "owner": owner.full_name if owner else None,
                    "candidates": [{"id": str(u.id), "name": u.full_name} for u in routine.users_with(db, organization_id, s.perm)],
                    "can_change": p.has(organization_id, "accounting.close.approve")})
    return out


class OwnerIn(BaseModel):
    organization_id: uuid.UUID
    step: str
    user_id: uuid.UUID


@router.put("/routine/owners")
def set_owner(body: OwnerIn, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    _need(p, request, body.organization_id, "accounting.close.approve")
    step = routine.BY_CODE.get(body.step)
    if step is None:
        raise api_error(422, "validacion", "Paso desconocido.")
    if body.user_id not in {u.id for u in routine.users_with(db, body.organization_id, step.perm)}:
        raise api_error(422, "validacion", "Esa persona no tiene permiso para este paso.")
    row = db.execute(select(RoutineOwner).where(RoutineOwner.organization_id == body.organization_id,
                                                RoutineOwner.step == body.step)).scalar_one_or_none()
    before = str(row.user_id) if row else None
    if row is None:
        row = RoutineOwner(organization_id=body.organization_id, step=body.step, user_id=body.user_id, updated_by=p.id)
        db.add(row)
    else:
        row.user_id, row.updated_by, row.updated_at = body.user_id, p.id, _now()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="accounting.routine.owner", resource_type="organization",
                 resource_id=body.organization_id, organization_id=body.organization_id,
                 before={"paso": body.step, "responsable": before}, after={"paso": body.step, "responsable": str(body.user_id)},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"step": body.step, "owner": _uname(db, body.user_id)}


# ------------------------------------------------------------------ informes (F5.4b)
def _report_out(db: Session, r: AccountingReport, p: Principal, full: bool = False) -> dict:
    d = {"id": str(r.id), "kind": r.kind, "label": r.label, "period_from": r.period_from.isoformat(),
         "period_to": r.period_to.isoformat(), "version": r.version, "figures_sha256": r.figures_sha256,
         "generated_at": r.generated_at.isoformat(), "generated_by": _uname(db, r.generated_by) or "Rutina automática",
         "reviewed_by": _uname(db, r.reviewed_by), "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
         "review_note": r.review_note, "resultado_cents": r.figures["total"]["resultado"],
         "cobros_cents": r.figures["total"]["cobros"], "fiabilidad": r.figures["reliability"]["level"],
         "cumplimiento_pct": r.figures.get("routine", {}).get("cumplimiento_pct"),
         "can_review": r.reviewed_by is None and p.has(r.organization_id, "accounting.close.approve")}
    if full:
        d["figures"] = closing.for_viewer(r.figures, p.has(r.organization_id, "hr.salary"))
    return d


def _report(db: Session, p: Principal, request: Request, report_id: uuid.UUID, perm: str = "accounting.read") -> AccountingReport:
    r = db.get(AccountingReport, report_id)
    if r is None or r.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Informe no encontrado.")
    _need(p, request, r.organization_id, perm, "accounting_report", r.id)
    return r


@router.get("/reports")
def list_reports(request: Request, organization_id: uuid.UUID, kind: str | None = None, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> list[dict]:
    _need(p, request, organization_id, "accounting.read")
    q = select(AccountingReport).where(AccountingReport.organization_id == organization_id)
    if kind:
        if kind not in reporting.KINDS:
            raise api_error(422, "validacion", "Tipo de informe no válido.")
        q = q.where(AccountingReport.kind == kind)
    rows = db.execute(q.order_by(AccountingReport.period_from.desc(), AccountingReport.version.desc()).limit(120)).scalars()
    return [_report_out(db, r, p) for r in rows]


class ReportIn(BaseModel):
    organization_id: uuid.UUID
    kind: Literal["semanal", "quincenal", "mensual"]
    day: date  # cualquier día del periodo


@router.post("/reports", status_code=201)
def generate_report(body: ReportIn, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Genera ahora (o vuelve a generar: versión nueva) el informe del periodo que contiene `day`."""
    _need(p, request, body.organization_id, "accounting.close")
    start, end, label = reporting.period_of(body.kind, body.day)
    if start > datetime.now(routine.MADRID).date():
        raise api_error(422, "validacion", "Ese periodo aún no ha empezado.")
    r = reporting.create(db, body.organization_id, body.kind, start, end, label, p.id, req_ctx(request))
    db.commit()
    return _report_out(db, r, p, full=True)


@router.get("/reports/{report_id}")
def get_report(report_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    r = _report(db, p, request, report_id)
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="accounting.report.read", resource_type="accounting_report", resource_id=r.id,
                             organization_id=r.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    return _report_out(db, r, p, full=True)


@router.get("/reports/{report_id}/file")
def report_file(report_id: uuid.UUID, request: Request, fmt: Literal["pdf", "csv"] = "pdf", p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> Response:
    r = _report(db, p, request, report_id)
    f = closing.for_viewer(r.figures, p.has(r.organization_id, "hr.salary"))
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="accounting.report.download", resource_type="accounting_report",
                             resource_id=r.id, organization_id=r.organization_id, after={"formato": fmt},
                             ip=ctx.ip, request_id=ctx.request_id)
    name = f"informe_{r.kind}_{r.period_from:%Y%m%d}_v{r.version}"
    if fmt == "csv":
        return Response(reporting.to_csv(r, f), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    org = db.get(Organization, r.organization_id)
    return Response(reporting.pdf(r, f, org.name), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})


def review_report(db: Session, r: AccountingReport, p, note: str | None, ctx) -> AccountingReport:
    if r.reviewed_by is not None:
        raise ValueError("El informe ya está revisado.")
    r.reviewed_by, r.reviewed_at, r.review_note = p.id, _now(), (note or None)
    audit.record(db, actor_id=p.id, action="accounting.report.review", resource_type="accounting_report", resource_id=r.id,
                 organization_id=r.organization_id, reason=note, after={"tipo": r.kind, "periodo": r.label},
                 ip=getattr(ctx, "ip", None), request_id=getattr(ctx, "request_id", None))
    _close_props(db, "accounting_report", r.id, p.id, "Informe revisado.")
    routine.evaluate(db, r.organization_id, datetime.now(routine.MADRID).date())
    return r


@router.post("/reports/{report_id}/review")
def review(report_id: uuid.UUID, body: CloseDecision, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    r = _report(db, p, request, report_id, "accounting.close.approve")
    try:
        review_report(db, r, p, (body.note or "").strip() or None, req_ctx(request))
    except ValueError as exc:
        raise api_error(409, "conflicto", str(exc)) from exc
    db.commit()
    return _report_out(db, r, p, full=True)
