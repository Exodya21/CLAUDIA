"""Extractos Norma 43 FICTICIOS para probar la conciliación (solo APP_ENV development/test).

Se construyen a partir de los cobros marcados «[demo banco]» por `seed_bank` y añaden los casos que no tienen
cobro: comisión de TPV, seguro social, ingreso sin identificar, referencia sin cobro registrado y un traspaso A → C.
Ningún dato es real: nombres «DEMO», cuentas 1111/2222/3333.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CaseFile
from ..models_bank import BankAccount
from ..models_economy import Payment
from ..seed_bank import DEMO_NOTE
from .parsers import build_n43


def demo_statement(db: Session, acc: BankAccount) -> tuple[bytes, str]:
    today = date.today()
    start, end = today - timedelta(days=10), today - timedelta(days=1)
    pays = list(db.execute(select(Payment).where(Payment.organization_id == acc.organization_id,
                                                 Payment.notes.like(f"{DEMO_NOTE}%")).order_by(Payment.received_at)).scalars())
    moves: list[tuple[date, int, str, str, str]] = []
    if acc.purpose == "A_laboral":
        laboral = [x for x in pays if x.case_id and db.get(CaseFile, x.case_id).materia == "laboral"]
        cards = [x for x in laboral if x.method == "tarjeta"]
        for x in laboral:
            cf = db.get(CaseFile, x.case_id)
            d = x.received_at.date()
            if "referencia" in (x.notes or ""):
                moves.append((d, x.amount_cents, "04", "", f"TRANSF DEMO CLIENTE REF {cf.code} HONORARIOS"))
            elif x.method == "bizum":
                moves.append((d, x.amount_cents, "04", "", "BIZUM RECIBIDO DE CLIENTE DEMO"))
            elif "importe_fecha" in (x.notes or ""):
                moves.append((d + timedelta(days=1), x.amount_cents, "04", "", "TRANSFERENCIA RECIBIDA ORDENANTE DEMO"))
        if cards:
            day = cards[0].received_at.date() + timedelta(days=1)
            gross = sum(x.amount_cents for x in cards)
            moves.append((day, gross - 500, "12", "", "LIQUIDACION TPV COMERCIO 0001 DEMO"))
            moves.append((day, -500, "17", "", "COMISION TPV TARJETAS DEMO"))
        moves.append((end - timedelta(days=2), -62040, "15", "", "SEGURIDAD SOCIAL TGSS CUOTA DEMO"))
        moves.append((end - timedelta(days=1), 20000, "04", "", "TRANSFERENCIA DE J. FICTICIO DEMO"))
        second = next((cf for cf in db.execute(select(CaseFile).where(
            CaseFile.organization_id == acc.organization_id, CaseFile.materia == "laboral").order_by(CaseFile.code)
            .offset(1).limit(1)).scalars()), None)
        if second is not None:
            moves.append((end, 30000, "04", "", f"TRANSF REF {second.code} PROVISION FONDOS"))
        moves.append((end - timedelta(days=3), -100000, "04", "", "TRASPASO A CUENTA C TESORERIA DEMO"))
        # Cargo de las remesas de proveedores autorizadas y enviadas (F5.4)
        from ..models_accounting import PaymentBatch
        for b in db.execute(select(PaymentBatch).where(PaymentBatch.account_id == acc.id,
                                                       PaymentBatch.status.in_(("autorizada", "enviada")))).scalars():
            if start <= b.execution_date <= end:
                moves.append((b.execution_date, -b.total_cents, "04", "", f"REMESA TRANSFERENCIAS {b.code} DEMO"))
    elif acc.purpose == "B_extranjeria":
        for x in pays:
            cf = db.get(CaseFile, x.case_id) if x.case_id else None
            if cf and cf.materia in ("extranjeria", "nacionalidad"):
                moves.append((x.received_at.date(), x.amount_cents, "04", "", f"TRANSFERENCIA {cf.code} TASA Y HONORARIOS"))
        moves.append((end, -1200, "17", "", "COMISION MANTENIMIENTO CUENTA DEMO"))
    else:
        moves.append((end - timedelta(days=3), 100000, "04", "", "TRASPASO DESDE CUENTA A LABORAL DEMO"))
        moves.append((end, 35, "17", "", "INTERESES CUENTA REMUNERADA DEMO"))
    moves.sort(key=lambda m: m[0])
    opening = {"A_laboral": 1_000_000, "B_extranjeria": 500_000}.get(acc.purpose, 2_000_000)
    data = build_n43(bank="9999", branch="0001", account10=f"000000{acc.iban_last4}", start=start, end=end,
                     opening_cents=opening, moves=moves)
    return data, f"extracto_FICTICIO_{acc.iban_last4}_{end:%Y%m%d}.n43"
