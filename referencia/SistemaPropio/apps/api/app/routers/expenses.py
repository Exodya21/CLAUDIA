"""Gastos de empresa con justificante (F5.0). Requisitos: Q-4.13, Q-4.14, Q-4.5 (tarjetas), I-079 (patrón OCR).

Circuito: el empleado sube la foto o el PDF → el sistema lee y PROPONE fecha, proveedor, NIF, importe e IVA →
el empleado revisa y envía → Contabilidad aprueba, devuelve (con motivo) o anula → conciliación con la caja
(automática si fue en efectivo), con el extracto de la tarjeta de empresa o con la referencia del reembolso.
Nadie aprueba sus propios gastos. Ningún justificante sale del servidor. El IVA es un dato leído del justificante,
no un criterio de deducibilidad (lo decide Contabilidad).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, Organization, UserAccount
from ..models_economy import CardTransaction, CashMovement, CompanyCard, Expense, ExpenseEvent
from ..security.auth import Principal, get_principal
from ..services import receipts
from .common import ReqCtx, req_ctx

router = APIRouter(prefix="/expenses", tags=["gastos"])

CATEGORIES = {
    "desplazamiento": "Desplazamientos (taxi, tren, parking, peajes)", "comidas": "Comidas y dietas",
    "alojamiento": "Alojamiento", "material_oficina": "Material de oficina", "tasas_registros": "Tasas y registros",
    "mensajeria": "Mensajería y correos", "formacion": "Formación", "suministros": "Suministros y servicios",
    "otros": "Otros",
}
METHODS = ("efectivo_caja", "tarjeta_empresa", "personal")
EDITABLE = ("borrador", "devuelto")
MATCH_DAYS = 3


def _now() -> datetime:
    return datetime.now(UTC)


class ExpenseUpdate(BaseModel):
    expense_date: date | None = None
    supplier_name: str | None = Field(default=None, max_length=200)
    supplier_tax_id: str | None = Field(default=None, max_length=20)
    category: Literal[tuple(CATEGORIES)] | None = None  # type: ignore[valid-type]
    description: str | None = Field(default=None, max_length=500)
    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    vat_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    payment_method: Literal["efectivo_caja", "tarjeta_empresa", "personal"] | None = None
    card_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    version: int


class ReviewIn(BaseModel):
    action: Literal["aprobar", "devolver", "anular"]
    note: str | None = Field(default=None, max_length=500)


class ReconcileIn(BaseModel):
    card_transaction_id: uuid.UUID | None = None
    reference: str | None = Field(default=None, max_length=120)


class CardIn(BaseModel):
    organization_id: uuid.UUID
    holder_user_id: uuid.UUID
    last4: str = Field(pattern=r"^\d{4}$")
    label: str = Field(min_length=3, max_length=120)


# ------------------------------------------------------------------ utilidades
def _deny(p: Principal, ctx: ReqCtx, action: str, rid, org, reason: str) -> None:
    audit.record_independent(actor_id=p.id, action=action, resource_type="expense", resource_id=rid,
                             organization_id=org, outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _uname(db: Session, uid) -> str | None:
    return db.get(UserAccount, uid).full_name if uid else None


def _can_see(p: Principal, e: Expense) -> bool:
    return e.employee_id == p.id or p.has(e.organization_id, "expense.read.all") or p.has(e.organization_id, "expense.review")


def _get(db: Session, p: Principal, expense_id: uuid.UUID, request: Request, action: str) -> Expense:
    e = db.get(Expense, expense_id)
    if e is None or e.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Gasto no encontrado.")
    if not _can_see(p, e):
        _deny(p, req_ctx(request), action, e.id, e.organization_id, "gasto ajeno")
        raise api_error(403, "prohibido", "Solo la persona que hizo el gasto y Contabilidad pueden verlo.")
    return e


def _out(db: Session, p: Principal, e: Expense, detail: bool = False) -> dict:
    card = db.get(CompanyCard, e.card_id) if e.card_id else None
    org = e.organization_id
    reviewer = p.has(org, "expense.review")
    out = {
        "id": str(e.id), "organization_id": str(org), "status": e.status, "employee_id": str(e.employee_id),
        "employee": _uname(db, e.employee_id), "branch_id": str(e.branch_id), "branch": db.get(Branch, e.branch_id).name,
        "expense_date": e.expense_date.isoformat() if e.expense_date else None, "supplier_name": e.supplier_name,
        "supplier_tax_id": e.supplier_tax_id, "category": e.category, "description": e.description,
        "amount_cents": e.amount_cents, "vat_cents": e.vat_cents, "currency": e.currency,
        "payment_method": e.payment_method, "card_id": str(e.card_id) if e.card_id else None,
        "card": f"{card.label} ··{card.last4}" if card else None, "has_receipt": bool(e.receipt_path),
        "receipt_name": e.receipt_name, "receipt_mime": e.receipt_mime, "review_note": e.review_note,
        "reviewed_by": _uname(db, e.reviewed_by), "reconcile_ref": e.reconcile_ref, "version": e.version,
        "created_at": e.created_at.isoformat(), "submitted_at": e.submitted_at.isoformat() if e.submitted_at else None,
    }
    if detail:
        evs = db.execute(select(ExpenseEvent).where(ExpenseEvent.expense_id == e.id).order_by(ExpenseEvent.at)).scalars()
        out["events"] = [{"from": x.from_status, "to": x.to_status, "note": x.note, "actor": _uname(db, x.actor_user_id),
                          "at": x.at.isoformat()} for x in evs]
        out["ocr"] = {"engine": e.ocr_engine, "suggestion": e.ocr_suggestion or {}, "text": e.ocr_text or ""}
        own = e.employee_id == p.id
        out["allowed"] = {
            "edit": own and e.status in EDITABLE, "submit": own and e.status in EDITABLE,
            "review": reviewer and not own and e.status == "enviado",
            "annul": (reviewer and not own and e.status in ("enviado", "aprobado", "devuelto"))
                     or (own and e.status == "borrador"),
            "reconcile": reviewer and e.status == "aprobado",
        }
        dup = None
        if e.receipt_sha256:
            dup = db.execute(select(Expense.id).where(Expense.receipt_sha256 == e.receipt_sha256, Expense.id != e.id,
                                                      Expense.status != "anulado")).scalar()
        out["duplicate_of"] = str(dup) if dup else None
    return out


def _event(db: Session, e: Expense, actor: uuid.UUID, to: str, note: str | None = None) -> None:
    db.add(ExpenseEvent(expense_id=e.id, actor_user_id=actor, from_status=e.status, to_status=to, note=note))
    e.status = to
    e.version += 1


def _sync_cash(db: Session, e: Expense, actor: uuid.UUID) -> None:
    """La caja de la sede refleja los gastos pagados en efectivo que siguen vivos (enviado en adelante)."""
    current = int(db.execute(select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(
        CashMovement.concept.like(f"%[gasto {e.id}]"))).scalar_one())
    live = e.payment_method == "efectivo_caja" and e.status in ("enviado", "aprobado", "conciliado", "devuelto")
    target = -(e.amount_cents or 0) if live else 0
    if target != current:
        kind = "gasto" if target < current else "anulacion_gasto"
        db.add(CashMovement(organization_id=e.organization_id, branch_id=e.branch_id, kind=kind,
                            amount_cents=target - current, currency=e.currency,
                            concept=f"{(e.supplier_name or 'Gasto')[:120]} · {_uname(db, e.employee_id)} [gasto {e.id}]",
                            created_by=actor))


def _default_branch(db: Session, p: Principal, org: uuid.UUID) -> Branch:
    for m in p.memberships:
        if m.organization_id == org and m.branch_id:
            b = db.get(Branch, m.branch_id)
            if b.kind == "sede":
                return b
    b = db.execute(select(Branch).where(Branch.organization_id == org, Branch.kind == "sede").order_by(Branch.name)).scalars().first()
    if b is None:
        raise api_error(422, "validacion", "La entidad no tiene sedes.")
    return b


# ------------------------------------------------------------------ alta con justificante
@router.post("", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), organization_id: uuid.UUID | None = Form(None),
                 p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    ctx = req_ctx(request)
    orgs = p.orgs_with("expense.submit")
    org = organization_id or (sorted(orgs, key=str)[0] if len(orgs) == 1 else None)
    if not orgs:
        _deny(p, ctx, "expense.create", None, None, "sin expense.submit")
        raise api_error(403, "prohibido", "Su rol no registra gastos.")
    if org is None:
        raise api_error(422, "validacion", "Indique la entidad del gasto.", [{"field": "organization_id", "message": "Obligatoria"}])
    if org not in orgs:
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    data = await file.read(receipts.MAX_BYTES + 1)
    try:
        mime = receipts.sniff(data, file.content_type)
    except receipts.ReceiptError as exc:
        raise api_error(422, "justificante_no_valido", exc.message, [{"field": "file", "message": exc.message}]) from exc
    sha = hashlib.sha256(data).hexdigest()
    dup = db.execute(select(Expense).where(Expense.receipt_sha256 == sha, Expense.organization_id == org,
                                           Expense.status != "anulado")).scalars().first()
    if dup is not None:
        raise api_error(409, "justificante_duplicado",
                        "Este mismo justificante ya está registrado. No se puede presentar dos veces.",
                        {"expense_id": str(dup.id) if _can_see(p, dup) else None})
    sug = receipts.read(data, mime)
    path, _ = receipts.store(data)
    f = {k: v["value"] for k, v in sug.fields.items()}
    e = Expense(organization_id=org, employee_id=p.id, branch_id=_default_branch(db, p, org).id, status="borrador",
                currency=db.get(Organization, org).currency, receipt_name=(file.filename or "justificante")[:200],
                receipt_mime=mime, receipt_size=len(data), receipt_sha256=sha, receipt_path=path,
                ocr_engine=sug.engine, ocr_text=sug.text or None,
                ocr_suggestion={"fields": sug.fields, "message": sug.message},
                expense_date=date.fromisoformat(f["expense_date"]) if "expense_date" in f else None,
                supplier_name=f.get("supplier_name"), supplier_tax_id=f.get("supplier_tax_id"),
                amount_cents=f.get("amount_cents"), vat_cents=f.get("vat_cents"))
    if e.vat_cents is not None and (e.amount_cents is None or e.vat_cents >= e.amount_cents):
        e.vat_cents = None
    db.add(e)
    db.flush()
    db.add(ExpenseEvent(expense_id=e.id, actor_user_id=p.id, from_status=None, to_status="borrador",
                        note=f"Justificante subido; lectura: {sug.engine}"))
    audit.record(db, actor_id=p.id, action="expense.create", resource_type="expense", resource_id=e.id,
                 organization_id=org, after={"archivo": e.receipt_name, "sha256": sha, "lectura": sug.engine,
                                             "campos_propuestos": sorted(sug.fields)}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, e, detail=True)


@router.get("/catalog")
def catalog(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    orgs = p.orgs_with("expense.submit") | p.orgs_with("expense.review")
    return {
        "categories": CATEGORIES,
        "organizations": [{"id": str(o.id), "name": o.name, "currency": o.currency,
                           "branches": [{"id": str(b.id), "name": b.name} for b in db.execute(
                               select(Branch).where(Branch.organization_id == o.id, Branch.kind == "sede")
                               .order_by(Branch.name)).scalars()]}
                          for o in db.execute(select(Organization).where(Organization.id.in_(orgs or [uuid.uuid4()]))
                                              .order_by(Organization.name)).scalars()],
        "my_cards": [{"id": str(c.id), "label": f"{c.label} ··{c.last4}", "organization_id": str(c.organization_id)}
                     for c in db.execute(select(CompanyCard).where(CompanyCard.holder_user_id == p.id,
                                                                   CompanyCard.active.is_(True))).scalars()],
        "can_review": bool(p.orgs_with("expense.review")), "can_read_all": bool(p.orgs_with("expense.read.all")),
        "ocr_available": receipts.extractor() is not None,
    }


@router.get("")
def list_expenses(scope: Literal["mine", "all"] = "mine", status: str | None = None,
                  month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> list[dict]:
    q = select(Expense)
    if scope == "mine":
        q = q.where(Expense.employee_id == p.id)
    else:
        orgs = p.orgs_with("expense.read.all") | p.orgs_with("expense.review")
        if not orgs:
            raise api_error(403, "prohibido", "Solo Contabilidad y Dirección ven todos los gastos.")
        q = q.where(Expense.organization_id.in_(orgs))
    if status:
        q = q.where(Expense.status == status)
    if month:
        y, m = map(int, month.split("-"))
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1)
        q = q.where(Expense.expense_date >= start, Expense.expense_date < end)
    rows = db.execute(q.order_by(Expense.created_at.desc()).limit(500)).scalars()
    return [_out(db, p, e) for e in rows]


@router.get("/{expense_id}")
def get_expense(expense_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    return _out(db, p, _get(db, p, expense_id, request, "expense.read"), detail=True)


@router.get("/{expense_id}/receipt")
def receipt(expense_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> Response:
    e = _get(db, p, expense_id, request, "expense.receipt")
    if not e.receipt_path:
        raise api_error(404, "no_encontrado", "Sin justificante.")
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="expense.receipt", resource_type="expense", resource_id=e.id,
                             organization_id=e.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[e.receipt_mime]
    return Response(receipts.load(e.receipt_path), media_type=e.receipt_mime,
                    headers={"Content-Disposition": f'inline; filename="justificante-{str(e.id)[:8]}.{ext}"',
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})


@router.patch("/{expense_id}")
def update(expense_id: uuid.UUID, body: ExpenseUpdate, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    e = _get(db, p, expense_id, request, "expense.update")
    ctx = req_ctx(request)
    if e.employee_id != p.id:
        _deny(p, ctx, "expense.update", e.id, e.organization_id, "modificar gasto ajeno")
        raise api_error(403, "prohibido", "Solo la persona que hizo el gasto lo corrige. Contabilidad puede devolverlo con un motivo.")
    if e.status not in EDITABLE:
        raise api_error(409, "conflicto", "El gasto ya está enviado; no se puede modificar.")
    if body.version != e.version:
        raise api_error(409, "conflicto_version", "El gasto ha cambiado. Recargue la página.")
    data = body.model_dump(exclude_unset=True, exclude={"version"})
    if "branch_id" in data and data["branch_id"]:
        b = db.get(Branch, data["branch_id"])
        if b is None or b.organization_id != e.organization_id:
            raise api_error(422, "validacion", "Sede no válida.", [{"field": "branch_id", "message": "Sede no válida"}])
    if data.get("card_id"):
        c = db.get(CompanyCard, data["card_id"])
        if c is None or c.holder_user_id != p.id or not c.active or c.organization_id != e.organization_id:
            raise api_error(422, "validacion", "Esa tarjeta no está a su nombre.", [{"field": "card_id", "message": "Tarjeta no válida"}])
    if data.get("supplier_tax_id"):
        data["supplier_tax_id"] = re.sub(r"[\s.\-]", "", data["supplier_tax_id"]).upper()
    before = {k: getattr(e, k) for k in data}
    for k, v in data.items():
        setattr(e, k, v)
    if e.payment_method != "tarjeta_empresa":
        e.card_id = None
    if e.vat_cents is not None and e.amount_cents is not None and e.vat_cents >= e.amount_cents:
        raise api_error(422, "validacion", "El IVA no puede ser igual o mayor que el total.", [{"field": "vat_cents", "message": "Revise"}])
    e.version += 1
    audit.record(db, actor_id=p.id, action="expense.update", resource_type="expense", resource_id=e.id,
                 organization_id=e.organization_id, before={k: str(v) if v is not None else None for k, v in before.items()},
                 after={k: str(v) if v is not None else None for k, v in data.items()}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, e, detail=True)


@router.post("/{expense_id}/submit")
def submit(expense_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    e = _get(db, p, expense_id, request, "expense.submit")
    if e.employee_id != p.id:
        raise api_error(403, "prohibido", "Solo la persona que hizo el gasto lo envía.")
    if e.status not in EDITABLE:
        raise api_error(409, "conflicto", "Ya está enviado.")
    missing = [lbl for f, lbl in (("expense_date", "fecha"), ("supplier_name", "proveedor"), ("category", "concepto"),
                                  ("amount_cents", "importe"), ("payment_method", "forma de pago")) if getattr(e, f) is None]
    if e.payment_method == "tarjeta_empresa" and not e.card_id:
        missing.append("tarjeta")
    if missing:
        raise api_error(422, "incompleto", f"Complete antes: {', '.join(missing)}.")
    if e.expense_date > date.today():
        raise api_error(422, "validacion", "La fecha del gasto no puede ser futura.")
    e.submitted_at = _now()
    _event(db, e, p.id, "enviado", "Datos revisados y confirmados por la persona")
    _sync_cash(db, e, p.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="expense.submit", resource_type="expense", resource_id=e.id,
                 organization_id=e.organization_id, after={"importe": e.amount_cents, "forma_pago": e.payment_method},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, e, detail=True)


@router.post("/{expense_id}/review")
def review(expense_id: uuid.UUID, body: ReviewIn, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    e = _get(db, p, expense_id, request, "expense.review")
    ctx = req_ctx(request)
    own = e.employee_id == p.id
    if body.action == "anular" and own and e.status == "borrador":
        _event(db, e, p.id, "anulado", body.note or "Descartado por la propia persona antes de enviarlo")
        audit.record(db, actor_id=p.id, action="expense.annul", resource_type="expense", resource_id=e.id,
                     organization_id=e.organization_id, reason=body.note, ip=ctx.ip, request_id=ctx.request_id)
        db.commit()
        return _out(db, p, e, detail=True)
    if not p.has(e.organization_id, "expense.review"):
        _deny(p, ctx, f"expense.{body.action}", e.id, e.organization_id, "sin expense.review")
        raise api_error(403, "prohibido", "Solo Contabilidad revisa gastos.")
    if own:
        _deny(p, ctx, f"expense.{body.action}", e.id, e.organization_id, "revisar gasto propio")
        raise api_error(403, "doble_control", "Nadie revisa sus propios gastos.")
    allowed = {"aprobar": ("enviado",), "devolver": ("enviado",), "anular": ("enviado", "aprobado", "devuelto")}
    if e.status not in allowed[body.action]:
        raise api_error(409, "conflicto", f"No se puede {body.action} un gasto en estado «{e.status}».")
    note = (body.note or "").strip()
    if body.action in ("devolver", "anular") and len(note) < 5:
        raise api_error(422, "validacion", "Indique el motivo.", [{"field": "note", "message": "Obligatorio"}])
    e.reviewed_by, e.reviewed_at, e.review_note = p.id, _now(), note or None
    if body.action == "aprobar":
        if e.payment_method == "efectivo_caja":
            e.reconciled_by, e.reconciled_at, e.reconcile_ref = p.id, _now(), "Caja de la sede"
            _event(db, e, p.id, "conciliado", "Aprobado; pagado en efectivo: conciliado con la caja de la sede")
        else:
            _event(db, e, p.id, "aprobado", note or None)
    elif body.action == "devolver":
        _event(db, e, p.id, "devuelto", note)
    else:
        _event(db, e, p.id, "anulado", note)
        if e.card_id:
            for t in db.execute(select(CardTransaction).where(CardTransaction.expense_id == e.id)).scalars():
                t.expense_id = None
    _sync_cash(db, e, p.id)
    audit.record(db, actor_id=p.id, action=f"expense.{body.action}", resource_type="expense", resource_id=e.id,
                 organization_id=e.organization_id, reason=note or None, after={"estado": e.status},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, e, detail=True)


@router.post("/{expense_id}/reconcile")
def reconcile(expense_id: uuid.UUID, body: ReconcileIn, request: Request, p: Principal = Depends(get_principal),
              db: Session = Depends(get_db)) -> dict:
    e = _get(db, p, expense_id, request, "expense.reconcile")
    ctx = req_ctx(request)
    if not p.has(e.organization_id, "expense.review"):
        _deny(p, ctx, "expense.reconcile", e.id, e.organization_id, "sin expense.review")
        raise api_error(403, "prohibido", "Solo Contabilidad concilia gastos.")
    if e.status != "aprobado":
        raise api_error(409, "conflicto", "Solo se concilian gastos aprobados.")
    if e.payment_method == "tarjeta_empresa":
        t = db.get(CardTransaction, body.card_transaction_id) if body.card_transaction_id else None
        if t is None or t.card_id != e.card_id:
            raise api_error(422, "validacion", "Elija el movimiento del extracto de esa tarjeta.")
        if t.expense_id and t.expense_id != e.id:
            raise api_error(409, "conflicto", "Ese movimiento ya está conciliado con otro gasto.")
        if t.amount_cents != e.amount_cents:
            raise api_error(422, "importe_distinto", "El importe del extracto no coincide con el del justificante.")
        t.expense_id = e.id
        ref = f"Extracto {t.txn_date.isoformat()} · {t.description}"
    else:
        ref = (body.reference or "").strip()
        if len(ref) < 3:
            raise api_error(422, "validacion", "Indique la referencia del reembolso (p. ej. transferencia o nómina).")
    e.reconciled_by, e.reconciled_at, e.reconcile_ref = p.id, _now(), ref[:120]
    _event(db, e, p.id, "conciliado", ref[:500])
    audit.record(db, actor_id=p.id, action="expense.reconcile", resource_type="expense", resource_id=e.id,
                 organization_id=e.organization_id, after={"referencia": ref[:120]}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(db, p, e, detail=True)


# ------------------------------------------------------------------ tarjetas de empresa y extractos
def _review_orgs(p: Principal, request: Request, action: str) -> set[uuid.UUID]:
    orgs = p.orgs_with("expense.review")
    if not orgs:
        _deny(p, req_ctx(request), action, None, None, "sin expense.review")
        raise api_error(403, "prohibido", "Solo Contabilidad gestiona tarjetas y extractos.")
    return orgs


@router.get("/cards/all")
def list_cards(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = _review_orgs(p, request, "card.list")
    rows = db.execute(select(CompanyCard).where(CompanyCard.organization_id.in_(orgs)).order_by(CompanyCard.label)).scalars()
    return [{"id": str(c.id), "label": c.label, "last4": c.last4, "holder": _uname(db, c.holder_user_id),
             "holder_user_id": str(c.holder_user_id), "active": c.active, "organization_id": str(c.organization_id)}
            for c in rows]


@router.post("/cards", status_code=201)
def add_card(body: CardIn, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    orgs = _review_orgs(p, request, "card.create")
    if body.organization_id not in orgs:
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    from ..security.auth import active_memberships

    if not any(m.organization_id == body.organization_id for m in active_memberships(db, body.holder_user_id)):
        raise api_error(422, "validacion", "La persona titular no pertenece a la entidad.")
    c = CompanyCard(organization_id=body.organization_id, holder_user_id=body.holder_user_id, last4=body.last4,
                    label=body.label.strip())
    db.add(c)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="card.create", resource_type="company_card", resource_id=c.id,
                 organization_id=c.organization_id, after={"titular": _uname(db, c.holder_user_id), "ultimos4": c.last4},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"id": str(c.id)}


@router.get("/cards/holders")
def holders(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    from ..models import Membership

    orgs = _review_orgs(p, request, "card.holders")
    rows = db.execute(select(UserAccount, Membership.organization_id).join(Membership, Membership.user_id == UserAccount.id)
                      .where(Membership.organization_id.in_(orgs), Membership.status == "activa",
                             UserAccount.status == "activo").distinct().order_by(UserAccount.full_name)).all()
    return [{"id": str(u.id), "full_name": u.full_name, "organization_id": str(o)} for u, o in rows]


def _parse_eur(raw: str) -> int:
    v = raw.strip().replace("€", "").replace(" ", "")
    neg = v.startswith("-") or (v.startswith("(") and v.endswith(")"))
    v = v.strip("-()+")
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    cents = round(float(v) * 100)
    return -cents if neg else cents


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


@router.post("/cards/import")
async def import_statement(request: Request, file: UploadFile = File(...), organization_id: uuid.UUID = Form(...),
                           p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Extracto en CSV con columnas: fecha;concepto;importe;tarjeta (4 últimos dígitos). Cargos en positivo."""
    orgs = _review_orgs(p, request, "card.import")
    if organization_id not in orgs:
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    raw = (await file.read(2_000_000)).decode("utf-8-sig", "replace")
    dialect = ";" if raw.count(";") >= raw.count(",") else ","
    reader = csv.reader(io.StringIO(raw), delimiter=dialect)
    cards = {c.last4: c for c in db.execute(select(CompanyCard).where(CompanyCard.organization_id == organization_id)).scalars()}
    imported, duplicates, errors, matched = 0, 0, [], 0
    seen: dict[str, int] = {}
    for n, row in enumerate(reader, start=1):
        if not row or all(not c.strip() for c in row):
            continue
        if n == 1 and not re.search(r"\d", row[0]):
            continue  # cabecera
        try:
            if len(row) < 4:
                raise ValueError("faltan columnas")
            d, desc, amount, last4 = _parse_date(row[0]), row[1].strip()[:200], _parse_eur(row[2]), row[3].strip()[-4:]
        except (ValueError, IndexError) as exc:
            errors.append({"linea": n, "error": f"No se entiende la línea ({exc})"})
            continue
        card = cards.get(last4)
        if card is None:
            errors.append({"linea": n, "error": f"Tarjeta ··{last4} no registrada"})
            continue
        if amount <= 0:
            continue  # abonos: fuera del control de gastos
        # Huella estable: filas idénticas dentro del mismo extracto se distinguen por su orden de aparición,
        # así reimportar el mismo archivo (o uno que se solapa) no duplica movimientos.
        key = f"{card.id}|{d}|{desc}|{amount}"
        seen[key] = seen.get(key, 0) + 1
        fp = hashlib.sha256(f"{key}|{seen[key]}".encode()).hexdigest()
        if db.execute(select(CardTransaction.id).where(CardTransaction.fingerprint == fp)).first():
            duplicates += 1
            continue
        t = CardTransaction(organization_id=organization_id, card_id=card.id, txn_date=d, description=desc,
                            amount_cents=amount, fingerprint=fp, imported_by=p.id)
        db.add(t)
        db.flush()
        imported += 1
        if _suggest(db, t):
            matched += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="card.import", resource_type="organization", resource_id=organization_id,
                 organization_id=organization_id, after={"importados": imported, "duplicados": duplicates,
                                                         "errores": len(errors), "con_propuesta": matched},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"imported": imported, "duplicates": duplicates, "errors": errors[:50], "with_suggestion": matched}


def _suggest(db: Session, t: CardTransaction) -> list[Expense]:
    return list(db.execute(select(Expense).where(
        Expense.card_id == t.card_id, Expense.amount_cents == t.amount_cents, Expense.status.in_(("enviado", "aprobado")),
        Expense.expense_date >= t.txn_date - timedelta(days=MATCH_DAYS),
        Expense.expense_date <= t.txn_date + timedelta(days=MATCH_DAYS))).scalars())


@router.get("/cards/transactions")
def card_transactions(request: Request, unmatched: bool = True, p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> list[dict]:
    orgs = _review_orgs(p, request, "card.transactions")
    q = select(CardTransaction).where(CardTransaction.organization_id.in_(orgs))
    if unmatched:
        q = q.where(CardTransaction.expense_id.is_(None))
    out = []
    for t in db.execute(q.order_by(CardTransaction.txn_date.desc()).limit(300)).scalars():
        card = db.get(CompanyCard, t.card_id)
        out.append({"id": str(t.id), "date": t.txn_date.isoformat(), "description": t.description,
                    "amount_cents": t.amount_cents, "card": f"{card.label} ··{card.last4}",
                    "holder": _uname(db, card.holder_user_id), "expense_id": str(t.expense_id) if t.expense_id else None,
                    "suggestions": [{"id": str(e.id), "supplier_name": e.supplier_name, "status": e.status,
                                     "expense_date": e.expense_date.isoformat() if e.expense_date else None}
                                    for e in _suggest(db, t)] if not t.expense_id else []})
    return out


# ------------------------------------------------------------------ resumen mensual
def _summary(db: Session, orgs: set[uuid.UUID], month: str) -> dict:
    y, m = map(int, month.split("-"))
    start, end = date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1)
    rows = list(db.execute(select(Expense).where(Expense.organization_id.in_(orgs), Expense.expense_date >= start,
                                                 Expense.expense_date < end,
                                                 Expense.status.in_(("enviado", "aprobado", "conciliado", "devuelto"))))
                .scalars())
    groups: dict[str, dict] = {k: defaultdict(lambda: {"total": 0, "iva": 0, "n": 0}) for k in
                               ("empleado", "sede", "concepto", "forma_pago")}
    total = {"total": 0, "iva": 0, "n": 0}
    by_status: dict[str, int] = defaultdict(int)
    for e in rows:
        keys = {"empleado": _uname(db, e.employee_id), "sede": db.get(Branch, e.branch_id).name,
                "concepto": CATEGORIES.get(e.category or "otros", e.category), "forma_pago": e.payment_method}
        for g, k in keys.items():
            groups[g][k]["total"] += e.amount_cents or 0
            groups[g][k]["iva"] += e.vat_cents or 0
            groups[g][k]["n"] += 1
        total["total"] += e.amount_cents or 0
        total["iva"] += e.vat_cents or 0
        total["n"] += 1
        by_status[e.status] += 1
    card_unmatched = db.execute(select(func.count()).where(CardTransaction.organization_id.in_(orgs),
                                                           CardTransaction.expense_id.is_(None),
                                                           CardTransaction.txn_date >= start,
                                                           CardTransaction.txn_date < end)).scalar_one()
    return {"month": month, "total": total, "por_estado": dict(by_status),
            "grupos": {g: dict(sorted(v.items(), key=lambda kv: -kv[1]["total"])) for g, v in groups.items()},
            "cargos_tarjeta_sin_justificante": card_unmatched, "rows": rows}


@router.get("/summary/month")
def monthly(request: Request, month: str = Query(pattern=r"^\d{4}-\d{2}$"), p: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> dict:
    orgs = p.orgs_with("expense.read.all") | p.orgs_with("expense.review")
    if not orgs:
        _deny(p, req_ctx(request), "expense.summary", None, None, "sin expense.read.all")
        raise api_error(403, "prohibido", "Solo Contabilidad y Dirección ven el resumen de gastos.")
    s = _summary(db, orgs, month)
    s.pop("rows")
    return s


@router.get("/summary/month.csv")
def monthly_csv(request: Request, month: str = Query(pattern=r"^\d{4}-\d{2}$"), p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> Response:
    orgs = p.orgs_with("expense.read.all") | p.orgs_with("expense.review")
    if not orgs:
        _deny(p, req_ctx(request), "expense.export", None, None, "sin expense.read.all")
        raise api_error(403, "prohibido", "Solo Contabilidad y Dirección exportan gastos.")
    s = _summary(db, orgs, month)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Fecha", "Empleado", "Sede", "Proveedor", "NIF proveedor", "Concepto", "Descripción", "Forma de pago",
                "Total", "IVA", "Estado", "Conciliación"])
    for e in sorted(s["rows"], key=lambda x: (x.expense_date, x.created_at)):
        w.writerow([e.expense_date.strftime("%d/%m/%Y"), _uname(db, e.employee_id), db.get(Branch, e.branch_id).name,
                    e.supplier_name or "", e.supplier_tax_id or "", CATEGORIES.get(e.category or "otros", ""),
                    e.description or "", e.payment_method or "", f"{(e.amount_cents or 0) / 100:.2f}".replace(".", ","),
                    f"{(e.vat_cents or 0) / 100:.2f}".replace(".", ","), e.status, e.reconcile_ref or ""])
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="expense.export", resource_type="organization", resource_id=month,
                             after={"filas": len(s["rows"])}, ip=ctx.ip, request_id=ctx.request_id)
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="gastos_{month}.csv"'})
