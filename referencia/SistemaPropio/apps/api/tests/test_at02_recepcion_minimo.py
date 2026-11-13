"""AT-02 Recepción localiza por teléfono con datos minimizados, sin pruebas ni historial jurídico."""

from sqlalchemy import select


def _lucia_phone(db, ids):
    from app.models import ContactPoint

    return db.execute(select(ContactPoint.value_normalized).where(
        ContactPoint.contact_id == ids["lucia"], ContactPoint.kind == "phone")).scalar_one()


def test_recepcion_busca_por_telefono_y_obtiene_ficha_minima(login, ids, db):
    phone = _lucia_phone(db, ids)
    c = login("recepcion.bcn")
    r = c.get("/api/v1/contacts", params={"q": phone[-9:]})
    assert r.status_code == 200
    items = r.json()["items"]
    hit = next(x for x in items if x["id"] == str(ids["lucia"]))
    assert hit["access_level"] == "minimal"
    assert hit["display_name"] == "Lucía Ferrer Demo"
    # Ni el teléfono completo ni el documento completo viajan en la respuesta.
    assert phone not in r.text
    assert "ZZDEMO" not in r.text
    assert all("•" in m for m in hit["phones_masked"] + hit["identifiers_masked"])
    for forbidden in ("identifiers", "points", "addresses", "birth_date", "consents"):
        assert forbidden not in hit


def test_recepcion_detalle_es_minimo(login, ids):
    r = login("recepcion.bcn").get(f"/api/v1/contacts/{ids['lucia']}")
    assert r.status_code == 200 and r.json()["access_level"] == "minimal"
    assert "addresses" not in r.json()


def test_recepcion_ve_metadatos_pero_no_contenido_de_expedientes(login, ids):
    c = login("recepcion.bcn")
    meta = c.get(f"/api/v1/contacts/{ids['lucia']}/cases").json()
    assert {m["materia"] for m in meta} == {"laboral", "extranjeria"}
    assert all(m["access_level"] == "metadata" for m in meta)
    assert all("confidential_summary" not in m and "title" not in m for m in meta)
    assert c.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 403
    assert c.get(f"/api/v1/cases/{ids['lucia_ext']}").status_code == 403


def test_recepcion_no_ve_historial_de_auditoria(login, ids):
    assert login("recepcion.bcn").get(f"/api/v1/contacts/{ids['lucia']}/history").status_code == 403


def test_recepcion_no_puede_modificar(login, ids):
    r = login("recepcion.bcn").patch(f"/api/v1/contacts/{ids['lucia']}",
                                     json={"version": 1, "given_name": "Otra", "reason": "prueba"})
    assert r.status_code == 403


def test_recepcion_no_puede_listar_sin_criterio_ni_con_criterio_corto(login):
    c = login("recepcion.bcn")
    assert c.get("/api/v1/contacts").status_code == 422
    assert c.get("/api/v1/contacts", params={"q": "lu"}).status_code == 422


def test_atc_tampoco_lee_contenido(login, ids):
    c = login("atc.demo")
    assert c.get(f"/api/v1/cases/{ids['lucia_lab']}").status_code == 403
    assert c.get(f"/api/v1/contacts/{ids['lucia']}").json()["access_level"] == "minimal"
