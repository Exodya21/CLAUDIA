"""Recepción (F5.2): cobrar, justificante no fiscal, caja del día, cierre validado e informe por sede.

Permisos: cobrar = `payment.register` + `cash.operate` en ESA sede; ver lo pendiente de un expediente =
`reception.balance` (solo importes); validar cierres = `cash.close.validate`; ver otras sedes = `cash.read.all`.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import agents, audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, CaseFile, Contact, Organization
from ..models_economy import CashClosing, CashMovement, Payment
from ..reception import service as svc
from ..security.auth import Principal, get_principal
from ..security.policy import contact_level, contacts_with_full_case, load_case_scope
from .common import req_ctx
from .economy import MAX_CENTS, _uname, totals

router = APIRouter(prefix="/reception", tags=["recepción"])


def _deny(p: Principal, request: Request, action: str, rtype: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type=rtype, resource_id=rid, organization_id=org,
                             outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _err(e: svc.ReceptionError):
    return api_error(e.status, e.code, e.message, e.details)


def operable(p: Principal, b: Branch) -> bool:
    return any(m.branch_id in (None, b.id) for m in p.memberships_with(b.organization_id, "cash.operate"))


def viewable(p: Principal, b: Branch) -> bool:
    return operable(p, b) or p.has(b.organization_id, "cash.read.all")


def _branch(db: Session, p: Principal, branch_id: uuid.UUID, request: Request, write: bool, action: str) -> Branch:
    b = db.get(Branch, branch_id)
    if b is None or b.organization_id not in p.org_ids() or b.kind != "sede":
        raise api_error(404, "no_encontrado", "Sede no encontrada.")
    if not (operable(p, b) if write else viewable(p, b)):
        _deny(p, request, action, "branch", b.id, b.organization_id, "sede fuera de su ámbito")
        raise api_error(403, "prohibido", "Solo trabaja con la recepción y la caja de su sede.")
    return b


@router.get("/branches")
def branches(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    out = []
    for org in p.org_ids():
        for b in db.execute(select(Branch).where(Branch.organization_id == org, Branch.kind == "sede")
                            .order_by(Branch.name)).scalars():
            if viewable(p, b):
                out.append({"id": str(b.id), "name": b.name, "organization_id": str(org),
                            "organization": db.get(Organization, org).name, "currency": db.get(Organization, org).currency,
                            "can_operate": operable(p, b), "can_charge": operable(p, b) and p.has(org, "payment.register"),
                            "can_validate": p.has(org, "cash.close.validate"),
                            "can_balance": p.has(org, "reception.balance")})
    return out


# ------------------------------------------------------------------ cobrar
@router.get("/contacts/{contact_id}/cases")
def contact_cases(contact_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    """Expedientes de un cliente para elegir a qué se cobra: código, materia, fase y, con `reception.balance`,
    cuánto queda por cobrar (sin contenido jurídico)."""
    c = db.get(Contact, contact_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cliente no encontrado.")
    org = c.organization_id
    if contact_level(p, c, contacts_with_full_case(db, p, load_case_scope(db, p))) is None:
        raise api_error(404, "no_encontrado", "Cliente no encontrado.")
    show_balance = p.has(org, "reception.balance") or p.has(org, "economy.read.all")
    rows = []
    for cf in db.execute(select(CaseFile).where(CaseFile.contact_id == c.id).order_by(CaseFile.created_at.desc())).scalars():
        d = {"id": str(cf.id), "code": cf.code, "materia": cf.materia, "status": cf.status}
        if show_balance:
            t = totals(db, cf.id)
            d |= {"cargado_cents": t["cargado"], "cobrado_cents": t["cobrado"], "pendiente_cents": t["pendiente"]}
        rows.append(d)
    if show_balance and rows:
        ctx = req_ctx(request)
        audit.record_independent(actor_id=p.id, action="reception.balance.read", resource_type="contact",
                                 resource_id=c.id, organization_id=org, ip=ctx.ip, request_id=ctx.request_id)
    return {"contact": {"id": str(c.id), "name": f"{c.given_name} {c.family_names}", "organization_id": str(org)},
            "cases": rows, "show_balance": show_balance}


class ChargeIn(BaseModel):
    branch_id: uuid.UUID
    contact_id: uuid.UUID
    case_id: uuid.UUID | None = None
    kind: Literal["consulta", "provision", "servicio", "otro"]
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    method: Literal["efectivo", "tarjeta", "bizum", "transferencia"]
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    duplicate_reason: str | None = Field(default=None, max_length=300)


def _pay_out(db: Session, x: Payment) -> dict:
    cf = db.get(CaseFile, x.case_id) if x.case_id else None
    c = db.get(Contact, x.contact_id)
    r = svc.receipt_for(db, x.id)
    return {"id": str(x.id), "kind": x.kind, "amount_cents": x.amount_cents, "currency": x.currency, "method": x.method,
            "received_at": x.received_at.isoformat(), "reference": x.reference, "status": x.status,
            "case_code": cf.code if cf else None, "contact_name": f"{c.given_name} {c.family_names}",
            "registered_by": _uname(db, x.registered_by), "duplicate_reason": x.duplicate_reason,
            "receipt": {"number": r.number, "url": f"/reception/payments/{x.id}/receipt.pdf"} if r else None}


@router.post("/payments", status_code=201)
def charge(body: ChargeIn, request: Request, background: BackgroundTasks, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    b = _branch(db, p, body.branch_id, request, True, "reception.charge")
    org = b.organization_id
    if not p.has(org, "payment.register"):
        _deny(p, request, "reception.charge", "branch", b.id, org, "sin payment.register")
        raise api_error(403, "prohibido", "Su perfil no registra cobros.")
    c = db.get(Contact, body.contact_id)
    if c is None or c.organization_id != org:
        raise api_error(422, "validacion", "El cliente no es de esta entidad.", [{"field": "contact_id", "message": "No válido"}])
    cf = None
    if body.case_id:
        cf = db.get(CaseFile, body.case_id)
        if cf is None or cf.contact_id != c.id:
            raise api_error(422, "validacion", "El expediente no es de este cliente.", [{"field": "case_id", "message": "No válido"}])
        if cf.status in ("archivado", "desistido"):
            raise api_error(409, "conflicto", f"El expediente {cf.code} está {cf.status}.")
    elif body.kind != "consulta":
        raise api_error(422, "validacion", "Una provisión o un servicio se cobra a un expediente. Sin expediente solo se "
                        "cobra una consulta.", [{"field": "case_id", "message": "Elija el expediente"}])
    if body.method in ("transferencia", "bizum") and not (body.reference or "").strip():
        raise api_error(422, "validacion", "Indique la referencia de la transferencia o del Bizum.",
                        [{"field": "reference", "message": "Obligatoria"}])
    dups = svc.possible_duplicates(db, org, c.id, body.amount_cents, body.method, body.reference)
    reason = (body.duplicate_reason or "").strip()
    if dups and len(reason) < 10:
        raise api_error(409, "posible_duplicado",
                        "Parece que este cobro ya está registrado. Compruébelo; si es otro cobro distinto, explique por qué.",
                        [_pay_out(db, x) for x in dups])
    x = Payment(organization_id=org, case_id=cf.id if cf else None, contact_id=c.id, branch_id=b.id,
                amount_cents=body.amount_cents, currency=db.get(Organization, org).currency, method=body.method,
                received_at=svc.now(), reference=(body.reference or "").strip() or None, notes=body.notes,
                registered_by=p.id, kind=body.kind, duplicate_reason=reason if dups else None)
    db.add(x)
    db.flush()
    if body.method == "efectivo":
        db.add(CashMovement(organization_id=org, branch_id=b.id, kind="cobro", amount_cents=body.amount_cents,
                            currency=x.currency, concept=f"Cobro {svc.KINDS[body.kind].lower()} "
                            f"{cf.code if cf else c.given_name + ' ' + c.family_names}"[:200], payment_id=x.id,
                            created_by=p.id))
    r = svc.issue_receipt(db, x, p.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="payment.register", resource_type="case_file" if cf else "contact",
                 resource_id=cf.id if cf else c.id, organization_id=org,
                 after={"cobro": str(x.id), "tipo": x.kind, "importe": x.amount_cents, "forma": x.method,
                        "sede": b.name, "justificante": r.number, "posible_duplicado": bool(dups)},
                 reason=reason if dups else None, ip=ctx.ip, request_id=ctx.request_id)
    if dups:
        agents.emit(db, org, "payment.duplicate_override", "payment", x.id,
                    {"parecidos": [str(d.id) for d in dups], "motivo": reason})
    db.commit()
    background.add_task(agents.dispatch_events)
    return _pay_out(db, x)


@router.get("/payments/{payment_id}/receipt.pdf")
def receipt_pdf(payment_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> Response:
    x = db.get(Payment, payment_id)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cobro no encontrado.")
    b = db.get(Branch, x.branch_id) if x.branch_id else None
    allowed = p.has(x.organization_id, "payment.confirm") or (b is not None and viewable(p, b))
    if not allowed:
        _deny(p, request, "reception.receipt", "payment", x.id, x.organization_id, "fuera de su sede")
        raise api_error(403, "prohibido", "Este justificante es de otra sede.")
    r = svc.receipt_for(db, x.id)
    if r is None:
        raise api_error(404, "no_encontrado", "Este cobro no tiene justificante (se registró antes de F5.2).")
    try:
        data = svc.receipt_bytes(r)
    except svc.ReceptionError as e:
        raise _err(e) from e
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="reception.receipt.download", resource_type="payment",
                             resource_id=x.id, organization_id=x.organization_id, after={"justificante": r.number},
                             ip=ctx.ip, request_id=ctx.request_id)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r.number}.pdf"'})


# ------------------------------------------------------------------ caja del día
def _closing_out(db: Session, c: CashClosing | None) -> dict | None:
    if c is None:
        return None
    return {"id": str(c.id), "day": c.day.isoformat() if c.day else None, "expected_cents": c.expected_cents,
            "counted_cents": c.counted_cents, "difference_cents": c.difference_cents, "notes": c.notes,
            "status": c.status, "closed_by": _uname(db, c.closed_by), "closed_by_id": str(c.closed_by),
            "closed_at": c.closed_at.isoformat(), "validated_by": _uname(db, c.validated_by),
            "validated_at": c.validated_at.isoformat() if c.validated_at else None, "validation_note": c.validation_note,
            "branch_id": str(c.branch_id), "branch": db.get(Branch, c.branch_id).name}


@router.get("/day")
def day_view(request: Request, branch_id: uuid.UUID, day: date | None = None, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)) -> dict:
    b = _branch(db, p, branch_id, request, False, "reception.day")
    tz = svc.tz_for(b)
    d = day or svc.today_at(b)
    start, end = svc.day_bounds(d, tz)
    pays = list(db.execute(select(Payment).where(Payment.branch_id == b.id, Payment.received_at >= start,
                                                 Payment.received_at < end).order_by(Payment.received_at)).scalars())
    moves = list(db.execute(select(CashMovement).where(CashMovement.branch_id == b.id, CashMovement.at >= start,
                                                       CashMovement.at < end).order_by(CashMovement.at)).scalars())
    opening = svc.balance(db, b.id, start)
    closing = db.execute(select(CashClosing).where(CashClosing.branch_id == b.id, CashClosing.day == d)
                         .order_by(CashClosing.closed_at.desc())).scalars().all()
    is_today = d == svc.today_at(b)
    live = [x for x in pays if x.status != "anulado"]
    by_method: dict[str, int] = {}
    for x in live:
        by_method[x.method] = by_method.get(x.method, 0) + x.amount_cents
    return {
        "branch": {"id": str(b.id), "name": b.name}, "day": d.isoformat(), "is_today": is_today,
        "currency": db.get(Organization, b.organization_id).currency,
        "payments": [_pay_out(db, x) for x in pays],
        "totals": {"cobros": len(live), "importe_cents": sum(x.amount_cents for x in live), "por_forma": by_method},
        "cash": {"opening_cents": opening, "movements": [{"id": str(m.id), "kind": m.kind, "amount_cents": m.amount_cents,
                                                          "concept": m.concept, "at": m.at.isoformat(),
                                                          "by": _uname(db, m.created_by)} for m in moves],
                 "in_cents": sum(m.amount_cents for m in moves if m.amount_cents > 0),
                 "out_cents": sum(m.amount_cents for m in moves if m.amount_cents < 0),
                 "balance_cents": svc.balance(db, b.id, end) if not is_today else svc.balance(db, b.id)},
        "closings": [_closing_out(db, c) for c in closing],
        "can_close": is_today and operable(p, b) and svc.closing_of_day(db, b.id, d) is None,
        "can_charge": is_today and operable(p, b) and p.has(b.organization_id, "payment.register"),
    }


class CloseIn(BaseModel):
    counted_cents: int = Field(ge=0, le=MAX_CENTS)
    notes: str | None = Field(default=None, max_length=500)


@router.post("/cash/{branch_id}/close", status_code=201)
def close(branch_id: uuid.UUID, body: CloseIn, request: Request, background: BackgroundTasks,
          p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    b = _branch(db, p, branch_id, request, True, "cash.closing")
    db.execute(select(Branch).where(Branch.id == b.id).with_for_update())
    try:
        c = svc.close_day(db, b, body.counted_cents, body.notes, p.id, req_ctx(request))
    except svc.ReceptionError as e:
        db.rollback()
        raise _err(e) from e
    db.commit()
    background.add_task(agents.dispatch_events)
    return _closing_out(db, c)


@router.get("/closings")
def list_closings(request: Request, status: Literal["pendiente_validacion", "validado", "rechazado"] = "pendiente_validacion",
                  p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = p.orgs_with("cash.close.validate")
    rows = []
    for c in db.execute(select(CashClosing).where(CashClosing.organization_id.in_(p.org_ids()),
                                                  CashClosing.status == status, CashClosing.day.is_not(None))
                        .order_by(CashClosing.closed_at.desc()).limit(100)).scalars():
        b = db.get(Branch, c.branch_id)
        if c.organization_id in orgs or viewable(p, b):
            d = _closing_out(db, c)
            d["can_decide"] = c.organization_id in orgs and c.closed_by != p.id and c.status == "pendiente_validacion"
            rows.append(d)
    return rows


class DecideIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


@router.post("/closings/{closing_id}/decide")
def decide(closing_id: uuid.UUID, body: DecideIn, request: Request, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    from ..agents.engine import decide as decide_proposal
    from ..models_agents import AgentProposal

    c = db.get(CashClosing, closing_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cierre no encontrado.")
    db.execute(select(CashClosing).where(CashClosing.id == c.id).with_for_update())
    db.refresh(c)
    if not p.has(c.organization_id, "cash.close.validate"):
        _deny(p, request, "cash.closing.validate", "branch", c.branch_id, c.organization_id, "sin cash.close.validate")
        raise api_error(403, "prohibido", "Solo un responsable valida el cierre de caja.")
    ctx = req_ctx(request)
    prop = db.execute(select(AgentProposal).where(AgentProposal.ref_type == "cash_closing", AgentProposal.ref_id == c.id,
                                                  AgentProposal.status == "pendiente")).scalar_one_or_none()
    try:
        if prop is not None:
            decide_proposal(db, prop, p, body.approve, body.note, ctx)
        else:
            svc.decide_closing(db, c, p, body.approve, body.note, ctx)
    except svc.ReceptionError as e:
        db.rollback()
        raise _err(e) from e
    except Exception as e:  # ApplyError del agente
        from ..agents.base import ApplyError
        if isinstance(e, ApplyError):
            db.rollback()
            raise api_error(e.status, "conflicto" if e.status == 409 else ("prohibido" if e.status == 403 else "validacion"),
                            e.message) from e
        raise
    db.commit()
    return _closing_out(db, c)


# ------------------------------------------------------------------ informe diario / semanal (DR-REC-10)
@router.get("/report")
def report(request: Request, date_from: date = Query(alias="from"), date_to: date = Query(alias="to"),
           branch_id: uuid.UUID | None = None, p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    if date_to < date_from or (date_to - date_from).days > 62:
        raise api_error(422, "validacion", "Periodo no válido (máximo dos meses).")
    sedes = []
    for org in p.org_ids():
        for b in db.execute(select(Branch).where(Branch.organization_id == org, Branch.kind == "sede")
                            .order_by(Branch.name)).scalars():
            if viewable(p, b) and (branch_id is None or b.id == branch_id):
                sedes.append(b)
    if not sedes:
        _deny(p, request, "reception.report", "branch", branch_id, None, "sin sedes visibles")
        raise api_error(403, "prohibido", "No tiene sedes a su cargo.")
    out = []
    for b in sedes:
        tz = svc.tz_for(b)
        days = []
        d = date_from
        while d <= date_to:
            start, end = svc.day_bounds(d, tz)
            pays = [x for x in db.execute(select(Payment).where(Payment.branch_id == b.id, Payment.received_at >= start,
                                                                Payment.received_at < end)).scalars()]
            live = [x for x in pays if x.status != "anulado"]
            kinds: dict[str, int] = {}
            methods: dict[str, int] = {}
            for x in live:
                kinds[x.kind or "sin_tipo"] = kinds.get(x.kind or "sin_tipo", 0) + 1
                methods[x.method] = methods.get(x.method, 0) + x.amount_cents
            refunds_cash = sum(-m.amount_cents for m in db.execute(select(CashMovement).where(
                CashMovement.branch_id == b.id, CashMovement.kind == "devolucion", CashMovement.at >= start,
                CashMovement.at < end)).scalars())
            cl = db.execute(select(CashClosing).where(CashClosing.branch_id == b.id, CashClosing.day == d,
                                                      CashClosing.status != "rechazado")).scalars().first()
            days.append({"day": d.isoformat(), "cobros": len(live), "importe_cents": sum(x.amount_cents for x in live),
                         "por_tipo": kinds, "por_forma": methods, "anulados": len(pays) - len(live),
                         "posibles_duplicados": sum(1 for x in pays if x.duplicate_reason),
                         "devoluciones_efectivo_cents": refunds_cash,
                         "cierre": None if cl is None else {"estado": cl.status, "diferencia_cents": cl.difference_cents}})
            d += timedelta(days=1)
        out.append({"branch_id": str(b.id), "branch": b.name, "currency": db.get(Organization, b.organization_id).currency,
                    "days": days,
                    "total": {"cobros": sum(x["cobros"] for x in days), "importe_cents": sum(x["importe_cents"] for x in days),
                              "dias_sin_cierre": sum(1 for x in days if x["cobros"] and not x["cierre"]),
                              "diferencias_cents": sum((x["cierre"] or {}).get("diferencia_cents", 0) for x in days)}})
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="reception.report", resource_type="branch", resource_id=branch_id,
                             organization_id=sedes[0].organization_id,
                             after={"desde": date_from.isoformat(), "hasta": date_to.isoformat()},
                             ip=ctx.ip, request_id=ctx.request_id)
    return {"from": date_from.isoformat(), "to": date_to.isoformat(), "branches": out,
            "no_disponible": "Visitas y citas atendidas: no disponible aún (F5.5, citas propias)."}

