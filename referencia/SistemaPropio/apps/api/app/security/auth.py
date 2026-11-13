"""Identidad y sesión.

Métodos de acceso (AUTH_MODE, lista separada por comas):
- local: usuario + contraseña (Argon2id) + código TOTP obligatorio (F0.2).
- oidc: proveedor corporativo con MFA exigido en el token (F0.2; proveedor pendiente de T-01).
- demo: elegir un usuario ficticio marcado is_demo. Solo development/test (la configuración lo impide fuera).

Toda sesión es una fila de `user_session`. La cookie lleva un JWT HS256 con el identificador de
esa fila: si la sesión se revoca, caduca o queda inactiva, la cookie deja de valer de inmediato.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, get_engine
from ..models import Membership, UserAccount
from ..models_security import UserSession

COOKIE_NAME = "sp_session"
PENDING_COOKIE = "sp_pending"
_ALG = "HS256"
PENDING_TTL = 600  # 10 minutos para completar la doble verificación
_TOUCH_EVERY = timedelta(seconds=60)


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ sesiones
def start_session(db: Session, user: UserAccount, method: str, *, ip: str | None, user_agent: str | None
                  ) -> tuple[UserSession, str, int]:
    """Crea la sesión en BD (dentro de la transacción en curso) y devuelve el token de la cookie."""
    s = get_settings()
    now = _now()
    ttl = s.session_ttl_minutes * 60
    sess = UserSession(user_id=user.id, auth_method=method, last_seen_at=now,
                       expires_at=now + timedelta(seconds=ttl), ip=ip, user_agent=(user_agent or "")[:200] or None)
    db.add(sess)
    db.flush()
    user.last_login_at = now
    token = jwt.encode(
        {"sub": str(user.id), "sid": str(sess.id), "typ": "session", "iat": now,
         "exp": now + timedelta(seconds=ttl), "env": s.app_env},
        s.session_secret, algorithm=_ALG,
    )
    return sess, token, ttl


def set_session_cookie(response: Response, token: str, ttl: int) -> None:
    s = get_settings()
    response.set_cookie(COOKIE_NAME, token, max_age=ttl, httponly=True, secure=s.cookie_secure,
                        samesite="strict", path="/")
    response.delete_cookie(PENDING_COOKIE, path="/api/v1/auth")


def revoke_sessions(db: Session, user_id: uuid.UUID, *, by: uuid.UUID | None, reason: str,
                    except_id: uuid.UUID | None = None) -> int:
    q = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_id:
        q = q.where(UserSession.id != except_id)
    res = db.execute(q.values(revoked_at=_now(), revoked_by=by, revoke_reason=reason[:200]))
    return res.rowcount or 0


def session_state(sess: UserSession) -> str:
    s = get_settings()
    now = _now()
    if sess.revoked_at:
        return "revocada"
    if sess.expires_at <= now:
        return "caducada"
    if sess.last_seen_at + timedelta(minutes=s.session_idle_minutes) <= now:
        return "inactiva"
    return "activa"


# ------------------------------------------------------------------ paso intermedio (doble verificación)
def issue_pending(user_id: uuid.UUID, stage: str) -> str:
    s = get_settings()
    now = _now()
    return jwt.encode({"sub": str(user_id), "typ": "pending", "stage": stage, "iat": now,
                       "exp": now + timedelta(seconds=PENDING_TTL), "env": s.app_env},
                      s.session_secret, algorithm=_ALG)


def set_pending_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(PENDING_COOKIE, token, max_age=PENDING_TTL, httponly=True, secure=s.cookie_secure,
                        samesite="strict", path="/api/v1/auth")


def read_pending(request: Request) -> tuple[uuid.UUID, str]:
    token = request.cookies.get(PENDING_COOKIE)
    s = get_settings()
    try:
        if not token:
            raise jwt.InvalidTokenError("sin token")
        c = jwt.decode(token, s.session_secret, algorithms=[_ALG], options={"require": ["exp", "sub"]})
        if c.get("typ") != "pending" or c.get("env") != s.app_env:
            raise jwt.InvalidTokenError("tipo")
        return uuid.UUID(c["sub"]), c["stage"]
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, detail={"code": "verificacion_caducada",
                                         "message": "El paso de verificación ha caducado. Vuelva a introducir su contraseña."}) from exc


# ------------------------------------------------------------------ principal
@dataclass
class Principal:
    user: UserAccount
    memberships: list[Membership]
    session_id: uuid.UUID | None = None
    auth_method: str = "demo"
    _perm_cache: dict[uuid.UUID, set[str]] = field(default_factory=dict)

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    def org_ids(self) -> set[uuid.UUID]:
        return {m.organization_id for m in self.memberships}

    def perms(self, org_id: uuid.UUID) -> set[str]:
        if org_id not in self._perm_cache:
            p: set[str] = set()
            for m in self.memberships:
                if m.organization_id == org_id:
                    p |= {rp.permission for rp in m.role.permissions}
            self._perm_cache[org_id] = p
        return self._perm_cache[org_id]

    def has(self, org_id: uuid.UUID, perm: str) -> bool:
        return perm in self.perms(org_id)

    def orgs_with(self, perm: str) -> set[uuid.UUID]:
        return {o for o in self.org_ids() if self.has(o, perm)}

    def memberships_with(self, org_id: uuid.UUID, perm: str) -> list[Membership]:
        return [
            m for m in self.memberships
            if m.organization_id == org_id and perm in {rp.permission for rp in m.role.permissions}
        ]


def active_memberships(db: Session, user_id: uuid.UUID) -> list[Membership]:
    now = _now()
    return list(db.execute(select(Membership).where(
        Membership.user_id == user_id, Membership.status == "activa", Membership.valid_from <= now,
        or_(Membership.valid_to.is_(None), Membership.valid_to > now))).scalars())


def load_principal(db: Session, user_id: uuid.UUID) -> Principal | None:
    user = db.get(UserAccount, user_id)
    if not user or user.status != "activo":
        return None
    return Principal(user=user, memberships=active_memberships(db, user.id))


def _unauth(code: str, message: str) -> HTTPException:
    return HTTPException(401, detail={"code": code, "message": message})


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauth("no_autenticado", "Inicie sesión.")
    s = get_settings()
    try:
        claims = jwt.decode(token, s.session_secret, algorithms=[_ALG], options={"require": ["exp", "sub", "sid"]})
        if claims.get("env") != s.app_env or claims.get("typ") != "session":
            raise jwt.InvalidTokenError("entorno o tipo distinto")
        uid = uuid.UUID(claims["sub"])
        sid = uuid.UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise _unauth("sesion_invalida", "Sesión caducada o no válida.") from exc
    sess = db.get(UserSession, sid)
    if sess is None or sess.user_id != uid:
        raise _unauth("sesion_invalida", "Sesión caducada o no válida.")
    state = session_state(sess)
    if state != "activa":
        msg = {"revocada": "Su sesión se ha cerrado desde la administración o desde otro dispositivo.",
               "caducada": "Su sesión ha caducado. Vuelva a entrar.",
               "inactiva": "Sesión cerrada por inactividad. Vuelva a entrar."}[state]
        raise _unauth(f"sesion_{state}", msg)
    if sess.auth_method == "demo" and "demo" not in s.auth_methods:
        raise _unauth("sesion_invalida", "El acceso de demostración ya no está habilitado.")
    p = load_principal(db, uid)
    if p is None:
        raise _unauth("usuario_inactivo", "Usuario no activo.")
    now = _now()
    if now - sess.last_seen_at > _TOUCH_EVERY:
        # Conexión propia: la actividad cuenta aunque la petición sea de solo lectura.
        with get_engine().begin() as conn:
            conn.execute(update(UserSession).where(UserSession.id == sid).values(last_seen_at=now))
    p.session_id = sid
    p.auth_method = sess.auth_method
    request.state.actor_id = p.id
    return p
