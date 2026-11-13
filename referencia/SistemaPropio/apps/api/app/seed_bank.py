"""Datos FICTICIOS de F5.1: cuentas A/B/C y cobros registrados que reproducen los casos típicos de conciliación.

Incremental e idempotente. Los cobros llevan la nota «[demo banco]» para que el generador de extractos ficticios
(`bank/demo.py`, solo en desarrollo y pruebas) cree el extracto que los concilia.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Branch, CaseFile, Organization, UserAccount
from .models_bank import BankAccount
from .models_economy import Payment

DEMO_NOTE = "[demo banco]"
# (cuenta, materia del expediente, nº de orden, método, importe, días atrás, regla esperada)
SCENARIO = [
    ("A", "laboral", 0, "transferencia", 41250, 6, "referencia"),
    ("A", "laboral", 1, "bizum", 8000, 5, "bizum"),
    ("A", "laboral", 2, "tarjeta", 15000, 4, "tpv"),
    ("A", "laboral", 3, "tarjeta", 10000, 4, "tpv"),
    ("A", "laboral", 4, "transferencia", 37500, 3, "importe_fecha"),
    ("B", "extranjeria", 0, "transferencia", 25000, 4, "referencia"),
]


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def seed_bank(db: Session) -> None:
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None or db.execute(select(func.count()).select_from(BankAccount)).scalar_one() > 0:
        return
    conta = _u(db, "contabilidad.demo") or _u(db, "direccion.demo")
    recep = _u(db, "recepcion.bcn") or conta
    branches = {b.name: b for b in db.execute(select(Branch).where(Branch.organization_id == es.id)).scalars()}
    accounts = {
        "A": BankAccount(organization_id=es.id, name="Cuenta A · Laboral", bank_name="Banco Ficticio Uno",
                         iban_last4="1111", purpose="A_laboral", activity="laboral", created_by=conta.id),
        "B": BankAccount(organization_id=es.id, name="Cuenta B · Extranjería", bank_name="Banco Ficticio Uno",
                         iban_last4="2222", purpose="B_extranjeria", activity="extranjeria", created_by=conta.id),
        "C": BankAccount(organization_id=es.id, name="Cuenta C · Tesorería", bank_name="Banco Ficticio Dos",
                         iban_last4="3333", purpose="C_tesoreria", activity="compartida", created_by=conta.id),
    }
    for a in accounts.values():
        db.add(a)
    now = datetime.now(UTC).replace(hour=11, minute=0, second=0, microsecond=0)
    by_materia: dict[str, list[CaseFile]] = {}
    for cf in db.execute(select(CaseFile).where(CaseFile.organization_id == es.id).order_by(CaseFile.code)).scalars():
        by_materia.setdefault(cf.materia, []).append(cf)
    for _acc, materia, idx, method, amount, days, rule in SCENARIO:
        cases = by_materia.get(materia) or []
        if not cases:
            continue
        cf = cases[idx % len(cases)]
        db.add(Payment(organization_id=es.id, case_id=cf.id, contact_id=cf.contact_id,
                       branch_id=branches["Barcelona"].id if "Barcelona" in branches else None, amount_cents=amount,
                       currency="EUR", method=method, received_at=now - timedelta(days=days),
                       reference=None, notes=f"{DEMO_NOTE} regla esperada: {rule}",
                       registered_by=(recep if method == "tarjeta" else conta).id, status="registrado"))
    db.flush()
