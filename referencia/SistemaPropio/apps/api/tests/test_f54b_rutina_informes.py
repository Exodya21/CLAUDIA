"""F5.4b Contabilidad: rutina de trabajo (pasos comprobados por el sistema, tareas en la Agenda, «no aplica» con motivo,
responsables) e informes semanales, quincenales y mensuales (inmutables, versiones, PDF/CSV, correo sin cifras,
revisión de Dirección). Datos FICTICIOS."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

API = "/api/v1"


def _routine(s, ids):
    r = s.get(f"{API}/accounting/routine", params={"organization_id": str(ids["es"])})
    assert r.status_code == 200, r.text
    return r.json()


def test_rutina_crea_pasos_con_responsable_y_tarea(login, ids, db):
    from app.models_work import Task

    rt = _routine(login("contabilidad.demo"), ids)
    steps = {x["step"]: x for x in rt["items"]}
    # Siempre existen los de la semana y los del cierre del mes anterior; los diarios solo en días laborables
    for code in ("s_facturas", "s_pagos", "s_cajas", "s_informe", "q_informe", "m_extractos", "m_conciliar",
                 "m_documentos", "m_cierre", "m_aprobar", "m_informe"):
        assert code in steps, code
    assert steps["s_facturas"]["owner"] == "Contabilidad (demo)"
    assert steps["m_aprobar"]["owner"] == "Dirección (demo)"
    assert all(x["evidence"] for x in rt["items"]), "cada paso explica qué ha comprobado"
    # Los pendientes semanales/mensuales están en la Agenda de su responsable; los diarios, no
    db.rollback()
    for x in rt["items"]:
        if x["status"] == "pendiente" and x["cadence"] != "diaria":
            t = db.get(Task, uuid.UUID(x["task_id"]))
            assert t is not None and t.assignee_id == ids["users"]["contabilidad.demo" if x["owner"] == "Contabilidad (demo)" else "direccion.demo"]
        if x["cadence"] == "diaria":
            assert x["task_id"] is None
    # Comprobar otra vez no duplica
    again = _routine(login("contabilidad.demo"), ids)
    assert again["sync"]["creados"] == 0


def test_paso_se_da_por_hecho_al_comprobarlo_y_cierra_su_tarea(login, ids, db):
    from app.models_work import Task, TaskEvent

    c = login("contabilidad.demo")
    before = {x["step"]: x for x in _routine(c, ids)["items"]}["s_facturas"]
    # Contabilidad valida todo lo que estaba por validar (la rutina NO se marca a mano)
    for inv in c.get(f"{API}/accounting/invoices", params={"organization_id": str(ids["es"]), "status": "recibida"}).json():
        r = c.post(f"{API}/accounting/invoices/{inv['id']}/decide", json={"version": inv["version"], "approve": True,
                                                                         "activity": inv["activity"]})
        assert r.status_code == 200, r.text
    after = {x["step"]: x for x in _routine(c, ids)["items"]}["s_facturas"]
    assert after["status"] == "hecho" and "validadas" in after["evidence"]
    assert after["on_time"] in (True, False, None)
    if before["status"] == "pendiente" and before["task_id"]:
        db.rollback()
        t = db.get(Task, uuid.UUID(before["task_id"]))
        assert t.status == "completada" and t.completed_at is not None
        ev = db.execute(select(TaskEvent).where(TaskEvent.task_id == t.id, TaskEvent.to_status == "completada")).scalar_one()
        assert ev.reason.startswith("Comprobado por la rutina de Contabilidad")


def test_no_aplica_exige_motivo_y_no_vuelve_atras(login, ids, db):
    c = login("contabilidad.demo")
    item = next(x for x in _routine(c, ids)["items"] if x["status"] == "pendiente" and x["can_na"])
    assert c.post(f"{API}/accounting/routine/{item['id']}/na", json={"reason": "corto"}).status_code == 422
    r = c.post(f"{API}/accounting/routine/{item['id']}/na", json={"reason": "Cuenta sin movimientos ese periodo (ficticio)"})
    assert r.status_code == 200 and r.json()["status"] == "no_aplica" and r.json()["na_by"] == "Contabilidad (demo)"
    assert c.post(f"{API}/accounting/routine/{item['id']}/na", json={"reason": "Otra vez lo mismo (ficticio)"}).status_code == 409
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE accounting_routine_item SET status = 'pendiente' WHERE id = :i"), {"i": uuid.UUID(item["id"])})
    db.rollback()
    # Recepción no ve la rutina; auditado
    rec = login("recepcion.bcn")
    assert rec.get(f"{API}/accounting/routine", params={"organization_id": str(ids["es"])}).status_code == 403
    assert denied_events(db, "accounting.read", ids["es"])


def test_responsables_los_asigna_direccion(login, ids):
    body = {"organization_id": str(ids["es"]), "step": "s_informe", "user_id": str(ids["users"]["socio.demo"])}
    assert login("contabilidad.demo").put(f"{API}/accounting/routine/owners", json=body).status_code == 403
    d = login("direccion.demo")
    bad = body | {"user_id": str(ids["users"]["recepcion.bcn"])}
    assert d.put(f"{API}/accounting/routine/owners", json=bad).status_code == 422
    assert d.put(f"{API}/accounting/routine/owners", json=body).status_code == 200
    owners = {o["step"]: o for o in d.get(f"{API}/accounting/routine/owners", params={"organization_id": str(ids["es"])}).json()}
    assert owners["s_informe"]["owner"] == "Socio Director (demo)"
    assert {c["name"] for c in owners["s_informe"]["candidates"]} >= {"Dirección (demo)", "Socio Director (demo)"}
    # Se deja como estaba para el resto de pruebas
    d.put(f"{API}/accounting/routine/owners", json=body | {"user_id": str(ids["users"]["direccion.demo"])})


def test_informes_se_generan_solos_y_no_cambian(login, ids, db):
    from app.agents.engine import run_scheduled
    from app.models_comm import CommOutbox
    from app.services import textcrypt

    db.rollback()
    run_scheduled(db, only="contabilidad", org_ids={ids["es"]})
    db.commit()
    c = login("contabilidad.demo")
    reps = c.get(f"{API}/accounting/reports", params={"organization_id": str(ids["es"])}).json()
    kinds = {r["kind"] for r in reps}
    assert {"semanal", "quincenal"} <= kinds and ("mensual" in kinds) == (date.today().day >= 5)
    week = next(r for r in reps if r["kind"] == "semanal")
    assert week["generated_by"] == "Rutina automática" and week["reviewed_by"] is None
    # Correo de aviso SIN cifras a quien puede leer Contabilidad
    db.rollback()
    mails = list(db.execute(select(CommOutbox).where(CommOutbox.purpose == "informe_contabilidad")).scalars())
    assert mails and all("€" not in textcrypt.dec(m.body_enc) for m in mails)
    # Repetir no duplica informes
    db.rollback()
    run_scheduled(db, only="contabilidad", org_ids={ids["es"]})
    db.commit()
    assert len(c.get(f"{API}/accounting/reports", params={"organization_id": str(ids["es"])}).json()) == len(reps)
    # Volver a generar = versión nueva; la anterior se conserva
    r2 = c.post(f"{API}/accounting/reports", json={"organization_id": str(ids["es"]), "kind": "semanal", "day": week["period_from"]})
    assert r2.status_code == 201 and r2.json()["version"] == week["version"] + 1 and r2.json()["generated_by"] == "Contabilidad (demo)"
    # PDF y CSV (descargas auditadas)
    pdf = c.get(f"{API}/accounting/reports/{week['id']}/file", params={"fmt": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    csv = c.get(f"{API}/accounting/reports/{week['id']}/file", params={"fmt": "csv"})
    assert csv.status_code == 200 and "Rutina" in csv.text and "Resultado provisional" in csv.text
    # Solo Dirección revisa; desde su pendiente en Contabilidad
    assert c.post(f"{API}/accounting/reports/{r2.json()['id']}/review", json={}).status_code == 403
    d = login("direccion.demo")
    prop = next(p for p in d.get(f"{API}/proposals", params={"agent": "contabilidad", "kind": "informe_revisar"}).json()["items"]
                if p["ref_id"] == week["id"])
    assert d.post(f"{API}/proposals/{prop['id']}/decide", json={"approve": True, "note": "Leído"}).status_code == 200
    assert d.get(f"{API}/accounting/reports/{week['id']}").json()["reviewed_by"] == "Dirección (demo)"
    assert d.post(f"{API}/accounting/reports/{week['id']}/review", json={}).status_code == 409
    rv = d.post(f"{API}/accounting/reports/{r2.json()['id']}/review", json={"note": "Versión 2 conforme"})
    assert rv.status_code == 200
    # La rutina da por hecho «Revisar el informe semanal»
    s_inf = {x["step"]: x for x in _routine(d, ids)["items"]}["s_informe"]
    assert s_inf["status"] == "hecho", s_inf
    # Inmutable en la base de datos
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE accounting_report SET figures = '{}'::jsonb WHERE id = :i"), {"i": uuid.UUID(week["id"])})
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE accounting_report SET review_note = 'x' WHERE id = :i"), {"i": uuid.UUID(week["id"])})
    db.rollback()


def test_informe_mensual_protege_salarios(login, ids):
    c, d = login("contabilidad.demo"), login("direccion.demo")
    first = date.today().replace(day=1)
    prev_day = date.fromordinal(first.toordinal() - 1)
    r = c.post(f"{API}/accounting/reports", json={"organization_id": str(ids["es"]), "kind": "mensual", "day": prev_day.isoformat()})
    assert r.status_code == 201
    assert r.json()["figures"].get("personal_agrupado") is True  # Contabilidad no tiene permiso de salarios
    full = d.get(f"{API}/accounting/reports/{r.json()['id']}").json()
    assert "personal_agrupado" not in full["figures"]
    assert c.post(f"{API}/accounting/reports", json={"organization_id": str(ids["es"]), "kind": "mensual",
                                                     "day": date(date.today().year + 1, 1, 1).isoformat()}).status_code == 422


def test_nada_se_borra_rutina_informes(db):
    db.rollback()
    for t in ("accounting_routine_owner", "accounting_routine_item", "accounting_report"):
        with pytest.raises(DBAPIError):
            db.execute(text(f"DELETE FROM {t}"))
        db.rollback()
