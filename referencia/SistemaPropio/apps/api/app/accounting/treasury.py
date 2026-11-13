"""Tesorería (DR-CON-7): saldos por banco, previsión de pagos y fichero SEPA de transferencias (pain.001.001.03).

- Saldo de una cuenta = saldo final del último extracto importado (comprobado) + nada inventado: si el extracto es
  antiguo se indica la fecha. Saldo de cajas = suma de sus movimientos.
- La previsión solo usa lo que existe: facturas validadas o programadas con su vencimiento y remesas autorizadas.
  No se inventan cobros futuros: los importes pendientes de cobro se muestran aparte, sin fecha.
- El fichero SEPA se genera para que una persona lo suba a la banca electrónica: el sistema no ordena pagos.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from xml.sax.saxutils import escape

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Organization
from ..models_accounting import PaymentBatch, PaymentBatchItem, Supplier, SupplierInvoice
from ..models_bank import BankAccount, BankImport, BankMovement
from ..models_economy import CashMovement
from ..services import textcrypt


def account_balance(db: Session, acc: BankAccount, until: date | None = None) -> dict:
    q = select(BankImport).where(BankImport.account_id == acc.id, BankImport.closing_cents.is_not(None),
                                 BankImport.period_to.is_not(None))
    if until:
        q = q.where(BankImport.period_to <= until)
    imp = db.execute(q.order_by(BankImport.period_to.desc(), BankImport.imported_at.desc()).limit(1)).scalar_one_or_none()
    if imp is None:
        return {"balance_cents": None, "as_of": None, "fiable": False}
    pending = db.execute(select(func.count()).select_from(BankMovement).where(
        BankMovement.account_id == acc.id, BankMovement.booking_date <= imp.period_to,
        BankMovement.status.in_(("pendiente", "propuesto", "parcial", "sin_justificar")))).scalar_one()
    return {"balance_cents": imp.closing_cents, "as_of": imp.period_to.isoformat(), "fiable": bool(imp.balance_ok),
            "movimientos_sin_conciliar": pending}


def cash_balances(db: Session, org_id, until: datetime | None = None) -> int:
    q = select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(CashMovement.organization_id == org_id)
    if until:
        q = q.where(CashMovement.at < until)
    return int(db.execute(q).scalar_one())


def forecast(db: Session, org_id, days: int = 90) -> dict:
    today = date.today()
    rows = list(db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == org_id, SupplierInvoice.status.in_(("validada", "programada")))).scalars())
    buckets = {"vencido": 0, "7": 0, "30": 0, "60": 0, "90": 0, "sin_fecha": 0}
    for x in rows:
        if x.due_date is None:
            buckets["sin_fecha"] += x.total_cents
            continue
        d = (x.due_date - today).days
        key = "vencido" if d < 0 else "7" if d <= 7 else "30" if d <= 30 else "60" if d <= 60 else "90" if d <= days else None
        if key:
            buckets[key] += x.total_cents
    accounts = []
    total_bank = 0
    for a in db.execute(select(BankAccount).where(BankAccount.organization_id == org_id, BankAccount.active)
                        .order_by(BankAccount.purpose, BankAccount.name)).scalars():
        b = account_balance(db, a)
        accounts.append({"id": str(a.id), "name": a.name, "bank": a.bank_name, "iban_last4": a.iban_last4,
                         "purpose": a.purpose, "currency": a.currency, "has_iban": bool(a.iban_enc), **b})
        total_bank += b["balance_cents"] or 0
    cash = cash_balances(db, org_id)
    outflow_30 = buckets["vencido"] + buckets["7"] + buckets["30"]
    return {"accounts": accounts, "bank_total_cents": total_bank, "cash_total_cents": cash,
            "payables": buckets, "payables_total_cents": sum(buckets.values()),
            "available_after_30_cents": total_bank + cash - outflow_30,
            "note": "Previsión con facturas validadas y programadas. Los cobros pendientes no tienen fecha cierta y "
                    "no se suman a la previsión."}


def next_batch_code(db: Session, year: int) -> str:
    n = db.execute(select(func.count()).select_from(PaymentBatch).where(PaymentBatch.code.like(f"REM-{year}-%"))).scalar_one()
    return f"REM-{year}-{n + 1:04d}"


def sepa_xml(db: Session, batch: PaymentBatch) -> bytes:
    """pain.001.001.03 (transferencias SEPA). Exige IBAN completo de la cuenta de cargo y de cada proveedor."""
    acc = db.get(BankAccount, batch.account_id)
    org = db.get(Organization, batch.organization_id)
    if not acc.iban_enc:
        raise ValueError(f"La cuenta «{acc.name}» no tiene el IBAN completo informado.")
    debtor_iban = textcrypt.dec(acc.iban_enc)
    items = list(db.execute(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)).scalars())
    tx = []
    for i, it in enumerate(items, start=1):
        inv = db.get(SupplierInvoice, it.invoice_id)
        sup = db.get(Supplier, inv.supplier_id)
        if not sup.iban_enc:
            raise ValueError(f"El proveedor «{sup.name}» no tiene IBAN.")
        iban = textcrypt.dec(sup.iban_enc)
        tx.append(f"""
      <CdtTrfTxInf>
        <PmtId><EndToEndId>{escape(batch.code)}-{i:03d}</EndToEndId></PmtId>
        <Amt><InstdAmt Ccy="{batch.currency}">{it.amount_cents / 100:.2f}</InstdAmt></Amt>
        <Cdtr><Nm>{escape(sup.name[:70])}</Nm></Cdtr>
        <CdtrAcct><Id><IBAN>{iban}</IBAN></Id></CdtrAcct>
        <RmtInf><Ustrd>{escape(f"Factura {inv.number}"[:140])}</Ustrd></RmtInf>
      </CdtTrfTxInf>""")
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    total = f"{sum(it.amount_cents for it in items) / 100:.2f}"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{escape(batch.code)}</MsgId><CreDtTm>{now}</CreDtTm><NbOfTxs>{len(items)}</NbOfTxs><CtrlSum>{total}</CtrlSum>
      <InitgPty><Nm>{escape(org.name[:70])}</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{escape(batch.code)}</PmtInfId><PmtMtd>TRF</PmtMtd><NbOfTxs>{len(items)}</NbOfTxs><CtrlSum>{total}</CtrlSum>
      <PmtTpInf><SvcLvl><Cd>SEPA</Cd></SvcLvl></PmtTpInf>
      <ReqdExctnDt>{batch.execution_date.isoformat()}</ReqdExctnDt>
      <Dbtr><Nm>{escape(org.name[:70])}</Nm></Dbtr>
      <DbtrAcct><Id><IBAN>{debtor_iban}</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId></DbtrAgt>
      <ChrgBr>SLEV</ChrgBr>{"".join(tx)}
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
"""
    return xml.encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def due_soon(db: Session, org_id, days: int = 7) -> list[SupplierInvoice]:
    lim = date.today() + timedelta(days=days)
    return list(db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == org_id,
                                                         SupplierInvoice.status == "validada",
                                                         SupplierInvoice.due_date.is_not(None),
                                                         SupplierInvoice.due_date <= lim)).scalars())
