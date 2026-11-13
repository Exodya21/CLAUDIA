"""Multiempresa, IDOR, inyección SQL, enumeración, CSRF, borrado y configuración."""

import uuid

import pytest
from sqlalchemy import select, text

from .conftest import CSRF, denied_events


# ---------------------------------------------------------------- multiempresa
def test_usuario_de_otra_entidad_no_enumera_ni_lee(login, ids, db):
    c = login("asesor.laboral.autonomo")
    r = c.get("/api/v1/contacts", params={"q": "Demo", "page_size": 50})
    assert r.status_code == 200
    orgs = {x["organization_id"] for x in r.json()["items"]}
    assert orgs == {str(ids["es2"])}
    # Forzar el identificador de un contacto/expediente de la otra entidad => 404 (no se confirma su existencia)
    assert c.get(f"/api/v1/contacts/{ids['lucia']}").status_code == 404
    assert c.get(f"/api/v1/contacts/{ids['lucia']}/cases").status_code == 404
    assert c.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 404
    assert denied_events(db, "case.read", ids["lucia_lab"])
    # Tampoco puede crear contactos en una entidad ajena.
    r = c.post("/api/v1/contacts", json={"organization_id": str(ids["es"]), "given_name": "X", "family_names": "Y"})
    assert r.status_code == 404
    assert {o["id"] for o in c.get("/api/v1/organizations").json()} == {str(ids["es2"])}


def test_soporte_colombia_sin_acceso_a_datos_de_espana(login, ids):
    c = login("soporte.colombia")
    r = c.get("/api/v1/contacts", params={"q": "Ferrer"})
    assert all(x["organization_id"] == str(ids["co"]) for x in r.json()["items"])
    assert c.get(f"/api/v1/contacts/{ids['lucia']}").status_code == 404
    assert c.get("/api/v1/cases").json()["total"] == 0


def test_direccion_con_dos_entidades_ve_ambas_pero_no_colombia(login, ids):
    c = login("direccion.demo")
    orgs = {o["id"] for o in c.get("/api/v1/organizations").json()}
    assert orgs == {str(ids["es"]), str(ids["es2"])}


# ---------------------------------------------------------------- IDOR y enumeración
def test_ids_aleatorios_o_malformados(login):
    c = login("direccion.demo")
    assert c.get(f"/api/v1/contacts/{uuid.uuid4()}").status_code == 404
    assert c.get(f"/api/v1/cases/{uuid.uuid4()}").status_code == 404
    r = c.get("/api/v1/contacts/1")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validacion"


def test_paginacion_limitada(login):
    c = login("direccion.demo")
    assert c.get("/api/v1/contacts", params={"page_size": 1000}).status_code == 422
    r = c.get("/api/v1/contacts", params={"page_size": 5, "page": 2}).json()
    assert len(r["items"]) == 5 and r["page"] == 2 and r["total"] >= 40


@pytest.mark.parametrize("payload", [
    "' OR 1=1 --", "'; DROP TABLE contact; --", "%%%", "___", "\\%\\", "Ferrer' UNION SELECT * FROM user_account--",
])
def test_inyeccion_sql_y_comodines_no_alteran_la_consulta(login, db, payload):
    c = login("recepcion.bcn")
    r = c.get("/api/v1/contacts", params={"q": payload})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    db.rollback()
    assert db.execute(text("SELECT count(*) FROM contact")).scalar_one() > 0


def test_busqueda_sin_tildes(login):
    r = login("recepcion.bcn").get("/api/v1/contacts", params={"q": "lucia ferrer"})
    assert any(x["display_name"] == "Lucía Ferrer Demo" for x in r.json()["items"])


# ---------------------------------------------------------------- sesión y CSRF
def test_sin_sesion_401_y_csrf(app, ids):
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    assert anon.get("/api/v1/me").status_code == 401
    assert anon.get("/api/v1/contacts", params={"q": "abc"}).json()["error"]["code"] == "no_autenticado"
    r = anon.post("/api/v1/auth/demo/login", json={"username": "direccion.demo"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"
    assert anon.post("/api/v1/auth/demo/login", json={"username": "no.existe"}, headers=CSRF).status_code == 401
    anon.cookies.set("sp_session", "token.manipulado.x")
    assert anon.get("/api/v1/me").status_code == 401


def test_cookie_es_httponly_y_samesite(app):
    from fastapi.testclient import TestClient

    r = TestClient(app).post("/api/v1/auth/demo/login", json={"username": "recepcion.bcn"}, headers=CSRF)
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=strict" in sc


# ---------------------------------------------------------------- borrado y modificación
def test_no_existe_borrado_de_expedientes_ni_contactos(login, ids, db):
    c = login("direccion.demo")
    assert c.delete(f"/api/v1/contacts/{ids['lucia']}").status_code == 405
    assert c.delete(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 405
    for stmt in (f"DELETE FROM case_file WHERE id='{ids['lucia_lab']}'", f"DELETE FROM contact WHERE id='{ids['lucia']}'"):
        with pytest.raises(Exception, match="inmutable"):
            db.execute(text(stmt))
        db.rollback()


def test_expediente_no_puede_mezclar_entidades_en_bd(db, ids):
    from app.models import CaseFile

    cf = db.execute(select(CaseFile).where(CaseFile.organization_id == ids["es2"])).scalars().first()
    with pytest.raises(Exception, match="otra entidad"):
        db.execute(text(f"UPDATE case_file SET contact_id='{ids['lucia']}' WHERE id='{cf.id}'"))
    db.rollback()


def test_control_de_version_y_documentos_sensibles(login, ids, db):
    from app.models import Contact

    created = login("asesor.laboral.bcn").post("/api/v1/contacts", json={
        "organization_id": str(ids["es"]), "given_name": "Versión", "family_names": "Ficticia"}).json()
    asesor = login("asesor.laboral.bcn")
    assert asesor.patch(f"/api/v1/contacts/{created['id']}", json={
        "version": 99, "given_name": "X", "reason": "prueba"}).status_code == 409
    # El asesor no gestiona documentos de identidad; el gestor sí, pero solo de contactos accesibles.
    r = asesor.patch(f"/api/v1/contacts/{created['id']}", json={
        "version": 1, "add_identifiers": [{"kind": "NIE", "number": "X1234567L", "country": "ES"}], "reason": "alta doc"})
    assert r.status_code == 403
    gestor = login("gestor.laboral.vlc")
    assert gestor.patch(f"/api/v1/contacts/{created['id']}", json={
        "version": 1, "add_identifiers": [{"kind": "NIE", "number": "X1234567L", "country": "ES"}],
        "reason": "alta doc"}).status_code == 403  # solo ve la ficha mínima: no puede modificarla
    db.rollback()
    assert db.get(Contact, created["id"]).version == 1


def test_asesor_ve_ficha_completa_de_sus_contactos_y_minima_del_resto(login, ids, db):
    from app.models import CaseFile, Contact

    ext_contact = db.execute(select(Contact).join(CaseFile, CaseFile.contact_id == Contact.id).where(
        CaseFile.materia == "extranjeria", Contact.id != ids["lucia"])).scalars().first()
    c = login("asesor.laboral.bcn")
    assert c.get(f"/api/v1/contacts/{ids['lucia']}").json()["access_level"] == "full"
    assert c.get(f"/api/v1/contacts/{ext_contact.id}").json()["access_level"] == "minimal"


# ---------------------------------------------------------------- configuración
def test_demo_prohibido_en_produccion(monkeypatch):
    from pydantic import ValidationError

    from app.config import Settings

    for env in ("production", "staging"):
        with pytest.raises(ValidationError, match="prohibido"):
            Settings(app_env=env, auth_mode="demo", database_url="postgresql+psycopg://x@y/z", session_secret="s" * 40)
    with pytest.raises(ValidationError):
        Settings(app_env="development", auth_mode="demo", database_url="postgresql+psycopg://x@y/z", session_secret="corta")
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(app_env="production", auth_mode="oidc", database_url="postgresql+psycopg://x@y/z",
                 session_secret="s" * 40, cookie_secure=False)
    ok = Settings(app_env="production", auth_mode="oidc", database_url="postgresql+psycopg://x@y/z",
                  session_secret="s" * 40, cookie_secure=True)
    assert ok.auth_mode == "oidc"


def test_semilla_se_niega_fuera_de_desarrollo(monkeypatch):
    from app import seed
    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    get_settings.cache_clear()
    try:
        assert seed.main() == 2
    finally:
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("AUTH_MODE", "demo")
        get_settings.cache_clear()


def test_openapi_y_salud(app):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    spec = c.get("/api/v1/openapi.json").json()
    assert spec["info"]["title"] == "SISTEMA PROPIO API"
    assert all(p.startswith("/api/v1/") for p in spec["paths"])
    assert c.get("/api/v1/health").json()["status"] == "ok"


def test_oidc_no_simula_login(app, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings

    # Sin proveedor configurado (T-01 pendiente) el acceso corporativo responde "No disponible aún".
    monkeypatch.setattr(get_settings(), "oidc_issuer", None)
    r = TestClient(app).get("/api/v1/auth/oidc/login")
    assert r.status_code == 501 and r.json()["error"]["code"] == "no_disponible_aun"


def test_migracion_reversible_ejecutada():
    from .conftest import MIGRATION_LOG

    assert MIGRATION_LOG == ["upgrade", "downgrade", "upgrade"]
