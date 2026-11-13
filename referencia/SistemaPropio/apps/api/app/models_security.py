"""Modelo F0.2: sesiones revocables, intentos de acceso y copias de seguridad.

Requisitos: Q-1.2 (acceso seguro), I-120 (control de accesos), AT-29 (copia y restauración).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class UserSession(Base):
    """Cada inicio de sesión. El token de la cookie solo es válido mientras esta fila siga vigente."""

    __tablename__ = "user_session"
    id: Mapped[uuid.UUID] = _uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False, index=True)
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False)  # demo | local_mfa | oidc
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    revoke_reason: Mapped[str | None] = mapped_column(String(200))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(200))


class AuthAttempt(Base):
    """Intentos de acceso (contraseña o código) para limitar ataques de fuerza bruta."""

    __tablename__ = "auth_attempt"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _created()
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # password | totp | oidc
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (Index("ix_auth_attempt_user_at", "username", "at"), Index("ix_auth_attempt_ip_at", "ip", "at"))


class BackupRun(Base):
    """Cada copia y su comprobación de restauración (AT-29). Solo se añade; nunca se modifica."""

    __tablename__ = "backup_run"
    id: Mapped[uuid.UUID] = _uuid()
    created_at: Mapped[datetime] = _created()
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(40))
    restore_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    audit_chain_ok: Mapped[bool | None] = mapped_column(Boolean)
    audit_events: Mapped[int | None] = mapped_column(Integer)
    matches_live_chain: Mapped[bool | None] = mapped_column(Boolean)
    table_counts: Mapped[dict | None] = mapped_column(JSONB)
    detail: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(80), nullable=False)  # script | usuario


__all__ = ["UserSession", "AuthAttempt", "BackupRun", "UUID"]
