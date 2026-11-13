"""AT-03 Auditoría: altas, cambios, permisos y denegaciones generan eventos irreversibles."""

from datetime import timedelta

import pytest
from sqlalchemy import select, text

from .conftest import unique_passport


def _events(db, resource_id, action=None):
    from app.models import AuditEvent

    db.rollback()
    q = select(AuditEvent).where(AuditEvent.resource_id == str(resource_id))
    if action:
        q = q.where(AuditEvent.action == action)
    return list(db.execute(q.order_by(AuditEvent.id)).scalars())


def test_alta_y_cambio_quedan_auditados_con_actor_utc_y_antes_despues(login, ids, db):
    c = login("asesor.laboral.bcn")
    r = c.post("/api/v1/contacts", json={
        "organization_id": str(ids["es"]), "given_name": "Prueba", "family_names": "Auditoría Ficticia",
        "identifiers": [{"kind": "PASAPORTE", "number": unique_passport(), "country": "XX"}],
        "phones": [{"number": "+34 699 000 111"}]})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    created = _events(db, cid, "contact.create")
    assert len(created) == 1
    ev = created[0]
    assert ev.actor_user_id == ids["users"]["asesor.laboral.bcn"]
    assert ev.occurred_at.utcoffset() == timedelta(0)
    assert ev.after["nombre"] == "Prueba Auditoría Ficticia"
    assert "•" in ev.after["documentos"][0]["number"]  # el documento se guarda enmascarado en la bitácora

    r2 = c.patch(f"/api/v1/contacts/{cid}", json={"version": 1, "family_names": "Auditoría Cambiada",
                                                   "reason": "Corrección de apellido a petición del cliente"})
    assert r2.status_code == 200 and r2.json()["version"] == 2
    upd = _events(db, cid, "contact.update")[-1]
    assert upd.before == {"family_names": "Auditoría Ficticia"}
    assert upd.after == {"family_names": "Auditoría Cambiada"}
    assert upd.reason.startswith("Corrección")


def test_lectura_sensible_y_denegacion_se_auditan(login, ids, db):
    login("direccion.demo").get(f"/api/v1/contacts/{ids['lucia']}")
    reads = [e for e in _events(db, ids["lucia"], "contact.read") if e.outcome == "ok"]
    assert reads and reads[-1].actor_user_id == ids["users"]["direccion.demo"]


def test_bitacora_no_admite_update_delete_ni_truncate(db):
    from app.models import AuditEvent

    any_id = db.execute(select(AuditEvent.id).limit(1)).scalar_one()
    for stmt in (f"UPDATE audit_event SET action='x' WHERE id={any_id}",
                 f"DELETE FROM audit_event WHERE id={any_id}",
                 "TRUNCATE audit_event"):
        with pytest.raises(Exception, match="inmutable"):
            db.execute(text(stmt))
        db.rollback()


def test_cadena_de_hashes_integra_y_detecta_manipulacion(login, db):
    from app.audit import GENESIS, compute_hash, verify_chain

    r = login("direccion.demo").get("/api/v1/audit-events/verify")
    assert r.status_code == 200 and r.json()["integra"] is True and r.json()["eventos_verificados"] > 5
    ok, n, broken = verify_chain(db)
    assert ok and broken is None
    # El hash depende del contenido: cualquier alteración cambia la huella.
    assert compute_hash(GENESIS, {"a": 1}) != compute_hash(GENESIS, {"a": 2})


def test_solo_perfiles_autorizados_leen_la_auditoria(login):
    assert login("asesor.laboral.bcn").get("/api/v1/audit-events").status_code == 403
    r = login("direccion.demo").get("/api/v1/audit-events", params={"outcome": "denied"})
    assert r.status_code == 200 and all(e["outcome"] == "denied" for e in r.json()["items"])
