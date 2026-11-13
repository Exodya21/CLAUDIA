"""Reglas deterministas de conciliación (DR-CON-3). Cada regla es verificable a mano y deja su explicación.

Orden de reglas por movimiento (la primera que encuentra un candidato ÚNICO gana):
1. traspaso     – mismo importe con signo contrario en otra cuenta propia (±3 días) y «traspaso» en uno de los dos.
2. referencia   – el concepto trae un código de expediente (LAB-2026-0001…) y hay cobros registrados de ese
                  expediente que suman exactamente el importe (hasta 4 cobros).
3. bizum        – «bizum» en el concepto y un único cobro Bizum registrado del mismo importe (±3 días).
4. tpv          – liquidación de TPV: cobros con tarjeta de un día (1–4 días antes) que suman el importe, o el importe
                  más la comisión que el banco carga aparte el mismo día (bruto = neto + comisión).
5. devolucion   – cargo igual a una devolución pagada por transferencia/Bizum (±5 días).
6. importe_fecha – transferencia sin referencia: un único cobro por transferencia del mismo importe (±5 días).
Si no hay candidato único → excepción en la bandeja (con categoría sugerida si el concepto la deja clara).
Nunca se concilia sola una propuesta: siempre la valida Contabilidad.
"""

from __future__ import annotations

import itertools
import re
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import CaseFile
from ..models_bank import BankAccount, BankMatch, BankMovement
from ..models_economy import Payment, Refund

CASE_CODE = re.compile(r"\b(LAB|EXT|NAC)[\s\-/_]?(20\d{2})[\s\-/_]?(\d{4})\b")
KW_TRASPASO = re.compile(r"\bTRASPASO", re.I)
KW_BIZUM = re.compile(r"\bBIZUM\b", re.I)
KW_TPV = re.compile(r"\b(TPV|DATAFONO|DATÁFONO|LIQUIDACI[OÓ]N TARJETAS|LIQ\.? TARJETAS|COMERCIO)\b", re.I)
KW_COMISION = re.compile(r"\bCOMISI[OÓ]N", re.I)
CATEGORY_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(TGSS|SEGURIDAD SOCIAL|SEG\.? SOCIAL)\b", re.I), "seguridad_social"),
    (re.compile(r"\b(AEAT|HACIENDA|AGENCIA TRIBUTARIA|MODELO \d{3})\b", re.I), "impuestos"),
    (re.compile(r"\bN[OÓ]MINA", re.I), "nomina"),
    (re.compile(r"\bALQUILER\b", re.I), "alquiler"),
    (KW_COMISION, "comision"),
    (KW_TPV, "tpv"),
    (KW_BIZUM, "bizum"),
    (KW_TRASPASO, "traspaso"),
]
MATERIA_ACTIVITY = {"laboral": "laboral", "extranjeria": "extranjeria", "nacionalidad": "extranjeria"}


def eur(c: int) -> str:
    s = f"{abs(c) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if c < 0 else ''}{s} €"


@dataclass
class Target:
    type: str  # payment | refund | movement
    id: uuid.UUID
    amount_cents: int
    case_id: uuid.UUID | None = None


@dataclass
class Candidate:
    rule: str
    targets: list[Target]
    explanation: str
    warnings: list[str] = field(default_factory=list)

    @property
    def case_id(self):
        ids = {t.case_id for t in self.targets if t.case_id}
        return ids.pop() if len(ids) == 1 else None


@dataclass
class Exception_:
    reason: str
    detail: str
    category: str | None = None
    case_id: uuid.UUID | None = None
    priority: str = "media"


def suggest_category_text(description: str, reference: str | None, amount_cents: int) -> str | None:
    text = f"{description} {reference or ''}"
    for rx, cat in CATEGORY_HINTS:
        if rx.search(text):
            return cat
    return "cobro" if amount_cents > 0 and CASE_CODE.search(text.upper()) else None


def suggest_category(m: BankMovement) -> str | None:
    return suggest_category_text(m.description, m.reference, m.amount_cents)


def _taken(db: Session, target_type: str):
    """Destinos ya emparejados (propuesta abierta o validada)."""
    return select(BankMatch.target_id).where(BankMatch.target_type == target_type,
                                             BankMatch.status.in_(("propuesta", "validada")))


def _open_payments(db: Session, org_id, methods: tuple[str, ...], amount: int | None = None, around=None,
                   days: int = 5, case_id=None) -> list[Payment]:
    q = select(Payment).where(Payment.organization_id == org_id, Payment.status == "registrado",
                              Payment.method.in_(methods), Payment.id.not_in(_taken(db, "payment")))
    if amount is not None:
        q = q.where(Payment.amount_cents == amount)
    if case_id is not None:
        q = q.where(Payment.case_id == case_id)
    rows = list(db.execute(q.order_by(Payment.received_at)).scalars())
    if around is not None:
        rows = [x for x in rows if abs((x.received_at.date() - around).days) <= days]
    return rows


def _activity_warning(db: Session, acc: BankAccount, case_ids: set) -> list[str]:
    if acc.activity == "compartida":
        return []
    out = []
    for cid in case_ids:
        if cid is None:
            continue
        cf = db.get(CaseFile, cid)
        act = MATERIA_ACTIVITY.get(cf.materia) if cf else None
        if act and act != acc.activity:
            out.append(f"Atención: el expediente {cf.code} es de {cf.materia} y el dinero entró en la cuenta "
                       f"de {acc.activity} ({acc.name}).")
    return out


def _pay_targets(db: Session, pays: list[Payment]) -> list[Target]:
    return [Target("payment", x.id, x.amount_cents, x.case_id) for x in pays]


def _pay_text(db: Session, pays: list[Payment]) -> str:
    parts = []
    for x in pays:
        cf = db.get(CaseFile, x.case_id) if x.case_id else None
        parts.append(f"{cf.code if cf else 'consulta'} {eur(x.amount_cents)} ({x.method}, {x.received_at:%d/%m/%Y})")
    return "; ".join(parts)


# ------------------------------------------------------------------ reglas
def rule_traspaso(db: Session, m: BankMovement) -> Candidate | Exception_ | None:
    q = select(BankMovement).where(BankMovement.organization_id == m.organization_id,
                                   BankMovement.account_id != m.account_id,
                                   BankMovement.amount_cents == -m.amount_cents,
                                   BankMovement.status.in_(("pendiente", "sin_justificar")),
                                   BankMovement.booking_date.between(m.booking_date - timedelta(days=3),
                                                                     m.booking_date + timedelta(days=3)))
    others = [o for o in db.execute(q).scalars()
              if KW_TRASPASO.search(m.description) or KW_TRASPASO.search(o.description)]
    if not others:
        if KW_TRASPASO.search(m.description):
            return Exception_("traspaso_sin_contrapartida",
                              f"Parece un traspaso entre cuentas propias de {eur(m.amount_cents)}, pero no aparece el "
                              "movimiento contrario en otra cuenta (¿falta importar su extracto?). Un traspaso nunca "
                              "es un ingreso.", "traspaso", priority="media")
        return None
    if len(others) > 1:
        return Exception_("traspaso_ambiguo", f"Hay {len(others)} movimientos contrarios posibles para este "
                          "traspaso. Elija el correcto a mano.", "traspaso")
    o = others[0]
    oacc = db.get(BankAccount, o.account_id)
    return Candidate("traspaso", [Target("movement", o.id, -o.amount_cents)],
                     f"Traspaso entre cuentas propias: {eur(m.amount_cents)} el {m.booking_date:%d/%m/%Y} y "
                     f"{eur(o.amount_cents)} el {o.booking_date:%d/%m/%Y} en «{oacc.name}». No es un ingreso.")


def rule_referencia(db: Session, m: BankMovement, acc: BankAccount) -> Candidate | Exception_ | None:
    if m.amount_cents <= 0:
        return None
    hit = CASE_CODE.search(f"{m.description} {m.reference or ''}".upper())
    if not hit:
        return None
    code = f"{hit.group(1)}-{hit.group(2)}-{hit.group(3)}"
    cf = db.execute(select(CaseFile).where(CaseFile.organization_id == m.organization_id,
                                           CaseFile.code == code)).scalar_one_or_none()
    if cf is None:
        return Exception_("referencia_desconocida", f"El concepto menciona {code}, que no existe en esta entidad.",
                          "cobro", priority="alta")
    pays = _open_payments(db, m.organization_id, ("transferencia", "bizum", "pasarela"), case_id=cf.id)
    pays = [x for x in pays if x.amount_cents <= m.amount_cents]
    for n in range(1, min(4, len(pays)) + 1):
        combos = [c for c in itertools.combinations(pays, n) if sum(x.amount_cents for x in c) == m.amount_cents]
        if len(combos) == 1:
            c = list(combos[0])
            return Candidate("referencia", _pay_targets(db, c),
                             f"El concepto trae la referencia {code} y {'el cobro registrado' if n == 1 else f'{n} cobros registrados'} "
                             f"de ese expediente {'suma' if n > 1 else 'es de'} exactamente {eur(m.amount_cents)}: "
                             f"{_pay_text(db, c)}.", _activity_warning(db, acc, {cf.id}))
        if len(combos) > 1:
            return Exception_("referencia_ambigua", f"{code}: varias combinaciones de cobros suman "
                              f"{eur(m.amount_cents)}. Elija a mano.", "cobro", cf.id)
    return Exception_("cobro_no_registrado", f"Ha entrado {eur(m.amount_cents)} con la referencia {code}, pero no hay "
                      "cobros registrados de ese expediente que lo justifiquen. Registre el cobro en el expediente "
                      "(o concílielo a mano) para que cuadre.", "cobro", cf.id, priority="alta")


def rule_bizum(db: Session, m: BankMovement, acc: BankAccount) -> Candidate | Exception_ | None:
    if m.amount_cents <= 0 or not KW_BIZUM.search(m.description):
        return None
    pays = _open_payments(db, m.organization_id, ("bizum",), m.amount_cents, m.booking_date, days=3)
    if len(pays) == 1:
        return Candidate("bizum", _pay_targets(db, pays),
                         f"Bizum de {eur(m.amount_cents)} y un único cobro Bizum registrado del mismo importe en "
                         f"±3 días: {_pay_text(db, pays)}.", _activity_warning(db, acc, {pays[0].case_id}))
    if len(pays) > 1:
        return Exception_("bizum_ambiguo", f"Hay {len(pays)} cobros Bizum de {eur(m.amount_cents)} en esas fechas: "
                          f"{_pay_text(db, pays)}. Elija el correcto.", "bizum")
    return None


def rule_tpv(db: Session, m: BankMovement, acc: BankAccount) -> Candidate | Exception_ | None:
    if m.amount_cents <= 0 or not KW_TPV.search(m.description):
        return None
    pays = _open_payments(db, m.organization_id, ("tarjeta",), around=m.booking_date, days=4)
    pays = [x for x in pays if x.received_at.date() <= m.booking_date]
    by_day: dict = {}
    for x in pays:
        by_day.setdefault(x.received_at.date(), []).append(x)
    commissions = list(db.execute(select(BankMovement).where(
        BankMovement.account_id == m.account_id, BankMovement.amount_cents < 0,
        BankMovement.status.in_(("pendiente", "sin_justificar")),
        BankMovement.booking_date.between(m.booking_date - timedelta(days=1), m.booking_date + timedelta(days=1)))
    ).scalars())
    commissions = [c for c in commissions if KW_COMISION.search(c.description) and
                   (KW_TPV.search(c.description) or re.search(r"TARJETA", c.description, re.I))]
    found: list[Candidate] = []
    for day, ps in sorted(by_day.items(), reverse=True):
        gross = sum(x.amount_cents for x in ps)
        if gross == m.amount_cents:
            found.append(Candidate("tpv", _pay_targets(db, ps),
                                   f"Liquidación de TPV de {eur(m.amount_cents)} = {len(ps)} cobros con tarjeta del "
                                   f"{day:%d/%m/%Y} ({eur(gross)}), sin comisión descontada.",
                                   _activity_warning(db, acc, {x.case_id for x in ps})))
        for c in commissions:
            if gross == m.amount_cents - c.amount_cents and -c.amount_cents <= gross * 0.1:
                found.append(Candidate("tpv", _pay_targets(db, ps) + [Target("movement", c.id, c.amount_cents)],
                                       f"Liquidación de TPV: bruto {eur(gross)} ({len(ps)} cobros con tarjeta del "
                                       f"{day:%d/%m/%Y}) − comisión {eur(-c.amount_cents)} cargada el "
                                       f"{c.booking_date:%d/%m/%Y} = neto {eur(m.amount_cents)}.",
                                       _activity_warning(db, acc, {x.case_id for x in ps})))
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return Exception_("tpv_ambiguo", "Varias combinaciones de días de TPV cuadran con este abono. Elija a mano.",
                          "tpv")
    return Exception_("tpv_sin_cuadre", f"Liquidación de TPV de {eur(m.amount_cents)} que no cuadra con los cobros con "
                      "tarjeta registrados (ni con comisión). Revise los cobros con tarjeta de esos días.", "tpv",
                      priority="alta")


def rule_devolucion(db: Session, m: BankMovement) -> Candidate | Exception_ | None:
    if m.amount_cents >= 0:
        return None
    lo, hi = m.booking_date - timedelta(days=5), m.booking_date + timedelta(days=5)
    paid = [r for r in db.execute(select(Refund).where(
        Refund.organization_id == m.organization_id, Refund.status == "pagada",
        Refund.amount_cents == -m.amount_cents, Refund.pay_method.in_(("transferencia", "bizum")),
        Refund.id.not_in(_taken(db, "refund")))).scalars() if r.paid_at and lo <= r.paid_at.date() <= hi]
    if len(paid) == 1:
        r = paid[0]
        cf = db.get(CaseFile, r.case_id)
        return Candidate("devolucion", [Target("refund", r.id, m.amount_cents, r.case_id)],
                         f"Devolución pagada de {eur(r.amount_cents)} del expediente {cf.code} "
                         f"({r.pay_method}, {r.paid_at:%d/%m/%Y}).")
    if len(paid) > 1:
        return Exception_("devolucion_ambigua", f"{len(paid)} devoluciones pagadas de {eur(-m.amount_cents)} en esas "
                          "fechas. Elija la correcta.", "devolucion")
    approved = db.execute(select(func.count()).select_from(Refund).where(
        Refund.organization_id == m.organization_id, Refund.status == "aprobada",
        Refund.amount_cents == -m.amount_cents)).scalar()
    if approved:
        return Exception_("devolucion_sin_pago", f"Sale {eur(-m.amount_cents)} y hay una devolución APROBADA de ese "
                          "importe todavía sin pago registrado. Si es ella, registre el pago en la devolución y vuelva "
                          "a conciliar.", "devolucion", priority="alta")
    return None


REMESA = re.compile(r"\b(REM-20\d{2}-\d{4})\b")


def rule_factura(db: Session, m: BankMovement) -> Candidate | Exception_ | None:
    """Pago a proveedores: una remesa autorizada (cargo único por su total o con su código) o una factura validada
    del mismo importe cuyo proveedor aparece en el concepto (±10 días del vencimiento)."""
    from ..models_accounting import PaymentBatch, PaymentBatchItem, Supplier, SupplierInvoice

    if m.amount_cents >= 0:
        return None
    text = f"{m.description} {m.reference or ''}".upper()
    hit = REMESA.search(text)
    batches = list(db.execute(select(PaymentBatch).where(
        PaymentBatch.organization_id == m.organization_id, PaymentBatch.account_id == m.account_id,
        PaymentBatch.status.in_(("autorizada", "enviada")))).scalars())
    for b in batches:
        if (hit and hit.group(1) == b.code) or (b.total_cents == -m.amount_cents
                                                and abs((b.execution_date - m.booking_date).days) <= 5):
            invs = [(it, db.get(SupplierInvoice, it.invoice_id)) for it in db.execute(
                select(PaymentBatchItem).where(PaymentBatchItem.batch_id == b.id)).scalars()]
            invs = [(it, inv) for it, inv in invs if inv.status == "programada"
                    and inv.id not in set(db.execute(_taken(db, "invoice")).scalars())]
            if sum(it.amount_cents for it, _ in invs) == -m.amount_cents:
                return Candidate("remesa", [Target("invoice", inv.id, -it.amount_cents) for it, inv in invs],
                                 f"Cargo de la remesa {b.code} autorizada (doble firma): {len(invs)} factura(s) por "
                                 f"{eur(-m.amount_cents)}, fecha de ejecución {b.execution_date:%d/%m/%Y}.")
            if hit and hit.group(1) == b.code:
                return Exception_("remesa_no_cuadra", f"El cargo cita la remesa {b.code} pero su importe no coincide con "
                                  "las facturas pendientes de esa remesa. Revise si el banco la ha cargado en partes.",
                                  "proveedor", priority="alta")
    cands = []
    for inv in db.execute(select(SupplierInvoice).where(
            SupplierInvoice.organization_id == m.organization_id, SupplierInvoice.status.in_(("validada", "programada")),
            SupplierInvoice.total_cents == -m.amount_cents, SupplierInvoice.id.not_in(_taken(db, "invoice")))).scalars():
        sup = db.get(Supplier, inv.supplier_id)
        ref = inv.due_date or inv.issue_date
        words = [w for w in re.findall(r"[A-ZÁÉÍÓÚÑ]{4,}", sup.name.upper()) if w not in ("DEMO", "SOCIEDAD", "LIMITADA")]
        named = any(w in text for w in words) or inv.number.upper() in text
        if named and -10 <= (m.booking_date - ref).days <= 30:
            cands.append((inv, sup))
    if len(cands) == 1:
        inv, sup = cands[0]
        return Candidate("factura", [Target("invoice", inv.id, m.amount_cents)],
                         f"Pago de la factura {inv.number} de {sup.name} ({eur(inv.total_cents)}, vence "
                         f"{(inv.due_date or inv.issue_date):%d/%m/%Y}): mismo importe y el proveedor aparece en el concepto.")
    if len(cands) > 1:
        return Exception_("factura_ambigua", f"{len(cands)} facturas del mismo proveedor e importe. Elija la correcta.",
                          "proveedor")
    return None


def rule_importe_fecha(db: Session, m: BankMovement, acc: BankAccount) -> Candidate | Exception_ | None:
    if m.amount_cents <= 0:
        return None
    pays = _open_payments(db, m.organization_id, ("transferencia",), m.amount_cents, m.booking_date, days=5)
    if len(pays) == 1:
        return Candidate("importe_fecha", _pay_targets(db, pays),
                         f"Transferencia SIN referencia de expediente: un único cobro por transferencia de "
                         f"{eur(m.amount_cents)} registrado en ±5 días ({_pay_text(db, pays)}). Compruebe el "
                         f"ordenante{f' («{m.counterparty}»)' if m.counterparty else ''} antes de validar.",
                         _activity_warning(db, acc, {pays[0].case_id}))
    if len(pays) > 1:
        return Exception_("importe_ambiguo", f"{len(pays)} cobros por transferencia de {eur(m.amount_cents)} en esas "
                          f"fechas: {_pay_text(db, pays)}. Elija el correcto.", "cobro")
    return None


def evaluate(db: Session, m: BankMovement) -> Candidate | Exception_:
    acc = db.get(BankAccount, m.account_id)
    for fn in (lambda: rule_traspaso(db, m), lambda: rule_referencia(db, m, acc), lambda: rule_bizum(db, m, acc),
               lambda: rule_tpv(db, m, acc), lambda: rule_devolucion(db, m), lambda: rule_factura(db, m),
               lambda: rule_importe_fecha(db, m, acc)):
        r = fn()
        if r is not None:
            return r
    cat = suggest_category(m)
    if m.amount_cents > 0:
        return Exception_("ingreso_sin_identificar", f"Ha entrado {eur(m.amount_cents)} y no hay cobro registrado que lo "
                          "justifique. Identifique al cliente y registre el cobro, o concílielo a mano.", cat,
                          priority="alta")
    return Exception_("cargo_sin_justificar", f"Ha salido {eur(-m.amount_cents)}"
                      f"{f' (parece {cat.replace('_', ' ')})' if cat else ''}. Si es un proveedor, registre su factura en "
                      "Contabilidad → Proveedores y facturas y se conciliará; si no, dé el cargo por justificado con su categoría.", cat, priority="media" if cat else "alta")


def validated_sum(db: Session, movement_id) -> int:
    return int(db.execute(select(func.coalesce(func.sum(BankMatch.amount_cents), 0)).where(
        and_(BankMatch.movement_id == movement_id, BankMatch.status == "validada"))).scalar())
