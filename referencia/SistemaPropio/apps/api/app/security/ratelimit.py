"""Límite de intentos de acceso (fuerza bruta), persistido en BD para valer con varios procesos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from ..config import get_settings
from ..db import get_sessionmaker
from ..models_security import AuthAttempt


def _norm(username: str) -> str:
    return (username or "").strip().lower()[:80]


def record_attempt(username: str, ip: str | None, kind: str, success: bool) -> None:
    """En transacción propia: el fallo queda registrado aunque la petición termine en error."""
    s = get_sessionmaker()()
    try:
        s.add(AuthAttempt(username=_norm(username), ip=ip, kind=kind, success=success))
        s.commit()
    finally:
        s.close()


def blocked_for(username: str, ip: str | None) -> int:
    """Segundos de espera si el usuario o la IP superan el límite de fallos en la ventana; 0 si no."""
    cfg = get_settings()
    window = timedelta(minutes=cfg.login_window_minutes)
    since = datetime.now(UTC) - window
    s = get_sessionmaker()()
    try:
        u = _norm(username)
        # Los fallos cuentan desde el último acierto del usuario.
        last_ok = s.execute(select(func.max(AuthAttempt.at)).where(
            AuthAttempt.username == u, AuthAttempt.success.is_(True), AuthAttempt.kind != "password")).scalar()
        start_u = max(since, last_ok) if last_ok else since
        fails_u = s.execute(select(func.count(), func.max(AuthAttempt.at)).where(
            AuthAttempt.username == u, AuthAttempt.success.is_(False), AuthAttempt.at > start_u)).one()
        wait = 0
        if fails_u[0] >= cfg.login_max_failures_user and fails_u[1]:
            wait = max(wait, int((fails_u[1] + window - datetime.now(UTC)).total_seconds()))
        if ip:
            fails_ip = s.execute(select(func.count(), func.max(AuthAttempt.at)).where(
                AuthAttempt.ip == ip, AuthAttempt.success.is_(False), AuthAttempt.at > since)).one()
            if fails_ip[0] >= cfg.login_max_failures_ip and fails_ip[1]:
                wait = max(wait, int((fails_ip[1] + window - datetime.now(UTC)).total_seconds()))
        return max(wait, 0)
    finally:
        s.close()
