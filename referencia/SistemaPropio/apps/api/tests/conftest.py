"""Fixtures de prueba: BD PostgreSQL real dedicada (TEST_DATABASE_URL), migrada y sembrada.

Al arrancar la sesión se ejecuta upgrade -> downgrade -> upgrade para demostrar que la
migración es reversible, y después se cargan los datos ficticios.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import uuid
from pathlib import Path

import pytest


def _from_dotenv(key: str) -> str | None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip() or None
    return None


# Base de datos de pruebas SEPARADA: se vacía (downgrade) y recrea en cada ejecución.
TEST_DB = os.environ.get("TEST_DATABASE_URL") or _from_dotenv("TEST_DATABASE_URL") or ""
if not TEST_DB:
    raise RuntimeError("Defina TEST_DATABASE_URL (entorno o apps/api/.env).")
if not TEST_DB.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test.")
RESTORE_DB = (os.environ.get("RESTORE_TEST_DATABASE_URL") or _from_dotenv("RESTORE_TEST_DATABASE_URL")
              or TEST_DB.rsplit("/", 1)[0] + "/sistema_propio_restore_test")
os.environ.update({
    "APP_ENV": "test",
    "AUTH_MODE": "demo,local,oidc",
    # Proveedor OIDC ficticio: las pruebas lo simulan con httpx.MockTransport (sin red).
    "OIDC_ISSUER": "https://idp.ficticio.invalid",
    "OIDC_CLIENT_ID": "sistema-propio-pruebas",
    "WEB_ORIGIN": "http://testserver",
    "RESTORE_DATABASE_URL": RESTORE_DB,
    # Todas las pruebas comparten la IP "testclient": el límite por IP se prueba aparte con su propia IP.
    "LOGIN_MAX_FAILURES_IP": "100000",
    "DATABASE_URL": TEST_DB,
    "SESSION_SECRET": secrets.token_urlsafe(48),
    "COOKIE_SECURE": "false",
    # Documentos de expedientes (cifrados) de la semilla y las pruebas: carpeta temporal propia
    "DOCUMENTS_DIR": tempfile.mkdtemp(prefix="sp_documentos_"),
})

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]
CSRF = {"X-Requested-With": "sistema-propio"}
MIGRATION_LOG: list[str] = []


def _alembic_cfg() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def database():
    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")
    MIGRATION_LOG.append("upgrade")
    command.downgrade(cfg, "base")
    MIGRATION_LOG.append("downgrade")
    command.upgrade(cfg, "head")
    MIGRATION_LOG.append("upgrade")
    from app.db import get_sessionmaker
    from app.seed import seed

    db = get_sessionmaker()()
    try:
        assert seed(db) is True
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="session")
def app(database):
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def login(app):
    def _login(username: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/api/v1/auth/demo/login", json={"username": username}, headers=CSRF)
        assert r.status_code == 204, r.text
        c.headers.update(CSRF)
        return c

    return _login


@pytest.fixture
def db():
    from app.db import get_sessionmaker

    s = get_sessionmaker()()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def ids(db):
    """Identificadores útiles de la semilla."""
    from app.models import CaseFile, Contact, Organization, UserAccount
    from app.seed import ORG_CO, ORG_ES, ORG_ES2

    orgs = {o.name: o for o in db.execute(select(Organization)).scalars()}
    users = {u.username: u.id for u in db.execute(select(UserAccount)).scalars()}
    lucia = db.execute(select(Contact).where(Contact.given_name == "Lucía", Contact.family_names == "Ferrer Demo",
                                             Contact.organization_id == orgs[ORG_ES].id)).scalar_one()
    cases = list(db.execute(select(CaseFile).where(CaseFile.contact_id == lucia.id)).scalars())
    return {
        "es": orgs[ORG_ES].id, "es2": orgs[ORG_ES2].id, "co": orgs[ORG_CO].id, "users": users,
        "lucia": lucia.id,
        "lucia_lab": next(c.id for c in cases if c.materia == "laboral"),
        "lucia_ext": next(c.id for c in cases if c.materia == "extranjeria"),
    }


def denied_events(db, action: str, resource_id) -> list:
    from app.models import AuditEvent

    db.rollback()
    return list(db.execute(select(AuditEvent).where(AuditEvent.action == action, AuditEvent.outcome == "denied",
                                                    AuditEvent.resource_id == str(resource_id))).scalars())


def unique_passport() -> str:
    return "ZZT" + uuid.uuid4().hex[:10].upper()


# ---------------------------------------------------------------- F0.2: usuarios con contraseña + TOTP
def totp_now(secret: str, offset_steps: int = 0) -> str:
    import time

    import pyotp

    t = pyotp.TOTP(secret)
    return t.at(int(time.time()) + offset_steps * t.interval)


@pytest.fixture
def new_user(login, ids):
    """Crea (como Dirección) un usuario nuevo y devuelve (username, contraseña provisional, datos)."""

    def _make(role: str = "asesor_laboral", org: str = "es", dept_code: str | None = "LAB") -> tuple[str, str, dict]:
        admin = login("direccion.demo")
        cat = admin.get("/api/v1/admin/catalog").json()
        o = next(x for x in cat["organizations"] if x["id"] == str(ids[org]))
        dept = next((d["id"] for d in o["departments"] if d["code"] == dept_code), None) if dept_code else None
        username = "f02." + uuid.uuid4().hex[:8]
        r = admin.post("/api/v1/admin/users", json={
            "username": username, "full_name": "Persona Ficticia F02", "email": f"{username}@demo.invalid",
            "membership": {"organization_id": str(ids[org]), "role_code": role, "department_id": dept},
            "reason": "alta de prueba ficticia"})
        assert r.status_code == 201, r.text
        return username, r.json()["temporary_password"], r.json()["user"]

    return _make


@pytest.fixture
def enrolled(app, new_user):
    """Usuario que ya completó el primer acceso. Devuelve (cliente con sesión, username, contraseña, secreto)."""

    def _make(role: str = "asesor_laboral", **kw):
        username, temp, user = new_user(role, **kw)
        c = TestClient(app)
        c.headers.update(CSRF)
        r = c.post("/api/v1/auth/login", json={"username": username, "password": temp})
        assert r.json() == {"stage": "enroll"}, r.text
        secret = c.post("/api/v1/auth/enroll/start").json()["secret"]
        password = "Clave-Ficticia-" + uuid.uuid4().hex[:6]
        r = c.post("/api/v1/auth/enroll/confirm", json={"code": totp_now(secret), "new_password": password})
        assert r.status_code == 204, r.text
        return c, username, password, secret, user

    return _make
