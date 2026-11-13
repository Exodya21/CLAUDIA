"""Comunicaciones cliente–despacho y portal del cliente (F2.3 + M12 fase 1).

Decisión de Dirección (06/11/2026, T-31): el despacho tendrá un portal propio y no dependerá de WhatsApp.

- Cada expediente tiene su hilo; cada contacto tiene además un hilo general para lo que aún no es expediente.
- Nada se borra: un mensaje oculto deja de verlo el cliente pero sigue en el historial; las ediciones guardan
  la versión anterior. Los textos se guardan cifrados (Fernet con FIELD_ENCRYPTION_KEY).
- El cliente entra con un código de un solo uso enviado a su correo; su sesión es independiente de la del equipo.
- Los correos que salen (código, avisos) pasan por una cola con clave de idempotencia y nunca llevan el contenido
  de los mensajes, solo el aviso de que hay algo nuevo en el portal.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- portal del cliente
class PortalAccount(Base):
    """Acceso de un contacto al portal. Un contacto (persona) = una cuenta por entidad."""

    __tablename__ = "portal_account"
    __table_args__ = (UniqueConstraint("organization_id", "contact_id"), UniqueConstraint("organization_id", "email"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invitada")  # invitada | activa | bloqueada
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    invited_at: Mapped[datetime] = _created()
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("consent.id"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PortalCode(Base):
    """Código de acceso de un solo uso (solo su hash). 10 minutos, 5 intentos."""

    __tablename__ = "portal_code"
    id: Mapped[uuid.UUID] = _uuid()
    portal_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portal_account.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ip: Mapped[str | None] = mapped_column(String(64))


class PortalSession(Base):
    __tablename__ = "portal_session"
    id: Mapped[uuid.UUID] = _uuid()
    portal_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portal_account.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(200))


# ---------------------------------------------------------------- hilos y mensajes
class CommThread(Base):
    __tablename__ = "comm_thread"
    __table_args__ = (
        Index("ux_comm_thread_case", "case_id", unique=True, postgresql_where="case_id IS NOT NULL"),
        Index("ux_comm_thread_general", "contact_id", unique=True, postgresql_where="kind = 'general'"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)  # expediente | general
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_file.id"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="abierto")
    created_at: Mapped[datetime] = _created()
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_client_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommMessage(Base):
    __tablename__ = "comm_message"
    __table_args__ = (Index("ix_comm_message_thread_created", "thread_id", "created_at"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comm_thread.id"), nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    author_portal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portal_account.id"))
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="texto")  # texto | sistema
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="cliente")  # cliente | interna
    level: Mapped[str] = mapped_column(String(12), nullable=False, default="normal")  # normal | importante | urgente
    body_enc: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("comm_message.id"))
    template: Mapped[str | None] = mapped_column(String(40))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task.id"))
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalated_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task.id"))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    hidden_reason: Mapped[str | None] = mapped_column(String(300))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()


class CommMessageVersion(Base):
    """Texto anterior de un mensaje editado (solo inserción)."""

    __tablename__ = "comm_message_version"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comm_message.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_enc: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by_user: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    edited_by_portal: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portal_account.id"))
    edited_at: Mapped[datetime] = _created()


class CommAttachment(Base):
    """Archivo adjunto a un mensaje (almacén cifrado de documentos). Puede incorporarse al expediente."""

    __tablename__ = "comm_attachment"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comm_message.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)
    requirement_index: Mapped[int | None] = mapped_column(Integer)  # requisito de la lista del trámite al que responde
    incorporated_doc_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("immig_document.id"))
    incorporated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    incorporated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommReadMark(Base):
    """Hasta dónde ha leído cada persona un hilo (equipo o cliente)."""

    __tablename__ = "comm_read_mark"
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comm_thread.id"), primary_key=True)
    reader_type: Mapped[str] = mapped_column(String(8), primary_key=True)  # user | portal
    reader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommConfirmation(Base):
    """Confirmación de lectura de un aviso urgente por el cliente (solo inserción)."""

    __tablename__ = "comm_confirmation"
    __table_args__ = (UniqueConstraint("message_id", "portal_account_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comm_message.id"), nullable=False)
    portal_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portal_account.id"), nullable=False)
    confirmed_at: Mapped[datetime] = _created()
    ip: Mapped[str | None] = mapped_column(String(64))


class CommOutbox(Base):
    """Cola de envíos (correo; SMS cuando haya proveedor). Idempotente por `idem_key`. El cuerpo va cifrado."""

    __tablename__ = "comm_outbox"
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)  # email | sms
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # codigo_acceso | aviso | invitacion
    to_address: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body_enc: Mapped[str] = mapped_column(Text, nullable=False)
    idem_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")  # pendiente | enviado | error | no_configurado
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("comm_message.id"))
    portal_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portal_account.id"))
    created_at: Mapped[datetime] = _created()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
