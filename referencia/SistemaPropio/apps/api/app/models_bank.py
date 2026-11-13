"""F5.1 — Cuentas bancarias, extractos y conciliación (DR-CON-2, DR-CON-3; Q-4.5).

- El extracto original se guarda sin modificar y cifrado; cada movimiento lleva un identificador estable por
  cuenta, así que reimportar el mismo extracto NUNCA duplica movimientos.
- Cada importación comprueba que saldo inicial + movimientos = saldo final del banco (criterio de Dirección).
- El agente de conciliación PROPONE emparejamientos (reglas deterministas y verificables); Contabilidad los valida.
- Un traspaso entre cuentas propias nunca es un ingreso. Importes en céntimos con signo (+ entra, − sale).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class BankAccount(Base):
    __tablename__ = "bank_account"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(80), nullable=False)
    iban_last4: Mapped[str] = mapped_column(String(4), nullable=False)  # lo único que se muestra
    iban_enc: Mapped[str | None] = mapped_column(String(200))  # F5.4: IBAN completo cifrado (solo para el fichero SEPA)
    purpose: Mapped[str] = mapped_column(String(14), nullable=False)  # A_laboral | B_extranjeria | C_tesoreria | otra
    activity: Mapped[str] = mapped_column(String(12), nullable=False)  # laboral | extranjeria | compartida
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class BankImport(Base):
    __tablename__ = "bank_import"
    __table_args__ = (UniqueConstraint("account_id", "sha256"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # n43 | camt053 | csv
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)  # original cifrado, sin modificar
    period_from: Mapped[date | None] = mapped_column(Date)
    period_to: Mapped[date | None] = mapped_column(Date)
    opening_cents: Mapped[int | None] = mapped_column(BigInteger)
    closing_cents: Mapped[int | None] = mapped_column(BigInteger)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_ok: Mapped[bool | None] = mapped_column(Boolean)  # saldo inicial + movimientos = saldo final
    errors: Mapped[list | None] = mapped_column(JSONB)
    imported_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    imported_at: Mapped[datetime] = _created()


class BankMovement(Base):
    __tablename__ = "bank_movement"
    __table_args__ = (UniqueConstraint("account_id", "ext_id"),
                      Index("ix_bank_movement_account_date", "account_id", "booking_date"),
                      Index("ix_bank_movement_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.id"), nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_import.id"), nullable=False)
    ext_id: Mapped[str] = mapped_column(String(80), nullable=False)  # identificador estable (banco o huella)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    counterparty: Mapped[str | None] = mapped_column(String(140))
    balance_after_cents: Mapped[int | None] = mapped_column(BigInteger)
    # pendiente | propuesto | conciliado | parcial | traspaso | sin_justificar | ignorado
    status: Mapped[str] = mapped_column(String(14), nullable=False, default="pendiente")
    # cobro | tpv | comision | bizum | traspaso | devolucion | nomina | seguridad_social | impuestos | alquiler | proveedor | otro
    category: Mapped[str | None] = mapped_column(String(18))
    activity: Mapped[str | None] = mapped_column(String(12))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"))
    note: Mapped[str | None] = mapped_column(String(500))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BankMatch(Base):
    """Emparejamiento de un movimiento con lo que lo justifica (cobro, devolución, traspaso o comisión)."""

    __tablename__ = "bank_match"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    movement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_movement.id"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(14), nullable=False)  # payment | refund | movement
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule: Mapped[str] = mapped_column(String(20), nullable=False)  # referencia | tpv | bizum | traspaso | devolucion | manual
    explanation: Mapped[str] = mapped_column(Text, nullable=False)  # por qué se empareja (verificable)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="propuesta")  # propuesta | validada | rechazada
    proposed_by_agent: Mapped[str | None] = mapped_column(String(40))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = _created()
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(500))
