"""F2.1 expedientes (AT-15, AT-16) y F2.2 tareas (AT-19, AT-20, Q-6.23, I-074)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text

from .conftest import denied_events


def _branch(c, org_id, name):
    org = next(o for o in c.get("/api/v1/organizations").json() if o["id"] == str(org_id))
    return next(b["id"] for b in org["branches"] if b["name"] == name)


def _new_case(c, ids, materia="laboral", branch="Barcelona", contact=None, **extra):
    body = {"organization_id": str(ids["es"]), "contact_id": str(contact or ids["lucia"]), "materia": materia,
            "branch_id": _branch(c, ids["es"], branch), "title": f"Expediente de prueba {materia}", **extra}
    return c.post("/api/v1/cases", json=body)


# ---------------------------------------------------------------- F2.1
def test_apertura_respeta_la_rama(login, ids):
    asesor = login("asesor.laboral.bcn")
    r = _new_case(asesor, ids)
    assert r.status_code == 201 and r.json()["status"] == "preapertura" and r.json()["code"].startswith("LAB-")
    assert asesor.get(f"/api/v1/cases/{r.json()['id']}").status_code == 200  # queda asignado a quien lo abre
    assert _new_case(asesor, ids, materia="extranjeria", branch="Madrid").status_code == 403
    assert _new_case(asesor, ids, branch="Madrid").status_code == 403  # su pertenencia está acotada a Barcelona
    assert _new_case(login("recepcion.bcn"), ids).status_code == 403
    r = _new_case(login("lider.laboral"), ids, responsible_user_id=str(ids["users"]["asesor.extranjeria.mad"]))
    assert r.status_code == 422  # un responsable de Extranjería no puede llevar un expediente Laboral


def test_at15_dos_expedientes_mismo_cliente_codigos_distintos_y_relacion(login, ids):
    d = login("direccion.demo")
    a = _new_case(d, ids).json()
    b = _new_case(d, ids).json()
    assert a["code"] != b["code"] and a["id"] != b["id"]
    num = lambda code: int(code.rsplit("-", 1)[1])  # noqa: E731
    assert num(b["code"]) == num(a["code"]) + 1  # consecutivo sin reutilización
    r = d.post(f"/api/v1/cases/{a['id']}/relations", json={"related_case_id": b["id"], "kind": "mismo_cliente"})
    assert r.status_code == 201
    assert d.post(f"/api/v1/cases/{b['id']}/relations", json={"related_case_id": a["id"], "kind": "conexo"}).status_code == 409
    rel = d.get(f"/api/v1/cases/{b['id']}").json()["relations"]
    assert rel[0]["code"] == a["code"]
    # Relacionar con un expediente de otra rama al que el usuario no accede: 403 auditado
    r = login("lider.laboral").post(f"/api/v1/cases/{a['id']}/relations",
                                    json={"related_case_id": str(ids["lucia_ext"]), "kind": "mismo_cliente"})
    assert r.status_code == 403


def test_relacion_no_revela_expedientes_de_otra_rama(login, ids):
    d = login("direccion.demo")
    r = d.post(f"/api/v1/cases/{ids['lucia_lab']}/relations", json={"related_case_id": str(ids["lucia_ext"]), "kind": "mismo_cliente"})
    assert r.status_code in (201, 409)
    lab_view = login("asesor.laboral.bcn").get(f"/api/v1/cases/{ids['lucia_lab']}").json()
    assert all(x["materia"] != "extranjeria" for x in lab_view["relations"])
    assert any(x["materia"] == "extranjeria" for x in d.get(f"/api/v1/cases/{ids['lucia_lab']}").json()["relations"])


def test_at16_fases_solo_por_rol_designado_y_registradas(login, ids, db):
    asesor = login("asesor.laboral.bcn")
    case = _new_case(asesor, ids).json()
    cid = case["id"]
    t = asesor.post("/api/v1/tasks", json={"organization_id": str(ids["es"]), "case_id": cid, "title": "Tarea previa",
                                           "assignee_id": str(ids["users"]["asesor.laboral.bcn"]),
                                           "due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat()})
    assert t.status_code == 201
    r = asesor.post(f"/api/v1/cases/{cid}/transition", json={"to": "abierto"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "engagement_confirmed"
    assert asesor.post(f"/api/v1/cases/{cid}/transition", json={"to": "abierto", "engagement_confirmed": True}).status_code == 200
    assert asesor.post(f"/api/v1/cases/{cid}/transition", json={"to": "en_tramite"}).status_code == 200
    assert asesor.post(f"/api/v1/cases/{cid}/transition", json={"to": "archivado", "note": "x" * 6}).status_code == 409
    r = asesor.post(f"/api/v1/cases/{cid}/transition", json={"to": "resuelto", "note": "Sentencia estimatoria (ficticia)"})
    assert r.status_code == 403
    assert denied_events(db, "case.transition", cid)
    lider = login("lider.laboral")
    assert lider.post(f"/api/v1/cases/{cid}/transition", json={"to": "resuelto"}).status_code == 422  # requiere motivo
    assert lider.post(f"/api/v1/cases/{cid}/transition", json={"to": "resuelto", "note": "Sentencia estimatoria (ficticia)"}).status_code == 200
    detail = asesor.get(f"/api/v1/cases/{cid}").json()
    assert [e["to"] for e in detail["phase_events"]] == ["resuelto", "en_tramite", "abierto", "preapertura"]
    assert detail["engagement_confirmed_at"] and detail["status_allowed"] == []  # el asesor no tiene fases jurídicas
    tasks = asesor.get("/api/v1/tasks", params={"case_id": cid, "scope": "all"}).json()["items"]
    assert len(tasks) == 1  # las tareas persisten tras cambiar de fase
    with pytest.raises(Exception, match="inmutable"):
        db.execute(text(f"UPDATE case_phase_event SET note='x' WHERE case_id='{cid}'"))
    db.rollback()


def test_responsables_por_rama(login, ids):
    lider = login("lider.laboral")
    case = _new_case(lider, ids, branch="Valencia").json()
    cid = case["id"]
    r = lider.post(f"/api/v1/cases/{cid}/assignments",
                   json={"user_id": str(ids["users"]["gestor.laboral.vlc"]), "role_in_case": "responsable", "reason": "Reparto de carga"})
    assert r.status_code == 201
    assert login("gestor.laboral.vlc").get(f"/api/v1/cases/{cid}").status_code == 200
    r = lider.post(f"/api/v1/cases/{cid}/assignments",
                   json={"user_id": str(ids["users"]["asesor.extranjeria.mad"]), "role_in_case": "apoyo", "reason": "Ayuda puntual"})
    assert r.status_code == 422
    assert login("asesor.laboral.bcn").post(f"/api/v1/cases/{ids['lucia_lab']}/assignments",
                                            json={"user_id": str(ids["users"]["gestor.laboral.vlc"]), "reason": "intento"}).status_code == 403
    detail = lider.get(f"/api/v1/cases/{cid}").json()
    active = [a for a in detail["assignments"] if a["until"] is None and a["role"] == "responsable"]
    assert len(active) == 1 and active[0]["user_id"] == str(ids["users"]["gestor.laboral.vlc"])


def test_indicador_de_inactividad(login, db):
    from app.models import CaseFile

    d = login("direccion.demo")
    r = d.get("/api/v1/cases", params={"inactive": True}).json()
    assert r["total"] >= 1 and all(x["inactive_days"] >= 30 for x in r["items"])
    cid = r["items"][0]["id"]
    assert d.get(f"/api/v1/cases/{cid}").json()["inactive"] is True
    # Cualquier actividad (aquí, una tarea) reinicia el indicador
    t = d.post("/api/v1/tasks", json={"organization_id": str(db.get(CaseFile, cid).organization_id), "case_id": cid,
                                      "title": "Retomar contacto", "assignee_id": str(d.get("/api/v1/me").json()["id"]),
                                      "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()})
    assert t.status_code == 201
    assert cid not in {x["id"] for x in d.get("/api/v1/cases", params={"inactive": True}).json()["items"]}
    assert login("recepcion.bcn").get("/api/v1/cases", params={"inactive": True}).json()["total"] == 0


# ---------------------------------------------------------------- F2.2
def _task(c, ids, case_id, assignee, **extra):
    body = {"organization_id": str(ids["es"]), "case_id": str(case_id), "title": "Tarea de prueba",
            "assignee_id": str(ids["users"][assignee]), "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(), **extra}
    return c.post("/api/v1/tasks", json=body)


def test_at19_plazo_legal_pendiente_hasta_validacion_y_separado(login, ids):
    asesor = login("asesor.laboral.bcn")
    legal = (date.today() + timedelta(days=10)).isoformat()
    assert _task(asesor, ids, ids["lucia_lab"], "asesor.laboral.bcn", kind="plazo", legal_deadline=legal).status_code == 422
    r = _task(asesor, ids, ids["lucia_lab"], "asesor.laboral.bcn", kind="plazo", legal_deadline=legal,
              legal_source="Diligencia ficticia de prueba")
    assert r.status_code == 201
    t = r.json()
    assert t["legal_status"] == "pendiente_validacion" and t["legal_deadline"] == legal
    assert t["due_at"] != legal and not t["can_validate_legal"]
    assert asesor.post(f"/api/v1/tasks/{t['id']}/legal-deadline/decision",
                       json={"version": t["version"], "decision": "validar"}).status_code == 403
    lider = login("lider.laboral")
    lt = lider.get(f"/api/v1/tasks/{t['id']}").json()
    assert lt["can_validate_legal"]
    assert lider.post(f"/api/v1/tasks/{t['id']}/legal-deadline/decision",
                      json={"version": lt["version"], "decision": "rechazar"}).status_code == 422
    v = lider.post(f"/api/v1/tasks/{t['id']}/legal-deadline/decision", json={"version": lt["version"], "decision": "validar"})
    assert v.status_code == 200 and v.json()["legal_status"] == "validado" and v.json()["legal_validated_by"] == "lider.laboral"
    pending = lider.get("/api/v1/tasks", params={"scope": "all", "legal_pending": True}).json()["items"]
    assert t["id"] not in {x["id"] for x in pending}


def test_quien_propone_no_valida(login, ids):
    lider = login("lider.laboral")
    t = _task(lider, ids, ids["lucia_lab"], "asesor.laboral.bcn", kind="plazo",
              legal_deadline=(date.today() + timedelta(days=5)).isoformat(), legal_source="Notificación ficticia").json()
    r = lider.post(f"/api/v1/tasks/{t['id']}/legal-deadline/decision", json={"version": t["version"], "decision": "validar"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "doble_validacion"


def test_at20_aplazar_exige_motivo_y_fecha_y_conserva_la_anterior(login, ids):
    asesor = login("asesor.laboral.bcn")
    t = _task(asesor, ids, ids["lucia_lab"], "asesor.laboral.bcn").json()
    old_due = t["due_at"]
    r = asesor.post(f"/api/v1/tasks/{t['id']}/transition", json={"to": "pospuesta", "version": 1})
    assert r.status_code == 422 and {d["field"] for d in r.json()["error"]["details"]} == {"reason", "new_due_at"}
    new_due = (datetime.now(UTC) + timedelta(days=9)).isoformat()
    r = asesor.post(f"/api/v1/tasks/{t['id']}/transition",
                    json={"to": "pospuesta", "version": 1, "reason": "Falta documentación del cliente", "new_due_at": new_due})
    assert r.status_code == 200 and r.json()["status"] == "pospuesta"
    ev = asesor.get(f"/api/v1/tasks/{t['id']}").json()["events"][0]
    assert ev["kind"] == "aplazada" and ev["reason"].startswith("Falta")
    assert datetime.fromisoformat(ev["old_due_at"]) == datetime.fromisoformat(old_due)
    assert asesor.post(f"/api/v1/tasks/{t['id']}/transition",
                       json={"to": "anulada", "version": 2, "reason": "Ya no procede"}).status_code == 403  # sin task.cancel
    assert asesor.post(f"/api/v1/tasks/{t['id']}/transition", json={"to": "completada", "version": 2}).status_code == 200


def test_q623_no_se_modifican_tareas_ajenas(login, ids, db):
    lider = login("lider.laboral")
    case = _new_case(lider, ids, branch="Valencia").json()
    lider.post(f"/api/v1/cases/{case['id']}/assignments",
               json={"user_id": str(ids["users"]["gestor.laboral.vlc"]), "role_in_case": "gestor", "reason": "Tramitación"})
    t = _task(lider, ids, case["id"], "lider.laboral").json()
    gestor = login("gestor.laboral.vlc")
    seen = gestor.get(f"/api/v1/tasks/{t['id']}").json()
    assert seen["can_edit"] is False and seen["allowed_transitions"] == []
    r = gestor.post(f"/api/v1/tasks/{t['id']}/transition", json={"to": "completada", "version": 1})
    assert r.status_code == 403 and denied_events(db, "task.transition", t["id"])
    assert login("asesor.extranjeria.mad").get(f"/api/v1/tasks/{t['id']}").status_code == 404
    assert _task(lider, ids, case["id"], "asesor.extranjeria.mad").status_code == 422  # sin acceso al expediente


def test_agenda_solapes_y_orden(login):
    a = login("asesor.laboral.bcn")
    items = a.get("/api/v1/tasks", params={"scope": "mine"}).json()["items"]
    senal = [x for x in items if x["kind"] == "senalamiento"]
    assert len(senal) >= 2 and all(x["overlaps"] for x in senal)
    assert any(x["overdue"] for x in items)
    week = a.get("/api/v1/tasks/agenda/week").json()
    assert week["items"] and week["week_start"]


def test_senalamiento_exige_horario(login, ids):
    r = _task(login("asesor.laboral.bcn"), ids, ids["lucia_lab"], "asesor.laboral.bcn", kind="senalamiento")
    assert r.status_code == 422


def test_tareas_no_se_borran_y_historial_inmutable(db):
    from app.models_work import Task

    t = db.execute(select(Task).limit(1)).scalar_one()
    for stmt in (f"DELETE FROM task WHERE id='{t.id}'", f"DELETE FROM task_event WHERE task_id='{t.id}'"):
        with pytest.raises(Exception, match="inmutable"):
            db.execute(text(stmt))
        db.rollback()
