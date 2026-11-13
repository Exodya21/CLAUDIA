"""F5.0 — Control económico no fiscal: cobros, devoluciones (A-09), caja por sede y resumen. Datos ficticios."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, text

from .conftest import denied_events


def _branch(c, case_id, name="Barcelona"):
    return next(b["id"] for b in c.get(f"/api/v1/economy/cases/{case_id}").json()["branches"] if b["name"] == name)


def test_economia_visible_segun_rol(login, ids):
    case = ids["lucia_lab"]
    assert login("asesor.laboral.bcn").get(f"/api/v1/economy/cases/{case}").status_code == 200
    assert login("contabilidad.demo").get(f"/api/v1/economy/cases/{case}").status_code == 200
    # Recepción ve metadatos del expediente pero no su economía; Marketing nada; otra entidad → 404
    assert login("recepcion.bcn").get(f"/api/v1/economy/cases/{case}").status_code == 403
    assert login("marketing.demo").get(f"/api/v1/economy/cases/{case}").status_code == 403
    assert login("asesor.laboral.autonomo").get(f"/api/v1/economy/cases/{case}").status_code == 404
    # Asesor laboral no ve la economía de un expediente de Extranjería
    assert login("asesor.laboral.bcn").get(f"/api/v1/economy/cases/{ids['lucia_ext']}").status_code == 403


def test_importe_pactado_y_saldo_pendiente(login, ids):
    c = login("asesor.laboral.bcn")
    case = ids["lucia_lab"]
    before = c.get(f"/api/v1/economy/cases/{case}").json()["totals"]
    r = c.post(f"/api/v1/economy/cases/{case}/charges",
               json={"kind": "honorarios", "concept": "Hoja de encargo (ficticia)", "amount_cents": 50000})
    assert r.status_code == 201
    after = c.get(f"/api/v1/economy/cases/{case}").json()["totals"]
    assert after["cargado"] == before["cargado"] + 50000 and after["pendiente"] == before["pendiente"] + 50000
    # Importes absurdos o negativos: rechazados
    assert c.post(f"/api/v1/economy/cases/{case}/charges",
                  json={"kind": "honorarios", "concept": "x" * 5, "amount_cents": -1}).status_code == 422
    # El asesor no anula importes; Contabilidad sí, con motivo
    assert c.post(f"/api/v1/economy/charges/{r.json()['id']}/cancel", json={"reason": "error de importe"}).status_code == 403
    conta = login("contabilidad.demo")
    assert conta.post(f"/api/v1/economy/charges/{r.json()['id']}/cancel", json={"reason": "error de importe"}).json()["status"] == "anulado"


def test_recepcion_cobra_en_efectivo_y_entra_en_caja(login, ids):
    rec = login("recepcion.bcn")
    case = ids["lucia_lab"]
    found = rec.get("/api/v1/economy/lookup", params={"code": login("asesor.laboral.bcn").get(
        f"/api/v1/economy/cases/{case}").json()["code"]}).json()
    match = next(m for m in found if m["case_id"] == str(case))
    assert match["can_pay"] and not match["can_read"]
    bcn = next(b["id"] for b in match["branches"] if b["name"] == "Barcelona")
    caja_antes = next(x for x in rec.get("/api/v1/economy/cash").json() if x["branch"] == "Barcelona")["balance_cents"]
    r = rec.post(f"/api/v1/economy/cases/{case}/payments", json={"amount_cents": 4000, "method": "efectivo", "branch_id": bcn})
    assert r.status_code == 201 and r.json()["status"] == "registrado"
    caja = next(x for x in rec.get("/api/v1/economy/cash").json() if x["branch"] == "Barcelona")
    assert caja["balance_cents"] == caja_antes + 4000 and caja["can_operate"]
    # Transferencia sin referencia: rechazada; efectivo sin sede: rechazado
    assert rec.post(f"/api/v1/economy/cases/{case}/payments", json={"amount_cents": 100, "method": "transferencia"}).status_code == 422
    assert rec.post(f"/api/v1/economy/cases/{case}/payments", json={"amount_cents": 100, "method": "efectivo"}).status_code == 422


def test_solo_contabilidad_confirma_y_anula_cobros(login, ids, db):
    case = ids["lucia_lab"]
    a = login("asesor.laboral.bcn")
    pid = a.post(f"/api/v1/economy/cases/{case}/payments",
                 json={"amount_cents": 2500, "method": "transferencia", "reference": "TRF-TEST-1"}).json()["id"]
    assert a.post(f"/api/v1/economy/payments/{pid}/confirm", json={}).status_code == 403
    assert denied_events(db, "payment.confirm", pid)
    conta = login("contabilidad.demo")
    assert any(x["id"] == pid for x in conta.get("/api/v1/economy/payments").json())
    r = conta.post(f"/api/v1/economy/payments/{pid}/confirm", json={"invoice_ref": "F-2026-000123"})
    assert r.json()["status"] == "confirmado" and r.json()["invoice_ref"] == "F-2026-000123"


def test_devolucion_atc_registra_contabilidad_decide(login, ids, db):
    case = ids["lucia_lab"]
    atc = login("atc.demo")
    rid = atc.post(f"/api/v1/economy/cases/{case}/refunds",
                   json={"amount_cents": 1000, "reason": "Cliente reclama cobro duplicado (ficticio)"}).json()["id"]
    # ATC investiga y escala; NO aprueba
    assert atc.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "en_revision"}).status_code == 200
    r = atc.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "aprobada", "note": "me parece bien"})
    assert r.status_code == 403 and "Contabilidad" in r.json()["error"]["message"]
    assert denied_events(db, "refund.aprobada", rid)
    assert atc.post(f"/api/v1/economy/refunds/{rid}/transition",
                    json={"to": "escalada_legal", "note": "Depende de lo pactado en la hoja de encargo"}).status_code == 200
    # El letrado informa (no decide) y la devuelve a revisión
    lider = login("lider.laboral")
    assert lider.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "en_revision", "note": "corto"}).status_code == 422
    r = lider.post(f"/api/v1/economy/refunds/{rid}/transition",
                   json={"to": "en_revision", "note": "La hoja de encargo no contempla ese segundo cobro (ficticio)."})
    assert r.json()["legal_opinion"].startswith("La hoja") and "aprobada" not in r.json()["allowed"]
    conta = login("contabilidad.demo")
    r = conta.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "aprobada", "note": "Cobro duplicado verificado"})
    assert r.status_code == 200 and r.json()["status"] == "aprobada"
    r = conta.post(f"/api/v1/economy/refunds/{rid}/transition",
                   json={"to": "pagada", "pay_method": "transferencia", "pay_reference": "TRF-DEV-1"})
    assert r.json()["status"] == "pagada"
    assert [e["to"] for e in r.json()["events"]] == ["registrada", "en_revision", "escalada_legal", "en_revision", "aprobada", "pagada"]
    # Historial inmutable
    from sqlalchemy.exc import DBAPIError

    db.rollback()
    try:
        db.execute(text("DELETE FROM refund_event WHERE refund_id = :r"), {"r": rid})
        db.flush()
        raise AssertionError("se pudo borrar el historial")
    except DBAPIError:
        db.rollback()


def test_no_se_devuelve_mas_de_lo_cobrado(login, ids):
    case = ids["lucia_lab"]
    conta = login("contabilidad.demo")
    t = conta.get(f"/api/v1/economy/cases/{case}").json()["totals"]
    rid = login("atc.demo").post(f"/api/v1/economy/cases/{case}/refunds",
                                 json={"amount_cents": t["devolvible"] + 100, "reason": "Pide más de lo pagado (ficticio)"}).json()["id"]
    r = conta.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "aprobada", "note": "probar límite"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "excede_cobrado"
    assert conta.post(f"/api/v1/economy/refunds/{rid}/transition", json={"to": "rechazada", "note": "Supera lo cobrado"}).status_code == 200


def test_quien_solicita_no_decide(login, ids):
    conta = login("contabilidad.demo")
    case = ids["lucia_lab"]
    # Contabilidad no tiene refund.request: no puede autoaprobarse por la vía de crear la solicitud
    assert conta.post(f"/api/v1/economy/cases/{case}/refunds",
                      json={"amount_cents": 100, "reason": "Autoservicio no permitido"}).status_code == 403


def test_caja_arqueo_con_diferencia_exige_motivo(login, ids):
    rec = login("recepcion.bcn")
    caja = next(x for x in rec.get("/api/v1/economy/cash").json() if x["branch"] == "Barcelona")
    bid = caja["branch_id"]
    # Recepción de Barcelona no opera otras sedes
    otras = [x for x in login("contabilidad.demo").get("/api/v1/economy/cash").json() if x["branch"] != "Barcelona"]
    assert rec.post(f"/api/v1/economy/cash/{otras[0]['branch_id']}/movements",
                    json={"kind": "aportacion", "amount_cents": 100, "concept": "intento"}).status_code == 403
    r = rec.post(f"/api/v1/economy/cash/{bid}/movements", json={"kind": "gasto", "amount_cents": 1, "concept": "Sellos"})
    assert r.status_code == 201
    saldo = r.json()["balance_cents"]
    assert rec.post(f"/api/v1/economy/cash/{bid}/movements",
                    json={"kind": "gasto", "amount_cents": saldo + 1, "concept": "más de lo que hay"}).status_code == 422
    assert rec.post(f"/api/v1/economy/cash/{bid}/closings", json={"counted_cents": saldo - 50}).status_code == 422
    r = rec.post(f"/api/v1/economy/cash/{bid}/closings", json={"counted_cents": saldo - 50, "notes": "Falta una moneda de 50 céntimos"})
    assert r.json()["difference_cents"] == -50 and r.json()["balance_cents"] == saldo - 50


def test_resumen_solo_direccion_y_contabilidad(login):
    q = {"from": date.today().replace(day=1).isoformat(), "to": date.today().isoformat()}
    assert login("asesor.laboral.bcn").get("/api/v1/economy/summary", params=q).status_code == 403
    r = login("contabilidad.demo").get("/api/v1/economy/summary", params=q)
    assert r.status_code == 200 and r.json()[0]["currency"] == "EUR" and "por_sede" in r.json()[0]


def test_reglas_en_base_de_datos(db, ids):
    """Aunque alguien salte la API: sin borrados, importes positivos y sin mezclar entidades."""
    import pytest
    from sqlalchemy.exc import DBAPIError

    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM payment"))
        db.flush()
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE cash_movement SET amount_cents = 1"))
        db.flush()
    db.rollback()
    with pytest.raises(DBAPIError):  # cargo de la entidad A sobre un expediente de la entidad B
        db.execute(text("INSERT INTO charge (id, organization_id, case_id, contact_id, kind, concept, amount_cents, currency,"
                        " status, created_by) SELECT gen_random_uuid(), :o, c.id, c.contact_id, 'otro', 'x', 1, 'EUR',"
                        " 'vigente', c.created_by FROM case_file c WHERE c.id = :c"), {"o": ids["es2"], "c": ids["lucia_lab"]})
        db.flush()
    db.rollback()
    from app.models_economy import Charge

    assert db.execute(select(Charge)).first() is not None
