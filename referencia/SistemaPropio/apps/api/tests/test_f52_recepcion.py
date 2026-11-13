"""F5.2 Recepción: cobros (también consulta sin expediente), duplicados, justificante NO fiscal numerado, caja del
día, cierre validado por otra persona, separación por sede e informe diario. Datos FICTICIOS."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

API = "/api/v1"


def _branch(db, ids, name):
    from app.models import Branch

    db.rollback()
    return db.execute(select(Branch).where(Branch.organization_id == ids["es"], Branch.name == name)).scalar_one().id


def _contact(db, ids, given="Recepción", family="Prueba Ficticia"):
    from app.models import Branch, Contact
    from app.validation import fold

    db.rollback()
    bcn = db.execute(select(Branch).where(Branch.organization_id == ids["es"], Branch.name == "Barcelona")).scalar_one()
    c = Contact(organization_id=ids["es"], primary_branch_id=bcn.id, given_name=given, family_names=family,
                search_name=fold(f"{given} {family}"), nationality="XX", is_synthetic=True,
                created_by=ids["users"]["recepcion.bcn"])
    db.add(c)
    db.commit()
    return c.id


def _charge(s, branch, contact, **kw):
    body = {"branch_id": str(branch), "contact_id": str(contact), "kind": "consulta", "amount_cents": 6000,
            "method": "efectivo"} | kw
    return s.post(f"{API}/reception/payments", json=body)


def test_consulta_sin_expediente_con_justificante_y_caja(login, db, ids):
    from app.models_economy import CashMovement, Payment

    s = login("recepcion.bcn")
    bcn = _branch(db, ids, "Barcelona")
    contact = _contact(db, ids, "Consulta", "Sin Expediente Demo")
    r = _charge(s, bcn, contact)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["kind"] == "consulta" and j["case_code"] is None and j["receipt"]["number"].startswith("REC-BCN-")
    pdf = s.get(f"{API}{j['receipt']['url']}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert b"NO ES UNA FACTURA" in pdf.content
    # Volver a descargarlo devuelve exactamente el mismo documento
    assert s.get(f"{API}{j['receipt']['url']}").content == pdf.content
    db.rollback()
    x = db.get(Payment, uuid.UUID(j["id"]))
    assert x.case_id is None and x.status == "registrado"
    assert db.execute(select(CashMovement).where(CashMovement.payment_id == x.id)).scalar_one().amount_cents == 6000
    # Un servicio o una provisión sin expediente no se aceptan
    r = _charge(s, bcn, contact, kind="provision", amount_cents=10000)
    assert r.status_code == 422 and "expediente" in r.json()["error"]["message"]


def test_numeracion_correlativa_y_justificante_inmutable(login, db, ids):
    s = login("recepcion.bcn")
    bcn = _branch(db, ids, "Barcelona")
    a = _charge(s, bcn, _contact(db, ids, "Num", "Uno Demo"), amount_cents=1111).json()["receipt"]["number"]
    b = _charge(s, bcn, _contact(db, ids, "Num", "Dos Demo"), amount_cents=2222).json()["receipt"]["number"]
    assert int(b.rsplit("-", 1)[1]) == int(a.rsplit("-", 1)[1]) + 1
    db.rollback()
    for sql in ("DELETE FROM payment_receipt", "UPDATE payment_receipt SET number = 'X'"):
        with pytest.raises(DBAPIError):
            db.execute(text(sql))
        db.rollback()


def test_cobro_repetido_pide_motivo_y_contabilidad_decide(login, db, ids):
    from app.models_economy import Payment

    s = login("recepcion.bcn")
    bcn = _branch(db, ids, "Barcelona")
    contact = _contact(db, ids, "Duplicado", "Posible Demo")
    first = _charge(s, bcn, contact, amount_cents=5000, method="tarjeta").json()
    r = _charge(s, bcn, contact, amount_cents=5000, method="tarjeta")
    assert r.status_code == 409 and r.json()["error"]["code"] == "posible_duplicado"
    assert r.json()["error"]["details"][0]["id"] == first["id"]
    r = _charge(s, bcn, contact, amount_cents=5000, method="tarjeta", duplicate_reason="Paga también la consulta de su hermana")
    assert r.status_code == 201, r.text
    second = r.json()
    # Contabilidad lo ve en sus pendientes; «es repetido» lo anula con motivo
    c = login("contabilidad.demo")
    props = c.get(f"{API}/proposals", params={"agent": "recepcion"}).json()["items"]
    dup = next(p for p in props if p["kind"] == "cobro_duplicado" and p["ref_id"] == second["id"])
    assert "Paga también la consulta" in dup["detail"]
    assert c.post(f"{API}/proposals/{dup['id']}/decide", json={"approve": False}).status_code == 422
    r = c.post(f"{API}/proposals/{dup['id']}/decide", json={"approve": False, "note": "Cobrado dos veces por error"})
    assert r.status_code == 200, r.text
    db.rollback()
    assert db.get(Payment, uuid.UUID(second["id"])).status == "anulado"
    assert db.get(Payment, uuid.UUID(first["id"])).status == "registrado"
    # Recepción no puede decidirlo (no tiene payment.confirm)
    assert dup["id"] not in {p["id"] for p in s.get(f"{API}/proposals").json()["items"]}


def test_sede_ajena_y_permisos(login, db, ids):
    s = login("recepcion.bcn")
    mad = _branch(db, ids, "Madrid")
    r = _charge(s, mad, _contact(db, ids, "Otra", "Sede Demo"))
    assert r.status_code == 403
    assert denied_events(db, "reception.charge", mad)
    assert s.get(f"{API}/reception/day", params={"branch_id": str(mad)}).status_code == 403
    # Recepción de Madrid no ve la caja de Barcelona; Contabilidad (cash.read.all) sí
    bcn = _branch(db, ids, "Barcelona")
    assert login("recepcion.mad").get(f"{API}/reception/day", params={"branch_id": str(bcn)}).status_code == 403
    assert login("contabilidad.demo").get(f"{API}/reception/day", params={"branch_id": str(bcn)}).status_code == 200
    # Saldo pendiente: Recepción ve importes del expediente, no su contenido
    r = s.get(f"{API}/reception/contacts/{ids['lucia']}/cases")
    assert r.status_code == 200 and r.json()["show_balance"] is True
    assert all("pendiente_cents" in c and "title" not in c for c in r.json()["cases"])
    # Un asesor no tiene «reception.balance»
    r = login("asesor.extranjeria.mad").get(f"{API}/reception/contacts/{ids['lucia']}/cases")
    assert r.status_code in (200, 404) and (r.status_code == 404 or r.json()["show_balance"] is False)


def test_cobro_a_expediente_y_transferencia_con_referencia(login, db, ids):
    s = login("recepcion.bcn")
    bcn = _branch(db, ids, "Barcelona")
    r = _charge(s, bcn, ids["lucia"], case_id=str(ids["lucia_lab"]), kind="provision", amount_cents=15000,
                method="transferencia")
    assert r.status_code == 422  # sin referencia
    r = _charge(s, bcn, ids["lucia"], case_id=str(ids["lucia_lab"]), kind="provision", amount_cents=15000,
                method="transferencia", reference="TRF-REC-0001")
    assert r.status_code == 201 and r.json()["case_code"].startswith("LAB-")
    # Misma referencia otra vez: posible duplicado aunque sea otro importe
    r = _charge(s, bcn, ids["lucia"], case_id=str(ids["lucia_lab"]), kind="provision", amount_cents=9000,
                method="transferencia", reference="trf-rec-0001")
    assert r.status_code == 409
    # Expediente de otra persona: rechazado
    r = _charge(s, bcn, _contact(db, ids, "Ajeno", "Demo"), case_id=str(ids["lucia_lab"]), kind="servicio")
    assert r.status_code == 422


def _reopen_today(login, branch_name):
    """Si otra prueba ya cerró hoy esa caja, un responsable rechaza ese cierre para poder volver a contar."""
    d = login("direccion.demo")
    for x in d.get(f"{API}/reception/closings").json():
        if x["branch"] == branch_name and x["can_decide"]:
            assert d.post(f"{API}/reception/closings/{x['id']}/decide",
                          json={"approve": False, "note": "Recontar (prueba)"}).status_code == 200


def test_cierre_del_dia_lo_valida_otra_persona(login, db, ids):
    s = login("recepcion.bcn")
    bcn = _branch(db, ids, "Barcelona")
    _reopen_today(login, "Barcelona")
    day = s.get(f"{API}/reception/day", params={"branch_id": str(bcn)}).json()
    expected = day["cash"]["balance_cents"]
    assert day["can_close"] is True
    r = s.post(f"{API}/reception/cash/{bcn}/close", json={"counted_cents": expected - 500})
    assert r.status_code == 422  # diferencia sin motivo
    r = s.post(f"{API}/reception/cash/{bcn}/close", json={"counted_cents": expected - 500, "notes": "Faltan 5 € (cambio)"})
    assert r.status_code == 201, r.text
    closing = r.json()
    assert closing["status"] == "pendiente_validacion" and closing["difference_cents"] == -500
    # Un segundo cierre el mismo día: no
    assert s.post(f"{API}/reception/cash/{bcn}/close", json={"counted_cents": 0}).status_code == 409
    # Recepción no valida; Contabilidad sí, en sus pendientes, y con diferencia exige nota
    assert s.post(f"{API}/reception/closings/{closing['id']}/decide", json={"approve": True}).status_code == 403
    c = login("contabilidad.demo")
    prop = next(p for p in c.get(f"{API}/proposals", params={"agent": "recepcion"}).json()["items"]
                if p["kind"] == "cierre_caja" and p["ref_id"] == closing["id"])
    assert prop["priority"] == "alta" and "diferencia" in prop["detail"]
    assert c.post(f"{API}/proposals/{prop['id']}/decide", json={"approve": True}).status_code == 422
    r = c.post(f"{API}/proposals/{prop['id']}/decide", json={"approve": True, "note": "Revisado con el arqueo"})
    assert r.status_code == 200, r.text
    v = c.get(f"{API}/reception/closings", params={"status": "validado"}).json()
    assert any(x["id"] == closing["id"] and x["validated_by"] for x in v)


def test_quien_cuenta_no_valida_su_cierre(login, db, ids):
    c = login("contabilidad.demo")
    vlc = _branch(db, ids, "Valencia")
    _reopen_today(login, "Valencia")
    day = c.get(f"{API}/reception/day", params={"branch_id": str(vlc)}).json()
    r = c.post(f"{API}/reception/cash/{vlc}/close", json={"counted_cents": day["cash"]["balance_cents"]})
    assert r.status_code == 201, r.text
    r = c.post(f"{API}/reception/closings/{r.json()['id']}/decide", json={"approve": True})
    assert r.status_code == 403 and "propio" in r.json()["error"]["message"]
    d = login("direccion.demo")
    pend = d.get(f"{API}/reception/closings").json()
    x = next(x for x in pend if x["branch"] == "Valencia")
    assert d.post(f"{API}/reception/closings/{x['id']}/decide", json={"approve": False}).status_code == 422
    r = d.post(f"{API}/reception/closings/{x['id']}/decide", json={"approve": False, "note": "Volver a contar"})
    assert r.status_code == 200 and r.json()["status"] == "rechazado"
    # Rechazado: se puede volver a cerrar
    assert c.get(f"{API}/reception/day", params={"branch_id": str(vlc)}).json()["can_close"] is True


def test_informe_diario_por_sede(login, db, ids):
    s = login("recepcion.bcn")
    today = date.today().isoformat()
    r = s.get(f"{API}/reception/report", params={"from": today, "to": today})
    assert r.status_code == 200
    names = [b["branch"] for b in r.json()["branches"]]
    assert names == ["Barcelona"]
    day = r.json()["branches"][0]["days"][0]
    assert day["cobros"] >= 1 and "consulta" in day["por_tipo"]
    assert "no disponible" in r.json()["no_disponible"].lower()
    d = login("direccion.demo").get(f"{API}/reception/report", params={"from": today, "to": today})
    assert {"Barcelona", "Madrid", "Valencia"} <= {b["branch"] for b in d.json()["branches"]}
    assert login("asesor.laboral.bcn").get(f"{API}/reception/report", params={"from": today, "to": today}).status_code == 403
