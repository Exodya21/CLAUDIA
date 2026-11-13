"""Datos económicos FICTICIOS (F5.0): importes pactados, cobros, una devolución, caja y una tarjeta de empresa.

Incremental e idempotente: solo se cargan si la entidad demo no tiene aún ningún movimiento económico.
No se crean gastos con justificante (requieren un archivo): se prueban subiendo un ticket ficticio.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Branch, CaseFile, Organization, UserAccount
from .models_economy import CashMovement, Charge, CompanyCard, Payment, Refund, RefundEvent


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def seed_economy(db: Session) -> None:
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None or db.execute(select(func.count()).select_from(Charge)).scalar_one() > 0:
        return
    rnd = random.Random(2028)
    now = datetime.now(UTC)
    asesor, recep, conta, atc = (_u(db, n) for n in ("asesor.laboral.bcn", "recepcion.bcn", "contabilidad.demo", "atc.demo"))
    branches = {b.name: b for b in db.execute(select(Branch).where(Branch.organization_id == es.id)).scalars()}
    bcn = branches.get("Barcelona")
    cases = list(db.execute(select(CaseFile).where(CaseFile.organization_id == es.id)
                            .order_by(CaseFile.created_at).limit(10)).scalars())
    for i, cf in enumerate(cases):
        total = rnd.choice([30000, 45000, 60000, 90000])
        db.add(Charge(organization_id=es.id, case_id=cf.id, contact_id=cf.contact_id, kind="honorarios",
                      concept="Honorarios pactados en hoja de encargo (ficticio)", amount_cents=total, currency="EUR",
                      due_date=date.today() + timedelta(days=30 * (i % 3)), created_by=asesor.id))
        if i % 3 == 2:
            continue
        paid = total // 2
        method = "efectivo" if i % 2 == 0 else "transferencia"
        when = now - timedelta(days=10 - i)
        p = Payment(organization_id=es.id, case_id=cf.id, contact_id=cf.contact_id,
                    branch_id=bcn.id if bcn else None, amount_cents=paid, currency="EUR", method=method,
                    received_at=when, reference=None if method == "efectivo" else f"TRF-FICT-{1000 + i}",
                    registered_by=recep.id if method == "efectivo" else asesor.id,
                    status="confirmado" if i < 4 else "registrado")
        if p.status == "confirmado":
            p.confirmed_by, p.confirmed_at = conta.id, when + timedelta(days=1)
        db.add(p)
        db.flush()
        if method == "efectivo" and bcn:
            db.add(CashMovement(organization_id=es.id, branch_id=bcn.id, kind="cobro", amount_cents=paid, currency="EUR",
                                concept=f"Cobro {cf.code}", payment_id=p.id, created_by=recep.id))
    if bcn:
        db.add(CashMovement(organization_id=es.id, branch_id=bcn.id, kind="aportacion", amount_cents=20000,
                            currency="EUR", concept="Fondo de caja inicial (ficticio)", created_by=conta.id))
    if cases:
        cf = cases[0]
        r = Refund(organization_id=es.id, case_id=cf.id, contact_id=cf.contact_id, amount_cents=5000, currency="EUR",
                   reason="El cliente indica que pagó dos veces la primera consulta (ficticio)", requested_by=atc.id)
        db.add(r)
        db.flush()
        db.add(RefundEvent(refund_id=r.id, actor_user_id=atc.id, to_status="registrada", note=r.reason))
    if asesor and db.execute(select(func.count()).select_from(CompanyCard)).scalar_one() == 0:
        db.add(CompanyCard(organization_id=es.id, holder_user_id=asesor.id, last4="0042",
                           label="Visa empresa Laboral BCN (ficticia)"))
    db.flush()
