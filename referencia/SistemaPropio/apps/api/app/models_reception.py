"""F5.2 — Recepción: justificantes de pago NO fiscales numerados (DR-REC-3, T-44).

El justificante acredita que el despacho ha recibido un importe; NO es una factura (D-07, D-25). Se numera por
entidad, sede y año (REC-BCN-2026-000001), se genera una sola vez por cobro y se guarda cifrado y sin modificar:
volver a descargarlo devuelve exactamente el mismo documento. Nada se borra.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class ReceiptCounter(Base):
    __tablename__ = "receipt_counter"
    __table_args__ = (UniqueConstraint("organization_id", "prefix", "year"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PaymentReceipt(Base):
    __tablename__ = "payment_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment.id"), nullable=False, unique=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    number: Mapped[str] = mapped_column(String(30), nullable=False)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    issued_at: Mapped[datetime] = _created()
