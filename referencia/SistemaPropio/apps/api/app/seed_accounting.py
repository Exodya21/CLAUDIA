"""Datos FICTICIOS de F5.4: proveedores, facturas recibidas en todos los estados y una remesa con doble firma.

Las fechas se calculan desde hoy para que haya de todo: una factura recibida por validar, una que vence pronto, otra
vencida y una remesa autorizada y enviada cuyo cargo aparece en el extracto ficticio de la cuenta A (se concilia
con la regla «remesa»). CIF e IBAN inventados con dígitos de control válidos (entidad 9999, que no existe).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .accounting.invoices import demo_iban, invoice_pdf
from .accounting.treasury import sepa_xml, sha
from .models import Branch, Organization, UserAccount
from .models_accounting import PaymentBatch, PaymentBatchApproval, PaymentBatchItem, Supplier, SupplierInvoice
from .models_bank import BankAccount
from .services import textcrypt, vault

OWN_CIF = "B12345674"  # CIF ficticio del despacho en las muestras


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def seed_accounting(db: Session) -> None:
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None or db.execute(select(func.count()).select_from(Supplier)).scalar_one() > 0:
        return
    conta, dire, socio = _u(db, "contabilidad.demo"), _u(db, "direccion.demo"), _u(db, "socio.demo")
    if not (conta and dire and socio):
        return
    accounts = {a.purpose: a for a in db.execute(select(BankAccount).where(BankAccount.organization_id == es.id)).scalars()}
    for a in accounts.values():
        if not a.iban_enc:
            a.iban_enc = textcrypt.enc(demo_iban("9999", "0001", f"000000{a.iban_last4}"))
    bcn = db.execute(select(Branch).where(Branch.organization_id == es.id, Branch.name == "Barcelona")).scalar_one()
    today = date.today()
    prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    sup_rows = [
        ("Alquileres Demo SL", "B22222228", "alquiler", "compartida", bcn.id, 10, True, "0002"),
        ("Energía Ficticia SA", "A11111119", "suministros", "compartida", None, 15, True, "0003"),
        ("Software Jurídico Demo SL", "B33333337", "software", "compartida", None, 30, False, "0004"),
        ("Gestoría Prueba SL", "B44444446", "gestoria", "compartida", None, 30, True, "0005"),
        ("Telefonía Demo SL", "B55555551", "telefonia", "compartida", None, 20, True, "0006"),
    ]
    sups = {}
    for name, cif, cat, act, branch, terms, rec, n in sup_rows:
        iban = demo_iban("9999", n, f"0000{n}01")
        s = Supplier(organization_id=es.id, name=name, tax_id=cif, iban_enc=textcrypt.enc(iban), iban_last4=iban[-4:],
                     email=f"facturas@{name.split()[0].lower()}.invalid", category=cat, activity=act, branch_id=branch,
                     payment_terms_days=terms, recurring=rec, created_by=conta.id)
        db.add(s)
        sups[cat] = (s, iban)
    db.flush()
    # (categoría, número, emisión, base, % IVA, IVA, retención, estado, días desde registro, concepto)
    inv_rows = [
        ("alquiler", f"A-{prev:%Y}/{prev.month:02d}01", prev, 120000, 21, 25200, 22800, "programada", 30, "Alquiler oficina Barcelona"),
        ("suministros", f"E-{prev:%Y%m}-778", prev + timedelta(days=4), 30000, 21, 6300, 0, "programada", 25, "Electricidad oficinas"),
        ("software", f"SJ-{today:%Y}-0042", today - timedelta(days=25), 45000, 21, 9450, 0, "validada", 20, "Licencias del programa de gestión"),
        ("gestoria", f"G-{prev:%Y}-311", prev + timedelta(days=1), 50000, 21, 10500, 7500, "validada", 30, "Asesoría contable"),
        ("telefonia", f"T{today:%Y%m}-5521", today - timedelta(days=4), 8000, 21, 1680, 0, "recibida", 3, "Telefonía e internet"),
    ]
    invs = {}
    for cat, num, issue, base, rate, vat, wh, status, ago, concept in inv_rows:
        s, iban = sups[cat]
        due = issue + timedelta(days=s.payment_terms_days or 0)
        if cat == "software":
            due = today + timedelta(days=5)  # vence pronto
        if cat == "gestoria":
            due = today - timedelta(days=3)  # vencida
        data = invoice_pdf(supplier=s.name, supplier_tax_id=s.tax_id, customer=es.name, customer_tax_id=OWN_CIF, number=num,
                           issue=issue, due=due, concept=concept, base_cents=base, vat_rate=rate, vat_cents=vat,
                           withholding_cents=wh, iban=iban)
        path, digest = vault.store(data)
        x = SupplierInvoice(organization_id=es.id, supplier_id=s.id, number=num, issue_date=issue, due_date=due,
                            base_cents=base, vat_cents=vat, withholding_cents=wh, total_cents=base + vat - wh,
                            currency=es.currency, category=cat, activity=s.activity, branch_id=s.branch_id,
                            description=f"{concept} (ficticio)", status=status, file_name=f"factura_{num.replace('/', '-')}.pdf",
                            file_mime="application/pdf", file_sha256=digest, file_path=path, registered_by=conta.id,
                            registered_at=datetime.now(UTC) - timedelta(days=ago),
                            validated_by=dire.id if status != "recibida" else None,
                            validated_at=datetime.now(UTC) - timedelta(days=ago - 1) if status != "recibida" else None)
        db.add(x)
        invs[cat] = x
    db.flush()
    acc = accounts.get("A_laboral")
    if acc is None:
        return
    batch_invs = [invs["alquiler"], invs["suministros"]]
    b = PaymentBatch(organization_id=es.id, code=f"REM-{today:%Y}-0001", account_id=acc.id,
                     execution_date=today - timedelta(days=4), total_cents=sum(i.total_cents for i in batch_invs),
                     currency=es.currency, status="enviada", proposed_by=conta.id, sent_by=conta.id,
                     sent_at=datetime.now(UTC) - timedelta(days=5), note="Remesa ficticia de pruebas")
    db.add(b)
    db.flush()
    for i in batch_invs:
        db.add(PaymentBatchItem(organization_id=es.id, batch_id=b.id, invoice_id=i.id, amount_cents=i.total_cents))
    db.flush()
    for u in (dire, socio):
        db.add(PaymentBatchApproval(organization_id=es.id, batch_id=b.id, approver_id=u.id, decision="autoriza",
                                    note="Revisada (ficticio)"))
    db.flush()
    b.sepa_sha256 = sha(sepa_xml(db, b))
    db.flush()


DEMO_OWNERS = {"contabilidad.demo": ("d_extractos", "d_conciliar", "s_facturas", "s_pagos", "s_cajas", "m_extractos",
                                     "m_conciliar", "m_documentos", "m_cierre"),
               "direccion.demo": ("s_informe", "q_informe", "m_aprobar", "m_informe")}


def seed_routine_owners(db: Session) -> None:
    """Responsables FICTICIOS de la rutina de Contabilidad (F5.4b); en real los asigna Dirección."""
    from .models_accounting import RoutineOwner
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    dire = _u(db, "direccion.demo")
    if es is None or dire is None:
        return
    for username, steps in DEMO_OWNERS.items():
        u = _u(db, username)
        if u is None:
            continue
        for step in steps:
            if not db.execute(select(RoutineOwner.id).where(RoutineOwner.organization_id == es.id, RoutineOwner.step == step)).first():
                db.add(RoutineOwner(organization_id=es.id, step=step, user_id=u.id, updated_by=dire.id))
    db.flush()
