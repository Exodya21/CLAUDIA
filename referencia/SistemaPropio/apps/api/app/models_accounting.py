"""F5.4 — Contabilidad: proveedores, facturas recibidas, tesorería con remesas de doble autorización y cierre
provisional mensual (DR-CON-1, 4, 5, 7, 8).

- Nada de esto es la contabilidad oficial (la lleva la gestoría) ni emite facturas: registra lo recibido, lo
  conciliamos con el banco y preparamos el cierre provisional del día 5, siempre rastreable hasta el original.
- IVA y retenciones son DATOS leídos de la factura y confirmados por una persona; el sistema no aplica criterio fiscal.
- El agente nunca ordena transferencias: la remesa necesita DOS autorizaciones de personas distintas de quien la
  propone y se descarga como fichero SEPA para subirlo al banco; el pago se da por hecho al conciliarlo con el extracto.
- Nada se borra. Un cierre aprobado es inmutable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class Supplier(Base):
    __tablename__ = "supplier"
    __table_args__ = (UniqueConstraint("organization_id", "tax_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), nullable=False)  # CIF/NIF con control válido
    iban_enc: Mapped[str | None] = mapped_column(Text)  # cifrado; solo se muestra enmascarado
    iban_last4: Mapped[str | None] = mapped_column(String(4))
    email: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # alquiler, suministros, software…
    activity: Mapped[str] = mapped_column(String(12), nullable=False, default="compartida")
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    payment_terms_days: Mapped[int | None] = mapped_column(Integer)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # factura cada mes
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoice"
    __table_args__ = (UniqueConstraint("supplier_id", "number"),
                      Index("ix_supplier_invoice_org_status", "organization_id", "status"),
                      Index("ix_supplier_invoice_due", "organization_id", "due_date"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)  # fecha del documento
    operation_date: Mapped[date | None] = mapped_column(Date)  # fecha de la operación (si difiere)
    due_date: Mapped[date | None] = mapped_column(Date)
    base_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vat_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # dato de la factura
    withholding_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # retención (dato)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)  # base + IVA − retención
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # centro de coste / tipo de gasto
    activity: Mapped[str] = mapped_column(String(12), nullable=False)  # laboral | extranjeria | compartida
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    description: Mapped[str | None] = mapped_column(String(500))
    # recibida → validada → programada → pagada ; rechazada (con motivo). Nada se borra.
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="recibida")
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_mime: Mapped[str] = mapped_column(String(60), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)  # original cifrado, sin modificar
    extracted: Mapped[dict | None] = mapped_column(JSONB)  # lo que propuso la lectura
    registered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    registered_at: Mapped[datetime] = _created()
    validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(String(300))
    paid_at: Mapped[date | None] = mapped_column(Date)
    paid_movement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_movement.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PaymentBatch(Base):
    """Remesa de pagos a proveedores. Propone Contabilidad; autorizan DOS personas distintas (DR-CON-7)."""

    __tablename__ = "payment_batch"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # REM-2026-0001
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.id"), nullable=False)
    execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # propuesta → autorizada (2 firmas) → enviada (fichero descargado y subido al banco por una persona) ;
    # rechazada | anulada (con motivo)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="propuesta")
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    proposed_at: Mapped[datetime] = _created()
    note: Mapped[str | None] = mapped_column(String(500))
    sepa_sha256: Mapped[str | None] = mapped_column(String(64))  # huella del fichero generado
    sent_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PaymentBatchItem(Base):
    __tablename__ = "payment_batch_item"
    __table_args__ = (UniqueConstraint("batch_id", "invoice_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_batch.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_invoice.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PaymentBatchApproval(Base):
    __tablename__ = "payment_batch_approval"
    __table_args__ = (UniqueConstraint("batch_id", "approver_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_batch.id"), nullable=False, index=True)
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # autoriza | rechaza
    note: Mapped[str | None] = mapped_column(String(300))
    at: Mapped[datetime] = _created()


class MonthClose(Base):
    """Cierre provisional del mes (DR-CON-8). Cada recálculo es una versión; aprobado = congelado."""

    __tablename__ = "month_close"
    __table_args__ = (UniqueConstraint("organization_id", "month", "revision"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # AAAA-MM
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # borrador → revisado (Contabilidad) → aprobado (Dirección, persona distinta) ; sustituido (hay revisión nueva)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="borrador")
    figures: Mapped[dict] = mapped_column(JSONB, nullable=False)
    figures_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prepared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    prepared_at: Mapped[datetime] = _created()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(1000))


# ---------------------------------------------------------------- F5.4b — rutina de trabajo e informes periódicos
class RoutineOwner(Base):
    """Responsable de cada paso de la rutina de Contabilidad en una entidad (lo asigna Dirección)."""

    __tablename__ = "accounting_routine_owner"
    __table_args__ = (UniqueConstraint("organization_id", "step"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    step: Mapped[str] = mapped_column(String(30), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    updated_at: Mapped[datetime] = _created()


class RoutineItem(Base):
    """Un paso de la rutina en un periodo concreto (día, semana, quincena o mes).

    Se da por HECHO solo cuando el sistema lo comprueba con los datos (no basta con marcarlo); «no aplica» exige motivo.
    """

    __tablename__ = "accounting_routine_item"
    __table_args__ = (UniqueConstraint("organization_id", "step", "period"),
                      Index("ix_routine_item_org_due", "organization_id", "due_date"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    step: Mapped[str] = mapped_column(String(30), nullable=False)
    cadence: Mapped[str] = mapped_column(String(10), nullable=False)  # diaria | semanal | quincenal | mensual
    period: Mapped[str] = mapped_column(String(12), nullable=False)  # 2026-11-09 | 2026-W46 | 2026-11-Q1 | 2026-11
    period_label: Mapped[str] = mapped_column(String(60), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pendiente")  # pendiente | hecho | no_aplica
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task.id"))
    evidence: Mapped[str | None] = mapped_column(String(500))  # qué comprobó el sistema
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_time: Mapped[bool | None] = mapped_column(Boolean)
    na_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    na_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = _created()


class AccountingReport(Base):
    """Informe semanal, quincenal o mensual: foto inmutable de las cifras con su huella (DR-CON-8, DR-REC-10)."""

    __tablename__ = "accounting_report"
    __table_args__ = (UniqueConstraint("organization_id", "kind", "period_from", "version"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # semanal | quincenal | mensual
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    figures: Mapped[dict] = mapped_column(JSONB, nullable=False)
    figures_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))  # vacío = rutina automática
    generated_at: Mapped[datetime] = _created()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(1000))
