"""Modelo F4.1 — expediente de extranjería: trámite (catálogo versionado), fases y documentos.

Requisitos: I-007…I-010 (expediente), I-078…I-087 (documentos), M11 extranjería, Q-6.2. Decisiones: D-01 (sin
plazos universales), D-09 (sin envío automático a portales), A-11.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class ImmigProcedure(Base):
    """Versión de un trámite del catálogo. Una versión nueva no altera los expedientes ya abiertos."""

    __tablename__ = "immig_procedure"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_immig_procedure_version"),)
    id: Mapped[uuid.UUID] = _uuid()
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    family: Mapped[str] = mapped_column(String(30), nullable=False)
    materia: Mapped[str] = mapped_column(String(20), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)  # fuente, base legal, modelo, tasa, requisitos…
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="pendiente_validacion")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = _created()


class ImmigCase(Base):
    """Datos de extranjería de un expediente (1:1 con case_file)."""

    __tablename__ = "immig_case"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("immig_procedure.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="documentacion")
    stage_changed_at: Mapped[datetime] = _created()
    province: Mapped[str | None] = mapped_column(String(60))
    mercurio_identifier: Mapped[str | None] = mapped_column(String(60))
    registry_number: Mapped[str | None] = mapped_column(String(60))
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    office_file_number: Mapped[str | None] = mapped_column(String(60))
    resolution_at: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class ImmigStageEvent(Base):
    __tablename__ = "immig_stage_event"
    id: Mapped[uuid.UUID] = _uuid()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    at: Mapped[datetime] = _created()


class ImmigDocument(Base):
    """Documento del expediente. La lectura PROPONE tipo y datos; una persona los confirma."""

    __tablename__ = "immig_document"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente_revision")
    doc_type: Mapped[str | None] = mapped_column(String(40))            # confirmado por una persona
    suggested_type: Mapped[str | None] = mapped_column(String(40))      # propuesto por la lectura
    suggested_confidence: Mapped[str | None] = mapped_column(String(10))
    label: Mapped[str | None] = mapped_column(String(200))
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)
    extracted: Mapped[dict | None] = mapped_column(JSONB)               # MRZ, fechas, etc. (propuesta)
    ocr_engine: Mapped[str | None] = mapped_column(String(40))
    ocr_text: Mapped[str | None] = mapped_column(Text)
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    review_note: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    uploaded_at: Mapped[datetime] = _created()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_package: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ImmigForm(Base):
    """Ficha de datos para el modelo EX del expediente (F4.2). Solo se guardan los valores que una persona ha
    confirmado; las propuestas (cliente, pasaporte, despacho) se calculan al vuelo y nunca se presentan solas."""

    __tablename__ = "immig_form"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(10), nullable=False)          # EX10, EX03…
    values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)   # casillas marcadas del modelo
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)     # campos propios del modelo
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    confirmed_at: Mapped[datetime] = _created()


class ImmigOfficeProfile(Base):
    """Datos del despacho como representante a efectos de presentación (los introduce el despacho; nada fijo en código)."""

    __tablename__ = "immig_office_profile"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    updated_at: Mapped[datetime] = _created()


class ImmigFillToken(Base):
    """Código temporal con el que la extensión de navegador lee la ficha de UN expediente para rellenar Mercurio.
    Solo se guarda el hash; caduca a los 15 minutos y admite pocas lecturas."""

    __tablename__ = "immig_fill_token"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
