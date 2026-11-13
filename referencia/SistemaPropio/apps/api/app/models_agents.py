"""F5.1 — Motor de agentes y bandeja única de propuestas (documentos de Dirección del 08/11/2026).

Los «motores» de Dirección son aquí **agentes**: piezas del propio sistema con nombre, permisos limitados y registro
de todo lo que hacen. Reaccionan a hechos (`agent_event`, escrito en la MISMA transacción que el cambio que lo
provoca) o a su calendario, y dejan **propuestas** en una bandeja única con prioridad y responsable. Lo que tiene
efecto jurídico o económico lo aprueba una persona. Nada se borra.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class AgentSetting(Base):
    """Configuración de un agente en una entidad: activo y modo (`propone` o `automatico` donde se permite)."""

    __tablename__ = "agent_setting"
    __table_args__ = (UniqueConstraint("organization_id", "agent_code"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="propone")  # propone | automatico
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    updated_at: Mapped[datetime] = _created()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AgentEvent(Base):
    """Hecho que puede interesar a un agente (patrón «outbox»: se escribe con el cambio y se procesa después)."""

    __tablename__ = "agent_event"
    __table_args__ = (Index("ix_agent_event_pending", "processed_at", "created_at"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # case.opened, bank.imported, case.closed…
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[uuid.UUID | None] = mapped_column()
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))


class AgentRun(Base):
    """Cada vez que un agente trabaja: qué lo lanzó, qué hizo (recuentos) y si falló."""

    __tablename__ = "agent_run"
    __table_args__ = (Index("ix_agent_run_org_agent", "organization_id", "agent_code", "started_at"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger: Mapped[str] = mapped_column(String(60), nullable=False)  # evento:<kind> | calendario | manual
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_event.id"))
    started_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="en_curso")  # en_curso | ok | error
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String(500))


class AgentProposal(Base):
    """Bandeja única de propuestas y excepciones (prioridad, responsable, estado y decisión con motivo)."""

    __tablename__ = "agent_proposal"
    __table_args__ = (Index("ix_agent_proposal_open", "organization_id", "status", "priority"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # mensaje | conciliacion | excepcion_banco…
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(6), nullable=False, default="media")  # alta | media | baja
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pendiente")
    # pendiente → aprobada (aplicada) | rechazada | caducada
    permission: Mapped[str] = mapped_column(String(40), nullable=False)  # permiso para decidirla
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[uuid.UUID | None] = mapped_column()
    payload: Mapped[dict | None] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_run.id"))
    created_at: Mapped[datetime] = _created()
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(500))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)


class CommDispatch(Base):
    """Trazabilidad de cada mensaje automático al cliente (DR-MSG-8): plantilla y versión, evento, fecha prevista y
    real, resultado, respuestas, incidencias y gestor responsable. Uno por clave: nunca se duplica."""

    __tablename__ = "comm_dispatch"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_file.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False)
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    template_version: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(60), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task.id"))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(14), nullable=False, default="propuesto")
    # propuesto → enviado | cancelado | fallido
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_proposal.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("comm_message.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    snapshot: Mapped[dict | None] = mapped_column(JSONB)  # datos con los que se programó (fecha, lugar…)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()
