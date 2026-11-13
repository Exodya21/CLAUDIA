"""F0.2 — Acceso con contraseña + doble verificación, sesiones revocables y límite de intentos.

Requisitos: Q-1.2, I-120. Datos ficticios.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from .conftest import CSRF, totp_now


def _client(app) -> TestClient:
    c = TestClient(app)
    c.headers.update(CSRF)
    return c


def _events(db, action: str, outcome: str | None = None, resource_id=None):
    from app.models import AuditEvent

    db.rollback()
    q = select(AuditEvent).where(AuditEvent.action == action)
    if outcome:
        q = q.where(AuditEvent.outcome == outcome)
    if resource_id is not None:
        q = q.where(AuditEvent.resource_id == str(resource_id))
    return list(db.execute(q).scalars())


# ---------------------------------------------------------------- primer acceso y doble verificación
def test_primer_acceso_obliga_a_cambiar_contrasena_y_activar_totp(app, new_user, db):
    username, temp, user = new_user()
    c = _client(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": temp})
    assert r.status_code == 200 and r.json() == {"stage": "enroll"}
    # El paso intermedio NO es una sesión: no da acceso a nada.
    assert c.get("/api/v1/me").status_code == 401
    start = c.post("/api/v1/auth/enroll/start").json()
    assert start["otpauth_uri"].startswith("otpauth://totp/") and "<svg" in start["qr_svg"]
    # Contraseña débil o igual a la provisional → rechazada
    r = c.post("/api/v1/auth/enroll/confirm", json={"code": totp_now(start["secret"]), "new_password": "corta"})
    assert r.status_code == 422
    r = c.post("/api/v1/auth/enroll/confirm", json={"code": totp_now(start["secret"]), "new_password": temp})
    assert r.status_code == 422 and "provisional" in r.json()["error"]["message"]
    # Código incorrecto → rechazado
    r = c.post("/api/v1/auth/enroll/confirm", json={"code": "000000", "new_password": "Una-Clave-Ficticia-Larga"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "codigo_incorrecto"
    r = c.post("/api/v1/auth/enroll/confirm",
               json={"code": totp_now(start["secret"]), "new_password": "Una-Clave-Ficticia-Larga"})
    assert r.status_code == 204
    me = c.get("/api/v1/me").json()
    assert me["username"] == username and me["auth_mode"] == "local_mfa" and me["has_password"] is True
    assert _events(db, "auth.mfa_enroll", "ok", user["id"])

    # Los secretos no se guardan en claro
    from app.models import UserAccount

    u = db.get(UserAccount, user["id"])
    assert start["secret"] not in (u.totp_secret_enc or "") and u.password_hash.startswith("$argon2id$")


def test_acceso_normal_pide_codigo_y_rechaza_reutilizarlo(app, enrolled, db):
    _, username, password, secret, user = enrolled()
    c = _client(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.json() == {"stage": "mfa"}
    assert c.get("/api/v1/me").status_code == 401
    code = totp_now(secret, 1)
    assert c.post("/api/v1/auth/mfa", json={"code": code}).status_code == 204
    assert c.get("/api/v1/me").status_code == 200
    # Mismo código otra vez (aunque sea con la contraseña correcta) → rechazado por reutilización
    c2 = _client(app)
    c2.post("/api/v1/auth/login", json={"username": username, "password": password})
    r = c2.post("/api/v1/auth/mfa", json={"code": code})
    assert r.status_code == 401 and r.json()["error"]["code"] == "codigo_incorrecto"
    assert _events(db, "auth.login", "denied", user["id"])


def test_contrasena_incorrecta_mensaje_generico_y_auditado(app, enrolled, db):
    _, username, _, _, _ = enrolled()
    c = _client(app)
    r1 = c.post("/api/v1/auth/login", json={"username": username, "password": "no-es-esta"})
    r2 = c.post("/api/v1/auth/login", json={"username": "no.existe.nadie", "password": "no-es-esta"})
    # Mismo mensaje: no revela si el usuario existe
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]
    assert _events(db, "auth.login", "denied", "no.existe.nadie")


def test_bloqueo_por_intentos_fallidos(app, enrolled, db):
    _, username, password, secret, user = enrolled()
    c = _client(app)
    for _ in range(5):
        assert c.post("/api/v1/auth/login", json={"username": username, "password": "mala"}).status_code == 401
    # Ni siquiera la contraseña correcta entra mientras dura el bloqueo
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["error"]["code"] == "demasiados_intentos"
    ev = _events(db, "auth.login", "denied", user["id"])
    assert any("bloqueo" in (e.reason or "") for e in ev)


def test_bloqueo_por_ip_con_proxy_de_confianza(app, monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "trust_proxy", True)
    monkeypatch.setattr(s, "login_max_failures_ip", 3)
    c = _client(app)
    # El cliente intenta falsear su IP: solo cuenta la última entrada (la que añade el proxy).
    h = {"X-Forwarded-For": "1.2.3.4, 203.0.113.77"}
    for i in range(3):
        c.post("/api/v1/auth/login", json={"username": f"distinto{i}", "password": "x"}, headers=h)
    r = c.post("/api/v1/auth/login", json={"username": "otro.mas", "password": "x"}, headers=h)
    assert r.status_code == 429
    r = c.post("/api/v1/auth/login", json={"username": "otro.mas", "password": "x"},
               headers={"X-Forwarded-For": "203.0.113.78"})
    assert r.status_code == 401


def test_bloqueo_tambien_para_codigos_totp(app, enrolled):
    _, username, password, _, _ = enrolled()
    c = _client(app)
    c.post("/api/v1/auth/login", json={"username": username, "password": password})
    for _ in range(5):
        c.post("/api/v1/auth/mfa", json={"code": "123456"})
    assert c.post("/api/v1/auth/mfa", json={"code": "654321"}).status_code == 429


# ---------------------------------------------------------------- sesiones
def test_cerrar_sesion_invalida_la_cookie_al_instante(app, enrolled, db):
    c, _, _, _, user = enrolled()
    stolen = c.cookies.get("sp_session")
    assert c.post("/api/v1/auth/logout").status_code == 204
    thief = TestClient(app)
    thief.cookies.set("sp_session", stolen)
    r = thief.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "sesion_revocada"
    assert _events(db, "auth.logout", "ok", user["id"])


def test_cerrar_otra_sesion_propia(app, enrolled):
    c1, username, password, secret, _ = enrolled()
    c2 = _client(app)
    c2.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert c2.post("/api/v1/auth/mfa", json={"code": totp_now(secret, 1)}).status_code == 204
    sessions = c1.get("/api/v1/auth/sessions").json()
    assert len([s for s in sessions if s["state"] == "activa"]) == 2
    other = next(s for s in sessions if not s["current"])
    assert c1.post(f"/api/v1/auth/sessions/{other['id']}/revoke").json()["state"] == "revocada"
    assert c2.get("/api/v1/me").status_code == 401
    assert c1.get("/api/v1/me").status_code == 200


def test_no_se_cierran_sesiones_ajenas_desde_el_perfil(app, enrolled, login):
    c1, *_ = enrolled()
    sid = c1.get("/api/v1/auth/sessions").json()[0]["id"]
    other = login("asesor.laboral.bcn")
    assert other.post(f"/api/v1/auth/sessions/{sid}/revoke").status_code == 404


def test_cierre_por_inactividad(app, enrolled, db):
    from app.models_security import UserSession

    c, _, _, _, user = enrolled()
    sid = c.get("/api/v1/auth/sessions").json()[0]["id"]
    db.execute(update(UserSession).where(UserSession.id == sid)
               .values(last_seen_at=datetime.now(UTC) - timedelta(hours=3)))
    db.commit()
    r = c.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "sesion_inactiva"


def test_cambio_de_contrasena_cierra_las_demas_sesiones(app, enrolled):
    c1, username, password, secret, _ = enrolled()
    c2 = _client(app)
    c2.post("/api/v1/auth/login", json={"username": username, "password": password})
    c2.post("/api/v1/auth/mfa", json={"code": totp_now(secret, 1)})
    assert c1.post("/api/v1/auth/password", json={"current_password": "mala", "new_password": "Otra-Clave-Ficticia-1"}
                   ).status_code == 422
    r = c1.post("/api/v1/auth/password", json={"current_password": password, "new_password": "Otra-Clave-Ficticia-1"})
    assert r.status_code == 204
    assert c1.get("/api/v1/me").status_code == 200
    assert c2.get("/api/v1/me").status_code == 401


def test_token_antiguo_sin_sesion_no_vale(app):
    """Las cookies emitidas antes de F0.2 (sin identificador de sesión) dejan de valer."""
    import jwt

    from app.config import get_settings

    s = get_settings()
    now = datetime.now(UTC)
    old = jwt.encode({"sub": "00000000-0000-0000-0000-000000000000", "iat": now, "exp": now + timedelta(hours=1),
                      "env": s.app_env}, s.session_secret, algorithm="HS256")
    c = TestClient(app)
    c.cookies.set("sp_session", old)
    assert c.get("/api/v1/me").status_code == 401


def test_paso_intermedio_no_sirve_como_sesion(app, enrolled):
    _, username, password, _, _ = enrolled()
    c = _client(app)
    c.post("/api/v1/auth/login", json={"username": username, "password": password})
    pending = c.cookies.get("sp_pending")
    c2 = TestClient(app)
    c2.cookies.set("sp_session", pending)
    assert c2.get("/api/v1/me").status_code == 401


def test_demo_sigue_disponible_solo_en_desarrollo(app, login, monkeypatch):
    from app.config import get_settings

    c = login("recepcion.bcn")
    assert c.get("/api/v1/me").json()["auth_mode"] == "demo"
    # Si se retira el modo demo, las sesiones demo existentes dejan de valer.
    monkeypatch.setattr(get_settings(), "auth_mode", "local")
    assert c.get("/api/v1/me").status_code == 401
    assert TestClient(app).get("/api/v1/auth/demo/users").status_code == 404


def test_configuracion_segura_fuera_de_desarrollo():
    import pytest
    from pydantic import ValidationError

    from app.config import Settings

    base = {"database_url": "postgresql+psycopg://x@y/z", "session_secret": "s" * 40, "cookie_secure": True}
    with pytest.raises(ValidationError, match="FIELD_ENCRYPTION_KEY"):
        Settings(app_env="production", auth_mode="local", **base)
    with pytest.raises(ValidationError, match="prohibido"):
        Settings(app_env="staging", auth_mode="local,demo", field_encryption_key="k", **base)
    with pytest.raises(ValidationError, match="MFA"):
        Settings(app_env="production", auth_mode="oidc", oidc_require_mfa=False, **base)
    with pytest.raises(ValidationError, match="AUTH_MODE"):
        Settings(app_env="development", auth_mode="magia", **base)
    ok = Settings(app_env="production", auth_mode="local,oidc", field_encryption_key="k", **base)
    assert ok.auth_methods == {"local", "oidc"}


def test_totp_tolera_desfase_de_un_paso_y_no_mas():
    import pyotp

    from app.security.credentials import verify_totp

    secret = pyotp.random_base32()
    t = pyotp.TOTP(secret)
    now = 1_800_000_000
    assert verify_totp(secret, t.at(now - 30), None, now=now) is not None
    assert verify_totp(secret, t.at(now - 90), None, now=now) is None
    step = verify_totp(secret, t.at(now), None, now=now)
    assert verify_totp(secret, t.at(now), step, now=now) is None  # reutilización
