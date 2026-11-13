"""F5.3 RRHH: ficha única, permisos por función (salario y salud restringidos), carpeta con lectura de nóminas
confirmada por una persona, vacaciones con saldo y decisión de otra persona, avisos de vencimientos, resumen de
nóminas sin calcularlas e importación con duplicados. 5 fichas y nóminas FICTICIAS."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

API = "/api/v1"


def _emp(s, name):
    return next(e for e in s.get(f"{API}/hr/employees").json()["items"] if e["name"] == name)


def _next_monday(weeks=3):
    t = date.today()
    return t + timedelta(days=7 * weeks - t.weekday())


def test_plantilla_y_permisos_por_funcion(login, db, ids):
    r = login("rrhh.demo").get(f"{API}/hr/employees")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 5 and all(e["salary_annual_cents"] for e in items)
    assert {e["country"] for e in items} == {"ES", "CO"}
    # Recepción y asesores no ven la plantilla (403 auditado); sí su propia ficha
    s = login("recepcion.bcn")
    assert s.get(f"{API}/hr/employees").status_code == 403
    me = s.get(f"{API}/hr/me").json()
    assert me["name"] == "Laura Gómez Demo" and me["salary_annual_cents"] and me["is_me"]
    other = _emp(login("rrhh.demo"), "Marcos Vidal Ficticio")
    assert s.get(f"{API}/hr/employees/{other['id']}").status_code == 403
    assert denied_events(db, "hr.employee.read", other["id"])
    # Un líder ve a su equipo (sin salario) para decidir ausencias; no a otros departamentos
    lid = login("lider.extranjeria").get(f"{API}/hr/employees").json()["items"]
    assert [e["name"] for e in lid] == ["Daniel Ortiz Prueba"] and "salary_annual_cents" not in lid[0]
    # Contabilidad: ni plantilla ni salarios
    assert login("contabilidad.demo").get(f"{API}/hr/employees").status_code == 403
    # Datos de personal aislados: la ficha no aparece como cliente
    assert login("direccion.demo").get(f"{API}/contacts", params={"q": "Vidal Ficticio"}).json()["total"] == 0


def test_baja_medica_solo_la_ve_rrhh(login):
    r = login("rrhh.demo")
    sara = _emp(r, "Sara Molina Ficticia")
    full = r.get(f"{API}/hr/employees/{sara['id']}").json()
    assert any(lv["kind"] == "baja" for lv in full["leaves"])
    cal_month = date.fromisoformat(next(lv["start_date"] for lv in full["leaves"] if lv["kind"] == "baja")).strftime("%Y-%m")
    # La propia persona la ve; el calendario de su líder la muestra solo como «ausencia»
    assert any(lv["kind"] == "baja" for lv in login("gestor.laboral.vlc").get(f"{API}/hr/me").json()["leaves"])
    cal = login("lider.laboral").get(f"{API}/hr/calendar", params={"month": cal_month}).json()
    sara_cal = [lv for lv in cal if lv["employee"] == "Sara Molina Ficticia"]
    assert sara_cal and all(lv["kind"] == "ausencia" and lv["note"] is None for lv in sara_cal)


def test_alta_valida_y_avisa_duplicados(login, ids):
    r = login("rrhh.demo")
    branches = {b["name"]: b["id"] for b in login("direccion.demo").get(f"{API}/organizations").json()[0]["branches"]}
    body = {"organization_id": str(ids["es"]), "given_name": "Marcos", "family_names": "Vidal Ficticio",
            "branch_id": branches["Barcelona"], "category": "Titulado superior", "job_title": "Asesor",
            "contract_type": "indefinido", "workday": "completa", "weekly_hours": 40, "start_date": "2026-01-01"}
    x = r.post(f"{API}/hr/employees", json=body)
    assert x.status_code == 409 and x.json()["error"]["code"] == "posible_duplicado"
    body |= {"given_name": "Nuevo", "family_names": "Empleado Demo", "contract_type": "temporal"}
    x = r.post(f"{API}/hr/employees", json=body)
    assert x.status_code == 422  # temporal sin fecha de fin
    body |= {"contract_end_date": "2026-12-31", "id_kind": "DNI", "id_number": "12345678A"}
    x = r.post(f"{API}/hr/employees", json=body)
    assert x.status_code == 422 and "letra" in x.json()["error"]["message"]
    body["id_number"] = "12345678Z"
    x = r.post(f"{API}/hr/employees", json=body)
    assert x.status_code == 201, x.text
    e = x.json()
    assert e["code"].startswith("EMP-") and e["national_id_masked"] == "•••••678Z"
    # Cambio con versión y motivo; el salario no viaja en la auditoría
    upd = r.patch(f"{API}/hr/employees/{e['id']}", json={"version": e["version"], "reason": "Revisión salarial (ficticia)",
                                                         "salary_annual_cents": 2500000})
    assert upd.status_code == 200
    assert r.patch(f"{API}/hr/employees/{e['id']}", json={"version": e["version"], "reason": "Otra vez",
                                                          "job_title": "X Y"}).status_code == 409
    assert login("asesor.laboral.bcn").post(f"{API}/hr/employees", json=body).status_code == 403


def test_nomina_se_lee_y_la_confirma_una_persona(login):
    from app.hr.samples import payslip_pdf

    r = login("rrhh.demo")
    daniel = _emp(r, "Daniel Ortiz Prueba")
    data = payslip_pdf("Despacho Demo", "Daniel Ortiz Prueba", "Titulado superior", 2026, 7, 216667, 39000)
    up = r.post(f"{API}/hr/employees/{daniel['id']}/documents", data={"kind": "nomina"},
                files={"file": ("nomina.pdf", data, "application/pdf")})
    assert up.status_code == 201, up.text
    d = up.json()
    assert d["status"] == "pendiente_revision" and d["period"] == "2026-07"
    assert d["extracted"]["liquido_cents"] == 177667 and d["extracted"]["cuadra"] and d["extracted"]["confianza"] == "alta"
    # El mismo archivo otra vez: no se duplica
    assert r.post(f"{API}/hr/employees/{daniel['id']}/documents", data={"kind": "nomina"},
                  files={"file": ("n.pdf", data, "application/pdf")}).status_code == 409
    # Confirmar exige cifras que cuadren
    bad = r.post(f"{API}/hr/documents/{d['id']}/review", json={"version": d["version"], "status": "valido", "period": "2026-07",
                                                               "devengado_cents": 216667, "deducciones_cents": 39000,
                                                               "liquido_cents": 100})
    assert bad.status_code == 422
    ok = r.post(f"{API}/hr/documents/{d['id']}/review", json={"version": d["version"], "status": "valido", "period": "2026-07",
                                                              "devengado_cents": 216667, "deducciones_cents": 39000,
                                                              "liquido_cents": 177667})
    assert ok.status_code == 200 and ok.json()["confirmed"]["liquido_cents"] == 177667
    # La nómina la ve la propia persona, no su líder
    assert login("asesor.extranjeria.mad").get(f"{API}/hr/documents/{d['id']}/file").status_code == 200
    assert login("lider.extranjeria").get(f"{API}/hr/documents/{d['id']}/file").status_code == 403


def test_vacaciones_saldo_coincidencias_y_decision(login, db):
    s = login("asesor.laboral.bcn")
    me = s.get(f"{API}/hr/me").json()
    start = _next_monday(6)
    big = s.post(f"{API}/hr/employees/{me['id']}/leaves", json={"kind": "vacaciones", "start_date": start.isoformat(),
                                                                 "end_date": (start + timedelta(days=60)).isoformat()})
    assert big.status_code == 422 and "le quedan" in big.json()["error"]["message"]
    assert s.post(f"{API}/hr/employees/{me['id']}/leaves",
                  json={"kind": "baja", "start_date": start.isoformat(), "end_date": start.isoformat()}).status_code == 403
    r = s.post(f"{API}/hr/employees/{me['id']}/leaves", json={"kind": "vacaciones", "start_date": start.isoformat(),
                                                               "end_date": (start + timedelta(days=4)).isoformat()})
    assert r.status_code == 201, r.text
    lv = r.json()
    assert lv["working_days"] == 5 and lv["status"] == "solicitada"
    # Las mismas fechas otra vez: no
    assert s.post(f"{API}/hr/employees/{me['id']}/leaves", json={"kind": "asuntos_propios", "start_date": start.isoformat(),
                                                                  "end_date": start.isoformat()}).status_code == 409
    # Nadie aprueba lo suyo; su líder sí, y rechazar pide motivo
    assert s.post(f"{API}/hr/leaves/{lv['id']}/decide", json={"version": lv["version"], "approve": True}).status_code == 403
    lider = login("lider.laboral")
    queue = lider.get(f"{API}/hr/leaves").json()
    item = next(x for x in queue if x["id"] == lv["id"])
    assert item["can_decide"]
    assert lider.post(f"{API}/hr/leaves/{lv['id']}/decide", json={"version": lv["version"], "approve": False}).status_code == 422
    r = lider.post(f"{API}/hr/leaves/{lv['id']}/decide", json={"version": lv["version"], "approve": True})
    assert r.status_code == 200 and r.json()["status"] == "aprobada"
    bal = s.get(f"{API}/hr/me").json()["vacation"]
    assert bal["used"] >= 5 and bal["remaining"] == bal["total"] - bal["used"] - bal["pending"]
    # Un líder de otro departamento no decide ausencias de Laboral
    daniel_leave = next(x for x in login("rrhh.demo").get(f"{API}/hr/leaves").json() if x["employee"] == "Daniel Ortiz Prueba")
    assert lider.post(f"{API}/hr/leaves/{daniel_leave['id']}/decide",
                      json={"version": daniel_leave["version"], "approve": True}).status_code == 403


def test_avisos_de_vencimientos_crean_tarea(login, db, ids):
    from app.agents.engine import run_scheduled
    from app.models_work import Task

    db.rollback()
    run_scheduled(db, only="rrhh", org_ids={ids["es"]})
    from app.db import get_sessionmaker

    s2 = get_sessionmaker()()
    try:
        co = next(o for o in s2.execute(text("SELECT id FROM organization WHERE country = 'CO'")).scalars())
        run_scheduled(s2, only="rrhh", org_ids={co})
        s2.commit()
    finally:
        s2.close()
    db.commit()
    r = login("rrhh.demo")
    props = r.get(f"{API}/proposals", params={"agent": "rrhh"}).json()["items"]
    motives = {(p["payload"] or {}).get("motivo") for p in props}
    assert {"fin_contrato", "fin_prueba", "falta_contrato", "diferencia_nomina"} <= motives, motives
    fin = next(p for p in props if p["payload"]["motivo"] == "fin_contrato")
    assert "Laura Gómez Demo" in fin["title"] and fin["priority"] in ("alta", "media")
    res = r.post(f"{API}/proposals/{fin['id']}/decide", json={"approve": True})
    assert res.status_code == 200, res.text
    db.rollback()
    t = db.get(Task, __import__("uuid").UUID(res.json()["result"]["tarea"]))
    assert t.assignee_id == ids["users"]["rrhh.demo"] and t.case_id is None
    # Contabilidad y Recepción no ven avisos de plantilla
    assert not [p for p in login("contabilidad.demo").get(f"{API}/proposals").json()["items"] if p["agent"] == "rrhh"]
    # Repetir el agente no duplica
    db.rollback()
    run_scheduled(db, only="rrhh", org_ids={ids["es"]})
    db.commit()
    again = r.get(f"{API}/proposals", params={"agent": "rrhh"}).json()["items"]
    assert len([p for p in again if p["payload"]["motivo"] == "fin_contrato"]) == 0  # ya aprobada, no vuelve


def test_resumen_de_nominas_sin_calcular(login):
    today = date.today().replace(day=1)
    prev = (today - timedelta(days=1)).strftime("%Y-%m")
    r = login("rrhh.demo").get(f"{API}/hr/payroll", params={"month": prev})
    assert r.status_code == 200
    rows = {x["name"]: x for x in r.json()["rows"]}
    assert rows["Laura Gómez Demo"]["revisar"] is True and rows["Laura Gómez Demo"]["diferencia_pct"] == 18.0
    assert rows["Andrés Ruiz Demo"]["estado"] == "por_revisar"
    assert "no calcula" in r.json()["aviso"]
    assert login("lider.laboral").get(f"{API}/hr/payroll", params={"month": prev}).status_code == 403


def test_importacion_previsualiza_y_solo_crea_nuevas(login, ids):
    r = login("rrhh.demo")
    csv = (b"nombre;apellidos;sede;departamento;categoria;puesto;contrato;jornada;horas_semana;fecha_alta;fecha_fin_contrato\n"
           b"Marcos;Vidal Ficticio;Barcelona;LAB;Titulado;Asesor;indefinido;completa;40;01/03/2021;\n"
           b"Irene;Importada Demo;Madrid;EXT;Auxiliar;Apoyo;temporal;parcial;20;01/09/2026;31/03/2027\n"
           b"Pablo;Sin Sede Demo;Sevilla;LAB;Auxiliar;Apoyo;indefinido;completa;40;01/09/2026;\n"
           b";Falta Nombre Demo;Madrid;EXT;Auxiliar;Apoyo;indefinido;completa;40;01/09/2026;\n")
    pre = r.post(f"{API}/hr/import", data={"organization_id": str(ids["es"])}, files={"file": ("plantilla.csv", csv, "text/csv")})
    assert pre.status_code == 200, pre.text
    st = [x["status"] for x in pre.json()["rows"]]
    assert st == ["duplicado", "nuevo", "error", "error"] and pre.json()["created"] == []
    done = r.post(f"{API}/hr/import", data={"organization_id": str(ids["es"]), "confirm": "true"},
                  files={"file": ("plantilla.csv", csv, "text/csv")})
    assert done.status_code == 200 and len(done.json()["created"]) == 1
    assert any(e["name"] == "Irene Importada Demo" for e in r.get(f"{API}/hr/employees").json()["items"])


def test_nada_se_borra(db):
    db.rollback()
    for t in ("employee", "employee_document", "leave_request"):
        with pytest.raises(DBAPIError):
            db.execute(text(f"DELETE FROM {t}"))
        db.rollback()
