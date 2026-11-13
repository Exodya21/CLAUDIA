"""Control económico NO fiscal (F5.0): importes pactados, cobros, devoluciones, cajas por sede y resumen.

Reglas (A-09, D-05, D-07, D-16, D-18, D-25):
- El sistema no emite facturas ni calcula honorarios, IVA o suplidos: las cifras las introduce una persona.
- ATC registra, investiga y escala devoluciones; el letrado puede informar; SOLO Contabilidad aprueba o rechaza y
  paga, y nunca quien la solicitó. No se aprueba más de lo cobrado y confirmado.
- Nada se borra: anulaciones con motivo; la caja se corrige con movimientos; todo queda en la auditoría.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, CaseFile, Contact, Organization, UserAccount
from ..models_economy import CashClosing, CashMovement, Charge, Payment, Refund, RefundEvent
from ..security.auth import Principal, get_principal
from ..security.policy import case_level, load_case_scope
from .common import ReqCtx, req_ctx

router = APIRouter(prefix="/economy", tags=["economía"])
MAX_CENTS = 100_000_000  # 1.000.000,00


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ esquemas
class ChargeIn(BaseModel):
    kind: Literal["honorarios", "gasto_cliente", "otro"]
    concept: str = Field(min_length=3, max_length=200)
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    due_date: date | None = None


class PaymentIn(BaseModel):
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    method: Literal["efectivo", "tarjeta", "transferencia", "bizum"]
    received_at: datetime | None = None
    branch_id: uuid.UUID | None = None
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class ConfirmIn(BaseModel):
    invoice_ref: str | None = Field(default=None, max_length=60)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class RefundIn(BaseModel):
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    reason: str = Field(min_length=10, max_length=2000)


class RefundTransitionIn(BaseModel):
    to: Literal["en_revision", "escalada_legal", "aprobada", "rechazada", "pagada"]
    note: str | None = Field(default=None, max_length=2000)
    pay_method: Literal["transferencia", "efectivo", "tarjeta", "bizum"] | None = None
    pay_reference: str | None = Field(default=None, max_length=120)
    pay_branch_id: uuid.UUID | None = None
    version: int | None = None


class CashMovementIn(BaseModel):
    kind: Literal["gasto", "ingreso_banco", "aportacion"]
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    concept: str = Field(min_length=3, max_length=200)


class ClosingIn(BaseModel):
    counted_cents: int = Field(ge=0, le=MAX_CENTS)
    notes: str | None = Field(default=None, max_length=500)


# ------------------------------------------------------------------ acceso
def _deny(p: Principal, ctx: ReqCtx, action: str, rtype: str, rid, org, reason: str) -> None:
    audit.record_independent(actor_id=p.id, action=action, resource_type=rtype, resource_id=rid, organization_id=org,
                             outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def can_read_economy(p: Principal, cf: CaseFile, level: str | None) -> bool:
    org = cf.organization_id
    return p.has(org, "economy.read.all") or (p.has(org, "economy.read.case") and level == "full")


def _case(db: Session, p: Principal, case_id: uuid.UUID, request: Request, action: str,
          need: str = "read", perm: str | None = None) -> tuple[CaseFile, str | None]:
    """need='read': ver la economía del expediente. need='meta': basta con verlo (p. ej. Recepción cobra)."""
    ctx = req_ctx(request)
    cf = db.get(CaseFile, case_id)
    if cf is None or cf.organization_id not in p.org_ids():
        _deny(p, ctx, action, "case_file", case_id, cf.organization_id if cf else None, "fuera de entidad o inexistente")
        raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    level = case_level(p, cf, load_case_scope(db, p))
    ok = can_read_economy(p, cf, level) if need == "read" else level is not None
    if perm and not p.has(cf.organization_id, perm):
        ok = False
    if not ok:
        _deny(p, ctx, action, "case_file", cf.id, cf.organization_id, f"sin permiso económico ({perm or need})")
        raise api_error(403, "prohibido", "Su rol no permite esta operación económica en este expediente. "
                                          "El intento ha quedado registrado.")
    return cf, level


def _currency(db: Session, org: uuid.UUID) -> str:
    return db.get(Organization, org).currency


def _uname(db: Session, uid: uuid.UUID | None) -> str | None:
    return db.get(UserAccount, uid).full_name if uid else None


def _contact_name(db: Session, cid: uuid.UUID) -> str:
    c = db.get(Contact, cid)
    return f"{c.given_name} {c.family_names}"


def totals(db: Session, case_id: uuid.UUID) -> dict:
    charged = db.execute(select(func.coalesce(func.sum(Charge.amount_cents), 0)).where(
        Charge.case_id == case_id, Charge.status == "vigente")).scalar_one()
    paid = db.execute(select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
        Payment.case_id == case_id, Payment.status != "anulado")).scalar_one()
    confirmed = db.execute(select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
        Payment.case_id == case_id, Payment.status == "confirmado")).scalar_one()
    refunded = db.execute(select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
        Refund.case_id == case_id, Refund.status == "pagada")).scalar_one()
    committed = db.execute(select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
        Refund.case_id == case_id, Refund.status.in_(("aprobada", "pagada")))).scalar_one()
    charged, paid, confirmed, refunded, committed = map(int, (charged, paid, confirmed, refunded, committed))
    return {"cargado": charged, "cobrado": paid, "cobrado_confirmado": confirmed, "devuelto": refunded,
            "pendiente": charged - (paid - refunded), "devolvible": confirmed - committed}


def _charge_out(db: Session, c: Charge) -> dict:
    return {"id": str(c.id), "kind": c.kind, "concept": c.concept, "amount_cents": c.amount_cents,
            "currency": c.currency, "due_date": c.due_date.isoformat() if c.due_date else None, "status": c.status,
            "created_by": _uname(db, c.created_by), "created_at": c.created_at.isoformat(),
            "cancel_reason": c.cancel_reason}


def _payment_out(db: Session, x: Payment, with_case: bool = False) -> dict:
    out = {"id": str(x.id), "amount_cents": x.amount_cents, "currency": x.currency, "method": x.method,
           "received_at": x.received_at.isoformat(), "reference": x.reference, "notes": x.notes, "status": x.status,
           "invoice_ref": x.invoice_ref, "branch": db.get(Branch, x.branch_id).name if x.branch_id else None,
           "registered_by": _uname(db, x.registered_by), "confirmed_by": _uname(db, x.confirmed_by),
           "annul_reason": x.annul_reason}
    if with_case:
        cf = db.get(CaseFile, x.case_id) if x.case_id else None
        out |= {"case_id": str(cf.id) if cf else None, "case_code": cf.code if cf else "Consulta (sin expediente)",
                "contact_name": _contact_name(db, x.contact_id), "organization_id": str(x.organization_id)}
    out["kind"] = x.kind
    return out


def _refund_out(db: Session, r: Refund, with_case: bool = True, events: bool = False) -> dict:
    out = {"id": str(r.id), "amount_cents": r.amount_cents, "currency": r.currency, "reason": r.reason,
           "status": r.status, "requested_by": _uname(db, r.requested_by), "requested_by_id": str(r.requested_by),
           "created_at": r.created_at.isoformat(), "legal_opinion": r.legal_opinion,
           "legal_opinion_by": _uname(db, r.legal_opinion_by), "decided_by": _uname(db, r.decided_by),
           "decision_reason": r.decision_reason, "paid_at": r.paid_at.isoformat() if r.paid_at else None,
           "pay_method": r.pay_method, "pay_reference": r.pay_reference, "version": r.version,
           "organization_id": str(r.organization_id)}
    if with_case:
        cf = db.get(CaseFile, r.case_id)
        out |= {"case_id": str(cf.id), "case_code": cf.code, "materia": cf.materia,
                "contact_name": _contact_name(db, r.contact_id)}
    if events:
        evs = db.execute(select(RefundEvent).where(RefundEvent.refund_id == r.id).order_by(RefundEvent.at)).scalars()
        out["events"] = [{"from": e.from_status, "to": e.to_status, "note": e.note, "actor": _uname(db, e.actor_user_id),
                          "at": e.at.isoformat()} for e in evs]
    return out


def _cash(db: Session, org: uuid.UUID, branch_id: uuid.UUID, kind: str, cents: int, concept: str, actor: uuid.UUID,
          payment_id=None, refund_id=None) -> CashMovement:
    m = CashMovement(organization_id=org, branch_id=branch_id, kind=kind, amount_cents=cents,
                     currency=_currency(db, org), concept=concept[:200], payment_id=payment_id, refund_id=refund_id,
                     created_by=actor)
    db.add(m)
    return m


def _branch_ok(db: Session, org: uuid.UUID, branch_id: uuid.UUID | None) -> Branch:
    b = db.get(Branch, branch_id) if branch_id else None
    if b is None or b.organization_id != org:
        raise api_error(422, "validacion", "Indique la sede (caja) de la entidad.", [{"field": "branch_id", "message": "Sede no válida"}])
    return b


# ------------------------------------------------------------------ economía del expediente
@router.get("/cases/{case_id}")
def case_economy(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    cf, _ = _case(db, p, case_id, request, "economy.read")
    org = cf.organization_id
    charges = db.execute(select(Charge).where(Charge.case_id == cf.id).order_by(Charge.created_at)).scalars()
    payments = db.execute(select(Payment).where(Payment.case_id == cf.id).order_by(Payment.received_at)).scalars()
    refunds = db.execute(select(Refund).where(Refund.case_id == cf.id).order_by(Refund.created_at)).scalars()
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="economy.read", resource_type="case_file", resource_id=cf.id,
                             organization_id=org, ip=ctx.ip, request_id=ctx.request_id)
    return {
        "case_id": str(cf.id), "code": cf.code, "currency": _currency(db, org), "totals": totals(db, cf.id),
        "charges": [_charge_out(db, c) for c in charges], "payments": [_payment_out(db, x) for x in payments],
        "refunds": [_refund_out(db, r, with_case=False) for r in refunds],
        "can": {"charge": p.has(org, "charge.create"), "cancel_charge": p.has(org, "charge.cancel"),
                "pay": p.has(org, "payment.register"), "confirm": p.has(org, "payment.confirm"),
                "refund": p.has(org, "refund.request")},
        "branches": [{"id": str(b.id), "name": b.name} for b in db.execute(
            select(Branch).where(Branch.organization_id == org, Branch.kind == "sede").order_by(Branch.name)).scalars()],
        "aviso": "Control interno: este sistema no emite facturas. La factura se emite en el programa homologado (D-25).",
    }


@router.get("/lookup")
def lookup(code: str = Query(min_length=3, max_length=40), p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> list[dict]:
    """Localiza expedientes por código para registrar un cobro o una devolución (Recepción, ATC)."""
    scope = load_case_scope(db, p)
    out = []
    for cf in db.execute(select(CaseFile).where(CaseFile.code == code.strip().upper(),
                                                CaseFile.organization_id.in_(p.org_ids() or [uuid.uuid4()]))).scalars():
        level = case_level(p, cf, scope)
        if level is None:
            continue
        org = cf.organization_id
        out.append({"case_id": str(cf.id), "code": cf.code, "materia": cf.materia, "status": cf.status,
                    "organization": db.get(Organization, org).name,
                    "contact_name": _contact_name(db, cf.contact_id) if level == "full" or p.has(org, "economy.read.all") else None,
                    "can_pay": p.has(org, "payment.register"), "can_refund": p.has(org, "refund.request"),
                    "can_read": can_read_economy(p, cf, level),
                    "branches": [{"id": str(b.id), "name": b.name} for b in db.execute(
                        select(Branch).where(Branch.organization_id == org, Branch.kind == "sede")
                        .order_by(Branch.name)).scalars()]})
    return out


@router.post("/cases/{case_id}/charges", status_code=201)
def add_charge(case_id: uuid.UUID, body: ChargeIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    cf, _ = _case(db, p, case_id, request, "charge.create", perm="charge.create")
    c = Charge(organization_id=cf.organization_id, case_id=cf.id, contact_id=cf.contact_id, kind=body.kind,
               concept=body.concept.strip(), amount_cents=body.amount_cents, currency=_currency(db, cf.organization_id),
               due_date=body.due_date, created_by=p.id)
    db.add(c)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="charge.create", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after=_charge_out(db, c), ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _charge_out(db, c)


@router.post("/charges/{charge_id}/cancel")
def cancel_charge(charge_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    c = db.get(Charge, charge_id)
    if c is None:
        raise api_error(404, "no_encontrado", "Importe no encontrado.")
    _case(db, p, c.case_id, request, "charge.cancel", perm="charge.cancel")
    if c.status != "vigente":
        raise api_error(409, "conflicto", "Ya está anulado.")
    before = _charge_out(db, c)
    c.status, c.cancelled_by, c.cancelled_at, c.cancel_reason = "anulado", p.id, _now(), body.reason
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="charge.cancel", resource_type="case_file", resource_id=c.case_id,
                 organization_id=c.organization_id, reason=body.reason, before=before, after=_charge_out(db, c),
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _charge_out(db, c)


# ------------------------------------------------------------------ cobros
@router.post("/cases/{case_id}/payments", status_code=201)
def add_payment(case_id: uuid.UUID, body: PaymentIn, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    cf, _ = _case(db, p, case_id, request, "payment.register", need="meta", perm="payment.register")
    org = cf.organization_id
    received = body.received_at or _now()
    if received.tzinfo is None:
        received = received.replace(tzinfo=UTC)
    if received > _now() + timedelta(minutes=5) or received < _now() - timedelta(days=366):
        raise api_error(422, "validacion", "La fecha del cobro no puede ser futura ni de hace más de un año.",
                        [{"field": "received_at", "message": "Fecha no válida"}])
    branch = _branch_ok(db, org, body.branch_id) if (body.method == "efectivo" or body.branch_id) else None
    if body.method in ("transferencia", "bizum") and not body.reference:
        raise api_error(422, "validacion", "Indique la referencia de la transferencia o del Bizum.",
                        [{"field": "reference", "message": "Obligatoria"}])
    x = Payment(organization_id=org, case_id=cf.id, contact_id=cf.contact_id, branch_id=branch.id if branch else None,
                amount_cents=body.amount_cents, currency=_currency(db, org), method=body.method, received_at=received,
                reference=body.reference, notes=body.notes, registered_by=p.id)
    db.add(x)
    db.flush()
    if body.method == "efectivo":
        _cash(db, org, branch.id, "cobro", body.amount_cents, f"Cobro {cf.code}", p.id, payment_id=x.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="payment.register", resource_type="case_file", resource_id=cf.id,
                 organization_id=org, after=_payment_out(db, x), ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _payment_out(db, x)


def _payment_for_accounting(db: Session, p: Principal, payment_id: uuid.UUID, request: Request, action: str) -> Payment:
    x = db.get(Payment, payment_id)
    ctx = req_ctx(request)
    if x is None or x.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Cobro no encontrado.")
    if not p.has(x.organization_id, "payment.confirm"):
        _deny(p, ctx, action, "payment", x.id, x.organization_id, "sin payment.confirm")
        raise api_error(403, "prohibido", "Solo Contabilidad confirma o anula cobros.")
    return x


@router.get("/payments")
def list_payments(request: Request, status: Literal["registrado", "confirmado", "anulado"] = "registrado",
                  p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = p.orgs_with("payment.confirm")
    if not orgs:
        _deny(p, req_ctx(request), "payment.list", "payment", None, None, "sin payment.confirm")
        raise api_error(403, "prohibido", "Solo Contabilidad gestiona la bandeja de cobros.")
    rows = db.execute(select(Payment).where(Payment.organization_id.in_(orgs), Payment.status == status)
                      .order_by(Payment.received_at.desc()).limit(200)).scalars()
    return [_payment_out(db, x, with_case=True) for x in rows]


@router.post("/payments/{payment_id}/confirm")
def confirm_payment(payment_id: uuid.UUID, body: ConfirmIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    x = _payment_for_accounting(db, p, payment_id, request, "payment.confirm")
    if x.status != "registrado":
        raise api_error(409, "conflicto", f"El cobro está {x.status}.")
    before = _payment_out(db, x)
    x.status, x.confirmed_by, x.confirmed_at = "confirmado", p.id, _now()
    x.invoice_ref = (body.invoice_ref or "").strip() or None
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="payment.confirm", resource_type="case_file" if x.case_id else "payment",
                 resource_id=x.case_id or x.id,
                 organization_id=x.organization_id, before=before, after=_payment_out(db, x), ip=ctx.ip,
                 request_id=ctx.request_id)
    db.commit()
    return _payment_out(db, x)


@router.post("/payments/{payment_id}/annul")
def annul_payment(payment_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    x = _payment_for_accounting(db, p, payment_id, request, "payment.annul")
    if x.status == "anulado":
        raise api_error(409, "conflicto", "Ya está anulado.")
    try:
        annul(db, x, p.id, body.reason, req_ctx(request))
    except ValueError as exc:
        raise api_error(422, "validacion", str(exc)) from exc
    db.commit()
    return _payment_out(db, x)


def annul(db: Session, x: Payment, user_id: uuid.UUID, reason: str, ctx) -> None:
    """Anula un cobro (con motivo; el efectivo se devuelve a la caja con un movimiento). También desde Recepción."""
    t = totals(db, x.case_id) if x.case_id else {"devolvible": x.amount_cents}
    if x.status == "confirmado" and t["devolvible"] - x.amount_cents < 0:
        raise ValueError("No se puede anular: hay devoluciones aprobadas que dependen de este cobro.")
    before = _payment_out(db, x)
    x.status, x.annulled_by, x.annulled_at, x.annul_reason = "anulado", user_id, _now(), reason
    if x.method == "efectivo":
        _cash(db, x.organization_id, x.branch_id, "anulacion_cobro", -x.amount_cents,
              f"Anulación de cobro {db.get(CaseFile, x.case_id).code if x.case_id else 'de consulta'}", user_id,
              payment_id=x.id)
    audit.record(db, actor_id=user_id, action="payment.annul", resource_type="case_file" if x.case_id else "payment",
                 resource_id=x.case_id or x.id, organization_id=x.organization_id, reason=reason, before=before,
                 after=_payment_out(db, x), ip=ctx.ip, request_id=ctx.request_id)


# ------------------------------------------------------------------ devoluciones (Q-3.9, A-09)
REFUND_FLOW: dict[str, dict[str, str]] = {
    # estado actual -> {destino: permiso}
    "registrada": {"en_revision": "refund.review", "aprobada": "refund.decide", "rechazada": "refund.decide"},
    "en_revision": {"escalada_legal": "refund.review", "aprobada": "refund.decide", "rechazada": "refund.decide"},
    "escalada_legal": {"en_revision": "refund.legal_opinion"},
    "aprobada": {"pagada": "refund.decide"},
    "rechazada": {"en_revision": "refund.decide"},  # reapertura con motivo (nueva documentación)
    "pagada": {},
}


@router.post("/cases/{case_id}/refunds", status_code=201)
def add_refund(case_id: uuid.UUID, body: RefundIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    cf, _ = _case(db, p, case_id, request, "refund.request", need="meta", perm="refund.request")
    r = Refund(organization_id=cf.organization_id, case_id=cf.id, contact_id=cf.contact_id,
               amount_cents=body.amount_cents, currency=_currency(db, cf.organization_id), reason=body.reason.strip(),
               requested_by=p.id)
    db.add(r)
    db.flush()
    db.add(RefundEvent(refund_id=r.id, actor_user_id=p.id, from_status=None, to_status="registrada", note=body.reason))
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="refund.request", resource_type="refund", resource_id=r.id,
                 organization_id=cf.organization_id, after={"expediente": cf.code, "importe": body.amount_cents},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _refund_out(db, r)


def _legal_reader(db: Session, p: Principal, r: Refund) -> bool:
    """El informe jurídico solo lo da quien tiene acceso completo al expediente (respeta la separación de ramas)."""
    if not p.has(r.organization_id, "refund.legal_opinion"):
        return False
    return case_level(p, db.get(CaseFile, r.case_id), load_case_scope(db, p)) == "full"


def _refund_visible(db: Session, p: Principal, r: Refund) -> bool:
    org = r.organization_id
    return (r.requested_by == p.id or r.legal_opinion_by == p.id or p.has(org, "refund.review")
            or p.has(org, "refund.decide") or (r.status == "escalada_legal" and _legal_reader(db, p, r)))


@router.get("/refunds")
def list_refunds(request: Request, status: str | None = None, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> list[dict]:
    orgs = p.org_ids()
    rows = db.execute(select(Refund).where(Refund.organization_id.in_(orgs or [uuid.uuid4()]),
                                           *( [Refund.status == status] if status else [] ))
                      .order_by(Refund.created_at.desc()).limit(300)).scalars()
    return [_refund_out(db, r) for r in rows if _refund_visible(db, p, r)]


@router.get("/refunds/{refund_id}")
def get_refund(refund_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    r = db.get(Refund, refund_id)
    if r is None or r.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Devolución no encontrada.")
    if not _refund_visible(db, p, r):
        _deny(p, req_ctx(request), "refund.read", "refund", r.id, r.organization_id, "sin permiso sobre devoluciones")
        raise api_error(403, "prohibido", "No puede consultar esta devolución.")
    out = _refund_out(db, r, events=True)
    org = r.organization_id
    t = totals(db, r.case_id)
    out["totals"] = t if (p.has(org, "refund.decide") or p.has(org, "economy.read.all")) else None
    out["allowed"] = [to for to, perm in REFUND_FLOW[r.status].items() if p.has(org, perm)
                      and not (perm == "refund.decide" and r.requested_by == p.id and to in ("aprobada", "rechazada"))
                      and (perm != "refund.legal_opinion" or _legal_reader(db, p, r))]
    return out


@router.post("/refunds/{refund_id}/transition")
def transition_refund(refund_id: uuid.UUID, body: RefundTransitionIn, request: Request,
                      p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    ctx = req_ctx(request)
    r = db.get(Refund, refund_id)
    if r is None or r.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Devolución no encontrada.")
    org = r.organization_id
    if body.version is not None and body.version != r.version:
        raise api_error(409, "conflicto_version", "Otra persona ha cambiado esta devolución. Recargue la página.")
    perm = REFUND_FLOW[r.status].get(body.to)
    if perm is None:
        raise api_error(422, "transicion_no_valida", f"No se puede pasar de «{r.status}» a «{body.to}».")
    if not p.has(org, perm) or (perm == "refund.legal_opinion" and not _legal_reader(db, p, r)):
        _deny(p, ctx, f"refund.{body.to}", "refund", r.id, org, f"sin {perm}")
        msg = ("Solo Contabilidad aprueba, rechaza o paga devoluciones." if perm == "refund.decide"
               else "Su rol no permite este paso de la devolución.")
        raise api_error(403, "prohibido", msg)
    if body.to in ("aprobada", "rechazada") and r.requested_by == p.id:
        _deny(p, ctx, f"refund.{body.to}", "refund", r.id, org, "quien solicita no decide")
        raise api_error(403, "doble_control", "Quien registró la devolución no puede decidirla.")
    note = (body.note or "").strip()
    if body.to in ("aprobada", "rechazada", "escalada_legal") or (r.status == "rechazada"):
        if len(note) < 5:
            raise api_error(422, "validacion", "Indique el motivo.", [{"field": "note", "message": "Obligatorio"}])
    before = {"estado": r.status}
    if r.status == "escalada_legal":
        if len(note) < 10:
            raise api_error(422, "validacion", "Escriba el informe jurídico (orienta la decisión; no la toma).",
                            [{"field": "note", "message": "Obligatorio"}])
        r.legal_opinion, r.legal_opinion_by, r.legal_opinion_at = note, p.id, _now()
    if body.to == "aprobada":
        t = totals(db, r.case_id)
        if r.amount_cents > t["devolvible"]:
            raise api_error(422, "excede_cobrado",
                            f"Solo hay {t['devolvible'] / 100:.2f} cobrados y confirmados disponibles para devolver. "
                            "Confirme antes los cobros o ajuste el importe.")
    if body.to in ("aprobada", "rechazada"):
        r.decided_by, r.decided_at, r.decision_reason = p.id, _now(), note
    if body.to == "pagada":
        if not body.pay_method:
            raise api_error(422, "validacion", "Indique cómo se ha devuelto.", [{"field": "pay_method", "message": "Obligatorio"}])
        if body.pay_method != "efectivo" and not body.pay_reference:
            raise api_error(422, "validacion", "Indique la referencia del pago.", [{"field": "pay_reference", "message": "Obligatoria"}])
        r.paid_by, r.paid_at, r.pay_method, r.pay_reference = p.id, _now(), body.pay_method, body.pay_reference
        if body.pay_method == "efectivo":
            b = _branch_ok(db, org, body.pay_branch_id)
            r.pay_branch_id = b.id
            _cash(db, org, b.id, "devolucion", -r.amount_cents, f"Devolución {db.get(CaseFile, r.case_id).code}",
                  p.id, refund_id=r.id)
    db.add(RefundEvent(refund_id=r.id, actor_user_id=p.id, from_status=r.status, to_status=body.to, note=note or None))
    r.status = body.to
    r.version += 1
    audit.record(db, actor_id=p.id, action=f"refund.{body.to}", resource_type="refund", resource_id=r.id,
                 organization_id=org, reason=note or None, before=before, after={"estado": r.status},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return get_refund(r.id, request, p, db)


# ------------------------------------------------------------------ cajas por sede (Q-4.14)
def _cash_branches(db: Session, p: Principal, write: bool) -> list[Branch]:
    out: dict[uuid.UUID, Branch] = {}
    for org in p.org_ids():
        all_b = list(db.execute(select(Branch).where(Branch.organization_id == org, Branch.kind == "sede")).scalars())
        if not write and p.has(org, "cash.read.all"):
            out |= {b.id: b for b in all_b}
        for m in p.memberships_with(org, "cash.operate"):
            out |= {b.id: b for b in all_b if m.branch_id in (None, b.id)}
    return sorted(out.values(), key=lambda b: b.name)


def _balance(db: Session, branch_id: uuid.UUID) -> int:
    return int(db.execute(select(func.coalesce(func.sum(CashMovement.amount_cents), 0))
                          .where(CashMovement.branch_id == branch_id)).scalar_one())


@router.get("/cash")
def cash_overview(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    writable = {b.id for b in _cash_branches(db, p, write=True)}
    out = []
    for b in _cash_branches(db, p, write=False):
        last = db.execute(select(CashClosing).where(CashClosing.branch_id == b.id)
                          .order_by(CashClosing.closed_at.desc()).limit(1)).scalar_one_or_none()
        moves = db.execute(select(CashMovement).where(CashMovement.branch_id == b.id)
                           .order_by(CashMovement.at.desc()).limit(30)).scalars()
        out.append({
            "branch_id": str(b.id), "branch": b.name, "organization": db.get(Organization, b.organization_id).name,
            "currency": _currency(db, b.organization_id), "balance_cents": _balance(db, b.id), "can_operate": b.id in writable,
            "last_closing": None if not last else {"at": last.closed_at.isoformat(), "expected_cents": last.expected_cents,
                                                   "counted_cents": last.counted_cents,
                                                   "difference_cents": last.difference_cents,
                                                   "by": _uname(db, last.closed_by), "notes": last.notes,
                                                   "status": last.status},
            "movements": [{"id": str(m.id), "kind": m.kind, "amount_cents": m.amount_cents, "concept": m.concept,
                           "at": m.at.isoformat(), "by": _uname(db, m.created_by)} for m in moves],
        })
    return out


def _writable_branch(db: Session, p: Principal, branch_id: uuid.UUID, request: Request, action: str) -> Branch:
    b = db.get(Branch, branch_id)
    if b is None or b.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Sede no encontrada.")
    if b.id not in {x.id for x in _cash_branches(db, p, write=True)}:
        _deny(p, req_ctx(request), action, "branch", b.id, b.organization_id, "sin cash.operate en esa sede")
        raise api_error(403, "prohibido", "Solo opera la caja de su sede.")
    return b


@router.post("/cash/{branch_id}/movements", status_code=201)
def cash_movement(branch_id: uuid.UUID, body: CashMovementIn, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    b = _writable_branch(db, p, branch_id, request, "cash.movement")
    sign = 1 if body.kind == "aportacion" else -1
    if sign < 0 and _balance(db, b.id) - body.amount_cents < 0:
        raise api_error(422, "saldo_insuficiente", "La caja no tiene ese efectivo según los registros. Revise o haga un arqueo.")
    m = _cash(db, b.organization_id, b.id, body.kind, sign * body.amount_cents, body.concept.strip(), p.id)
    db.flush()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="cash.movement", resource_type="branch", resource_id=b.id,
                 organization_id=b.organization_id, after={"tipo": body.kind, "importe": m.amount_cents,
                                                           "concepto": m.concept}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"id": str(m.id), "balance_cents": _balance(db, b.id)}


@router.post("/cash/{branch_id}/closings", status_code=201)
def cash_closing(branch_id: uuid.UUID, body: ClosingIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    """Cierre del día (mismo circuito que Recepción: queda pendiente de validar por otra persona)."""
    from .. import agents
    from ..reception import service as rsvc

    b = _writable_branch(db, p, branch_id, request, "cash.closing")
    try:
        c = rsvc.close_day(db, b, body.counted_cents, body.notes, p.id, req_ctx(request))
    except rsvc.ReceptionError as exc:
        db.rollback()
        raise api_error(exc.status, exc.code, exc.message, exc.details) from exc
    db.commit()
    agents.dispatch_events()
    return {"expected_cents": c.expected_cents, "counted_cents": c.counted_cents, "difference_cents": c.difference_cents,
            "balance_cents": _balance(db, b.id), "status": c.status}


# ------------------------------------------------------------------ resumen (base del cuadro de mando, I-110)
@router.get("/summary")
def summary(request: Request, date_from: date = Query(alias="from"), date_to: date = Query(alias="to"),
            p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[dict]:
    orgs = p.orgs_with("economy.report")
    if not orgs:
        _deny(p, req_ctx(request), "economy.report", "organization", None, None, "sin economy.report")
        raise api_error(403, "prohibido", "Solo Dirección y Contabilidad ven el resumen económico.")
    if date_to < date_from or (date_to - date_from).days > 366:
        raise api_error(422, "validacion", "Periodo no válido (máximo un año).")
    start = datetime.combine(date_from, datetime.min.time(), UTC)
    end = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), UTC)
    out = []
    for org in sorted(orgs, key=str):
        o = db.get(Organization, org)
        rows = db.execute(select(Payment.branch_id, Payment.method, Payment.status, func.sum(Payment.amount_cents),
                                 func.count()).where(Payment.organization_id == org, Payment.received_at >= start,
                                                     Payment.received_at < end, Payment.status != "anulado")
                          .group_by(Payment.branch_id, Payment.method, Payment.status)).all()
        by_branch: dict[str, dict] = {}
        for bid, method, st, total, n in rows:
            name = db.get(Branch, bid).name if bid else "Sin sede (transferencia/Bizum)"
            d = by_branch.setdefault(name, {"cobrado": 0, "confirmado": 0, "pendiente_confirmar": 0, "por_metodo": {}, "cobros": 0})
            total = int(total)
            d["cobrado"] += total
            d["cobros"] += n
            d["confirmado" if st == "confirmado" else "pendiente_confirmar"] += total
            d["por_metodo"][method] = d["por_metodo"].get(method, 0) + total
        refunded = db.execute(select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
            Refund.organization_id == org, Refund.paid_at >= start, Refund.paid_at < end)).scalar_one()
        open_refunds = db.execute(select(func.count()).where(
            Refund.organization_id == org, Refund.status.in_(("registrada", "en_revision", "escalada_legal", "aprobada")))
        ).scalar_one()
        charged_all = db.execute(select(func.coalesce(func.sum(Charge.amount_cents), 0)).where(
            Charge.organization_id == org, Charge.status == "vigente")).scalar_one()
        paid_all = db.execute(select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.organization_id == org, Payment.status != "anulado")).scalar_one()
        refunded_all = db.execute(select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
            Refund.organization_id == org, Refund.status == "pagada")).scalar_one()
        out.append({"organization_id": str(org), "organization": o.name, "currency": o.currency,
                    "por_sede": by_branch, "devoluciones_abiertas": open_refunds,
                    "devuelto": int(refunded),
                    "pendiente_de_cobro_total": int(charged_all) - (int(paid_all) - int(refunded_all))})
    return out


