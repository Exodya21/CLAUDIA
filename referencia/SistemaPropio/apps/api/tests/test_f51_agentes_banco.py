"""F5.1: motor de agentes, bandeja única, conciliación bancaria y agente de mensajes al cliente.

Todo con datos FICTICIOS (cuentas 1111/2222/3333, extractos generados). Comprueba lectura de los tres formatos,
cuadre de saldos, que reimportar no duplica, reglas deterministas con su explicación, que nada se concilia sin una
persona, permisos reales (404/403 auditados), avisos solo con fecha y lugar de la agenda, sin duplicados, cancelación
al cerrar y modo automático solo donde se permite (T-47)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

API = "/api/v1"


# ------------------------------------------------------------------ utilidades
def _acc(db, purpose: str):
    from app.models_bank import BankAccount

    db.rollback()
    return db.execute(select(BankAccount).where(BankAccount.purpose == purpose)).scalars().first()


def _import_demo(s, acc_id) -> dict:
    r = s.get(f"{API}/bank/accounts/{acc_id}/demo-statement")
    assert r.status_code == 200, r.text
    name = r.headers["content-disposition"].split('filename="')[1].rstrip('"')
    r2 = s.post(f"{API}/bank/accounts/{acc_id}/imports", files={"file": (name, r.content, "application/octet-stream")})
    return {"status": r2.status_code, "json": r2.json(), "data": r.content, "name": name}


def _proposals(s, **params) -> list[dict]:
    r = s.get(f"{API}/proposals", params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _movements(s, acc_id, tab="importados") -> list[dict]:
    r = s.get(f"{API}/bank/accounts/{acc_id}/movements", params={"tab": tab})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _run(db, code: str, org_id):
    from app.agents.engine import run_scheduled

    db.rollback()
    runs = run_scheduled(db, only=code, org_ids={org_id})
    db.commit()
    return runs


@pytest.fixture(scope="module")
def bank_flow(app, database):
    """Importa el extracto ficticio de la cuenta A una sola vez para el módulo."""
    from fastapi.testclient import TestClient

    from .conftest import CSRF

    c = TestClient(app)
    assert c.post(f"{API}/auth/demo/login", json={"username": "contabilidad.demo"}, headers=CSRF).status_code == 204
    c.headers.update(CSRF)
    from app.db import get_sessionmaker
    from app.models_bank import BankAccount

    s = get_sessionmaker()()
    acc = s.execute(select(BankAccount).where(BankAccount.purpose == "A_laboral")).scalars().first()
    s.close()
    res = _import_demo(c, acc.id)
    assert res["status"] == 201, res["json"]
    return {"client": c, "acc": acc.id, "import": res}


# ------------------------------------------------------------------ lectura de extractos
def test_n43_lectura_cuadre_e_ids_estables():
    from app.bank import parsers

    moves = [(date(2026, 11, 2), 41250, "04", "", "TRANSF REF LAB-2026-0001 DEMO"),
             (date(2026, 11, 3), -500, "17", "", "COMISION DEMO"),
             (date(2026, 11, 3), -500, "17", "", "COMISION DEMO")]
    data = parsers.build_n43(bank="9999", branch="0001", account10="0000001111", start=date(2026, 11, 1),
                             end=date(2026, 11, 5), opening_cents=100000, moves=moves)
    st = parsers.parse(data, "x.n43")
    assert st.file_format == "n43" and st.account_hint == "1111" and not st.errors
    assert [ln.amount_cents for ln in st.lines] == [41250, -500, -500]
    assert st.opening_cents + sum(ln.amount_cents for ln in st.lines) == st.closing_cents == 140250
    ids = [ln.ext_id for ln in st.lines]
    assert len(set(ids)) == 3 and ids == [ln.ext_id for ln in parsers.parse(data, "y.n43").lines]
    assert "Transferencia" in st.lines[0].description and "LAB-2026-0001" in st.lines[0].description
    # Una línea ilegible se informa y no se importa (nunca se adivina un importe)
    lines = data.split(b"\r\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith(b"22"))
    lines[i] = lines[i][:28] + b"0000000004X250" + lines[i][42:]
    bad = b"\r\n".join(lines)
    st2 = parsers.parse(bad, "z.n43")
    assert len(st2.lines) == 2 and st2.errors and "importe" in st2.errors[0]["error"]


def test_camt053_y_csv():
    from app.bank import parsers

    xml = b"""<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt>
    <Stmt><Acct><Id><IBAN>ES0000000000000000002222</IBAN></Id><Ccy>EUR</Ccy></Acct>
    <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">100.00</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
    <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">125.50</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
    <Ntry><Amt Ccy="EUR">30.50</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-11-02</Dt></BookgDt>
      <AcctSvcrRef>BANK-1</AcctSvcrRef><NtryDtls><TxDtls><Refs><EndToEndId>EXT-2026-0001</EndToEndId></Refs>
      <RltdPties><Dbtr><Nm>CLIENTE DEMO</Nm></Dbtr></RltdPties><RmtInf><Ustrd>HONORARIOS</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
    <Ntry><Amt Ccy="EUR">5.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-11-03</Dt></BookgDt>
      <AddtlNtryInf>COMISION</AddtlNtryInf></Ntry>
    </Stmt></BkToCstmrStmt></Document>"""
    st = parsers.parse(xml, "e.xml")
    assert st.file_format == "camt053" and st.account_hint == "2222"
    assert [ln.amount_cents for ln in st.lines] == [3050, -500]
    assert st.lines[0].ext_id == "b:BANK-1" and st.lines[0].counterparty == "CLIENTE DEMO"
    assert st.opening_cents + 2550 == st.closing_cents
    with pytest.raises(parsers.ParseError):
        parsers.parse(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><Document/>', "m.xml")
    # CSV español en orden inverso (lo habitual en la banca en línea) con saldos
    csv = (b"Fecha;Concepto;Importe;Saldo\n03/11/2026;COMISION;-5,00;1.025,50\n"
           b"02/11/2026;BIZUM DEMO;30,50;1.030,50\n")
    st = parsers.parse(csv, "m.csv")
    assert st.opening_cents == 100000 and st.closing_cents == 102550 and not st.errors
    with pytest.raises(parsers.ParseError):
        parsers.parse(b"col1;col2\n1;2\n", "m.csv")


# ------------------------------------------------------------------ permisos
def test_permisos_banco(login, db, ids):
    from app.models_bank import BankAccount

    acc = _acc(db, "A_laboral")
    r = login("recepcion.bcn").get(f"{API}/bank/accounts")
    assert r.status_code == 403
    r = login("asesor.laboral.bcn").get(f"{API}/bank/accounts/{acc.id}/movements")
    assert r.status_code == 403
    assert denied_events(db, "bank.bank.read", acc.id)
    # Dirección ve pero NO concilia (separación de funciones, como en «Confirmar cobro»)
    d = login("direccion.demo")
    assert d.get(f"{API}/bank/accounts").status_code == 200
    assert d.post(f"{API}/bank/reconcile/run", params={"organization_id": str(ids["es"])}).status_code == 403
    # Cuenta de otra entidad → 404
    other = BankAccount(organization_id=ids["es2"], name="Cuenta otra entidad", bank_name="Banco Ficticio",
                        iban_last4="9090", purpose="otra", activity="laboral", created_by=ids["users"]["direccion.demo"])
    db.add(other)
    db.commit()
    assert login("contabilidad.demo").get(f"{API}/bank/accounts/{other.id}/movements").status_code == 404


# ------------------------------------------------------------------ importación y conciliación
def test_importacion_cuadra_y_no_duplica(bank_flow):
    c, acc, imp = bank_flow["client"], bank_flow["acc"], bank_flow["import"]
    j = imp["json"]
    assert j["balance_ok"] is True and j["new_lines"] == j["total_lines"] >= 9 and j["errors"] == []
    # El mismo archivo otra vez: rechazado sin tocar nada
    r = c.post(f"{API}/bank/accounts/{acc}/imports", files={"file": (imp["name"], imp["data"], "application/octet-stream")})
    assert r.status_code == 409 and "ya se importó" in r.json()["error"]["message"]
    # Un extracto solapado (mismas líneas + una nueva) solo añade la nueva
    from app.bank import parsers

    st = parsers.parse(imp["data"], imp["name"])
    extra = parsers.build_n43(bank="9999", branch="0001", account10="0000001111", start=st.period_to,
                              end=st.period_to + timedelta(days=1), opening_cents=st.closing_cents,
                              moves=[(st.period_to + timedelta(days=1), 1234, "02", "", "INGRESO EFECTIVO DEMO")])
    r = c.post(f"{API}/bank/accounts/{acc}/imports", files={"file": ("extra.n43", extra, "application/octet-stream")})
    assert r.status_code == 201 and r.json()["new_lines"] == 1 and r.json()["balance_ok"] is True
    r = c.post(f"{API}/bank/accounts/{acc}/imports", files={"file": ("extra2.n43", extra + b"\r\n", "application/octet-stream")})
    assert r.status_code == 201 and r.json()["new_lines"] == 0 and r.json()["duplicate_lines"] == 1
    # Extracto de otra cuenta → rechazado
    other = parsers.build_n43(bank="9999", branch="0001", account10="0000004444", start=date(2026, 1, 1),
                              end=date(2026, 1, 2), opening_cents=0, moves=[(date(2026, 1, 1), 100, "02", "", "X")])
    r = c.post(f"{API}/bank/accounts/{acc}/imports", files={"file": ("o.n43", other, "application/octet-stream")})
    assert r.status_code == 422 and "4444" in r.json()["error"]["message"]


def test_saldo_que_no_cuadra_se_marca(login, db):
    from app.bank import parsers

    acc = _acc(db, "B_extranjeria")
    data = parsers.build_n43(bank="9999", branch="0001", account10="0000002222", start=date(2025, 1, 1),
                             end=date(2025, 1, 3), opening_cents=1000, moves=[(date(2025, 1, 2), 500, "02", "", "INGRESO DEMO")])
    # Se altera el saldo final del registro 33 (15,00 → 16,00): el sistema debe avisar, no corregir
    lines = data.split(b"\r\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith(b"33"))
    lines[i] = lines[i][:59] + b"00000000001600" + lines[i][73:]
    bad = b"\r\n".join(lines)
    r = login("contabilidad.demo").post(f"{API}/bank/accounts/{acc.id}/imports",
                                        files={"file": ("mal.n43", bad, "application/octet-stream")})
    assert r.status_code == 201, r.text
    assert r.json()["balance_ok"] is False
    assert any("saldo final" in e["error"] for e in r.json()["errors"])
    errs = login("contabilidad.demo").get(f"{API}/bank/accounts/{acc.id}/errors").json()
    assert any("saldo final" in e["error"] for e in errs)


def test_reglas_proponen_y_explican(bank_flow, db):
    c, acc = bank_flow["client"], bank_flow["acc"]
    props = [p for p in _proposals(c, agent="conciliacion")]
    rules = {(p["payload"] or {}).get("regla") for p in props if p["kind"] == "conciliacion"}
    assert {"referencia", "bizum", "tpv", "importe_fecha"} <= rules, rules
    motives = {(p["payload"] or {}).get("motivo") for p in props if p["kind"] == "excepcion_banco"}
    assert {"ingreso_sin_identificar", "traspaso_sin_contrapartida", "cargo_sin_justificar"} <= motives, motives
    assert motives & {"cobro_no_registrado", "referencia_ambigua"} or "referencia" in rules
    tpv = next(p for p in props if (p["payload"] or {}).get("regla") == "tpv")
    assert "bruto" in tpv["detail"] and "comisión" in tpv["detail"]
    # Nada se concilia solo
    assert not [m for m in _movements(c, acc, "conciliados")]
    # Contabilidad la ve; el asesor laboral no (no tiene bank.reconcile)
    assert tpv["id"] not in {p["id"] for p in _proposals(_login_as(c, "asesor.laboral.bcn"))}


def _login_as(c, username):
    from fastapi.testclient import TestClient

    from .conftest import CSRF

    x = TestClient(c.app)
    assert x.post(f"{API}/auth/demo/login", json={"username": username}, headers=CSRF).status_code == 204
    x.headers.update(CSRF)
    return x


def test_validar_confirma_cobro_y_cierra_comision(bank_flow, db):
    from app.models_economy import Payment

    c = bank_flow["client"]
    props = _proposals(c, agent="conciliacion")
    ref = next(p for p in props if (p["payload"] or {}).get("regla") == "referencia")
    r = c.post(f"{API}/proposals/{ref['id']}/decide", json={"approve": True, "note": "Comprobado con el banco"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "aprobada"
    mv = c.get(f"{API}/bank/movements/{ref['ref_id']}").json()
    assert mv["status"] == "conciliado" and mv["reconciled_cents"] == mv["amount_cents"]
    pay_id = next(m["target_id"] for m in mv["matches"] if m["target_type"] == "payment")
    db.rollback()
    pay = db.get(Payment, uuid.UUID(pay_id))
    assert pay.status == "confirmado" and pay.confirmed_by is not None
    # TPV: validar desde la pantalla del banco concilia también la comisión y cierra su excepción
    tpv = next(p for p in props if (p["payload"] or {}).get("regla") == "tpv")
    r = c.post(f"{API}/bank/movements/{tpv['ref_id']}/validate", json={"note": "Liquidación revisada"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "conciliado"
    com = next(m for m in r.json()["matches"] if m["target_type"] == "movement")
    cm = c.get(f"{API}/bank/movements/{com['target_id']}").json()
    assert cm["status"] == "conciliado" and cm["category"] == "comision" and cm["proposal"] is None
    # Repetir la decisión: conflicto
    assert c.post(f"{API}/proposals/{ref['id']}/decide", json={"approve": True}).status_code == 409


def test_rechazar_pide_motivo_y_no_se_repite(bank_flow, ids):
    c = bank_flow["client"]
    p = next(x for x in _proposals(c, agent="conciliacion") if (x["payload"] or {}).get("regla") == "importe_fecha")
    assert c.post(f"{API}/proposals/{p['id']}/decide", json={"approve": False}).status_code == 422
    r = c.post(f"{API}/proposals/{p['id']}/decide", json={"approve": False, "note": "El ordenante no es el cliente"})
    assert r.status_code == 200 and r.json()["status"] == "rechazada"
    mv = c.get(f"{API}/bank/movements/{p['ref_id']}").json()
    assert mv["status"] == "sin_justificar"
    # Volver a pasar el agente no repite la misma propuesta: deja una excepción para resolver a mano
    c.post(f"{API}/bank/reconcile/run", params={"organization_id": str(ids["es"])})
    mv = c.get(f"{API}/bank/movements/{p['ref_id']}").json()
    assert mv["proposal"]["kind"] == "excepcion_banco"
    assert mv["proposal"]["payload"]["motivo"] == "propuesta_ya_revisada"


def test_conciliacion_manual_cuadre_exacto(bank_flow):
    c, acc = bank_flow["client"], bank_flow["acc"]
    unknown = next(m for m in _movements(c, acc, "pendientes") if "J. FICTICIO" in m["description"])
    cands = c.get(f"{API}/bank/movements/{unknown['id']}/candidates").json()
    assert cands, "debe ofrecer cobros registrados"
    wrong = next((x for x in cands if x["type"] == "payment" and x["amount_cents"] != unknown["amount_cents"]), None)
    if wrong:
        r = c.post(f"{API}/bank/movements/{unknown['id']}/manual",
                   json={"targets": [{"type": "payment", "id": wrong["id"]}], "note": "Prueba sin cuadre",
                         "version": unknown["version"]})
        assert r.status_code == 422 and "cuadrar exactamente" in r.json()["error"]["message"]
    # Un ingreso de cliente no se «justifica» por categoría
    r = c.post(f"{API}/bank/movements/{unknown['id']}/justify",
               json={"category": "cobro", "note": "Intento indebido", "version": unknown["version"]})
    assert r.status_code == 422


def test_excepcion_aprobada_justifica_cargo_y_traspaso_entre_cuentas(bank_flow, login, db):
    c, acc = bank_flow["client"], bank_flow["acc"]
    tgss = next(p for p in _proposals(c, agent="conciliacion")
                if p["kind"] == "excepcion_banco" and (p["payload"] or {}).get("categoria_sugerida") == "seguridad_social")
    r = c.post(f"{API}/proposals/{tgss['id']}/decide", json={"approve": True, "note": "Cuota TGSS del mes"})
    assert r.status_code == 200, r.text
    mv = c.get(f"{API}/bank/movements/{tgss['ref_id']}").json()
    assert mv["status"] == "conciliado" and mv["category"] == "seguridad_social"
    # Ingreso sin identificar: aprobar la excepción no sirve (hay que conciliarlo a mano)
    unk = next(p for p in _proposals(c, agent="conciliacion")
               if p["kind"] == "excepcion_banco" and (p["payload"] or {}).get("motivo") == "ingreso_sin_identificar")
    assert unk["approvable"] is False
    # Una excepción de traspaso o de cobro tampoco se «aprueba»: se concilia con lo que la justifica
    for x in _proposals(c, agent="conciliacion"):
        if x["kind"] == "excepcion_banco" and (x["payload"] or {}).get("categoria_sugerida") in ("traspaso", "cobro"):
            assert x["approvable"] is False
    assert c.post(f"{API}/proposals/{unk['id']}/decide", json={"approve": True}).status_code == 422
    # Traspaso A → C: al importar C aparece la pareja y se concilian las dos caras
    accC = _acc(db, "C_tesoreria")
    res = _import_demo(c, accC.id)
    assert res["status"] == 201, res["json"]
    tr = next(p for p in _proposals(c, agent="conciliacion") if (p["payload"] or {}).get("regla") == "traspaso")
    assert "No es un ingreso" in tr["detail"]
    r = c.post(f"{API}/proposals/{tr['id']}/decide", json={"approve": True})
    assert r.status_code == 200, r.text
    both = [m for m in _movements(c, accC.id, "conciliados") + _movements(c, acc, "conciliados") if m["category"] == "traspaso"]
    assert len(both) == 2 and all(m["status"] == "traspaso" for m in both)
    assert all(m["proposal"] is None for m in both)


def test_nada_se_borra_y_exportacion(bank_flow, db):
    c, acc = bank_flow["client"], bank_flow["acc"]
    r = c.get(f"{API}/bank/accounts/{acc}/export.csv")
    assert r.status_code == 200 and "Conciliado con" in r.text
    r = c.get(f"{API}/bank/accounts/{acc}/imports")
    first = r.json()[-1]
    r = c.get(f"{API}/bank/imports/{first['id']}/original")
    assert r.status_code == 200 and r.content == bank_flow["import"]["data"]
    db.rollback()
    for table in ("bank_movement", "bank_match", "agent_proposal", "bank_import"):
        with pytest.raises(DBAPIError):
            db.execute(text(f"DELETE FROM {table}"))
        db.rollback()


# ------------------------------------------------------------------ agente de mensajes
def _open_case(login, db, ids, with_portal=False):
    """Expediente laboral ficticio nuevo en preapertura → abierto (dispara la bienvenida)."""
    s = login("asesor.laboral.bcn")
    from app.models import Branch

    db.rollback()
    bcn = db.execute(select(Branch).where(Branch.organization_id == ids["es"], Branch.name == "Barcelona")).scalar_one()
    r = s.post(f"{API}/cases", json={"organization_id": str(ids["es"]), "materia": "laboral", "branch_id": str(bcn.id),
                                     "contact_id": str(ids["lucia"]), "title": "Prueba F5.1 (ficticio)",
                                     "summary": "[FICTICIO]"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = s.post(f"{API}/cases/{cid}/transition", json={"to": "abierto", "engagement_confirmed": True})
    assert r.status_code == 200, r.text
    return s, cid


def test_bienvenida_se_propone_sin_duplicar(login, db, ids):
    from app.agents import emit
    from app.models_agents import CommDispatch

    s, cid = _open_case(login, db, ids)
    props = [p for p in _proposals(s, agent="mensajes") if p["case_id"] == cid]
    assert len(props) == 1 and props[0]["kind"] == "mensaje"
    assert props[0]["detail"].startswith("Buenos días, Lucía Ferrer Demo.") and "LAB-" in props[0]["detail"]
    # Contabilidad no ve mensajes de expedientes (no tiene acceso al contenido)
    assert cid not in {p["case_id"] for p in _proposals(login("contabilidad.demo"))}
    # El mismo hecho otra vez no duplica
    db.rollback()
    emit(db, ids["es"], "case.opened", "case_file", uuid.UUID(cid))
    db.commit()
    from app.agents import dispatch_events

    dispatch_events()
    db.rollback()
    assert len(list(db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid))).scalars())) == 1
    # Aprobar: se publica en su hilo con la plantilla, queda trazado y se propone invitar al portal si no tiene acceso
    r = s.post(f"{API}/proposals/{props[0]['id']}/decide", json={"approve": True})
    assert r.status_code == 200, r.text
    db.rollback()
    d = db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid))).scalar_one()
    assert d.status == "enviado" and d.message_id and d.template_version and d.sent_at
    t = s.get(f"{API}/comm/cases/{cid}/thread").json()
    assert any(m.get("template") == "bienvenida_expediente" for m in t["messages"])


def test_avisos_de_fecha_y_recordatorio(login, db, ids):
    from app.models_agents import CommDispatch

    s, cid = _open_case(login, db, ids)
    start = (datetime.now(UTC) + timedelta(days=9)).replace(hour=9, minute=30, second=0, microsecond=0)
    body = {"organization_id": str(ids["es"]), "title": "Conciliación CMAC (ficticia)", "kind": "conciliacion", "case_id": cid,
            "assignee_id": str(ids["users"]["asesor.laboral.bcn"]), "due_at": start.isoformat(),
            "start_at": start.isoformat(), "end_at": (start + timedelta(hours=1)).isoformat()}
    r = s.post(f"{API}/tasks", json=body)
    assert r.status_code == 201, r.text
    task = r.json()
    # Sin lugar no se avisa: se pide completarlo
    falta = [p for p in _proposals(s, agent="mensajes") if p["case_id"] == cid and p["kind"] == "dato_falta"]
    assert falta and "lugar" in falta[0]["detail"]
    r = s.post(f"{API}/tasks/{task['id']}/location", json={"version": task["version"], "location": "CMAC Barcelona (ficticio)"})
    assert r.status_code == 200, r.text
    props = [p for p in _proposals(s, agent="mensajes") if p["case_id"] == cid]
    assert not [p for p in props if p["kind"] == "dato_falta"]
    aviso = next(p for p in props if (p["payload"] or {}).get("plantilla") == "aviso_fecha_conciliacion")
    from app.comm.templates import MADRID

    assert "CMAC Barcelona (ficticio)" in aviso["detail"]
    assert start.astimezone(MADRID).strftime("%d/%m/%Y") in aviso["detail"] and "a las 1" in aviso["detail"]
    db.rollback()
    rec = db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid),
                                                CommDispatch.template == "recordatorio_conciliacion_24h")).scalar_one()
    local = rec.scheduled_for.astimezone(MADRID)
    assert local.hour == 10 and local.minute == 0
    assert local.date() == start.astimezone(MADRID).date() - timedelta(days=1)
    # Aplazar la tarea: lo programado con la fecha vieja se cancela y se programa con la nueva
    r = s.post(f"{API}/tasks/{task['id']}/transition",
               json={"to": "pospuesta", "version": task["version"] + 1, "reason": "Nueva citación (ficticia)",
                     "new_due_at": (start + timedelta(days=7)).isoformat()})
    assert r.status_code == 200, r.text
    db.rollback()
    ds = list(db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid))).scalars())
    old = [d for d in ds if d.template.startswith(("aviso", "recordatorio")) and d.status == "cancelado"]
    new = [d for d in ds if d.template.startswith(("aviso", "recordatorio")) and d.status == "propuesto"]
    assert len(old) == 2 and len(new) == 2
    assert all("cambió" in (d.cancel_reason or "") for d in old)
    # El aviso viejo ya no está en la bandeja
    assert aviso["id"] not in {p["id"] for p in _proposals(s, agent="mensajes")}
    # Archivar el expediente cancela lo pendiente
    d = login("direccion.demo")
    r = d.post(f"{API}/cases/{cid}/transition", json={"to": "desistido", "note": "Cliente desiste (ficticio)"})
    assert r.status_code == 200, r.text
    db.rollback()
    assert not [x for x in db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid))).scalars()
                if x.status == "propuesto"]


def test_modo_automatico_solo_donde_se_permite(login, db, ids):
    from app.models_agents import CommDispatch

    d = login("direccion.demo")
    body = {"organization_id": str(ids["es"]), "enabled": True, "mode": "automatico", "reason": "Piloto aprobado (ficticio)"}
    assert login("contabilidad.demo").post(f"{API}/agents/mensajes/settings", json=body).status_code == 403
    assert d.post(f"{API}/agents/conciliacion/settings", json=body).status_code == 422
    assert d.post(f"{API}/agents/mensajes/settings", json=body).status_code == 200
    try:
        s, cid = _open_case(login, db, ids)
        db.rollback()
        x = db.execute(select(CommDispatch).where(CommDispatch.case_id == uuid.UUID(cid))).scalar_one()
        assert x.status == "enviado" and x.proposal_id is None
        t = s.get(f"{API}/comm/cases/{cid}/thread").json()
        welcome = next(m for m in t["messages"] if m.get("template") == "bienvenida_expediente")
        assert welcome["author"]["type"] == "sistema"
    finally:
        body["mode"] = "propone"
        assert d.post(f"{API}/agents/mensajes/settings", json=body).status_code == 200


def test_seguimiento_75_dias(login, db, ids):
    from app.models import CaseFile
    from app.models_agents import CommDispatch

    s, cid = _open_case(login, db, ids)
    db.rollback()
    cf = db.get(CaseFile, uuid.UUID(cid))
    cf.engagement_confirmed_at = datetime.now(UTC) - timedelta(days=80)
    db.commit()
    # Tiene un mensaje del despacho reciente (la bienvenida propuesta no cuenta: no se ha enviado)
    _run(db, "mensajes", ids["es"])
    _run(db, "mensajes", ids["es"])
    rows = list(db.execute(select(CommDispatch).where(CommDispatch.case_id == cf.id,
                                                      CommDispatch.template == "seguimiento_expediente")).scalars())
    assert len(rows) == 1
    assert "continúa en trámite" in next(p for p in _proposals(s, agent="mensajes")
                                         if p["case_id"] == cid and (p["payload"] or {}).get("plantilla") == "seguimiento_expediente")["detail"]


def test_panel_de_agentes_y_metricas(login, ids):
    d = login("direccion.demo")
    r = d.get(f"{API}/agents")
    assert r.status_code == 200
    codes = {a["code"]: a for a in r.json()}
    assert {"conciliacion", "mensajes"} <= set(codes)
    assert codes["conciliacion"]["can_be_automatic"] is False and codes["conciliacion"]["limits"]
    assert "DR-PLT-1" in codes["mensajes"]["covers"]
    m = d.get(f"{API}/agents/mensajes/metrics").json()
    assert m["programados"] >= 1 and "por_plantilla" in m
    assert login("recepcion.bcn").get(f"{API}/agents").status_code == 403
    assert len(d.get(f"{API}/agents/mensajes/templates").json()) == 6
