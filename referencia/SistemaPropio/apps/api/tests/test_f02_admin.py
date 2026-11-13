"""F0.2 — Administración de usuarios y pertenencias (Dirección). Cambios inmediatos, auditados y acotados."""

from __future__ import annotations

from sqlalchemy import select

from .conftest import denied_events


def _audit(db, action, resource_id):
    from app.models import AuditEvent

    db.rollback()
    return list(db.execute(select(AuditEvent).where(AuditEvent.action == action,
                                                    AuditEvent.resource_id == str(resource_id))).scalars())


def test_solo_direccion_administra_y_se_audita(login, ids, db):
    for who in ("recepcion.bcn", "lider.laboral", "marketing.demo"):
        c = login(who)
        assert c.get("/api/v1/admin/users").status_code == 403
        assert c.get("/api/v1/admin/backups").status_code == 403
    uid = ids["users"]["recepcion.bcn"]
    from app.models import AuditEvent

    db.rollback()
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "admin.users.list", AuditEvent.outcome == "denied",
                                               AuditEvent.actor_user_id == uid)).first()


def test_alta_de_usuario_auditada_sin_contrasena(login, new_user, db):
    username, temp, user = new_user()
    assert len(temp) >= 16
    ev = _audit(db, "admin.user_create", user["id"])
    assert len(ev) == 1 and ev[0].reason == "alta de prueba ficticia"
    assert temp not in str(ev[0].after) and ev[0].after["rol"] == "asesor_laboral"
    assert user["must_change_password"] is True and user["mfa_enrolled"] is False
    # Nombre de usuario duplicado → 409
    admin = login("direccion.demo")
    r = admin.post("/api/v1/admin/users", json={
        "username": username, "full_name": "Otra Persona Ficticia", "email": "otra@demo.invalid",
        "membership": {"organization_id": user["memberships"][0]["organization_id"], "role_code": "atc"},
        "reason": "duplicado de prueba"})
    assert r.status_code == 409


def test_cambio_de_rol_tiene_efecto_inmediato(login, enrolled, ids):
    c, username, *_rest, user = enrolled("recepcion", dept_code="REC")
    assert c.get("/api/v1/admin/users").status_code == 403
    perms = c.get("/api/v1/me").json()["permissions"][str(ids["es"])]
    assert "lead.create" in perms and "case.create" not in perms
    admin = login("direccion.demo")
    mid = user["memberships"][0]["id"]
    cat = admin.get("/api/v1/admin/catalog").json()
    lab = next(d["id"] for o in cat["organizations"] if o["id"] == str(ids["es"]) for d in o["departments"]
               if d["code"] == "LAB")
    r = admin.post(f"/api/v1/admin/users/{user['id']}/memberships", json={
        "organization_id": str(ids["es"]), "role_code": "asesor_laboral", "department_id": lab,
        "reason": "pasa a Laboral"})
    assert r.status_code == 201
    r = admin.post(f"/api/v1/admin/memberships/{mid}/end", json={"reason": "deja Recepción"})
    assert r.status_code == 200
    estados = {m["role_code"]: m["status"] for m in r.json()["memberships"]}
    assert estados == {"recepcion": "finalizada", "asesor_laboral": "activa"}
    # Misma sesión, sin volver a entrar: los permisos ya son los nuevos
    perms = c.get("/api/v1/me").json()["permissions"][str(ids["es"])]
    assert "case.create" in perms


def test_desactivar_cierra_sesiones_al_instante(login, enrolled, db):
    c, *_rest, user = enrolled()
    assert c.get("/api/v1/me").status_code == 200
    admin = login("direccion.demo")
    r = admin.post(f"/api/v1/admin/users/{user['id']}/deactivate", json={"reason": "baja ficticia"})
    assert r.status_code == 200 and r.json()["status"] == "inactivo" and r.json()["active_sessions"] == 0
    assert c.get("/api/v1/me").status_code == 401
    ev = _audit(db, "admin.user_deactivate", user["id"])
    assert ev[0].before["status"] == "activo" and ev[0].after["status"] == "inactivo"
    assert ev[0].after["sesiones_cerradas"] >= 1
    r = admin.post(f"/api/v1/admin/users/{user['id']}/reactivate", json={"reason": "vuelve (ficticio)"})
    assert r.json()["status"] == "activo"


def test_restablecer_credenciales_exige_nuevo_primer_acceso(app, login, enrolled):
    from fastapi.testclient import TestClient

    from .conftest import CSRF

    c, username, password, _secret, user = enrolled()
    admin = login("direccion.demo")
    r = admin.post(f"/api/v1/admin/users/{user['id']}/reset-credentials", json={"reason": "perdió el móvil (ficticio)"})
    assert r.status_code == 200
    temp = r.json()["temporary_password"]
    assert r.json()["user"]["mfa_enrolled"] is False
    assert c.get("/api/v1/me").status_code == 401
    n = TestClient(app)
    n.headers.update(CSRF)
    assert n.post("/api/v1/auth/login", json={"username": username, "password": password}).status_code == 401
    assert n.post("/api/v1/auth/login", json={"username": username, "password": temp}).json() == {"stage": "enroll"}


def test_admin_cierra_una_sesion_concreta(login, enrolled):
    c, *_rest, user = enrolled()
    admin = login("direccion.demo")
    detail = admin.get(f"/api/v1/admin/users/{user['id']}").json()
    sid = next(s["id"] for s in detail["sessions"] if s["state"] == "activa")
    r = admin.post(f"/api/v1/admin/sessions/{sid}/revoke", json={"reason": "dispositivo perdido (ficticio)"})
    assert r.json()["state"] == "revocada"
    assert c.get("/api/v1/me").status_code == 401


def test_no_puede_quitarse_a_si_mismo_ni_dejar_la_entidad_sin_admin(login, ids):
    admin = login("direccion.demo")
    me = admin.get("/api/v1/me").json()
    r = admin.post(f"/api/v1/admin/users/{me['id']}/deactivate", json={"reason": "probar autobaja"})
    assert r.status_code == 422
    users = admin.get("/api/v1/admin/users?q=direccion.demo").json()
    mid = next(m["id"] for m in users[0]["memberships"] if m["organization_id"] == str(ids["es"]))
    r = admin.post(f"/api/v1/admin/memberships/{mid}/end", json={"reason": "probar autorretirada"})
    assert r.status_code == 422


def test_ultima_persona_administradora_protegida(login, enrolled, ids):
    """Con dos administradores, uno puede retirar al otro; nunca quedar en cero."""
    c2, *_rest, user2 = enrolled("direccion", dept_code="DIR")
    admin = login("direccion.demo")
    mid2 = user2["memberships"][0]["id"]
    assert admin.post(f"/api/v1/admin/memberships/{mid2}/end", json={"reason": "fin de prueba"}).status_code == 200
    # Desde ese momento la segunda persona ya no administra (efecto inmediato en su sesión)
    assert c2.get("/api/v1/admin/users").status_code == 403


def test_no_se_gestiona_a_usuarios_de_otra_entidad(login, new_user, ids):
    # direccion.demo administra ES y ES2, pero no Colombia.
    admin = login("direccion.demo")
    co_user = ids["users"]["soporte.colombia"]
    assert admin.get(f"/api/v1/admin/users/{co_user}").status_code == 404
    assert admin.post(f"/api/v1/admin/users/{co_user}/deactivate", json={"reason": "no es mío"}).status_code == 404
    r = admin.post("/api/v1/admin/users", json={
        "username": "intruso.co", "full_name": "Intruso Ficticio", "email": "intruso@demo.invalid",
        "membership": {"organization_id": str(ids["co"]), "role_code": "direccion"}, "reason": "escalar a Colombia"})
    assert r.status_code == 404


def test_sede_o_departamento_de_otra_entidad_rechazado(login, ids):
    admin = login("direccion.demo")
    cat = admin.get("/api/v1/admin/catalog").json()
    es2 = next(o for o in cat["organizations"] if o["id"] == str(ids["es2"]))
    r = admin.post("/api/v1/admin/users", json={
        "username": "mezcla.ficticia", "full_name": "Mezcla Ficticia", "email": "mezcla@demo.invalid",
        "membership": {"organization_id": str(ids["es"]), "role_code": "atc", "branch_id": es2["branches"][0]["id"]},
        "reason": "sede cruzada"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "branch_id"


def test_usuario_compartido_con_otra_entidad_no_se_desactiva(login, ids, db):
    """Un usuario con pertenencia vigente fuera del ámbito del administrador no se desactiva desde aquí."""
    from app.models import Membership, Role, UserAccount

    db.rollback()
    u = UserAccount(username="compartido.ficticio", full_name="Compartido Ficticio", email="c@demo.invalid")
    db.add(u)
    db.flush()
    role = db.execute(select(Role).where(Role.code == "atc")).scalar_one()
    db.add_all([Membership(user_id=u.id, organization_id=ids["es"], role_id=role.id),
                Membership(user_id=u.id, organization_id=ids["co"], role_id=role.id)])
    db.commit()
    admin = login("direccion.demo")
    detail = admin.get(f"/api/v1/admin/users/{u.id}").json()
    assert [m["organization_id"] for m in detail["memberships"]] == [str(ids["es"])]  # no ve la de Colombia
    r = admin.post(f"/api/v1/admin/users/{u.id}/deactivate", json={"reason": "probar alcance"})
    assert r.status_code == 403
    assert denied_events(db, "admin.user_deactivate", u.id)


def test_alta_de_autorizacion_desde_formulario(login, ids):
    """El código de expediente es consecutivo por entidad: Dirección (dos entidades) ve dos coincidencias."""
    admin = login("direccion.demo")
    r = admin.get("/api/v1/grants/lookup?code=lab-2026-0001")
    assert r.status_code == 200
    matches = r.json()["matches"]
    assert len(matches) == 2 and {m["organization"] for m in matches} == {
        "Despacho Demo España S.L. (ficticia)", "Entidad Demo Autónomo (ficticia)"}
    es = next(m for m in matches if m["organization"].startswith("Despacho"))
    assert all(c["username"] != "soporte.colombia" for c in es["candidates"])
    assert login("asesor.laboral.bcn").get("/api/v1/grants/lookup?code=LAB-2026-0001").status_code == 403
    assert admin.get("/api/v1/grants/lookup?code=NOP-0000-0000").status_code == 404
