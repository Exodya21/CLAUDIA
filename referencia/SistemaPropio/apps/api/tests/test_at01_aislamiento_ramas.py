"""AT-01 Seguridad transversal: Laboral no lee Extranjería (ni por URL ni por API) y se registra."""

from sqlalchemy import select

from .conftest import denied_events


def test_asesor_laboral_recibe_403_en_expediente_extranjeria_y_se_audita(login, ids, db):
    c = login("asesor.laboral.bcn")
    r = c.get(f"/api/v1/cases/{ids['lucia_ext']}")
    assert r.status_code == 403
    body = r.json()["error"]
    assert body["code"] == "acceso_denegado" and body["request_id"]
    assert "confidential_summary" not in r.text and "Notas confidenciales" not in r.text
    events = denied_events(db, "case.read", ids["lucia_ext"])
    assert events and events[-1].actor_user_id == ids["users"]["asesor.laboral.bcn"]


def test_asesor_laboral_si_lee_su_expediente_laboral(login, ids):
    r = login("asesor.laboral.bcn").get(f"/api/v1/cases/{ids['lucia_lab']}")
    assert r.status_code == 200
    assert r.json()["confidential_summary"].startswith("[FICTICIO]")


def test_listado_y_filtro_no_revelan_extranjeria_al_asesor_laboral(login):
    c = login("asesor.laboral.bcn")
    assert c.get("/api/v1/cases", params={"materia": "extranjeria"}).json()["total"] == 0
    all_cases = c.get("/api/v1/cases", params={"page_size": 50}).json()["items"]
    assert all_cases and all(x["materia"] == "laboral" for x in all_cases)


def test_expedientes_del_contacto_ocultan_la_otra_rama(login, ids):
    lab = login("asesor.laboral.bcn").get(f"/api/v1/contacts/{ids['lucia']}/cases").json()
    assert [x["materia"] for x in lab] == ["laboral"]
    ext = login("asesor.extranjeria.mad").get(f"/api/v1/contacts/{ids['lucia']}/cases").json()
    assert [x["materia"] for x in ext] == ["extranjeria"]


def test_asesor_extranjeria_no_lee_laboral(login, ids):
    assert login("asesor.extranjeria.mad").get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 403


def test_gestor_laboral_solo_ve_asignados_aunque_sea_de_su_rama(login, db):
    from app.models import CaseAssignment, CaseFile, UserAccount

    gestor = db.execute(select(UserAccount).where(UserAccount.username == "gestor.laboral.vlc")).scalar_one()
    mine = set(db.execute(select(CaseAssignment.case_id).where(CaseAssignment.user_id == gestor.id)).scalars())
    other_lab = db.execute(select(CaseFile).where(CaseFile.materia == "laboral", CaseFile.id.not_in(mine))).scalars().first()
    c = login("gestor.laboral.vlc")
    assert c.get(f"/api/v1/cases/{other_lab.id}").status_code == 403
    listed = {x["id"] for x in c.get("/api/v1/cases", params={"page_size": 50}).json()["items"]}
    assert listed == {str(i) for i in mine}


def test_lider_laboral_ve_toda_la_rama_laboral_pero_no_extranjeria(login, ids):
    c = login("lider.laboral")
    assert c.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 200
    assert c.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 403
    assert c.get("/api/v1/cases", params={"materia": "extranjeria"}).json()["total"] == 0


def test_direccion_lee_ambas_ramas(login, ids):
    c = login("direccion.demo")
    assert c.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 200
    assert c.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 200


def test_autorizacion_puntual_concede_y_revoca_acceso(login, ids):
    from datetime import UTC, datetime, timedelta

    asesor = login("asesor.laboral.bcn")
    assert asesor.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 403
    d = login("direccion.demo")
    r = d.post("/api/v1/grants", json={
        "user_id": str(ids["users"]["asesor.laboral.bcn"]), "case_id": str(ids["lucia_ext"]),
        "reason": "Sustitución puntual por baja de la asesora titular (prueba)",
        "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat()})
    assert r.status_code == 201, r.text
    assert asesor.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 200
    assert d.post(f"/api/v1/grants/{r.json()['id']}/revoke").status_code == 200
    assert asesor.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 403


def test_solo_direccion_concede_y_nunca_a_otra_entidad(login, ids):
    from datetime import UTC, datetime, timedelta

    body = {"user_id": str(ids["users"]["asesor.laboral.bcn"]), "case_id": str(ids["lucia_ext"]),
            "reason": "Intento de autoconcesión (prueba)", "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()}
    assert login("lider.laboral").post("/api/v1/grants", json=body).status_code == 403
    body["user_id"] = str(ids["users"]["asesor.laboral.autonomo"])
    r = login("direccion.demo").post("/api/v1/grants", json=body)
    assert r.status_code == 422
    body["user_id"] = str(ids["users"]["asesor.laboral.bcn"])
    body["expires_at"] = (datetime.now(UTC) + timedelta(days=90)).isoformat()
    assert login("direccion.demo").post("/api/v1/grants", json=body).status_code == 422
