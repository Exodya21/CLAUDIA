"""Acceso: local (contraseña + TOTP), OIDC corporativo con MFA y demo (solo desarrollo). Sesiones revocables.

Requisitos: Q-1.2, I-120. Toda entrada, fallo, bloqueo, alta de doble verificación y cierre se audita.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from html import escape

import jwt
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..errors import api_error
from ..models import Membership, Role, UserAccount
from ..models_security import UserSession
from ..schemas import (
    DemoLoginIn,
    DemoUserOut,
    EnrollConfirmIn,
    EnrollStartOut,
    LoginIn,
    LoginStep,
    MfaIn,
    PasswordChangeIn,
    SessionOut,
)
from ..security import credentials as cred
from ..security import oidc
from ..security.auth import (
    COOKIE_NAME,
    PENDING_COOKIE,
    Principal,
    get_principal,
    issue_pending,
    read_pending,
    revoke_sessions,
    session_state,
    set_pending_cookie,
    set_session_cookie,
    start_session,
)
from ..security.ratelimit import blocked_for, record_attempt
from .common import ReqCtx, req_ctx

router = APIRouter(prefix="/auth", tags=["autenticación"])
OIDC_COOKIE = "sp_oidc"
GENERIC_FAIL = "Usuario o contraseña incorrectos."


@router.get("/mode")
def auth_mode() -> dict:
    s = get_settings()
    m = s.auth_methods
    return {
        "methods": sorted(m),
        "mode": ",".join(sorted(m)),
        "environment": s.app_env,
        "local": "local" in m,
        "demo": "demo" in m,
        "oidc_configured": s.oidc_enabled,
        "oidc_requested": "oidc" in m,
    }


def _require(method: str) -> None:
    if method not in get_settings().auth_methods:
        raise api_error(404, "no_disponible", "Este método de acceso no está habilitado en este entorno.")


def _deny(ctx: ReqCtx, username: str, reason: str, user_id: uuid.UUID | None = None, action: str = "auth.login") -> None:
    audit.record_independent(actor_id=user_id, action=action, resource_type="user",
                             resource_id=str(user_id) if user_id else username[:80], outcome="denied",
                             reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _check_block(ctx: ReqCtx, username: str, user_id: uuid.UUID | None = None) -> None:
    wait = blocked_for(username, ctx.ip)
    if wait > 0:
        _deny(ctx, username, "bloqueo temporal por intentos fallidos", user_id)
        mins = max(1, (wait + 59) // 60)
        raise api_error(429, "demasiados_intentos",
                        f"Demasiados intentos fallidos. Espere {mins} min y vuelva a intentarlo, o contacte con Dirección.",
                        headers={"Retry-After": str(wait)})


def _finish_login(db: Session, response: Response, user: UserAccount, method: str, ctx: ReqCtx, reason: str) -> None:
    sess, token, ttl = start_session(db, user, method, ip=ctx.ip, user_agent=ctx.user_agent)
    audit.record(db, actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id,
                 reason=reason, after={"sesion": str(sess.id), "metodo": method}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    set_session_cookie(response, token, ttl)


# ------------------------------------------------------------------ demo (solo desarrollo)
@router.get("/demo/users", response_model=list[DemoUserOut])
def demo_users(db: Session = Depends(get_db)) -> list[DemoUserOut]:
    _require("demo")
    rows = db.execute(
        select(UserAccount, Role.name)
        .join(Membership, Membership.user_id == UserAccount.id)
        .join(Role, Role.id == Membership.role_id)
        .where(UserAccount.is_demo.is_(True), UserAccount.status == "activo", Membership.status == "activa")
        .order_by(UserAccount.username)
    ).all()
    out: dict[str, DemoUserOut] = {}
    for u, role_name in rows:
        if u.username in out:
            out[u.username].description += f" · {role_name}"
        else:
            out[u.username] = DemoUserOut(username=u.username, full_name=u.full_name, description=role_name)
    return list(out.values())


@router.post("/demo/login", status_code=204)
def demo_login(body: DemoLoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    _require("demo")
    ctx = req_ctx(request)
    user = db.execute(select(UserAccount).where(UserAccount.username == body.username)).scalar_one_or_none()
    if not user or not user.is_demo or user.status != "activo":
        _deny(ctx, body.username, "usuario demo inexistente o inactivo")
        raise api_error(401, "credenciales_invalidas", "Usuario de demostración no válido.")
    _finish_login(db, response, user, "demo", ctx, "modo demo")


# ------------------------------------------------------------------ local: contraseña + TOTP
@router.post("/login", response_model=LoginStep)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginStep:
    _require("local")
    ctx = req_ctx(request)
    username = body.username.strip().lower()
    user = db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()
    _check_block(ctx, username, user.id if user else None)
    ok = cred.verify_password(user.password_hash if user else None, body.password)
    if not ok or user is None or user.status != "activo":
        record_attempt(username, ctx.ip, "password", False)
        why = "contraseña incorrecta" if user and user.password_hash else "usuario inexistente o sin contraseña"
        if ok and user and user.status != "activo":
            why = "usuario desactivado"
        _deny(ctx, username, why, user.id if user else None)
        raise api_error(401, "credenciales_invalidas", GENERIC_FAIL)
    record_attempt(username, ctx.ip, "password", True)
    stage = "enroll" if (user.must_change_password or not user.totp_confirmed_at) else "mfa"
    set_pending_cookie(response, issue_pending(user.id, stage))
    return LoginStep(stage=stage)


def _pending_user(request: Request, db: Session, expected: str) -> tuple[UserAccount, ReqCtx]:
    uid, stage = read_pending(request)
    if stage != expected:
        raise api_error(409, "paso_incorrecto", "Paso de verificación no esperado. Vuelva a introducir su contraseña.")
    user = db.get(UserAccount, uid)
    if user is None or user.status != "activo":
        raise api_error(401, "credenciales_invalidas", GENERIC_FAIL)
    return user, req_ctx(request)


@router.post("/mfa", status_code=204)
def mfa(body: MfaIn, request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    user, ctx = _pending_user(request, db, "mfa")
    _check_block(ctx, user.username, user.id)
    secret = cred.decrypt(user.totp_secret_enc) if user.totp_secret_enc else None
    step = cred.verify_totp(secret, body.code, user.totp_last_step) if secret else None
    if step is None:
        record_attempt(user.username, ctx.ip, "totp", False)
        _deny(ctx, user.username, "código de verificación incorrecto o reutilizado", user.id)
        raise api_error(401, "codigo_incorrecto", "Código incorrecto o ya utilizado. Espere al siguiente código.")
    user.totp_last_step = step
    record_attempt(user.username, ctx.ip, "totp", True)
    _finish_login(db, response, user, "local_mfa", ctx, "contraseña + código TOTP")


@router.post("/enroll/start", response_model=EnrollStartOut)
def enroll_start(request: Request, db: Session = Depends(get_db)) -> EnrollStartOut:
    user, ctx = _pending_user(request, db, "enroll")
    secret = cred.new_totp_secret()
    user.totp_secret_enc = cred.encrypt(secret)
    user.totp_confirmed_at = None
    user.totp_last_step = None
    db.commit()
    uri, svg = cred.provisioning(secret, user.username)
    return EnrollStartOut(username=user.username, otpauth_uri=uri, secret=secret, qr_svg=svg)


@router.post("/enroll/confirm", status_code=204)
def enroll_confirm(body: EnrollConfirmIn, request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    user, ctx = _pending_user(request, db, "enroll")
    _check_block(ctx, user.username, user.id)
    problems = cred.password_problems(body.new_password, user.username)
    if cred.verify_password(user.password_hash, body.new_password):
        problems.append("Debe ser distinta de la contraseña provisional.")
    if problems:
        raise api_error(422, "validacion", " ".join(problems), [{"field": "new_password", "message": " ".join(problems)}])
    secret = cred.decrypt(user.totp_secret_enc) if user.totp_secret_enc else None
    if not secret:
        raise api_error(409, "paso_incorrecto", "Primero genere el código QR.")
    step = cred.verify_totp(secret, body.code, user.totp_last_step)
    if step is None:
        record_attempt(user.username, ctx.ip, "totp", False)
        _deny(ctx, user.username, "código incorrecto al activar la doble verificación", user.id, "auth.mfa_enroll")
        raise api_error(422, "codigo_incorrecto", "El código no coincide. Compruebe la hora del móvil y escriba el código actual.",
                        [{"field": "code", "message": "Código incorrecto"}])
    now = datetime.now(UTC)
    user.password_hash = cred.hash_password(body.new_password)
    user.password_changed_at = now
    user.must_change_password = False
    user.totp_confirmed_at = now
    user.totp_last_step = step
    revoke_sessions(db, user.id, by=user.id, reason="nuevas credenciales")
    record_attempt(user.username, ctx.ip, "totp", True)
    audit.record(db, actor_id=user.id, action="auth.mfa_enroll", resource_type="user", resource_id=user.id,
                 reason="contraseña definitiva y doble verificación activadas", ip=ctx.ip, request_id=ctx.request_id)
    _finish_login(db, response, user, "local_mfa", ctx, "primer acceso: contraseña + código TOTP")


# ------------------------------------------------------------------ sesión actual
@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        s = get_settings()
        try:
            c = jwt.decode(token, s.session_secret, algorithms=["HS256"])
            sess = db.get(UserSession, uuid.UUID(c["sid"]))
            if sess and sess.revoked_at is None:
                sess.revoked_at = datetime.now(UTC)
                sess.revoked_by = sess.user_id
                sess.revoke_reason = "cierre de sesión"
                ctx = req_ctx(request)
                audit.record(db, actor_id=sess.user_id, action="auth.logout", resource_type="user",
                             resource_id=sess.user_id, after={"sesion": str(sess.id)}, ip=ctx.ip, request_id=ctx.request_id)
                db.commit()
        except (jwt.PyJWTError, KeyError, ValueError):
            pass
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(PENDING_COOKIE, path="/api/v1/auth")


def session_out(sess: UserSession, current: uuid.UUID | None = None) -> SessionOut:
    return SessionOut(id=sess.id, auth_method=sess.auth_method, created_at=sess.created_at,
                      last_seen_at=sess.last_seen_at, expires_at=sess.expires_at, state=session_state(sess),
                      ip=sess.ip, user_agent=sess.user_agent, revoke_reason=sess.revoke_reason,
                      current=sess.id == current)


@router.get("/sessions", response_model=list[SessionOut])
def my_sessions(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[SessionOut]:
    rows = db.execute(select(UserSession).where(UserSession.user_id == p.id)
                      .order_by(UserSession.created_at.desc()).limit(20)).scalars()
    return [session_out(x, p.session_id) for x in rows]


@router.post("/sessions/{session_id}/revoke", response_model=SessionOut)
def revoke_my_session(session_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> SessionOut:
    sess = db.get(UserSession, session_id)
    if sess is None or sess.user_id != p.id:
        raise api_error(404, "no_encontrado", "Sesión no encontrada.")
    if sess.revoked_at is None:
        sess.revoked_at = datetime.now(UTC)
        sess.revoked_by = p.id
        sess.revoke_reason = "cerrada por el propio usuario"
        ctx = req_ctx(request)
        audit.record(db, actor_id=p.id, action="session.revoke", resource_type="user", resource_id=p.id,
                     after={"sesion": str(sess.id)}, reason="cerrada por el propio usuario", ip=ctx.ip,
                     request_id=ctx.request_id)
        db.commit()
    return session_out(sess, p.session_id)


@router.post("/password", status_code=204)
def change_password(body: PasswordChangeIn, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> None:
    ctx = req_ctx(request)
    user = p.user
    if not user.password_hash:
        raise api_error(409, "sin_contrasena", "Su cuenta no usa contraseña local (acceso demo o corporativo).")
    _check_block(ctx, user.username, user.id)
    if not cred.verify_password(user.password_hash, body.current_password):
        record_attempt(user.username, ctx.ip, "password", False)
        _deny(ctx, user.username, "contraseña actual incorrecta al cambiarla", user.id, "auth.password_change")
        raise api_error(422, "validacion", "La contraseña actual no es correcta.",
                        [{"field": "current_password", "message": "Incorrecta"}])
    problems = cred.password_problems(body.new_password, user.username)
    if body.new_password == body.current_password:
        problems.append("Debe ser distinta de la actual.")
    if problems:
        raise api_error(422, "validacion", " ".join(problems), [{"field": "new_password", "message": " ".join(problems)}])
    user.password_hash = cred.hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    n = revoke_sessions(db, user.id, by=user.id, reason="cambio de contraseña", except_id=p.session_id)
    audit.record(db, actor_id=user.id, action="auth.password_change", resource_type="user", resource_id=user.id,
                 after={"otras_sesiones_cerradas": n}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()


# ------------------------------------------------------------------ OIDC corporativo
def _oidc_ready() -> None:
    if not get_settings().oidc_enabled:
        raise api_error(501, "no_disponible_aun",
                        "No disponible aún: falta elegir y configurar el proveedor corporativo (decisión T-01).")


@router.get("/oidc/login")
def oidc_login() -> RedirectResponse:
    _oidc_ready()
    s = get_settings()
    try:
        url, saved = oidc.begin()
    except oidc.OidcError as e:
        raise api_error(502, e.code, e.message) from e
    now = datetime.now(UTC)
    token = jwt.encode({**saved, "typ": "oidc", "exp": now + timedelta(minutes=10)}, s.session_secret, algorithm="HS256")
    resp = RedirectResponse(url, status_code=302)
    # Lax: el proveedor devuelve al usuario con una navegación entre sitios.
    resp.set_cookie(OIDC_COOKIE, token, max_age=600, httponly=True, secure=s.cookie_secure, samesite="lax",
                    path="/api/v1/auth/oidc")
    return resp


def _bounce(target: str) -> HTMLResponse:
    """Redirección desde la propia página: así la cookie SameSite=Strict se envía en la siguiente navegación."""
    t = escape(target, quote=True)
    resp = HTMLResponse(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={t}">'
                        f'<title>Entrando…</title><p>Entrando… <a href="{t}">Continuar</a></p>')
    resp.delete_cookie(OIDC_COOKIE, path="/api/v1/auth/oidc")
    return resp


@router.get("/oidc/callback")
def oidc_callback(request: Request, code: str | None = Query(None), state: str | None = Query(None),
                  error: str | None = Query(None), db: Session = Depends(get_db)) -> HTMLResponse:
    _oidc_ready()
    s = get_settings()
    ctx = req_ctx(request)

    def fail(code_: str, reason: str, user_id: uuid.UUID | None = None, who: str = "oidc") -> HTMLResponse:
        _deny(ctx, who, reason, user_id)
        return _bounce(f"/login?error={code_}")

    try:
        saved = jwt.decode(request.cookies.get(OIDC_COOKIE) or "", s.session_secret, algorithms=["HS256"])
        if saved.get("typ") != "oidc":
            raise jwt.InvalidTokenError("tipo")
    except jwt.PyJWTError:
        return fail("oidc_caducado", "OIDC: solicitud caducada o sin cookie de estado")
    if error:
        return fail("oidc_cancelado", f"OIDC: el proveedor devolvió error {error[:60]}")
    if not code or not state or state != saved.get("state"):
        return fail("oidc_estado", "OIDC: estado no coincide (posible CSRF)")
    try:
        claims = oidc.finish(code, saved)
    except oidc.OidcError as e:
        record_attempt("oidc", ctx.ip, "oidc", False)
        return fail(e.code, f"OIDC: {e.message}")
    sub = oidc.subject(claims)
    user = db.execute(select(UserAccount).where(UserAccount.external_subject == sub)).scalar_one_or_none()
    bound = False
    if user is None:
        email = str(claims.get(s.oidc_email_claim) or "").strip().lower()
        if email:
            cands = list(db.execute(select(UserAccount).where(UserAccount.external_subject.is_(None))).scalars())
            matches = [u for u in cands if u.email.strip().lower() == email]
            if len(matches) == 1:
                user, bound = matches[0], True
    if user is None:
        return fail("oidc_sin_cuenta", f"OIDC: identidad sin cuenta dada de alta ({sub[:120]})")
    if user.status != "activo":
        return fail("oidc_sin_cuenta", "OIDC: usuario desactivado", user.id, user.username)
    if bound:
        user.external_subject = sub
        audit.record(db, actor_id=user.id, action="auth.oidc_link", resource_type="user", resource_id=user.id,
                     after={"proveedor": claims.get("iss")}, reason="primer acceso corporativo: enlazado por correo",
                     ip=ctx.ip, request_id=ctx.request_id)
    record_attempt(user.username, ctx.ip, "oidc", True)
    sess, token, ttl = start_session(db, user, "oidc", ip=ctx.ip, user_agent=ctx.user_agent)
    audit.record(db, actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id,
                 reason="proveedor corporativo con MFA", after={"sesion": str(sess.id), "metodo": "oidc"},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    resp = _bounce("/")
    set_session_cookie(resp, token, ttl)
    return resp
