"""Operaciones de banco compartidas por la API y el agente de conciliación (siempre auditadas)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..models_agents import AgentProposal
from ..models_bank import BankAccount, BankImport, BankMatch, BankMovement
from ..models_economy import Payment
from ..services import vault
from . import matcher, parsers


class BankError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.message, self.status = message, status


def now() -> datetime:
    return datetime.now(UTC)


def import_statement(db: Session, acc: BankAccount, data: bytes, name: str, user_id, ctx) -> BankImport:
    """Importa un extracto: guarda el original cifrado, comprueba saldos y añade solo los movimientos nuevos."""
    sha = hashlib.sha256(data).hexdigest()
    prev = db.execute(select(BankImport).where(BankImport.account_id == acc.id, BankImport.sha256 == sha)).scalar_one_or_none()
    if prev is not None:
        raise BankError(f"Este extracto ya se importó el {prev.imported_at:%d/%m/%Y %H:%M}. No se duplica nada.")
    try:
        st = parsers.parse(data, name)
    except parsers.ParseError as exc:
        raise BankError(exc.message, 422) from exc
    if st.currency != acc.currency:
        raise BankError(f"El extracto es en {st.currency} y la cuenta en {acc.currency}.", 422)
    if st.account_hint and st.account_hint != acc.iban_last4:
        raise BankError(f"El extracto es de la cuenta terminada en {st.account_hint}, no de «{acc.name}» "
                        f"(…{acc.iban_last4}).", 422)
    path, _ = vault.store(data)
    imp = BankImport(organization_id=acc.organization_id, account_id=acc.id, original_name=name[:200],
                     file_format=st.file_format, sha256=sha, file_path=path, period_from=st.period_from,
                     period_to=st.period_to, opening_cents=st.opening_cents, closing_cents=st.closing_cents,
                     total_lines=len(st.lines), imported_by=user_id, errors=list(st.errors) or None)
    db.add(imp)
    db.flush()
    errors = list(st.errors)
    if st.opening_cents is not None and st.closing_cents is not None:
        total = sum(ln.amount_cents for ln in st.lines)
        imp.balance_ok = (st.opening_cents + total == st.closing_cents) and not st.errors
        if st.opening_cents + total != st.closing_cents:
            errors.append({"linea": "saldos", "error": f"saldo inicial {matcher.eur(st.opening_cents)} + movimientos "
                           f"{matcher.eur(total)} ≠ saldo final {matcher.eur(st.closing_cents)}"})
        # Continuidad con el extracto anterior de la misma cuenta
        last = db.execute(select(BankImport).where(BankImport.account_id == acc.id, BankImport.id != imp.id,
                                                   BankImport.closing_cents.is_not(None),
                                                   BankImport.period_to < (st.period_from or st.period_to))
                          .order_by(BankImport.period_to.desc()).limit(1)).scalar_one_or_none()
        if last is not None and last.closing_cents != st.opening_cents:
            errors.append({"linea": "continuidad", "error": f"el saldo inicial ({matcher.eur(st.opening_cents)}) no "
                           f"coincide con el final del extracto anterior ({matcher.eur(last.closing_cents)}, "
                           f"{last.period_to:%d/%m/%Y}): puede faltar un extracto intermedio"})
            imp.balance_ok = False
    else:
        errors.append({"linea": "saldos", "error": "el formato no trae saldos: no se puede comprobar el cuadre"})
    existing = set(db.execute(select(BankMovement.ext_id).where(BankMovement.account_id == acc.id,
                                                                BankMovement.ext_id.in_([ln.ext_id for ln in st.lines]))
                              ).scalars())
    new = 0
    for ln in st.lines:
        if ln.ext_id in existing:
            continue
        db.add(BankMovement(organization_id=acc.organization_id, account_id=acc.id, import_id=imp.id, ext_id=ln.ext_id,
                            booking_date=ln.booking_date, value_date=ln.value_date, amount_cents=ln.amount_cents,
                            currency=st.currency, description=ln.description, reference=ln.reference,
                            counterparty=ln.counterparty, balance_after_cents=ln.balance_after_cents,
                            activity=acc.activity, branch_id=acc.branch_id,
                            category=matcher.suggest_category_text(ln.description, ln.reference, ln.amount_cents)))
        new += 1
    imp.new_lines, imp.duplicate_lines = new, len(st.lines) - new
    imp.errors = errors or None
    audit.record(db, actor_id=user_id, action="bank.import", resource_type="bank_account", resource_id=acc.id,
                 organization_id=acc.organization_id,
                 after={"import_id": str(imp.id), "formato": st.file_format, "lineas": len(st.lines), "nuevas": new,
                        "repetidas": imp.duplicate_lines, "cuadre": imp.balance_ok, "errores": len(errors),
                        "sha256": sha}, ip=ctx.ip, request_id=ctx.request_id)
    db.flush()
    return imp


def _settle(db: Session, m: BankMovement, user_id) -> None:
    total = matcher.validated_sum(db, m.id)
    if total == m.amount_cents:
        m.status = "traspaso" if m.category == "traspaso" else "conciliado"
    elif total:
        m.status = "parcial"
    m.reviewed_by, m.reviewed_at = user_id, now()
    m.version += 1


def _confirm_payment(db: Session, pay: Payment, user, ctx, movement: BankMovement) -> None:
    if pay.status == "anulado":
        raise BankError("Uno de los cobros está anulado: no se puede conciliar con él.")
    if pay.status == "registrado":
        if not user.has(pay.organization_id, "payment.confirm"):
            raise BankError("Validar este emparejamiento confirma el cobro, y no tiene permiso para confirmar cobros.", 403)
        pay.status, pay.confirmed_by, pay.confirmed_at = "confirmado", user.id, now()
        audit.record(db, actor_id=user.id, action="payment.confirm", resource_type="case_file", resource_id=pay.case_id,
                     organization_id=pay.organization_id, before={"estado": "registrado"},
                     after={"estado": "confirmado", "por": "conciliación bancaria", "movimiento": str(movement.id)},
                     ip=ctx.ip, request_id=ctx.request_id)


def _mirror(db: Session, other: BankMovement, m: BankMovement, rule: str, expl: str, user_id, status: str) -> None:
    db.add(BankMatch(organization_id=other.organization_id, movement_id=other.id, target_type="movement",
                     target_id=m.id, amount_cents=other.amount_cents, rule=rule, explanation=expl, status=status,
                     created_by=user_id, decided_by=user_id if status == "validada" else None,
                     decided_at=now() if status == "validada" else None))


def validate_matches(db: Session, m: BankMovement, matches: list[BankMatch], user, ctx, note: str | None = None) -> dict:
    """Valida emparejamientos propuestos: confirma los cobros y marca los movimientos (también la otra cara)."""
    if m.status in ("conciliado", "traspaso", "ignorado"):
        raise BankError(f"El movimiento ya está {m.status}.")
    for bm in matches:
        if bm.status != "propuesta":
            raise BankError(f"El emparejamiento ya está {bm.status}.")
    for bm in matches:
        if bm.target_type == "payment":
            _confirm_payment(db, db.get(Payment, bm.target_id), user, ctx, m)
        elif bm.target_type == "invoice":
            from ..models_accounting import SupplierInvoice
            inv = db.get(SupplierInvoice, bm.target_id)
            if inv is None or inv.status not in ("validada", "programada"):
                raise BankError("La factura ya no está pendiente de pago.")
            if not user.has(inv.organization_id, "bank.reconcile"):
                raise BankError("Sin permiso para conciliar pagos.", 403)
            before = inv.status
            inv.status, inv.paid_at, inv.paid_movement_id = "pagada", m.booking_date, m.id
            inv.version += 1
            audit.record(db, actor_id=user.id, action="invoice.paid", resource_type="supplier_invoice", resource_id=inv.id,
                         organization_id=inv.organization_id, before={"estado": before},
                         after={"estado": "pagada", "movimiento": str(m.id), "fecha": m.booking_date.isoformat()},
                         ip=ctx.ip, request_id=ctx.request_id)
            m.category = m.category if m.category not in (None, "comision", "otro") else "proveedor"
        elif bm.target_type == "movement":
            other = db.get(BankMovement, bm.target_id)
            if other.status in ("conciliado", "traspaso", "ignorado"):
                raise BankError("El movimiento de la otra cuenta ya está conciliado.")
            other.category = "traspaso" if bm.rule == "traspaso" else (other.category or "comision")
            _mirror(db, other, m, bm.rule, bm.explanation, user.id, "validada")
            db.flush()
            _settle(db, other, user.id)
            _close_open_proposals(db, other, user.id, "resuelta al conciliar el movimiento relacionado")
        bm.status, bm.decided_by, bm.decided_at, bm.decision_note = "validada", user.id, now(), note
    if any(bm.rule == "traspaso" for bm in matches):
        m.category = "traspaso"
    elif m.category is None and any(bm.target_type == "payment" for bm in matches):
        m.category = "cobro"
    elif m.category is None and any(bm.target_type == "refund" for bm in matches):
        m.category = "devolucion"
    elif any(bm.target_type == "invoice" for bm in matches):
        m.category = "proveedor"
    db.flush()
    _settle(db, m, user.id)
    _close_open_proposals(db, m, user.id, "resuelta al validar el emparejamiento")
    audit.record(db, actor_id=user.id, action="bank.match.validate", resource_type="bank_movement", resource_id=m.id,
                 organization_id=m.organization_id, reason=note,
                 after={"emparejamientos": [str(b.id) for b in matches], "estado": m.status,
                        "reglas": sorted({b.rule for b in matches})}, ip=ctx.ip, request_id=ctx.request_id)
    return {"movimiento": str(m.id), "estado": m.status}


def reject_matches(db: Session, m: BankMovement, matches: list[BankMatch], user_id, note: str | None) -> None:
    for bm in matches:
        if bm.status == "propuesta":
            bm.status, bm.decided_by, bm.decided_at, bm.decision_note = "rechazada", user_id, now(), note
    if m.status == "propuesto":
        m.status = "sin_justificar"
        m.version += 1


def manual_match(db: Session, m: BankMovement, targets: list[tuple[str, uuid.UUID]], user, ctx, note: str) -> dict:
    """Conciliación a mano (Contabilidad): los destinos deben sumar exactamente el importe del movimiento."""
    from ..models_economy import Refund
    if m.status in ("conciliado", "traspaso", "ignorado"):
        raise BankError(f"El movimiento ya está {m.status}.")
    already = matcher.validated_sum(db, m.id)
    rows: list[BankMatch] = []
    total = 0
    for ttype, tid in targets:
        if ttype == "payment":
            x = db.get(Payment, tid)
            if x is None or x.organization_id != m.organization_id:
                raise BankError("Cobro no encontrado.", 404)
            amount = x.amount_cents
        elif ttype == "refund":
            x = db.get(Refund, tid)
            if x is None or x.organization_id != m.organization_id or x.status != "pagada":
                raise BankError("La devolución no existe o no está pagada.", 422)
            amount = -x.amount_cents
        elif ttype == "invoice":
            from ..models_accounting import SupplierInvoice
            x = db.get(SupplierInvoice, tid)
            if x is None or x.organization_id != m.organization_id or x.status not in ("validada", "programada"):
                raise BankError("La factura no existe o no está pendiente de pago.", 422)
            amount = -x.total_cents
        else:
            x = db.get(BankMovement, tid)
            if x is None or x.organization_id != m.organization_id or x.id == m.id:
                raise BankError("Movimiento no encontrado.", 404)
            amount = -x.amount_cents if x.amount_cents == -m.amount_cents else x.amount_cents
        taken = db.execute(select(BankMatch.id).where(BankMatch.target_type == ttype, BankMatch.target_id == tid,
                                                      BankMatch.status == "validada")).first()
        if taken:
            raise BankError("Ese destino ya está conciliado con otro movimiento.")
        total += amount
        rule = "traspaso" if ttype == "movement" and x.amount_cents == -m.amount_cents else "manual"
        rows.append(BankMatch(organization_id=m.organization_id, movement_id=m.id, target_type=ttype, target_id=tid,
                              amount_cents=amount, rule=rule, explanation=f"Conciliación manual: {note}",
                              status="propuesta", created_by=user.id))
    if not rows:
        raise BankError("Elija al menos un cobro, devolución o movimiento.", 422)
    if already + total != m.amount_cents:
        raise BankError(f"Lo elegido suma {matcher.eur(total)} y falta conciliar {matcher.eur(m.amount_cents - already)}. "
                        "Debe cuadrar exactamente (sin redondeos).", 422)
    for bm in db.execute(select(BankMatch).where(BankMatch.movement_id == m.id, BankMatch.status == "propuesta")).scalars():
        bm.status, bm.decided_by, bm.decided_at, bm.decision_note = "rechazada", user.id, now(), "sustituida por conciliación manual"
    for r in rows:
        db.add(r)
    db.flush()
    return validate_matches(db, m, rows, user, ctx, note)


def justify(db: Session, m: BankMovement, category: str, user, ctx, note: str, ignore: bool = False) -> dict:
    """Da un movimiento por justificado con su categoría (p. ej. comisión o seguro social) o lo marca ignorado."""
    if m.status in ("conciliado", "traspaso", "ignorado"):
        raise BankError(f"El movimiento ya está {m.status}.")
    if m.amount_cents > 0 and category == "cobro" and not ignore:
        raise BankError("Un ingreso de cliente se concilia con su cobro registrado, no por categoría.", 422)
    before = {"estado": m.status, "categoria": m.category}
    m.category = category
    m.status = "ignorado" if ignore else "conciliado"
    m.note, m.reviewed_by, m.reviewed_at = note[:500], user.id, now()
    m.version += 1
    for bm in db.execute(select(BankMatch).where(BankMatch.movement_id == m.id, BankMatch.status == "propuesta")).scalars():
        bm.status, bm.decided_by, bm.decided_at, bm.decision_note = "rechazada", user.id, now(), "justificado por categoría"
    _close_open_proposals(db, m, user.id, "resuelta al justificar el movimiento")
    audit.record(db, actor_id=user.id, action="bank.movement.ignore" if ignore else "bank.movement.justify",
                 resource_type="bank_movement", resource_id=m.id, organization_id=m.organization_id, reason=note,
                 before=before, after={"estado": m.status, "categoria": category}, ip=ctx.ip, request_id=ctx.request_id)
    return {"movimiento": str(m.id), "estado": m.status}


def _close_open_proposals(db: Session, m: BankMovement, user_id, why: str) -> None:
    for p in db.execute(select(AgentProposal).where(AgentProposal.ref_type == "bank_movement",
                                                    AgentProposal.ref_id == m.id,
                                                    AgentProposal.status == "pendiente")).scalars():
        p.status, p.decided_by, p.decided_at, p.decision_note = "caducada", user_id, now(), why
