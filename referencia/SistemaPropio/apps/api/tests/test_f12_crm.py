"""F1.2 CRM: AT-05 (origen obligatorio), AT-06 (trazabilidad lead → expediente), permisos y seguimiento."""

from sqlalchemy import select

from .conftest import denied_events


def _contact(db, ids, given_like=None):
    from app.models import Contact

    q = select(Contact).where(Contact.organization_id == ids["es"], Contact.is_synthetic.is_(True))
    return db.execute(q.order_by(Contact.created_at.desc())).scalars().first()


def test_at05_sin_origen_no_se_guarda(login, ids, db):
    c = login("recepcion.bcn")
    ct = _contact(db, ids)
    base = {"organization_id": str(ids["es"]), "contact_id": str(ct.id), "materia": "laboral"}
    r = c.post("/api/v1/leads", json=base)
    assert r.status_code == 422 and any(d["field"] == "origin_code" for d in r.json()["error"]["details"])
    assert c.post("/api/v1/leads", json={**base, "origin_code": "inventado"}).status_code == 422
    r = c.post("/api/v1/leads", json={**base, "origin_code": "tiktok_live"})
    assert r.status_code == 422 and "campaña" in r.json()["error"]["message"]
    r = c.post("/api/v1/leads", json={**base, "origin_code": "google_ads", "utm_source": "google", "utm_medium": "cpc",
                                      "utm_campaign": "laboral-otono", "campaign": "Laboral otoño"})
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["status"] == "nuevo" and lead["utm"]["source"] == "google" and lead["origin_name"] == "Google Ads"
    assert "•" in lead["contact_phone_masked"]


def test_transiciones_motivos_y_version(login, ids, db):
    c = login("recepcion.bcn")
    ct = _contact(db, ids)
    lead = c.post("/api/v1/leads", json={"organization_id": str(ids["es"]), "contact_id": str(ct.id),
                                         "materia": "extranjeria", "origin_code": "telefono"}).json()
    lid = lead["id"]
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "cita_solicitada", "version": 1}).status_code == 409
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "convertido", "version": 1}).status_code == 422
    r = c.post(f"/api/v1/leads/{lid}/transition", json={"to": "cita_pagada", "version": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_disponible_aun"
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "descartado", "version": 1}).status_code == 422
    r = c.post(f"/api/v1/leads/{lid}/transition", json={"to": "contactado", "version": 1})
    assert r.status_code == 200 and r.json()["version"] == 2
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "en_seguimiento", "version": 1}).status_code == 409
    r = c.post(f"/api/v1/leads/{lid}/transition", json={"to": "descartado", "version": 2, "note": "No contesta (prueba)"})
    assert r.status_code == 200
    # Flujo reversible (Q-3.1): reabrir exige motivo
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "contactado", "version": 3}).status_code == 422
    assert c.post(f"/api/v1/leads/{lid}/transition", json={"to": "contactado", "version": 3,
                                                           "note": "Vuelve a llamar"}).status_code == 200
    detail = c.get(f"/api/v1/leads/{lid}").json()
    assert [e["to_status"] for e in detail["events"]] == ["contactado", "descartado", "contactado", "nuevo"]


def test_visibilidad_por_rol_y_entidad(login, ids, db):
    from app.models_work import Lead

    asesor = login("asesor.laboral.bcn")
    mine = asesor.get("/api/v1/leads", params={"page_size": 100}).json()["items"]
    uid = str(ids["users"]["asesor.laboral.bcn"])
    assert mine and all(x["assigned_user_id"] == uid for x in mine)
    other = db.execute(select(Lead).where(Lead.assigned_user_id != ids["users"]["asesor.laboral.bcn"],
                                          Lead.organization_id == ids["es"])).scalars().first()
    assert asesor.get(f"/api/v1/leads/{other.id}").status_code == 404
    assert login("asesor.laboral.autonomo").get(f"/api/v1/leads/{other.id}").status_code == 404
    assert login("contabilidad.demo").get("/api/v1/leads").status_code == 403
    assert denied_events(db, "lead.read", other.id)


def test_marketing_ve_leads_y_embudo_pero_nunca_expedientes(login, ids):
    mk = login("marketing.demo")
    assert mk.get("/api/v1/leads").json()["total"] > 10
    f = mk.get("/api/v1/leads/funnel").json()
    assert f["total"] == sum(f["por_estado"].values()) and f["convertidos"] >= 8
    assert mk.get("/api/v1/cases").json()["total"] == 0
    assert mk.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 403
    lead = mk.get("/api/v1/leads").json()["items"][0]
    assert mk.post(f"/api/v1/leads/{lead['id']}/transition", json={"to": "contactado", "version": lead["version"]}).status_code == 403
    assert login("asesor.laboral.bcn").get("/api/v1/leads/funnel").status_code == 403


def test_seguimiento_24h_72h_7d(login):
    c = login("recepcion.bcn")
    items = c.get("/api/v1/leads", params={"follow_up": True, "page_size": 100}).json()["items"]
    levels = {x["follow_up_level"] for x in items}
    assert items and levels <= {1, 2, 3} and {1, 2, 3} <= levels
    assert all(x["status"] in ("nuevo", "contactado", "en_seguimiento") for x in items)


def test_at06_lead_a_expediente_trazable(login, ids, db):
    rec = login("recepcion.bcn")
    ct = _contact(db, ids)
    lead = rec.post("/api/v1/leads", json={"organization_id": str(ids["es"]), "contact_id": str(ct.id),
                                           "materia": "laboral", "origin_code": "web",
                                           "assigned_user_id": str(ids["users"]["asesor.laboral.bcn"])}).json()
    funnel_before = login("direccion.demo").get("/api/v1/leads/funnel").json()["convertidos"]
    asesor = login("asesor.laboral.bcn")
    org = next(o for o in asesor.get("/api/v1/organizations").json() if o["id"] == str(ids["es"]))
    bcn = next(b["id"] for b in org["branches"] if b["name"] == "Barcelona")
    r = asesor.post("/api/v1/cases", json={"organization_id": str(ids["es"]), "contact_id": str(ct.id), "materia": "laboral",
                                           "branch_id": bcn, "title": "Despido (prueba AT-06)", "lead_id": lead["id"]})
    assert r.status_code == 201, r.text
    case = r.json()
    after = asesor.get(f"/api/v1/leads/{lead['id']}").json()
    assert after["status"] == "convertido" and after["case_code"] == case["code"] and after["case_access"] == "full"
    assert login("direccion.demo").get("/api/v1/leads/funnel").json()["convertidos"] == funnel_before + 1
    # Recepción ve el lead convertido y el código del expediente, pero el expediente solo como metadatos
    assert rec.get(f"/api/v1/leads/{lead['id']}").json()["case_access"] == "metadata"
    # Un lead convertido no puede abrir un segundo expediente
    r2 = asesor.post("/api/v1/cases", json={"organization_id": str(ids["es"]), "contact_id": str(ct.id), "materia": "laboral",
                                            "branch_id": bcn, "title": "Otro", "lead_id": lead["id"]})
    assert r2.status_code == 409


def test_lead_en_bd_no_se_borra_y_no_mezcla_entidades(db, ids):
    import pytest
    from sqlalchemy import text

    from app.models_work import Lead

    lead = db.execute(select(Lead).limit(1)).scalar_one()
    with pytest.raises(Exception, match="inmutable"):
        db.execute(text(f"DELETE FROM lead WHERE id='{lead.id}'"))
    db.rollback()
    from app.models import Contact

    other = db.execute(select(Contact).where(Contact.organization_id == ids["es2"])).scalars().first()
    with pytest.raises(Exception, match="otra entidad"):
        db.execute(text(f"UPDATE lead SET contact_id='{other.id}' WHERE id='{lead.id}'"))
    db.rollback()
