"""AT-04 Duplicados: mismo documento => alerta, nunca fusión. Teléfono compartido no fusiona."""

from sqlalchemy import select

# Valores de prueba documentados (ejemplo público de cálculo de letra), no de personas reales.
DNI_PRUEBA = "12345678Z"


def _payload(ids, **extra):
    base = {"organization_id": str(ids["es"]), "given_name": "Duplicado", "family_names": "Ficticio Uno",
            "identifiers": [{"kind": "DNI", "number": DNI_PRUEBA, "country": "ES"}]}
    base.update(extra)
    return base


def test_mismo_documento_advierte_y_no_fusiona(login, ids, db):
    from app.models import Contact, DuplicateReview

    c = login("recepcion.bcn")
    first = c.post("/api/v1/contacts", json=_payload(ids))
    assert first.status_code == 201, first.text

    chk = c.post("/api/v1/contacts/duplicate-check", json={
        "organization_id": str(ids["es"]), "identifiers": [{"kind": "DNI", "number": "12.345.678-z", "country": "ES"}]})
    assert chk.status_code == 200 and len(chk.json()["identifier_matches"]) == 1

    second = c.post("/api/v1/contacts", json=_payload(ids, family_names="Ficticio Dos"))
    assert second.status_code == 409
    err = second.json()["error"]
    assert err["code"] == "posible_duplicado" and err["details"]["candidates"][0]["id"] == first.json()["id"]

    no_reason = c.post("/api/v1/contacts", json=_payload(ids, family_names="Ficticio Dos", confirm_possible_duplicate=True))
    assert no_reason.status_code == 422

    forced = c.post("/api/v1/contacts", json=_payload(
        ids, family_names="Ficticio Dos", confirm_possible_duplicate=True,
        duplicate_justification="Persona distinta según comprobación presencial (prueba)"))
    assert forced.status_code == 201
    db.rollback()
    a = db.get(Contact, first.json()["id"])
    b = db.get(Contact, forced.json()["id"])
    assert a is not None and b is not None and a.id != b.id  # ambos existen: no hubo fusión
    assert a.possible_duplicate and b.possible_duplicate
    review = db.execute(select(DuplicateReview).where(DuplicateReview.contact_id == b.id)).scalar_one()
    assert review.status == "pendiente" and review.candidate_contact_id == a.id


def test_telefono_compartido_no_bloquea_ni_fusiona(login, ids):
    c = login("recepcion.bcn")
    phone = "+34 622 333 444"
    r1 = c.post("/api/v1/contacts", json={"organization_id": str(ids["es"]), "given_name": "Madre",
                                          "family_names": "Teléfono Compartido", "phones": [{"number": phone}]})
    r2 = c.post("/api/v1/contacts", json={"organization_id": str(ids["es"]), "given_name": "Hijo",
                                          "family_names": "Teléfono Compartido", "phones": [{"number": phone}]})
    assert r1.status_code == 201 and r2.status_code == 201 and r1.json()["id"] != r2.json()["id"]
    chk = c.post("/api/v1/contacts/duplicate-check", json={"organization_id": str(ids["es"]), "phones": [phone]})
    assert chk.json()["shared_phone_contacts"] == 2
    assert chk.json()["identifier_matches"] == []


def test_validaciones_de_documento_y_telefono(login, ids):
    c = login("recepcion.bcn")
    bad_letter = c.post("/api/v1/contacts", json={**_payload(ids), "identifiers": [
        {"kind": "DNI", "number": "12345678A", "country": "ES"}]})
    assert bad_letter.status_code == 422
    assert bad_letter.json()["error"]["details"][0]["field"] == "number"
    bad_nie = c.post("/api/v1/contacts", json={**_payload(ids), "identifiers": [
        {"kind": "NIE", "number": "X1234567A", "country": "ES"}]})
    assert bad_nie.status_code == 422
    bad_phone = c.post("/api/v1/contacts", json={"organization_id": str(ids["es"]), "given_name": "A",
                                                 "family_names": "B", "phones": [{"number": "+34 123"}]})
    assert bad_phone.status_code == 422
    missing = c.post("/api/v1/contacts", json={"organization_id": str(ids["es"]), "given_name": " ", "family_names": "B"})
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "validacion"


def test_nie_valido_se_normaliza(login, ids):
    from app.validation import validate_identifier

    assert validate_identifier("NIE", "x-1234567-l", "ES") == "X1234567L"
    assert validate_identifier("DNI", "12.345.678-z", "ES") == "12345678Z"
