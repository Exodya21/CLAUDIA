"""Acceso de clientes al portal: código de un solo uso enviado a su correo y sesión propia.

- Cookie `sp_portal` (JWT con el id de una fila de `portal_session`), distinta de la del equipo: una sesión de
  cliente no abre ninguna ruta del equipo ni al revés.
- El código solo se guarda como hash; vale 10 minutos y admite 5 intentos. Pedir un código siempre responde lo
  mismo, exista o no la cuenta (no se revela quién es cliente).
- En desarrollo y pruebas, si no hay correo configurado, el código se devuelve en la respuesta para poder probar.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, get_engine
from ..models import Contact
from ..models_comm import PortalAccount, PortalCode, PortalSession

COOKIE = "sp_portal"
_ALG = "HS256"
MAX_CODES_PER_HOUR = 5
MAX_CODE_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(UTC)


def norm_email(e: str) -> str:
    return (e or "").strip().lower()[:200]


def code_hash(account_id: uuid.UUID, code: str) -> str:
    key = get_settings().session_secret.encode()
    return hmac.new(key, f"{account_id}:{code}".encode(), hashlib.sha256).hexdigest()


def new_code(db: Session, acc: PortalAccount, ip: str | None) -> str | None:
    """Crea un código si no se ha superado el límite por hora. Devuelve el código en claro (solo para enviarlo)."""
    since = _now() - timedelta(hours=1)
    n = db.execute(select(func.count()).select_from(PortalCode).where(
        PortalCode.portal_account_id == acc.id, PortalCode.created_at > since)).scalar_one()
    if n >= MAX_CODES_PER_HOUR:
        return None
    # Un código nuevo anula los anteriores sin usar.
    db.execute(update(PortalCode).where(PortalCode.portal_account_id == acc.id, PortalCode.used_at.is_(None))
               .values(used_at=_now()))
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(PortalCode(portal_account_id=acc.id, code_hash=code_hash(acc.id, code), ip=ip,
                      expires_at=_now() + timedelta(minutes=get_settings().portal_code_minutes)))
    return code


def check_code(db: Session, acc: PortalAccount, code: str) -> bool:
    c = db.execute(select(PortalCode).where(PortalCode.portal_account_id == acc.id, PortalCode.used_at.is_(None),
                                            PortalCode.expires_at > _now()).order_by(PortalCode.created_at.desc())
                   .limit(1).with_for_update()).scalar_one_or_none()
    if c is None:
        return False
    c.attempts += 1
    ok = hmac.compare_digest(c.code_hash, code_hash(acc.id, (code or "").strip()))
    if ok or c.attempts >= MAX_CODE_ATTEMPTS:
        c.used_at = _now()
    return ok


def start(db: Session, acc: PortalAccount, ip: str | None, ua: str | None) -> tuple[str, int]:
    s = get_settings()
    now = _now()
    ttl = s.portal_session_minutes * 60
    sess = PortalSession(portal_account_id=acc.id, last_seen_at=now, expires_at=now + timedelta(seconds=ttl),
                         ip=ip, user_agent=(ua or "")[:200] or None)
    db.add(sess)
    db.flush()
    acc.last_login_at = now
    token = jwt.encode({"sub": str(acc.id), "sid": str(sess.id), "typ": "portal", "iat": now,
                        "exp": now + timedelta(seconds=ttl), "env": s.app_env}, s.session_secret, algorithm=_ALG)
    return token, ttl


def set_cookie(response: Response, token: str, ttl: int) -> None:
    s = get_settings()
    response.set_cookie(COOKIE, token, max_age=ttl, httponly=True, secure=s.cookie_secure, samesite="strict", path="/")


def revoke_all(db: Session, account_id: uuid.UUID) -> None:
    db.execute(update(PortalSession).where(PortalSession.portal_account_id == account_id,
                                           PortalSession.revoked_at.is_(None)).values(revoked_at=_now()))


@dataclass
class PortalUser:
    account: PortalAccount
    contact: Contact
    session_id: uuid.UUID

    @property
    def id(self) -> uuid.UUID:
        return self.account.id

    @property
    def org(self) -> uuid.UUID:
        return self.account.organization_id


def _unauth(code: str, msg: str) -> HTTPException:
    return HTTPException(401, detail={"code": code, "message": msg})


def get_portal_user(request: Request, db: Session = Depends(get_db)) -> PortalUser:
    token = request.cookies.get(COOKIE)
    if not token:
        raise _unauth("no_autenticado", "Entre con su correo electrónico para continuar.")
    s = get_settings()
    try:
        c = jwt.decode(token, s.session_secret, algorithms=[_ALG], options={"require": ["exp", "sub", "sid"]})
        if c.get("typ") != "portal" or c.get("env") != s.app_env:
            raise jwt.InvalidTokenError("tipo")
        aid, sid = uuid.UUID(c["sub"]), uuid.UUID(c["sid"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise _unauth("sesion_invalida", "Su sesión ha caducado. Vuelva a entrar.") from exc
    sess = db.get(PortalSession, sid)
    now = _now()
    if (sess is None or sess.portal_account_id != aid or sess.revoked_at or sess.expires_at <= now
            or sess.last_seen_at + timedelta(minutes=s.portal_idle_minutes) <= now):
        raise _unauth("sesion_caducada", "Su sesión ha caducado. Vuelva a entrar.")
    acc = db.get(PortalAccount, aid)
    if acc is None or acc.status == "bloqueada":
        raise _unauth("acceso_bloqueado", "Su acceso al portal no está disponible. Llame al despacho.")
    if now - sess.last_seen_at > timedelta(seconds=60):
        with get_engine().begin() as conn:
            conn.execute(update(PortalSession).where(PortalSession.id == sid).values(last_seen_at=now))
    return PortalUser(account=acc, contact=db.get(Contact, acc.contact_id), session_id=sid)


def require_terms(u: PortalUser = Depends(get_portal_user)) -> PortalUser:
    if u.account.terms_accepted_at is None:
        raise HTTPException(403, detail={"code": "condiciones_pendientes",
                                         "message": "Antes de continuar debe aceptar las condiciones del portal."})
    return u
