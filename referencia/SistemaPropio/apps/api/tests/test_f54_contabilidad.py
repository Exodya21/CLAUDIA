"""F5.4 Contabilidad: proveedores (CIF e IBAN comprobados), facturas recibidas con lectura y duplicados, remesas con
doble autorización y fichero SEPA, pago conciliado con el banco, cuadro de mando por actividad y oficina, cierre
provisional del mes (preparar → revisar → aprobar, inmutable) y agente de Contabilidad. Datos FICTICIOS."""

from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

API = "/api/v1"


def _sup(s, ids, name):
    return next(x for x in s.get(f"{API}/accounting/suppliers", params={"organization_id": str(ids["es"])}).json()
                if x["name"] == name)


def _inv(s, ids, number_prefix, status="todas"):
    return next(x for x in s.get(f"{API}/accounting/invoices", params={"organization_id": str(ids["es"]), "status": status}).json()
                if x["number"].startswith(number_prefix))


def _pdf(number, cif="B33333337", base=10000, vat=2100, wh=0, issue=None):
    from app.accounting.invoices import invoice_pdf

    return invoice_pdf(supplier="Software Jurídico Demo SL", supplier_tax_id=cif, customer="Despacho Demo",
                       customer_tax_id="B12345674", number=number, issue=issue or date.today() - timedelta(days=2),
                       due=date.today() + timedelta(days=20), concept="Prueba (ficticia)", base_cents=base, vat_rate=21,
                       vat_cents=vat, withholding_cents=wh)


def _register(s, ids, sup_id, number, pdf, **kw):
    data = {"organization_id": str(ids["es"]), "supplier_id": sup_id, "number": number,
            "issue_date": (date.today() - timedelta(days=2)).isoformat(), "base_cents": 10000, "vat_cents": 2100,
            "total_cents": 12100, "category": "software", "activity": "compartida"} | kw
    return s.post(f"{API}/accounting/invoices", data={"data": json.dumps(data)},
                  files={"file": (f"{number}.pdf", pdf, "application/pdf")})


def test_proveedores_validan_cif_e_iban(login, ids, db):
    c = login("contabilidad.demo")
    body = {"organization_id": str(ids["es"]), "name": "Proveedor Prueba Demo", "tax_id": "B12345670",
            "category": "material"}
    assert c.post(f"{API}/accounting/suppliers", json=body).status_code == 422
    body["tax_id"] = "B76543214"
    body["iban"] = "ES9121000418450200051333"
    r = c.post(f"{API}/accounting/suppliers", json=body)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "iban"
    body["iban"] = "ES9121000418450200051332"
    r = c.post(f"{API}/accounting/suppliers", json=body)
    assert r.status_code == 201 and r.json()["iban_masked"] == "•••• 1332" and "iban" not in r.json()
    assert c.post(f"{API}/accounting/suppliers", json=body).status_code == 409
    rec = login("recepcion.bcn")
    assert rec.get(f"{API}/accounting/suppliers", params={"organization_id": str(ids["es"])}).status_code == 403
    assert denied_events(db, "treasury.read", ids["es"])


def test_agente_avisa_y_propone_cierre(login, ids, db):
    """Sobre la semilla: factura recibida sin validar, una que vence en 5 días, otra vencida y, desde el día 5,
    el cierre del mes anterior por preparar."""
    from app.agents.engine import run_scheduled

    db.rollback()
    run_scheduled(db, only="contabilidad", org_ids={ids["es"]})
    db.commit()
    c = login("contabilidad.demo")
    props = c.get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"]
    titles = [p["title"] for p in props]
    assert any(t.startswith("Validar factura · Telefonía Demo SL") for t in titles), titles
    assert any(t.startswith("Vence pronto · Software Jurídico Demo SL") for t in titles), titles
    assert any(t.startswith("Factura vencida sin pagar · Gestoría Prueba SL") for t in titles), titles
    assert all(p["approvable"] is False for p in props if p["kind"] in ("factura_vence", "factura_validar", "factura_falta"))
    if date.today().day >= 5:
        assert any(p["kind"] == "cierre_mes" for p in props)
    # Repetir no duplica; Recepción no ve nada de esto
    db.rollback()
    run_scheduled(db, only="contabilidad", org_ids={ids["es"]})
    db.commit()
    assert len(c.get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"]) == len(props)
    assert login("recepcion.bcn").get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"] == []


def test_factura_se_lee_y_se_registra_sin_duplicados(login, ids):
    c = login("contabilidad.demo")
    sup = _sup(c, ids, "Software Jurídico Demo SL")
    pdf = _pdf("SJ-TEST-0001")
    r = c.post(f"{API}/accounting/invoices/read", data={"organization_id": str(ids["es"])},
               files={"file": ("f.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    prop = r.json()["proposal"]
    assert prop["numero"] == "SJ-TEST-0001" and prop["cif"] == "B33333337" and prop["cuadra"] and prop["confianza"] == "alta"
    assert r.json()["supplier"]["id"] == sup["id"]
    # Total que no cuadra con base + IVA − retención
    assert _register(c, ids, sup["id"], "SJ-TEST-0001", pdf, total_cents=12000).status_code == 422
    x = _register(c, ids, sup["id"], "SJ-TEST-0001", pdf, validate_now=True)
    assert x.status_code == 201, x.text
    assert x.json()["status"] == "validada" and x.json()["due_date"]
    # Mismo número del mismo proveedor, mismo archivo, o mismo importe y fecha: no se duplica sin explicación
    assert _register(c, ids, sup["id"], "SJ-TEST-0001", _pdf("SJ-OTRA")).status_code == 409
    assert _register(c, ids, sup["id"], "SJ-TEST-0002", pdf).status_code == 409
    sim = _register(c, ids, sup["id"], "SJ-TEST-0002", _pdf("SJ-TEST-0002"))
    assert sim.status_code == 409 and sim.json()["error"]["code"] == "posible_duplicado"
    ok = _register(c, ids, sup["id"], "SJ-TEST-0002", _pdf("SJ-TEST-0002"), duplicate_reason="Segunda licencia del mismo día")
    assert ok.status_code == 201
    # Dirección valida pero no registra
    assert _register(login("direccion.demo"), ids, sup["id"], "SJ-TEST-0003", _pdf("SJ-TEST-0003")).status_code == 403


def test_validar_o_rechazar_factura_recibida(login, ids):
    c = login("contabilidad.demo")
    tel = _inv(c, ids, "T", "recibida")
    assert c.post(f"{API}/accounting/invoices/{tel['id']}/decide", json={"version": tel["version"], "approve": False}).status_code == 422
    r = c.post(f"{API}/accounting/invoices/{tel['id']}/decide",
               json={"version": tel["version"], "approve": True, "activity": "laboral"})
    assert r.status_code == 200 and r.json()["status"] == "validada" and r.json()["activity"] == "laboral"
    f = c.get(f"{API}/accounting/invoices/{tel['id']}/file")
    assert f.status_code == 200 and f.content.startswith(b"%PDF")


def test_remesa_con_doble_autorizacion_y_fichero_sepa(login, ids, db):
    c = login("contabilidad.demo")
    acc = next(a for a in c.get(f"{API}/accounting/treasury", params={"organization_id": str(ids["es"])}).json()["accounts"]
               if a["purpose"] == "A_laboral")
    soft = _inv(c, ids, "SJ-2", "validada")
    gest = _inv(c, ids, "G-", "validada")
    body = {"organization_id": str(ids["es"]), "account_id": acc["id"],
            "execution_date": (date.today() + timedelta(days=2)).isoformat(), "invoice_ids": [soft["id"], gest["id"]]}
    r = c.post(f"{API}/accounting/batches", json=body)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "propuesta" and b["signatures_needed"] == 2 and b["total_cents"] == soft["total_cents"] + gest["total_cents"]
    # La misma factura no puede ir en dos remesas
    assert c.post(f"{API}/accounting/batches", json=body).status_code == 409
    # Quien propone no firma (ni por la API ni en la base de datos)
    assert c.post(f"{API}/accounting/batches/{b['id']}/sign", json={"approve": True}).status_code == 403
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("INSERT INTO payment_batch_approval (id, organization_id, batch_id, approver_id, decision, at) "
                        "VALUES (:i, :o, :b, :u, 'autoriza', now())"),
                   {"i": uuid.uuid4(), "o": ids["es"], "b": uuid.UUID(b["id"]), "u": ids["users"]["contabilidad.demo"]})
    db.rollback()
    # El fichero no existe hasta tener las dos firmas
    assert c.get(f"{API}/accounting/batches/{b['id']}/sepa.xml").status_code == 409
    d = login("direccion.demo")
    firma1 = next(p for p in d.get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"]
                  if p["kind"] == "remesa_firma" and p["ref_id"] == b["id"])
    assert "Firma 1 de 2" in firma1["title"]
    r = d.post(f"{API}/proposals/{firma1['id']}/decide", json={"approve": True})
    assert r.status_code == 200 and r.json()["result"]["estado"] == "propuesta"
    # Dirección ya firmó: no vuelve a ver la firma 2 ni puede firmar otra vez
    assert not [p for p in d.get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"]
                if p["kind"] == "remesa_firma" and p["ref_id"] == b["id"]]
    assert d.post(f"{API}/accounting/batches/{b['id']}/sign", json={"approve": True}).status_code == 409
    s2 = login("socio.demo")
    firma2 = next(p for p in s2.get(f"{API}/proposals", params={"agent": "contabilidad"}).json()["items"]
                  if p["kind"] == "remesa_firma" and p["ref_id"] == b["id"])
    assert "Firma 2 de 2" in firma2["title"]
    assert s2.post(f"{API}/proposals/{firma2['id']}/decide", json={"approve": True}).status_code == 200
    got = next(x for x in c.get(f"{API}/accounting/batches", params={"organization_id": str(ids["es"])}).json() if x["id"] == b["id"])
    assert got["status"] == "autorizada" and all(i["status"] == "programada" for i in got["items"])
    # Fichero SEPA pain.001 con las dos transferencias y su suma de control
    f = c.get(f"{API}/accounting/batches/{b['id']}/sepa.xml")
    assert f.status_code == 200
    ns = {"p": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
    root = ET.fromstring(f.content)
    assert root.find(".//p:GrpHdr/p:NbOfTxs", ns).text == "2"
    assert root.find(".//p:GrpHdr/p:CtrlSum", ns).text == f"{got['total_cents'] / 100:.2f}"
    assert len(root.findall(".//p:CdtTrfTxInf", ns)) == 2
    r = c.post(f"{API}/accounting/batches/{b['id']}/sent")
    assert r.status_code == 200 and r.json()["status"] == "enviada"
    assert c.post(f"{API}/accounting/batches/{b['id']}/cancel", json={"reason": "Ya no se puede"}).status_code == 409


def test_remesa_rechazada_libera_facturas(login, ids):
    c = login("contabilidad.demo")
    tel = _inv(c, ids, "T", "validada")
    acc = next(a for a in c.get(f"{API}/accounting/treasury", params={"organization_id": str(ids["es"])}).json()["accounts"]
               if a["purpose"] == "A_laboral")
    b = c.post(f"{API}/accounting/batches", json={"organization_id": str(ids["es"]), "account_id": acc["id"],
                                                  "execution_date": date.today().isoformat(), "invoice_ids": [tel["id"]]}).json()
    d = login("direccion.demo")
    assert d.post(f"{API}/accounting/batches/{b['id']}/sign", json={"approve": False}).status_code == 422
    r = d.post(f"{API}/accounting/batches/{b['id']}/sign", json={"approve": False, "note": "Esperar a fin de mes"})
    assert r.status_code == 200 and r.json()["status"] == "rechazada"
    assert _inv(c, ids, "T", "validada")["batch"] is None


def test_cargo_de_la_remesa_en_el_banco_paga_las_facturas(login, ids, db):
    c = login("contabilidad.demo")
    from app.models_bank import BankAccount

    db.rollback()
    acc = db.execute(select(BankAccount).where(BankAccount.purpose == "A_laboral")).scalars().first()
    st = c.get(f"{API}/bank/accounts/{acc.id}/demo-statement")
    r = c.post(f"{API}/bank/accounts/{acc.id}/imports", files={"file": ("a.n43", st.content, "application/octet-stream")})
    assert r.status_code in (201, 409), r.text
    props = c.get(f"{API}/proposals", params={"agent": "conciliacion"}).json()["items"]
    rem = next(p for p in props if (p["payload"] or {}).get("regla") == "remesa")
    assert "REM-" in rem["detail"] and "doble firma" in rem["detail"]
    assert c.post(f"{API}/proposals/{rem['id']}/decide", json={"approve": True}).status_code == 200
    paid = [x for x in c.get(f"{API}/accounting/invoices", params={"organization_id": str(ids["es"]), "status": "pagada"}).json()]
    assert len(paid) >= 2 and all(x["paid_at"] for x in paid)
    mv = c.get(f"{API}/bank/movements/{rem['ref_id']}").json()
    assert mv["status"] == "conciliado" and mv["category"] == "proveedor"


def test_cuadro_de_mando_por_actividad_y_oficina(login, ids):
    month = f"{date.today():%Y-%m}"
    prev = f"{(date.today().replace(day=1) - timedelta(days=1)):%Y-%m}"
    d = login("direccion.demo").get(f"{API}/accounting/dashboard", params={"organization_id": str(ids["es"]), "month": prev})
    assert d.status_code == 200, d.text
    f = d.json()
    t = f["total"]
    assert t["resultado"] == t["ingresos_devengados"] - t["gastos_proveedores"] - t["gastos_empleados"] - t["coste_personal"]
    assert t["coste_personal"] > 0 and t["gastos_proveedores"] > 0
    assert set(f["by_activity"]) == {"laboral", "extranjeria", "compartida", "sin_asignar"}
    assert sum(v["gastos_proveedores"] for v in f["by_activity"].values()) == t["gastos_proveedores"]
    assert f["reliability"]["level"] in ("alta", "media", "baja", "sin_datos") and "previous" in f
    # Contabilidad no ve el coste de personal de oficinas con menos de 3 personas (protege salarios)
    c = login("contabilidad.demo").get(f"{API}/accounting/dashboard", params={"organization_id": str(ids["es"]), "month": prev}).json()
    assert c["personal_agrupado"] is True and c["total"]["coste_personal"] == t["coste_personal"]
    assert any(v["coste_personal"] is None for v in c["by_branch"].values())
    assert login("recepcion.bcn").get(f"{API}/accounting/dashboard",
                                      params={"organization_id": str(ids["es"]), "month": month}).status_code == 403


def test_cierre_del_mes_preparar_revisar_aprobar(login, ids, db):
    prev = f"{(date.today().replace(day=1) - timedelta(days=1)):%Y-%m}"
    c = login("contabilidad.demo")
    r = c.post(f"{API}/accounting/closes", json={"organization_id": str(ids["es"]), "month": prev})
    assert r.status_code == 201, r.text
    cl = r.json()
    assert cl["status"] == "borrador" and cl["revision"] >= 1 and len(cl["figures_sha256"]) == 64
    # Recalcular crea una revisión nueva y la anterior queda sustituida
    r2 = c.post(f"{API}/accounting/closes", json={"organization_id": str(ids["es"]), "month": prev}).json()
    assert r2["revision"] == cl["revision"] + 1
    pend = {k: v for k, v in r2["figures"]["pending"].items() if k != "accounts_sin_extracto" and v}
    if pend:
        assert c.post(f"{API}/accounting/closes/{r2['id']}/review", json={}).status_code == 422
    r = c.post(f"{API}/accounting/closes/{r2['id']}/review", json={"note": "Pendientes revisados uno a uno (ficticio)"})
    assert r.status_code == 200 and r.json()["status"] == "revisado"
    assert c.post(f"{API}/accounting/closes/{r2['id']}/approve", json={}).status_code == 403
    a = login("direccion.demo").post(f"{API}/accounting/closes/{r2['id']}/approve", json={"note": "Conforme"})
    assert a.status_code == 200 and a.json()["status"] == "aprobado"
    # Aprobado = congelado (API y base de datos)
    assert c.post(f"{API}/accounting/closes", json={"organization_id": str(ids["es"]), "month": prev}).status_code == 409
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE month_close SET note = 'x' WHERE id = :i"), {"i": uuid.UUID(r2["id"])})
    db.rollback()
    csv = c.get(f"{API}/accounting/closes/{r2['id']}/export.csv")
    assert csv.status_code == 200 and "Resultado provisional" in csv.text
    hist = c.get(f"{API}/accounting/closes", params={"organization_id": str(ids["es"])}).json()
    assert [x["status"] for x in hist if x["month"] == prev][:2] == ["aprobado", "sustituido"]


def test_nada_se_borra(db):
    db.rollback()
    for t in ("supplier", "supplier_invoice", "payment_batch", "payment_batch_item", "payment_batch_approval", "month_close"):
        with pytest.raises(DBAPIError):
            db.execute(text(f"DELETE FROM {t}"))
        db.rollback()
