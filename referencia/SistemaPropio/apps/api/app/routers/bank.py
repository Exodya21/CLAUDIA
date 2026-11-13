"""Banco y conciliación (F5.1; DR-CON-2, DR-CON-3; Q-4.5). Datos SIEMPRE por entidad; Contabilidad concilia.

Pantalla pedida por Dirección: importados, conciliados, pendientes y errores de una cuenta.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import agents, audit
from ..agents import engine
from ..agents.base import ApplyError
from ..bank import matcher, parsers, service
from ..config import get_settings
from ..db import get_db
from ..errors import api_error
from ..models import Branch, CaseFile, Contact
from ..models_agents import AgentProposal
from ..models_bank import BankAccount, BankImport, BankMatch, BankMovement
from ..models_economy import Payment, Refund
from ..security.auth import Principal, get_principal
from ..services import textcrypt, vault
from .common import req_ctx

router = APIRouter(prefix="/bank", tags=["banco"])
MAX_UPLOAD = 10 * 1024 * 1024
CATEGORIES = ("cobro", "tpv", "comision", "bizum", "traspaso", "devolucion", "nomina", "seguridad_social",
              "impuestos", "alquiler", "proveedor", "otro")
PENDING = ("pendiente", "propuesto", "parcial", "sin_justificar")
DONE = ("conciliado", "traspaso", "ignorado")


def _deny(p: Principal, request: Request, action: str, rtype: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type=rtype, resource_id=rid, organization_id=org,
                             outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _account(db: Session, p: Principal, account_id: uuid.UUID, request: Request, perm: str) -> BankAccount:
    acc = db.get(BankAccount, account_id)
    if acc is None or acc.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cuenta no encontrada.")
    if not p.has(acc.organization_id, perm):
        _deny(p, request, f"bank.{perm}", "bank_account", acc.id, acc.organization_id, f"sin {perm}")
        raise api_error(403, "prohibido", "No tiene permiso para esta operación del banco.")
    return acc


def _movement(db: Session, p: Principal, movement_id: uuid.UUID, request: Request, perm: str) -> BankMovement:
    m = db.get(BankMovement, movement_id)
    if m is None or m.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Movimiento no encontrado.")
    if not p.has(m.organization_id, perm):
        _deny(p, request, f"bank.{perm}", "bank_movement", m.id, m.organization_id, f"sin {perm}")
        raise api_error(403, "prohibido", "Solo Contabilidad concilia movimientos.")
    return m


def _bank_error(exc: service.BankError | ApplyError):
    return api_error(exc.status, "conflicto" if exc.status == 409 else ("prohibido" if exc.status == 403 else "validacion"),
                     exc.message)


# ------------------------------------------------------------------ cuentas
class AccountIn(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=3, max_length=120)
    bank_name: str = Field(min_length=2, max_length=80)
    iban_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    iban: str | None = Field(default=None, max_length=40)  # completo: se guarda cifrado (remesas SEPA y reconocer extractos)
    purpose: Literal["A_laboral", "B_extranjeria", "C_tesoreria", "otra"]
    activity: Literal["laboral", "extranjeria", "compartida"]
    branch_id: uuid.UUID | None = None
    currency: Literal["EUR", "COP", "USD"] = "EUR"


def _counts(db: Session, account_id) -> dict:
    rows = dict(db.execute(select(BankMovement.status, func.count()).where(BankMovement.account_id == account_id)
                           .group_by(BankMovement.status)).all())
    errs = 0
    for imp in db.execute(select(BankImport).where(BankImport.account_id == account_id)).scalars():
        errs += len(imp.errors or [])
    return {"importados": sum(rows.values()), "conciliados": sum(rows.get(s, 0) for s in DONE),
            "pendientes": sum(rows.get(s, 0) for s in PENDING), "errores": errs,
            "por_estado": rows}


def _account_out(db: Session, a: BankAccount) -> dict:
    last = db.execute(select(BankImport).where(BankImport.account_id == a.id)
                      .order_by(BankImport.period_to.desc().nulls_last(), BankImport.imported_at.desc()).limit(1)).scalar_one_or_none()
    br = db.get(Branch, a.branch_id) if a.branch_id else None
    return {"id": str(a.id), "organization_id": str(a.organization_id), "name": a.name, "bank_name": a.bank_name,
            "iban_last4": a.iban_last4, "purpose": a.purpose, "activity": a.activity, "currency": a.currency,
            "branch": br.name if br else None, "active": a.active, "counts": _counts(db, a.id),
            "last_import": _import_out(last) if last else None}


@router.get("/accounts")
def list_accounts(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = p.orgs_with("bank.read")
    if not orgs:
        _deny(p, request, "bank.read", "bank_account", None, None, "sin bank.read")
        raise api_error(403, "prohibido", "No tiene acceso al banco.")
    rows = db.execute(select(BankAccount).where(BankAccount.organization_id.in_(orgs))
                      .order_by(BankAccount.purpose, BankAccount.name)).scalars()
    out = []
    for a in rows:
        d = _account_out(db, a)
        d["can_import"] = p.has(a.organization_id, "bank.import")
        d["can_reconcile"] = p.has(a.organization_id, "bank.reconcile")
        d["can_manage"] = p.has(a.organization_id, "bank.accounts.manage")
        d["demo_statement"] = get_settings().app_env in ("development", "test") and d["can_import"]
        out.append(d)
    return out


@router.post("/accounts", status_code=201)
def create_account(body: AccountIn, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    if body.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(body.organization_id, "bank.accounts.manage"):
        _deny(p, request, "bank.account.create", "bank_account", None, body.organization_id, "sin bank.accounts.manage")
        raise api_error(403, "prohibido", "No puede dar de alta cuentas.")
    iban_full = None
    if body.iban:
        from ..accounting.invoices import normalize_iban, valid_iban
        iban_full = normalize_iban(body.iban.replace("-", ""))
        if not valid_iban(iban_full):
            raise api_error(422, "validacion", "IBAN no válido (revise los dígitos de control).", [{"field": "iban", "message": "no válido"}])
        if body.iban_last4 and body.iban_last4 != iban_full[-4:]:
            raise api_error(422, "validacion", "El IBAN no termina en esos 4 dígitos.")
        body.iban_last4 = iban_full[-4:]
    if not body.iban_last4:
        raise api_error(422, "validacion", "Indique el IBAN o, al menos, los 4 últimos dígitos.", [{"field": "iban", "message": "obligatorio"}])
    if body.branch_id:
        br = db.get(Branch, body.branch_id)
        if br is None or br.organization_id != body.organization_id:
            raise api_error(422, "validacion", "Sede no válida.")
    dup = db.execute(select(BankAccount.id).where(BankAccount.organization_id == body.organization_id,
                                                  BankAccount.iban_last4 == body.iban_last4,
                                                  BankAccount.bank_name == body.bank_name.strip())).first()
    if dup:
        raise api_error(409, "conflicto", "Ya existe una cuenta de ese banco terminada en esos dígitos.")
    a = BankAccount(organization_id=body.organization_id, name=body.name.strip(), bank_name=body.bank_name.strip(),
                    iban_last4=body.iban_last4, purpose=body.purpose, activity=body.activity, branch_id=body.branch_id,
                    currency=body.currency, created_by=p.id, iban_enc=textcrypt.enc(iban_full) if iban_full else None)
    db.add(a)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="bank.account.create", resource_type="bank_account", resource_id=a.id,
                 organization_id=a.organization_id, after={"nombre": a.name, "banco": a.bank_name,
                                                           "termina": a.iban_last4, "uso": a.purpose},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _account_out(db, a)


class ActiveIn(BaseModel):
    active: bool
    reason: str = Field(min_length=5, max_length=300)


@router.post("/accounts/{account_id}/active")
def set_active(account_id: uuid.UUID, body: ActiveIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    a = _account(db, p, account_id, request, "bank.accounts.manage")
    before = a.active
    a.active = body.active
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="bank.account.active", resource_type="bank_account", resource_id=a.id,
                 organization_id=a.organization_id, reason=body.reason, before={"activa": before},
                 after={"activa": a.active}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _account_out(db, a)


# ------------------------------------------------------------------ importaciones
def _import_out(i: BankImport) -> dict:
    return {"id": str(i.id), "name": i.original_name, "format": i.file_format, "sha256": i.sha256,
            "period_from": i.period_from.isoformat() if i.period_from else None,
            "period_to": i.period_to.isoformat() if i.period_to else None,
            "opening_cents": i.opening_cents, "closing_cents": i.closing_cents, "total_lines": i.total_lines,
            "new_lines": i.new_lines, "duplicate_lines": i.duplicate_lines, "balance_ok": i.balance_ok,
            "errors": i.errors or [], "imported_at": i.imported_at.isoformat()}


@router.post("/accounts/{account_id}/imports", status_code=201)
async def import_statement(account_id: uuid.UUID, request: Request, background: BackgroundTasks,
                           file: UploadFile = File(...), p: Principal = Depends(get_principal),
                           db: Session = Depends(get_db)) -> dict:
    acc = _account(db, p, account_id, request, "bank.import")
    if not acc.active:
        raise api_error(409, "conflicto", "La cuenta está desactivada.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise api_error(422, "validacion", "El extracto supera 10 MB.")
    try:
        imp = service.import_statement(db, acc, data, file.filename or "extracto", p.id, req_ctx(request))
    except service.BankError as exc:
        db.rollback()
        raise _bank_error(exc) from exc
    agents.emit(db, acc.organization_id, "bank.imported", "bank_import", imp.id)
    db.commit()
    background.add_task(agents.dispatch_events)
    return _import_out(imp)


COLUMN_LABELS = {"booking": "Fecha", "value": "Fecha valor", "desc": "Concepto", "amount": "Importe", "debit": "Cargo",
                 "credit": "Abono", "balance": "Saldo", "ref": "Referencia", "party": "Ordenante/beneficiario", "id": "Id"}


@router.post("/accounts/{account_id}/check")
async def check_statement(account_id: uuid.UUID, request: Request, file: UploadFile = File(...),
                          p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Comprueba si el sistema sabe leer un extracto SIN GUARDAR NADA: ni el archivo ni los movimientos.

    Sirve para probar el formato de un banco real en una instalación de prueba. El archivo solo se lee en memoria;
    la auditoría registra que se comprobó (formato y número de líneas), nunca su contenido.
    """
    acc = _account(db, p, account_id, request, "bank.import")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise api_error(422, "validacion", "El extracto supera 10 MB.")
    try:
        st = parsers.parse(data, file.filename or "extracto")
    except parsers.ParseError as exc:
        raise api_error(422, "formato", exc.message) from exc
    total = sum(ln.amount_cents for ln in st.lines)
    balance_ok = None
    if st.opening_cents is not None and st.closing_cents is not None:
        balance_ok = st.opening_cents + total == st.closing_cents and not st.errors
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="bank.statement.check", resource_type="bank_account", resource_id=acc.id,
                             organization_id=acc.organization_id,
                             after={"formato": st.file_format, "lineas": len(st.lines), "errores": len(st.errors),
                                    "guardado": False}, ip=ctx.ip, request_id=ctx.request_id)
    lines_sorted = sorted(st.lines, key=lambda ln: ln.booking_date)
    return {
        "saved": False, "format": st.file_format,
        "columns": [{"field": COLUMN_LABELS.get(k, k), "header": v} for k, v in (st.columns or {}).items()],
        "account_hint": st.account_hint, "account_last4": acc.iban_last4,
        "account_matches": None if st.account_hint is None else st.account_hint == acc.iban_last4,
        "lines": len(st.lines), "period_from": st.period_from.isoformat() if st.period_from else None,
        "period_to": st.period_to.isoformat() if st.period_to else None,
        "credits": {"num": sum(1 for ln in st.lines if ln.amount_cents > 0), "cents": sum(ln.amount_cents for ln in st.lines if ln.amount_cents > 0)},
        "debits": {"num": sum(1 for ln in st.lines if ln.amount_cents < 0), "cents": sum(ln.amount_cents for ln in st.lines if ln.amount_cents < 0)},
        "opening_cents": st.opening_cents, "closing_cents": st.closing_cents, "balance_ok": balance_ok,
        "errors": st.errors[:30], "errors_total": len(st.errors),
        "sample": [{"date": ln.booking_date.isoformat(), "amount_cents": ln.amount_cents, "description": ln.description[:80]}
                   for ln in lines_sorted[:5]],
    }


@router.post("/imports/auto")
async def import_many(request: Request, background: BackgroundTasks, organization_id: uuid.UUID = Form(...),
                      files: list[UploadFile] = File(...), p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> dict:
    """Varios extractos a la vez (Caixa, BBVA…): cada archivo va a la cuenta cuyo IBAN termina como el del extracto.
    Si el extracto no dice la cuenta o hay dos con esos dígitos, NO se adivina: se informa y se importa a mano."""
    if organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(organization_id, "bank.import"):
        _deny(p, request, "bank.import", "organization", organization_id, organization_id, "sin bank.import")
        raise api_error(403, "prohibido", "No puede importar extractos.")
    if len(files) > 40:
        raise api_error(422, "validacion", "Como máximo 40 archivos a la vez.")
    accounts = list(db.execute(select(BankAccount).where(BankAccount.organization_id == organization_id,
                                                         BankAccount.active)).scalars())
    results = []
    for f in files:
        name = f.filename or "extracto"
        data = await f.read(MAX_UPLOAD + 1)
        row: dict = {"file": name}
        try:
            if len(data) > MAX_UPLOAD:
                raise service.BankError("El extracto supera 10 MB.")
            try:
                st = parsers.parse(data, name)
            except parsers.ParseError as exc:
                raise service.BankError(exc.message) from exc
            match = [a for a in accounts if st.account_hint and a.iban_last4 == st.account_hint]
            if not st.account_hint:
                raise service.BankError("El archivo no indica la cuenta: impórtelo desde la cuenta correspondiente.")
            if not match:
                raise service.BankError(f"No hay ninguna cuenta dada de alta que termine en {st.account_hint}. Dela de alta y vuelva a subirlo.")
            if len(match) > 1:
                raise service.BankError(f"Hay {len(match)} cuentas que terminan en {st.account_hint}: impórtelo desde la cuenta correcta.")
            acc = match[0]
            with db.begin_nested():
                imp = service.import_statement(db, acc, data, name, p.id, req_ctx(request))
                agents.emit(db, acc.organization_id, "bank.imported", "bank_import", imp.id)
            row |= {"ok": True, "account": acc.name, "account_last4": acc.iban_last4, **_import_out(imp)}
        except service.BankError as exc:
            row |= {"ok": False, "error": exc.message}
        results.append(row)
    db.commit()
    background.add_task(agents.dispatch_events)
    return {"results": results, "imported": sum(1 for r in results if r["ok"]), "failed": sum(1 for r in results if not r["ok"])}


@router.get("/accounts/{account_id}/imports")
def list_imports(account_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> list[dict]:
    acc = _account(db, p, account_id, request, "bank.read")
    rows = db.execute(select(BankImport).where(BankImport.account_id == acc.id)
                      .order_by(BankImport.imported_at.desc()).limit(100)).scalars()
    return [_import_out(i) for i in rows]


@router.get("/imports/{import_id}/original")
def download_original(import_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> Response:
    i = db.get(BankImport, import_id)
    if i is None or i.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Extracto no encontrado.")
    _account(db, p, i.account_id, request, "bank.read")
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="bank.import.download", resource_type="bank_import", resource_id=i.id,
                 organization_id=i.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    safe = "".join(ch for ch in i.original_name if ch.isalnum() or ch in "._-") or "extracto"
    return Response(vault.load(i.file_path), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{safe}"'})


@router.get("/accounts/{account_id}/demo-statement")
def demo_statement(account_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> Response:
    """Extracto Norma 43 FICTICIO para probar la conciliación. Solo existe en desarrollo y pruebas."""
    if get_settings().app_env not in ("development", "test"):
        raise api_error(404, "no_encontrado", "No disponible.")
    acc = _account(db, p, account_id, request, "bank.import")
    from ..bank.demo import demo_statement as build

    data, name = build(db, acc)
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------------ movimientos
def _target_out(db: Session, bm: BankMatch) -> dict:
    d = {"id": str(bm.id), "target_type": bm.target_type, "target_id": str(bm.target_id), "amount_cents": bm.amount_cents,
         "rule": bm.rule, "explanation": bm.explanation, "status": bm.status, "agent": bm.proposed_by_agent,
         "decided_at": bm.decided_at.isoformat() if bm.decided_at else None, "note": bm.decision_note}
    if bm.target_type == "payment":
        x = db.get(Payment, bm.target_id)
        cf = db.get(CaseFile, x.case_id) if x else None
        d["label"] = f"Cobro {cf.code if cf else ''} · {x.method} · {x.received_at:%d/%m/%Y} · {x.status}" if x else "Cobro"
    elif bm.target_type == "refund":
        x = db.get(Refund, bm.target_id)
        cf = db.get(CaseFile, x.case_id) if x else None
        d["label"] = f"Devolución {cf.code if cf else ''} · {x.status}" if x else "Devolución"
    elif bm.target_type == "invoice":
        from ..models_accounting import Supplier, SupplierInvoice
        inv = db.get(SupplierInvoice, bm.target_id)
        sup = db.get(Supplier, inv.supplier_id) if inv else None
        d["label"] = f"Factura {inv.number} · {sup.name} · {inv.status}" if inv else "Factura"
    else:
        o = db.get(BankMovement, bm.target_id)
        oa = db.get(BankAccount, o.account_id) if o else None
        d["label"] = f"Movimiento {o.booking_date:%d/%m/%Y} · {o.description[:60]} · {oa.name if oa else ''}" if o else "Movimiento"
    return d


def _movement_out(db: Session, m: BankMovement, detail: bool = False) -> dict:
    d = {"id": str(m.id), "account_id": str(m.account_id), "booking_date": m.booking_date.isoformat(),
         "value_date": m.value_date.isoformat() if m.value_date else None, "amount_cents": m.amount_cents,
         "currency": m.currency, "description": m.description, "reference": m.reference,
         "counterparty": m.counterparty, "balance_after_cents": m.balance_after_cents, "status": m.status,
         "category": m.category, "note": m.note, "version": m.version,
         "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None}
    open_prop = db.execute(select(AgentProposal).where(AgentProposal.ref_type == "bank_movement",
                                                       AgentProposal.ref_id == m.id,
                                                       AgentProposal.status == "pendiente")
                           .order_by(AgentProposal.created_at.desc()).limit(1)).scalar_one_or_none()
    d["proposal"] = ({"id": str(open_prop.id), "kind": open_prop.kind, "title": open_prop.title,
                      "detail": open_prop.detail, "priority": open_prop.priority, "payload": open_prop.payload}
                     if open_prop else None)
    if detail:
        d["matches"] = [_target_out(db, bm) for bm in db.execute(
            select(BankMatch).where(BankMatch.movement_id == m.id).order_by(BankMatch.created_at)).scalars()]
        d["reconciled_cents"] = matcher.validated_sum(db, m.id)
    return d


@router.get("/accounts/{account_id}/movements")
def list_movements(account_id: uuid.UUID, request: Request,
                   tab: Literal["importados", "conciliados", "pendientes"] = "pendientes",
                   q: str | None = Query(default=None, max_length=60), date_from: date | None = None,
                   date_to: date | None = None, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    acc = _account(db, p, account_id, request, "bank.read")
    stmt = select(BankMovement).where(BankMovement.account_id == acc.id)
    if tab == "conciliados":
        stmt = stmt.where(BankMovement.status.in_(DONE))
    elif tab == "pendientes":
        stmt = stmt.where(BankMovement.status.in_(PENDING))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(BankMovement.description.ilike(like), BankMovement.reference.ilike(like),
                              BankMovement.counterparty.ilike(like)))
    if date_from:
        stmt = stmt.where(BankMovement.booking_date >= date_from)
    if date_to:
        stmt = stmt.where(BankMovement.booking_date <= date_to)
    rows = list(db.execute(stmt.order_by(BankMovement.booking_date.desc(), BankMovement.id).limit(500)).scalars())
    return {"account": _account_out(db, acc), "items": [_movement_out(db, m) for m in rows]}


@router.get("/accounts/{account_id}/errors")
def list_errors(account_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> list[dict]:
    acc = _account(db, p, account_id, request, "bank.read")
    out = []
    for i in db.execute(select(BankImport).where(BankImport.account_id == acc.id)
                        .order_by(BankImport.imported_at.desc())).scalars():
        for e in i.errors or []:
            out.append({"import_id": str(i.id), "file": i.original_name, "imported_at": i.imported_at.isoformat(),
                        "line": str(e.get("linea")), "error": e.get("error")})
    return out


@router.get("/movements/{movement_id}")
def get_movement(movement_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    m = _movement(db, p, movement_id, request, "bank.read")
    out = _movement_out(db, m, detail=True)
    out["can_reconcile"] = p.has(m.organization_id, "bank.reconcile")
    return out


@router.get("/movements/{movement_id}/candidates")
def candidates(movement_id: uuid.UUID, request: Request, q: str | None = Query(default=None, max_length=40),
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    """Opciones para conciliar a mano: cobros registrados (ingresos), devoluciones pagadas (cargos) y movimientos
    de otras cuentas con el importe contrario (traspasos) o comisiones del mismo día."""
    m = _movement(db, p, movement_id, request, "bank.reconcile")
    lo, hi = m.booking_date - timedelta(days=45), m.booking_date + timedelta(days=10)
    out: list[dict] = []
    taken_pay = select(BankMatch.target_id).where(BankMatch.target_type == "payment", BankMatch.status == "validada")
    if m.amount_cents > 0:
        stmt = (select(Payment, CaseFile, Contact).outerjoin(CaseFile, CaseFile.id == Payment.case_id)
                .join(Contact, Contact.id == Payment.contact_id)
                .where(Payment.organization_id == m.organization_id, Payment.status == "registrado",
                       Payment.method != "efectivo", Payment.id.not_in(taken_pay),
                       func.date(Payment.received_at).between(lo, hi)))
        if q:
            stmt = stmt.where(or_(CaseFile.code.ilike(f"%{q}%"), Contact.search_name.ilike(f"%{q.lower()}%")))
        for x, cf, c in db.execute(stmt.order_by(Payment.received_at.desc()).limit(80)).all():
            out.append({"type": "payment", "id": str(x.id), "amount_cents": x.amount_cents,
                        "label": f"{cf.code if cf else 'Consulta'} · {c.given_name} {c.family_names} · {x.method} · {x.received_at:%d/%m/%Y}",
                        "exact": x.amount_cents == m.amount_cents})
    else:
        from ..models_accounting import Supplier, SupplierInvoice
        taken_inv = select(BankMatch.target_id).where(BankMatch.target_type == "invoice", BankMatch.status == "validada")
        for inv in db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == m.organization_id,
                                                            SupplierInvoice.status.in_(("validada", "programada")),
                                                            SupplierInvoice.id.not_in(taken_inv))
                              .order_by(SupplierInvoice.due_date).limit(80)).scalars():
            sup = db.get(Supplier, inv.supplier_id)
            if q and q.lower() not in f"{sup.name} {inv.number}".lower():
                continue
            out.append({"type": "invoice", "id": str(inv.id), "amount_cents": -inv.total_cents,
                        "label": f"Factura {inv.number} · {sup.name} · vence {inv.due_date:%d/%m/%Y}" if inv.due_date
                        else f"Factura {inv.number} · {sup.name}", "exact": inv.total_cents == -m.amount_cents})
        taken_ref = select(BankMatch.target_id).where(BankMatch.target_type == "refund", BankMatch.status == "validada")
        for r in db.execute(select(Refund).where(Refund.organization_id == m.organization_id, Refund.status == "pagada",
                                                 Refund.id.not_in(taken_ref))
                            .order_by(Refund.paid_at.desc()).limit(50)).scalars():
            cf = db.get(CaseFile, r.case_id)
            out.append({"type": "refund", "id": str(r.id), "amount_cents": -r.amount_cents,
                        "label": f"Devolución {cf.code} · {r.pay_method} · {r.paid_at:%d/%m/%Y}" if r.paid_at else f"Devolución {cf.code}",
                        "exact": r.amount_cents == -m.amount_cents})
    for o in db.execute(select(BankMovement).where(
            BankMovement.organization_id == m.organization_id, BankMovement.id != m.id,
            BankMovement.status.in_(PENDING),
            BankMovement.booking_date.between(m.booking_date - timedelta(days=5), m.booking_date + timedelta(days=5)),
            or_(BankMovement.amount_cents == -m.amount_cents,
                (BankMovement.account_id == m.account_id) & (BankMovement.amount_cents < 0) & (m.amount_cents > 0)))
            .limit(30)).scalars():
        oa = db.get(BankAccount, o.account_id)
        amount = -o.amount_cents if o.amount_cents == -m.amount_cents else o.amount_cents
        out.append({"type": "movement", "id": str(o.id), "amount_cents": amount,
                    "label": f"{'Traspaso' if amount == m.amount_cents else 'Cargo'} {oa.name} · {o.booking_date:%d/%m/%Y} · {o.description[:50]}",
                    "exact": amount == m.amount_cents})
    return out


class DecideIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


def _pending_proposal(db: Session, m: BankMovement, kind: str) -> AgentProposal | None:
    return db.execute(select(AgentProposal).where(AgentProposal.ref_type == "bank_movement",
                                                  AgentProposal.ref_id == m.id, AgentProposal.kind == kind,
                                                  AgentProposal.status == "pendiente")).scalar_one_or_none()


@router.post("/movements/{movement_id}/validate")
def validate(movement_id: uuid.UUID, body: DecideIn, request: Request, background: BackgroundTasks,
             p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    m = _movement(db, p, movement_id, request, "bank.reconcile")
    db.execute(select(BankMovement).where(BankMovement.id == m.id).with_for_update())
    prop = _pending_proposal(db, m, "conciliacion")
    if prop is None:
        raise api_error(409, "conflicto", "No hay ninguna propuesta de emparejamiento pendiente para este movimiento.")
    try:
        engine.decide(db, prop, p, True, body.note, req_ctx(request))
    except ApplyError as exc:
        db.rollback()
        raise _bank_error(exc) from exc
    db.commit()
    return _movement_out(db, m, detail=True)


@router.post("/movements/{movement_id}/reject")
def reject(movement_id: uuid.UUID, body: DecideIn, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    m = _movement(db, p, movement_id, request, "bank.reconcile")
    prop = _pending_proposal(db, m, "conciliacion")
    if prop is None:
        raise api_error(409, "conflicto", "No hay ninguna propuesta de emparejamiento pendiente para este movimiento.")
    if not (body.note or "").strip() or len(body.note.strip()) < 5:
        raise api_error(422, "validacion", "Indique por qué no es correcto (mín. 5 caracteres).")
    engine.decide(db, prop, p, False, body.note, req_ctx(request))
    db.commit()
    return _movement_out(db, m, detail=True)


class TargetIn(BaseModel):
    type: Literal["payment", "refund", "movement", "invoice"]
    id: uuid.UUID


class ManualIn(BaseModel):
    targets: list[TargetIn] = Field(min_length=1, max_length=20)
    note: str = Field(min_length=5, max_length=500)
    version: int = Field(ge=1)


@router.post("/movements/{movement_id}/manual")
def manual(movement_id: uuid.UUID, body: ManualIn, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    m = _movement(db, p, movement_id, request, "bank.reconcile")
    db.execute(select(BankMovement).where(BankMovement.id == m.id).with_for_update())
    db.refresh(m)
    if m.version != body.version:
        raise api_error(409, "conflicto_version", "El movimiento ha cambiado. Recargue.")
    try:
        service.manual_match(db, m, [(t.type, t.id) for t in body.targets], p, req_ctx(request), body.note.strip())
    except service.BankError as exc:
        db.rollback()
        raise _bank_error(exc) from exc
    db.commit()
    return _movement_out(db, m, detail=True)


class JustifyIn(BaseModel):
    category: Literal[CATEGORIES]  # type: ignore[valid-type]
    note: str = Field(min_length=5, max_length=500)
    ignore: bool = False
    version: int = Field(ge=1)


@router.post("/movements/{movement_id}/justify")
def justify(movement_id: uuid.UUID, body: JustifyIn, request: Request, p: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> dict:
    m = _movement(db, p, movement_id, request, "bank.reconcile")
    db.execute(select(BankMovement).where(BankMovement.id == m.id).with_for_update())
    db.refresh(m)
    if m.version != body.version:
        raise api_error(409, "conflicto_version", "El movimiento ha cambiado. Recargue.")
    try:
        service.justify(db, m, body.category, p, req_ctx(request), body.note.strip(), ignore=body.ignore)
    except service.BankError as exc:
        db.rollback()
        raise _bank_error(exc) from exc
    db.commit()
    return _movement_out(db, m, detail=True)


@router.get("/accounts/{account_id}/export.csv")
def export_csv(account_id: uuid.UUID, request: Request, date_from: date | None = None, date_to: date | None = None,
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> Response:
    """Exportación para la gestoría (T-40: hasta tener plan de cuentas no se proponen asientos)."""
    acc = _account(db, p, account_id, request, "bank.read")
    stmt = select(BankMovement).where(BankMovement.account_id == acc.id)
    if date_from:
        stmt = stmt.where(BankMovement.booking_date >= date_from)
    if date_to:
        stmt = stmt.where(BankMovement.booking_date <= date_to)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Fecha", "Fecha valor", "Concepto", "Referencia", "Importe", "Estado", "Categoría", "Conciliado con",
                "Nota"])
    for m in db.execute(stmt.order_by(BankMovement.booking_date, BankMovement.id)).scalars():
        with_ = "; ".join(_target_out(db, bm)["label"] for bm in db.execute(
            select(BankMatch).where(BankMatch.movement_id == m.id, BankMatch.status == "validada")).scalars())
        w.writerow([m.booking_date.strftime("%d/%m/%Y"), m.value_date.strftime("%d/%m/%Y") if m.value_date else "",
                    m.description, m.reference or "", f"{m.amount_cents / 100:.2f}".replace(".", ","), m.status,
                    m.category or "", with_, m.note or ""])
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="bank.export", resource_type="bank_account", resource_id=acc.id,
                 organization_id=acc.organization_id,
                 after={"desde": date_from.isoformat() if date_from else None, "hasta": date_to.isoformat() if date_to else None},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="movimientos_{acc.iban_last4}.csv"'})


@router.post("/reconcile/run")
def run_now(request: Request, organization_id: uuid.UUID = Query(...), p: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> dict:
    if organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(organization_id, "bank.reconcile"):
        _deny(p, request, "bank.reconcile.run", "agent", None, organization_id, "sin bank.reconcile")
        raise api_error(403, "prohibido", "Solo Contabilidad lanza la conciliación.")
    runs = engine.run_scheduled(db, only="conciliacion", user_id=p.id, org_ids={organization_id})
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="agent.run", resource_type="agent", resource_id=None,
                 organization_id=organization_id, after={"agente": "conciliacion"}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"runs": [{"id": str(r.id), "status": r.status, "summary": r.summary, "error": r.error} for r in runs]}
