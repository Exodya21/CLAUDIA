"""Recepción (F5.2; DR-REC-3, 4, 8, 9, 10): cobros, justificantes NO fiscales, caja del día y cierre validado.

- «Cada cobro se registra una sola vez»: antes de guardar se buscan cobros parecidos (mismo cliente, importe y forma de
  pago en ±2 días, o la misma referencia). Si los hay, solo se guarda si la persona explica por qué no es repetido;
  Contabilidad lo revisa en sus pendientes.
- El justificante se numera por sede y año, se genera una vez y se guarda cifrado: no es una factura (D-07, D-25).
- Cálculos de caja deterministas: saldo = suma de movimientos. El cierre del día lo valida otra persona.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import audit
from ..models import Branch, CaseFile, Contact, Organization, UserAccount
from ..models_economy import CashClosing, CashMovement, Payment
from ..models_reception import PaymentReceipt, ReceiptCounter
from ..services import pdfwrite, vault

MADRID = ZoneInfo("Europe/Madrid")
KINDS = {"consulta": "Consulta", "provision": "Provisión de fondos", "servicio": "Servicio", "otro": "Otro"}
METHODS = {"efectivo": "Efectivo", "tarjeta": "Tarjeta", "bizum": "Bizum", "transferencia": "Transferencia"}
BRANCH_CODES = {"barcelona": "BCN", "madrid": "MAD", "valencia": "VLC"}


class ReceptionError(Exception):
    def __init__(self, message: str, status: int = 422, code: str = "validacion", details=None):
        super().__init__(message)
        self.message, self.status, self.code, self.details = message, status, code, details


def now() -> datetime:
    return datetime.now(UTC)


def tz_for(branch: Branch | None) -> ZoneInfo:
    try:
        return ZoneInfo(branch.timezone) if branch and branch.timezone else MADRID
    except Exception:  # noqa: BLE001
        return MADRID


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    return start, start + timedelta(days=1)


def today_at(branch: Branch | None) -> date:
    return now().astimezone(tz_for(branch)).date()


def eur(c: int, cur: str = "EUR") -> str:
    s = f"{abs(c) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if c < 0 else ''}{s} {'€' if cur == 'EUR' else cur}"


# ------------------------------------------------------------------ duplicados (DR-REC-8)
def possible_duplicates(db: Session, org_id, contact_id, amount_cents: int, method: str, reference: str | None) -> list[Payment]:
    lo = now() - timedelta(days=2)
    cond = [(Payment.contact_id == contact_id) & (Payment.amount_cents == amount_cents) & (Payment.method == method)
            & (Payment.received_at >= lo)]
    ref = (reference or "").strip()
    if ref:
        cond.append((func.lower(Payment.reference) == ref.lower()) & (Payment.received_at >= now() - timedelta(days=90)))
    return list(db.execute(select(Payment).where(Payment.organization_id == org_id, Payment.status != "anulado",
                                                 or_(*cond)).order_by(Payment.received_at.desc()).limit(5)).scalars())


# ------------------------------------------------------------------ justificante (T-44)
def _prefix(branch: Branch | None) -> str:
    if branch is None:
        return "REC"
    key = unicodedata.normalize("NFKD", branch.city or branch.name).encode("ascii", "ignore").decode().lower().strip()
    code = BRANCH_CODES.get(key) or "".join(ch for ch in key.upper() if ch.isalpha())[:3] or "SED"
    return f"REC-{code}"


def _next_number(db: Session, org_id, prefix: str, year: int) -> str:
    db.execute(insert(ReceiptCounter).values(id=uuid.uuid4(), organization_id=org_id, prefix=prefix, year=year,
                                             last_value=0).on_conflict_do_nothing(
        index_elements=["organization_id", "prefix", "year"]))
    row = db.execute(select(ReceiptCounter).where(ReceiptCounter.organization_id == org_id,
                                                  ReceiptCounter.prefix == prefix, ReceiptCounter.year == year)
                     .with_for_update()).scalar_one()
    row.last_value += 1
    return f"{prefix}-{year}-{row.last_value:06d}"


def issue_receipt(db: Session, pay: Payment, user_id) -> PaymentReceipt:
    """Genera el justificante (una sola vez por cobro) y lo guarda cifrado, sin modificar."""
    existing = db.execute(select(PaymentReceipt).where(PaymentReceipt.payment_id == pay.id)).scalar_one_or_none()
    if existing:
        return existing
    branch = db.get(Branch, pay.branch_id) if pay.branch_id else None
    tz = tz_for(branch)
    local = pay.received_at.astimezone(tz)
    number = _next_number(db, pay.organization_id, _prefix(branch), local.year)
    org = db.get(Organization, pay.organization_id)
    c = db.get(Contact, pay.contact_id)
    cf = db.get(CaseFile, pay.case_id) if pay.case_id else None
    who = db.get(UserAccount, user_id)
    concept = KINDS.get(pay.kind or "", "Cobro") + (f" · expediente {cf.code}" if cf else " (sin expediente)")
    lines = [
        ("h", "JUSTIFICANTE DE PAGO"),
        ("b", "Documento interno del despacho. NO ES UNA FACTURA."),
        ("n", ""),
        ("n", f"Número: {number}"),
        ("n", f"Fecha y hora: {local:%d/%m/%Y %H:%M}"),
        ("n", f"Entidad: {org.name}"),
        ("n", f"Sede: {branch.name if branch else '—'}"),
        ("n", f"Recibido de: {c.given_name} {c.family_names}"),
        ("n", f"Concepto: {concept}"),
        ("b", f"Importe: {eur(pay.amount_cents, pay.currency)}"),
        ("n", f"Forma de pago: {METHODS.get(pay.method, pay.method)}" + (f" · ref. {pay.reference}" if pay.reference else "")),
        ("n", f"Atendido por: {who.full_name if who else '—'}"),
        ("n", ""),
        ("s", "Este justificante acredita la recepción del importe indicado. Cuando proceda, la factura se emite con "
              "el programa de facturación homologado del despacho. Conserve este documento."),
    ]
    data = pdfwrite.text_pdf(lines, footer=f"Justificante {number}")
    path, sha = vault.store(data)
    r = PaymentReceipt(organization_id=pay.organization_id, payment_id=pay.id, branch_id=pay.branch_id, number=number,
                       file_path=path, sha256=sha, issued_by=user_id)
    db.add(r)
    db.flush()
    return r


def receipt_for(db: Session, payment_id) -> PaymentReceipt | None:
    return db.execute(select(PaymentReceipt).where(PaymentReceipt.payment_id == payment_id)).scalar_one_or_none()


def receipt_bytes(r: PaymentReceipt) -> bytes:
    data = vault.load(r.file_path)
    if hashlib.sha256(data).hexdigest() != r.sha256:
        raise ReceptionError("El justificante guardado no coincide con su huella: avise a TI.", 500, "integridad")
    return data


# ------------------------------------------------------------------ caja del día y cierre (DR-REC-4)
def balance(db: Session, branch_id, until: datetime | None = None) -> int:
    q = select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(CashMovement.branch_id == branch_id)
    if until is not None:
        q = q.where(CashMovement.at < until)
    return int(db.execute(q).scalar_one())


def closing_of_day(db: Session, branch_id, day: date) -> CashClosing | None:
    return db.execute(select(CashClosing).where(CashClosing.branch_id == branch_id, CashClosing.day == day,
                                                CashClosing.status != "rechazado")
                      .order_by(CashClosing.closed_at.desc()).limit(1)).scalar_one_or_none()


def close_day(db: Session, branch: Branch, counted_cents: int, notes: str | None, user_id, ctx) -> CashClosing:
    """Cierre del día: se cuenta el efectivo, se anota la diferencia y queda PENDIENTE de validar por otra persona."""
    from .. import agents

    day = today_at(branch)
    prev = closing_of_day(db, branch.id, day)
    if prev is not None:
        raise ReceptionError(f"La caja de {branch.name} ya se cerró hoy ({prev.status.replace('_', ' ')}). Si hay que "
                             "rehacerlo, el responsable debe rechazar ese cierre.", 409, "conflicto")
    expected = balance(db, branch.id)
    diff = counted_cents - expected
    note = (notes or "").strip()
    if diff != 0 and len(note) < 5:
        raise ReceptionError("Hay diferencia entre lo contado y lo registrado: explique el motivo.", 422, "validacion",
                             [{"field": "notes", "message": "Obligatorio si hay diferencia"}])
    org = db.get(Organization, branch.organization_id)
    c = CashClosing(organization_id=branch.organization_id, branch_id=branch.id, expected_cents=expected,
                    counted_cents=counted_cents, difference_cents=diff, currency=org.currency, notes=note or None,
                    closed_by=user_id, day=day, status="pendiente_validacion")
    db.add(c)
    if diff:
        db.add(CashMovement(organization_id=branch.organization_id, branch_id=branch.id, kind="ajuste_arqueo",
                            amount_cents=diff, currency=org.currency, concept=f"Ajuste de arqueo: {note}"[:200],
                            created_by=user_id))
    db.flush()
    audit.record(db, actor_id=user_id, action="cash.closing", resource_type="branch", resource_id=branch.id,
                 organization_id=branch.organization_id, reason=note or None,
                 after={"dia": day.isoformat(), "esperado": expected, "contado": counted_cents, "diferencia": diff,
                        "estado": c.status}, ip=ctx.ip, request_id=ctx.request_id)
    agents.emit(db, branch.organization_id, "cash.closed", "cash_closing", c.id, {"diferencia": diff})
    return c


def decide_closing(db: Session, c: CashClosing, user, approve: bool, note: str | None, ctx) -> CashClosing:
    if c.status != "pendiente_validacion":
        raise ReceptionError(f"El cierre ya está {c.status.replace('_', ' ')}.", 409, "conflicto")
    if c.closed_by == user.id:
        raise ReceptionError("Quien cuenta la caja no puede validar su propio cierre.", 403, "prohibido")
    if not user.has(c.organization_id, "cash.close.validate"):
        raise ReceptionError("Solo un responsable valida el cierre de caja.", 403, "prohibido")
    note = (note or "").strip()
    if not approve and len(note) < 5:
        raise ReceptionError("Indique por qué rechaza el cierre (se volverá a contar).", 422, "validacion")
    if approve and c.difference_cents and len(note) < 5:
        raise ReceptionError("El cierre tiene diferencia: indique qué ha comprobado antes de validarlo.", 422, "validacion")
    before = {"estado": c.status}
    c.status = "validado" if approve else "rechazado"
    c.validated_by, c.validated_at, c.validation_note = user.id, now(), note or None
    audit.record(db, actor_id=user.id, action="cash.closing.validate" if approve else "cash.closing.reject",
                 resource_type="branch", resource_id=c.branch_id, organization_id=c.organization_id, reason=note or None,
                 before=before, after={"estado": c.status, "cierre": str(c.id), "diferencia": c.difference_cents},
                 ip=ctx.ip, request_id=ctx.request_id)
    return c
