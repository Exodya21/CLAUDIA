"""Modelo de datos F1.2 (CRM) y F2.1/F2.2 (expediente, tareas y agenda).

Requisitos: Q-2.1, Q-2.7, Q-2.8, Q-3.1, I-099, I-102 (leads); Q-6.2, Q-6.4, I-007…I-010,
I-088, I-092 (expedientes); I-067…I-077, Q-6.9, Q-6.10, Q-6.15, Q-6.16, Q-6.20, Q-6.20B,
Q-6.23, U-16 (tareas). Ninguna tabla guarda plazos legales calculados: la fecha legal la
introduce una persona y la valida un perfil autorizado (D-02, D-03, D-04, D-21).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- M02 CRM
class LeadOrigin(Base):
    """Catálogo versionable de orígenes (Q-2.1). Se desactiva, nunca se borra."""

    __tablename__ = "lead_origin"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    requires_campaign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Lead(Base):
    __tablename__ = "lead"
    __table_args__ = (Index("ix_lead_org_status", "organization_id", "status"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    origin_code: Mapped[str] = mapped_column(ForeignKey("lead_origin.code"), nullable=False)
    campaign: Mapped[str | None] = mapped_column(String(120))
    utm_source: Mapped[str | None] = mapped_column(String(120))
    utm_medium: Mapped[str | None] = mapped_column(String(120))
    utm_campaign: Mapped[str | None] = mapped_column(String(120))
    utm_content: Mapped[str | None] = mapped_column(String(120))
    utm_term: Mapped[str | None] = mapped_column(String(120))
    materia: Mapped[str] = mapped_column(String(20), nullable=False)  # laboral | extranjeria | nacionalidad | otra
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")  # motivo de consulta, sin estrategia jurídica
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="nuevo")
    case_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LeadEvent(Base):
    __tablename__ = "lead_event"
    id: Mapped[uuid.UUID] = _uuid()
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lead.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- M05 expediente (F2.1)
class CasePhaseEvent(Base):
    __tablename__ = "case_phase_event"
    id: Mapped[uuid.UUID] = _uuid()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = _created()


class CaseRelation(Base):
    __tablename__ = "case_relation"
    __table_args__ = (UniqueConstraint("case_id", "related_case_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    related_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # mismo_cliente | conexo | derivado
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- M09 tareas y agenda (F2.2)
class Task(Base):
    __tablename__ = "task"
    __table_args__ = (Index("ix_task_assignee_due", "assignee_id", "due_at"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # gestion | senalamiento | conciliacion | plazo | llamada | otro
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="media")
    assignee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # fecha objetivo INTERNA
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # señalamientos y conciliaciones
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    # Plazo legal: separado de la fecha interna y nunca calculado por el sistema (AT-19).
    legal_deadline: Mapped[date | None] = mapped_column(Date)
    legal_status: Mapped[str] = mapped_column(String(25), nullable=False, default="no_aplica")
    legal_source: Mapped[str | None] = mapped_column(Text)
    legal_proposed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    legal_validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    legal_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class TaskEvent(Base):
    """Historial de la tarea: estados, aplazamientos (fecha anterior y nueva), plazo legal (U-16, AT-20)."""

    __tablename__ = "task_event"
    id: Mapped[uuid.UUID] = _uuid()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    old_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = _created()
