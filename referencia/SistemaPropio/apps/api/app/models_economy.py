"""Modelo F5.0 — control económico NO fiscal (M14 parcial, M13 devoluciones).

Requisitos: Q-3.9 (devoluciones con Contabilidad), Q-4.4 (registro de devoluciones, sin facturas de abono),
Q-4.14 (caja por sede), Q-2.6/Q-4.3 (registro de cobros; la pasarela llega con F1.3), I-101, I-110 (base del
cuadro de mando).

Límites deliberados (decisiones abiertas D-05, D-07, D-16, D-18, D-25):
- Aquí NO se emiten facturas ni se calculan honorarios, IVA ni suplidos. Los importes los introduce una persona.
- `invoice_ref` solo guarda el número de la factura emitida en el programa homologado que elija el despacho.
- Ningún registro se borra: los errores se anulan con motivo y las cajas se corrigen con movimientos.
Importes en céntimos (enteros) y moneda de la entidad.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class Charge(Base):
    """Importe pactado pendiente de cobro en un expediente (lo introduce una persona; no se calcula)."""

    __tablename__ = "charge"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # honorarios | gasto_cliente | otro
    concept: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="vigente")  # vigente | anulado
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))


class Payment(Base):
    """Cobro recibido. Contabilidad lo confirma (conciliación) o lo anula con motivo."""

    __tablename__ = "payment"
    __table_args__ = (Index("ix_payment_org_status", "organization_id", "status"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    # F5.2: una consulta se puede cobrar en Recepción antes de abrir expediente (solo `kind == "consulta"`).
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"), index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))  # obligatoria si es efectivo
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # efectivo | tarjeta | transferencia | bizum | pasarela
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="registrado")  # registrado | confirmado | anulado
    invoice_ref: Mapped[str | None] = mapped_column(String(60))  # nº de factura del programa homologado (D-25)
    kind: Mapped[str | None] = mapped_column(String(12))  # F5.2: consulta | provision | servicio | otro
    duplicate_reason: Mapped[str | None] = mapped_column(String(300))  # F5.2: por qué no es un cobro repetido
    registered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    annulled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    annulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    annul_reason: Mapped[str | None] = mapped_column(String(500))


class Refund(Base):
    """Solicitud de devolución. ATC registra, investiga y escala; Contabilidad aprueba o rechaza y paga (A-09)."""

    __tablename__ = "refund"
    __table_args__ = (Index("ix_refund_org_status", "organization_id", "status"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # lo que pide el cliente, en sus términos
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="registrada")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    legal_opinion: Mapped[str | None] = mapped_column(Text)  # informe del letrado: orienta, no decide
    legal_opinion_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    legal_opinion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    paid_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pay_method: Mapped[str | None] = mapped_column(String(20))
    pay_reference: Mapped[str | None] = mapped_column(String(120))
    pay_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RefundEvent(Base):
    """Historial inmutable de la devolución."""

    __tablename__ = "refund_event"
    id: Mapped[uuid.UUID] = _uuid()
    refund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("refund.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = _created()


class CashMovement(Base):
    """Movimiento de la caja en efectivo de una sede. Solo se añade; los errores se corrigen con otro movimiento."""

    __tablename__ = "cash_movement"
    __table_args__ = (Index("ix_cash_branch_at", "branch_id", "at"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), nullable=False)
    # cobro | anulacion_cobro | devolucion | gasto | ingreso_banco | aportacion | ajuste_arqueo
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)  # con signo: + entra, − sale
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    concept: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment.id"))
    refund_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refund.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    at: Mapped[datetime] = _created()


class CashClosing(Base):
    """Arqueo: lo que debería haber, lo contado y la diferencia. Solo se añade."""

    __tablename__ = "cash_closing"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), nullable=False, index=True)
    expected_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counted_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    difference_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    closed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    closed_at: Mapped[datetime] = _created()
    # F5.2 (DR-REC-4): cierre del día validado por un responsable distinto de quien cuenta
    day: Mapped[date | None] = mapped_column(Date)  # día de trabajo (hora de la sede)
    status: Mapped[str] = mapped_column(String(22), nullable=False, default="validado", server_default="validado")
    # pendiente_validacion | validado | rechazado (los arqueos anteriores a F5.2 se consideran validados)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_note: Mapped[str | None] = mapped_column(String(500))


# ---------------------------------------------------------------- Gastos de empresa (Q-4.13, Q-4.14, Q-4.5 parcial)
class CompanyCard(Base):
    """Tarjeta de empresa asignada a una persona. Solo se guardan los 4 últimos dígitos."""

    __tablename__ = "company_card"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    holder_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = _created()


class Expense(Base):
    """Gasto de empresa con su justificante. La lectura automática propone; la persona confirma."""

    __tablename__ = "expense"
    __table_args__ = (Index("ix_expense_org_status", "organization_id", "status"),
                      Index("ix_expense_employee_date", "employee_id", "expense_date"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador")
    # borrador → enviado → aprobado → conciliado ; enviado → devuelto → enviado ; * → anulado
    expense_date: Mapped[date | None] = mapped_column(Date)
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    supplier_tax_id: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(String(500))
    amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    vat_cents: Mapped[int | None] = mapped_column(BigInteger)  # cuota de IVA leída del justificante (dato, no criterio fiscal)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(20))  # efectivo_caja | tarjeta_empresa | personal
    card_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company_card.id"))
    receipt_name: Mapped[str | None] = mapped_column(String(200))
    receipt_mime: Mapped[str | None] = mapped_column(String(60))
    receipt_size: Mapped[int | None] = mapped_column(Integer)
    receipt_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    receipt_path: Mapped[str | None] = mapped_column(String(200))  # archivo cifrado en el almacén de justificantes
    ocr_engine: Mapped[str | None] = mapped_column(String(40))
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_suggestion: Mapped[dict | None] = mapped_column(JSONB)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(500))
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconcile_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ExpenseEvent(Base):
    __tablename__ = "expense_event"
    id: Mapped[uuid.UUID] = _uuid()
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    at: Mapped[datetime] = _created()


class CardTransaction(Base):
    """Movimiento del extracto de una tarjeta de empresa (importado por Contabilidad)."""

    __tablename__ = "card_transaction"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company_card.id"), nullable=False, index=True)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)  # positivo = cargo en la tarjeta
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # evita duplicar al reimportar
    expense_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("expense.id"))
    imported_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    imported_at: Mapped[datetime] = _created()
