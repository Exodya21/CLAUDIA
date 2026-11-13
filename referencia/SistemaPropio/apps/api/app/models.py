"""Modelo de datos F0.1.

Requisitos vinculados: Q-1.1, Q-1.2, U-18 (multientidad/sedes), Q-6.17 (auditoría),
I-003 (duplicados), Q-6.2 (estructura mínima de expediente), D-13 (recepción).
Todas las marcas de tiempo se guardan en UTC (timestamptz).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- M00 núcleo
class Organization(Base):
    __tablename__ = "organization"
    id: Mapped[uuid.UUID] = _uuid()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")
    created_at: Mapped[datetime] = _created()


class Branch(Base):
    __tablename__ = "branch"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    timezone: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="sede")  # sede | soporte
    created_at: Mapped[datetime] = _created()


class Department(Base):
    __tablename__ = "department"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # LAB, EXT, NAC, ATC, REC, ...
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_legal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()


class UserAccount(Base):
    __tablename__ = "user_account"
    id: Mapped[uuid.UUID] = _uuid()
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True)  # 'sub' OIDC
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()
    # F0.2 — credenciales locales (contraseña Argon2id + TOTP cifrado). Nunca se exponen por la API.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))


class Role(Base):
    __tablename__ = "role"
    id: Mapped[uuid.UUID] = _uuid()
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    permissions: Mapped[list[RolePermission]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permission"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(80), primary_key=True)


class Membership(Base):
    """Pertenencia de un usuario a una entidad legal, opcionalmente acotada a sede y departamento."""

    __tablename__ = "membership"
    id: Mapped[uuid.UUID] = _uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("department.id"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id"), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")
    role: Mapped[Role] = relationship(lazy="selectin")


class AccessGrant(Base):
    """Autorización puntual, justificada y con caducidad (p. ej. acceso a un expediente concreto)."""

    __tablename__ = "access_grant"
    id: Mapped[uuid.UUID] = _uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))


# ---------------------------------------------------------------- M01 contactos
class Contact(Base):
    """Contacto maestro: una persona, N expedientes. Nunca se fusiona automáticamente."""

    __tablename__ = "contact"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)
    primary_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_names: Mapped[str] = mapped_column(String(200), nullable=False)
    search_name: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(2))
    preferred_language: Mapped[str] = mapped_column(String(5), nullable=False, default="es")
    origin: Mapped[str | None] = mapped_column(String(60))  # canal de entrada; obligatorio en leads (F1-CRM)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    identifiers: Mapped[list[Identifier]] = relationship(lazy="selectin", order_by="Identifier.created_at")
    points: Mapped[list[ContactPoint]] = relationship(lazy="selectin", order_by="ContactPoint.created_at")
    addresses: Mapped[list[Address]] = relationship(lazy="selectin", order_by="Address.created_at")
    consents: Mapped[list[Consent]] = relationship(lazy="selectin", order_by="Consent.recorded_at")


class Identifier(Base):
    __tablename__ = "identifier"
    __table_args__ = (Index("ix_identifier_lookup", "organization_id", "number_normalized"),)
    id: Mapped[uuid.UUID] = _uuid()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # DNI | NIE | PASAPORTE | OTRO
    number_normalized: Mapped[str] = mapped_column(String(40), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _created()


class ContactPoint(Base):
    """Teléfonos y correos. Un teléfono puede compartirse entre personas: sin restricción única."""

    __tablename__ = "contact_point"
    __table_args__ = (Index("ix_contact_point_value", "kind", "value_normalized"),)
    id: Mapped[uuid.UUID] = _uuid()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # phone | email
    value_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str | None] = mapped_column(String(40))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()


class Address(Base):
    __tablename__ = "address"
    id: Mapped[uuid.UUID] = _uuid()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # postal | empadronamiento | otro
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    municipality: Mapped[str] = mapped_column(String(120), nullable=False)
    province: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _created()


class Consent(Base):
    """Registro de consentimientos/bases jurídicas. Catálogo de finalidades pendiente del DPO."""

    __tablename__ = "consent"
    id: Mapped[uuid.UUID] = _uuid()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(60), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    recorded_at: Mapped[datetime] = _created()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DuplicateReview(Base):
    """Cola de revisión humana de posibles duplicados (AT-04). Nunca fusiona."""

    __tablename__ = "duplicate_review"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    candidate_contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- M05 expediente (mínimo)
class CaseFile(Base):
    __tablename__ = "case_file"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("department.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    materia: Mapped[str] = mapped_column(String(20), nullable=False)  # laboral | extranjeria | nacionalidad
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="abierto")
    confidential_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # F2.1: actividad y encargo
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    engagement_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engagement_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))


class CaseAssignment(Base):
    __tablename__ = "case_assignment"
    id: Mapped[uuid.UUID] = _uuid()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False, index=True)
    role_in_case: Mapped[str] = mapped_column(String(30), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseCodeCounter(Base):
    """Numeración consecutiva sin reutilización (Q-6.2)."""

    __tablename__ = "case_code_counter"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(10), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------- auditoría inmutable
class AuditEvent(Base):
    """Bitácora encadenada por hash. UPDATE/DELETE/TRUNCATE bloqueados por trigger en BD."""

    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_resource", "resource_type", "resource_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)  # ok | denied
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
