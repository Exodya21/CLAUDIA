"""F4.1 — Expediente de extranjería: catálogo validado, fases, lectura de documentos (MRZ), avisos de caducidad,
paquete para Mercurio y permisos. Pasaportes FICTICIOS (país «UTO» de la especificación OACI) generados aquí."""

from __future__ import annotations

import io
import random
import shutil
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import denied_events

OCR = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no instalado")
API = "/api/v1/immigration"


# ------------------------------------------------------------------ utilidades
def _new_case(db, materia="extranjeria", procedure=None, assignee="asesor.extranjeria.mad", given="Nerea",
              family="Pardo Prueba", birth=date(1990, 3, 14)):
    """Expediente FICTICIO nuevo (sede Madrid, Extranjería) con su contacto."""
    from app.immigration.sync import current
    from app.models import Branch, CaseAssignment, CaseFile, Contact, Department, Organization, UserAccount
    from app.models_immigration import ImmigCase, ImmigStageEvent
    from app.seed import ORG_ES, next_case_code
    from app.validation import fold

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one()
    br = db.execute(select(Branch).where(Branch.organization_id == es.id, Branch.name == "Madrid")).scalar_one()
    dept = db.execute(select(Department).where(Department.organization_id == es.id,
                                               Department.code == ("EXT" if materia == "extranjeria" else "NAC"))).scalar_one()
    users = {u.username: u for u in db.execute(select(UserAccount)).scalars()}
    creator = users["direccion.demo"]
    c = Contact(organization_id=es.id, primary_branch_id=br.id, given_name=given, family_names=family,
                search_name=fold(f"{given} {family}"), birth_date=birth, nationality="XX", is_synthetic=True,
                created_by=creator.id)
    db.add(c)
    db.flush()
    cf = CaseFile(organization_id=es.id, branch_id=br.id, department_id=dept.id, contact_id=c.id,
                  code=next_case_code(db, es.id, "EXT" if materia == "extranjeria" else "NAC", 2026), materia=materia,
                  title="Prueba F4.1 (ficticio)", status="abierto", confidential_summary="[FICTICIO]",
                  created_by=creator.id)
    db.add(cf)
    db.flush()
    if assignee:
        db.add(CaseAssignment(case_id=cf.id, user_id=users[assignee].id, role_in_case="responsable"))
    if procedure:
        pr = current(db, procedure)
        db.add(ImmigCase(case_id=cf.id, organization_id=es.id, procedure_id=pr.id, stage="documentacion",
                         created_by=creator.id))
        db.add(ImmigStageEvent(case_id=cf.id, actor_user_id=creator.id, to_stage="documentacion"))
    db.commit()
    return cf.id


def _number(seed: str) -> str:
    rnd = random.Random(seed)
    return "ZZ" + "".join(rnd.choice("2345679ACEFHKMNPRTUVWXY") for _ in range(7))


def _passport(surname="Pardo Prueba", given="Nerea", birth=date(1990, 3, 14), expiry=None, number=None, fmt="PNG"):
    from app.seed_immigration import passport_image

    png, _ = passport_image(surname, given, number or _number(f"{surname}{given}{expiry}"), birth,
                            expiry or date.today() + timedelta(days=2000))
    if fmt == "PNG":
        return png
    from PIL import Image

    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _pdf(title="Certificado de empadronamiento", lines=("Persona ficticia",)):
    from app.seed_immigration import text_pdf

    return text_pdf(title, list(lines))


def _upload(c, case_id, *files):
    h = {k: v for k, v in c.headers.items() if k.lower() != "content-type"}
    parts = [("files", (name, data, mime)) for name, data, mime in files]
    return c.post(f"{API}/cases/{case_id}/documents", files=parts, headers=h)


def _review(c, doc, doc_type, status="valido", **kw):
    body = {"doc_type": doc_type, "status": status, "version": doc["version"], "expires_on": doc["expires_on"],
            "issued_on": doc["issued_on"], **kw}
    r = c.post(f"{API}/documents/{doc['id']}/review", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ MRZ (unitarias)
def test_mrz_especimen_oaci_y_generada():
    from app.immigration import mrz

    spec = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
    r = mrz.parse(spec, date(2010, 1, 1))
    assert r["valid"] and r["surname"] == "ERIKSSON" and r["given_names"] == "ANNA MARIA"
    assert r["birth_date"] == "1974-08-12" and r["expiry_date"] == "2012-04-15"
    lines = mrz.build_td3("P", "UTO", "PRUEBA", "ANA", "ZZ1234567", "UTO", date(1990, 1, 2), "F", date(2031, 5, 6))
    assert mrz.parse("\n".join(lines))["valid"]
    # Un dígito alterado no supera el control; confusiones O/0 del OCR en campos de letras se corrigen
    bad = lines[1][:5] + ("1" if lines[1][5] != "1" else "2") + lines[1][6:]
    assert mrz.parse(lines[0] + "\n" + bad)["valid"] is False
    ocr = lines[0].replace("UTO", "UT0", 1) + "\n" + lines[1].replace("UTO", "UT0")
    assert mrz.parse(ocr)["nationality"] == "UTO"
    # Número con letras y cifras: la confusión O/0 se repara si una sola variante supera el control
    num = mrz.build_td3("P", "UTO", "PRUEBA", "ANA", "ZZC04C6F3", "UTO", date(1990, 3, 14), "F", date(2030, 12, 14))
    leido = num[1].replace("ZZC04", "ZZCO4")
    r = mrz.parse(num[0] + "\n" + leido)
    assert r["valid"] and r["document_number"] == "ZZC04C6F3"


def test_coincidencia_de_titular():
    from app.immigration.reader import name_matches

    assert name_matches("Nerea", "Pardo Prueba", {"given_names": "NEREA", "surname": "PARDO PRUEBA"}) is True
    assert name_matches("Nerea", "Pardo Prueba", {"given_names": "OMAR", "surname": "ROJAS DEMO"}) is False
    assert name_matches("Nerea", "Pardo Prueba", None) is None


# ------------------------------------------------------------------ catálogo
def test_catalogo_pendiente_de_validacion_y_solo_legal_lo_aprueba(login, db):
    c = login("asesor.extranjeria.mad")
    r = c.get(f"{API}/procedures").json()
    codes = {p["code"] for p in r["procedures"]}
    assert len(codes) == 14 and {"ARR-SOCIAL", "NAC-RESIDENCIA", "LD-UE", "REAG-FAM"} <= codes
    assert all(p["source_url"].startswith("https://") for p in r["procedures"])
    assert r["can_approve"] is False and r["mercurio"]["max_mb"] == 6
    pid = next(p["id"] for p in r["procedures"] if p["code"] == "EST-ESTUDIOS")
    assert c.post(f"{API}/procedures/{pid}/approve", json={}).status_code == 403
    lider = login("lider.extranjeria")
    r = lider.post(f"{API}/procedures/{pid}/approve", json={"note": "Revisado con la hoja oficial (prueba)"})
    assert r.status_code == 200 and r.json()["status"] == "aprobado" and r.json()["approved_by"]


def test_cambio_en_el_catalogo_crea_version_nueva_sin_tocar_expedientes(db):
    from app.immigration import catalog
    from app.immigration.sync import current, sync_procedures
    from app.models_immigration import ImmigProcedure

    proc = next(p for p in catalog.PROCEDURES if p["code"] == "MOD-RT")
    old = current(db, "MOD-RT")
    original = proc["note"]
    try:
        proc["note"] = (original or "") + " (cambio de prueba)"
        assert sync_procedures(db) == 1
        new = current(db, "MOD-RT")
        assert new.version == old.version + 1 and new.status == "pendiente_validacion"
        assert db.get(ImmigProcedure, old.id).status == "sustituido"
    finally:
        proc["note"] = original
        db.rollback()


# ------------------------------------------------------------------ alta del trámite
def test_alta_de_tramite_por_materia(login, db):
    cid = _new_case(db, materia="nacionalidad", assignee=None)
    d = login("direccion.demo")
    r = d.get(f"{API}/cases/{cid}").json()
    assert r["configured"] is False and [o["code"] for o in r["options"]] == ["NAC-RESIDENCIA"]
    assert d.post(f"{API}/cases/{cid}", json={"procedure_code": "ARR-SOCIAL"}).status_code == 422
    r = d.post(f"{API}/cases/{cid}", json={"procedure_code": "NAC-RESIDENCIA", "province": "Barcelona"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["stage"] == "documentacion" and body["procedure"]["mercurio"] is False
    assert any("pendiente de validar" in a["text"] for a in body["alerts"])
    assert d.post(f"{API}/cases/{cid}", json={"procedure_code": "NAC-RESIDENCIA"}).status_code == 409


# ------------------------------------------------------------------ documentos
@OCR
def test_lectura_de_pasaporte_propone_y_la_persona_confirma(login, db):
    cid = _new_case(db, procedure="ARR-SOCIOLABORAL")
    c = login("asesor.extranjeria.mad")
    exp = date.today() + timedelta(days=1500)
    r = _upload(c, cid, ("foto_pasaporte.jpg", _passport(expiry=exp, fmt="JPEG"), "image/jpeg"),
                ("padron.pdf", _pdf(lines=("Fecha de expedición: " + (date.today() - timedelta(days=10)).strftime("%d/%m/%Y"),)),
                 "application/pdf"))
    assert r.status_code == 201, r.text
    res = r.json()["results"]
    assert [x["suggested_type"] for x in res] == ["pasaporte", "empadronamiento"]
    assert res[0]["confidence"] == "alta"
    case = r.json()["case"]
    pas = next(d for d in case["documents"] if d["suggested_type"] == "pasaporte")
    assert pas["status"] == "pendiente_revision" and pas["doc_type"] is None
    assert pas["expires_on"] == exp.isoformat() and pas["mrz"]["valid"] and pas["mrz"]["nationality"] == "UTO"
    assert "Pendiente de revisar y confirmar" in pas["warnings"]
    pasaporte = next(x for x in case["checklist"] if x["doc_type"] == "pasaporte")
    assert pasaporte["state"] == "por_revisar"
    case = _review(c, pas, "pasaporte", label="Pasaporte")
    assert next(x for x in case["checklist"] if x["doc_type"] == "pasaporte")["state"] == "cumplido"
    pad = next(d for d in case["documents"] if d["suggested_type"] == "empadronamiento")
    assert pad["issued_on"] == (date.today() - timedelta(days=10)).isoformat()
    # El archivo se guarda cifrado y su descarga queda registrada
    from app.models import AuditEvent
    from app.services import vault

    r = c.get(f"{API}/documents/{pas['id']}/file")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    from app.models_immigration import ImmigDocument

    stored = (vault.documents_dir() / db.get(ImmigDocument, uuid.UUID(pas["id"])).file_path).read_bytes()
    assert not stored.startswith(b"\xff\xd8")
    db.rollback()
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "immig.document.read",
                                               AuditEvent.resource_id == str(cid))).first()


@OCR
def test_avisos_caducado_titular_distinto_y_duplicado(login, db):
    cid = _new_case(db, procedure="REN-RT-CA")
    c = login("asesor.extranjeria.mad")
    caducado = _passport(expiry=date.today() - timedelta(days=5))
    otro = _passport(surname="Rojas Demo", given="Omar", birth=date(1985, 6, 1))
    r = _upload(c, cid, ("a.png", caducado, "image/png"), ("b.png", otro, "image/png"), ("c.png", caducado, "image/png"))
    case = r.json()["case"]
    texts = " | ".join(a["text"] for a in case["alerts"])
    assert "Caducado el" in texts
    assert "no coincide con el cliente" in texts
    # F4.3: el mismo archivo no se guarda dos veces en el expediente
    assert r.json()["results"][2]["ok"] is False and "Ya estaba subido" in r.json()["results"][2]["error"]
    docs = case["documents"]
    assert len(docs) == 2
    case = _review(c, docs[0], "pasaporte")
    assert next(x for x in case["checklist"] if x["doc_type"] == "pasaporte")["state"] == "caducado"
    # Rechazar exige motivo; retirar lo saca del expediente sin borrarlo
    assert c.post(f"{API}/documents/{docs[1]['id']}/review",
                  json={"doc_type": "pasaporte", "status": "rechazado", "version": docs[1]["version"]}).status_code == 422
    case = c.post(f"{API}/documents/{docs[1]['id']}/retire", json={"reason": "Subido por error"}).json()
    assert docs[1]["id"] not in [d["id"] for d in case["documents"]]
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM immig_document WHERE id = :i"), {"i": docs[1]["id"]})
    db.rollback()


def test_formatos_no_admitidos_y_limites(login, db):
    cid = _new_case(db, procedure="ARR-SOCIAL")
    c = login("asesor.extranjeria.mad")
    r = _upload(c, cid, ("nota.txt", b"texto plano", "text/plain"), ("vacio.pdf", b"", "application/pdf"))
    assert r.status_code == 201 and [x["ok"] for x in r.json()["results"]] == [False, False]
    many = [(f"{i}.pdf", _pdf(lines=(str(i),)), "application/pdf") for i in range(21)]
    assert _upload(c, cid, *many).status_code == 422


# ------------------------------------------------------------------ fases
def test_fases_requerimiento_crea_tarea_sin_calcular_plazo(login, db):
    from app.models_work import Task

    cid = _new_case(db, procedure="ARR-FAMILIAR")
    c = login("asesor.extranjeria.mad")
    case = c.get(f"{API}/cases/{cid}").json()
    assert "resolucion_favorable" not in case["next_stages"]
    assert c.post(f"{API}/cases/{cid}/stage", json={"to": "presentado"}).status_code == 422  # salto no permitido
    for to in ("preparacion", "lista_presentar"):
        assert c.post(f"{API}/cases/{cid}/stage", json={"to": to}).status_code == 200
    r = c.post(f"{API}/cases/{cid}/stage", json={"to": "presentado"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "faltan_documentos"
    assert c.post(f"{API}/cases/{cid}/stage", json={"to": "presentado", "date": (date.today() + timedelta(days=1)).isoformat(),
                                                   "note": "Se presenta por urgencia de plazo"}).status_code == 422
    r = c.post(f"{API}/cases/{cid}/stage", json={"to": "presentado", "registry_number": "REGAGE-PRUEBA-1",
                                                 "note": "Se presenta por urgencia; el resto se aporta después"})
    assert r.status_code == 200 and r.json()["registry_number"] == "REGAGE-PRUEBA-1"
    assert r.json()["events"][-1]["data"]["faltaban"]
    assert c.post(f"{API}/cases/{cid}/stage", json={"to": "requerimiento"}).status_code == 422  # sin nota
    r = c.post(f"{API}/cases/{cid}/stage", json={"to": "requerimiento", "date": date.today().isoformat(),
                                                 "note": "Piden informe de vivienda actualizado"})
    assert r.status_code == 200
    task_id = r.json()["events"][-1]["data"]["tarea"]
    db.rollback()
    t = db.get(Task, uuid.UUID(task_id))
    assert t.kind == "plazo" and t.legal_deadline is None and t.legal_status == "no_aplica"
    assert "no calcula el plazo legal" in t.description
    # Fase con efecto jurídico: la asesora no puede; el líder sí, con fecha de resolución
    c.post(f"{API}/cases/{cid}/stage", json={"to": "requerimiento_respondido", "note": "Aportado"})
    r = c.post(f"{API}/cases/{cid}/stage", json={"to": "resolucion_favorable", "date": date.today().isoformat()})
    assert r.status_code == 403
    assert denied_events(db, "immig.stage.resolucion_favorable", cid)
    lider = login("lider.extranjeria")
    assert lider.post(f"{API}/cases/{cid}/stage", json={"to": "resolucion_favorable"}).status_code == 422
    r = lider.post(f"{API}/cases/{cid}/stage", json={"to": "resolucion_favorable", "date": date.today().isoformat()})
    assert r.status_code == 200 and r.json()["resolution_at"] == date.today().isoformat()
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE immig_stage_event SET note = 'x' WHERE case_id = :c"), {"c": cid})
    db.rollback()


def test_conflicto_de_version(login, db):
    cid = _new_case(db, procedure="ARR-SOCIAL")
    c = login("asesor.extranjeria.mad")
    v = c.get(f"{API}/cases/{cid}").json()["version"]
    assert c.patch(f"{API}/cases/{cid}", json={"province": "Madrid", "version": v}).status_code == 200
    assert c.patch(f"{API}/cases/{cid}", json={"province": "Toledo", "version": v}).status_code == 409


# ------------------------------------------------------------------ permisos
def test_permisos_por_departamento_y_entidad(login, db, ids):
    cid = _new_case(db, procedure="ARR-SOCIAL")
    lab = login("asesor.laboral.bcn")
    assert lab.get(f"{API}/cases/{cid}").status_code == 403
    assert denied_events(db, "immig.read", cid)
    assert lab.get(f"{API}/cases/{ids['lucia_ext']}").status_code == 403
    otra = login("asesor.laboral.autonomo")
    assert otra.get(f"{API}/cases/{cid}").status_code == 404
    assert lab.get(f"{API}/inbox").json()["cases"] == []
    mk = login("atc.demo")
    assert mk.get(f"{API}/cases/{cid}/package/check").status_code == 403


def test_recepcion_sube_pero_no_ve_ni_revisa(login, db):
    cid = _new_case(db, procedure="ARR-SOCIAL")
    rec = login("recepcion.bcn")
    r = _upload(rec, cid, ("padron.pdf", _pdf(), "application/pdf"))
    assert r.status_code == 201 and r.json()["results"][0]["ok"] and "case" not in r.json()
    doc_id = r.json()["results"][0]["id"]
    assert rec.get(f"{API}/cases/{cid}").status_code == 403
    assert rec.get(f"{API}/documents/{doc_id}/file").status_code == 403
    assert rec.post(f"{API}/documents/{doc_id}/review",
                    json={"doc_type": "empadronamiento", "status": "valido", "version": 1}).status_code == 403


# ------------------------------------------------------------------ paquete para Mercurio
def test_paquete_mercurio(login, db):
    from app.immigration.catalog import PROCEDURES

    cid = _new_case(db, procedure="EST-ESTUDIOS")
    c = login("asesor.extranjeria.mad")
    chk = c.get(f"{API}/cases/{cid}/package/check").json()
    assert chk["ready"] is False and chk["blocking"]
    assert c.get(f"{API}/cases/{cid}/package.zip").status_code == 422
    # Se aportan todos los obligatorios como PDF/PNG ficticios y se confirman a mano
    req = [r for r in next(p for p in PROCEDURES if p["code"] == "EST-ESTUDIOS")["requirements"] if r["kind"] == "obligatorio"]
    files = []
    for i, r in enumerate(req):
        if r["doc_type"] == "pasaporte":
            files.append((f"{i}.png", _passport(), "image/png"))
        else:
            files.append((f"{i}.pdf", _pdf(r["label"], (uuid.uuid4().hex,)), "application/pdf"))
    case = _upload(c, cid, *files).json()["case"]
    for i, r in enumerate(req):
        doc = next(d for d in case["documents"] if d["original_name"] == files[i][0])
        case = _review(c, doc, r["doc_type"], label=r["label"])
    chk = c.get(f"{API}/cases/{cid}/package/check").json()
    assert chk["ready"] is True, chk
    r = c.get(f"{API}/cases/{cid}/package.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "00_INDICE.txt" in names and "00_DATOS_FORMULARIO.txt" in names
    assert not any(n.endswith(".png") for n in names)  # PNG convertido a JPG (Mercurio no admite PNG)
    jpg = next(n for n in names if n.endswith(".jpg"))
    assert z.read(jpg).startswith(b"\xff\xd8")
    assert all(z.getinfo(n).file_size <= 6 * 1024 * 1024 for n in names)
    ficha = z.read("00_DATOS_FORMULARIO.txt").decode()
    assert "Pardo Prueba" in ficha and "EX-00" in ficha
    assert c.get(f"{API}/cases/{cid}/package.zip").status_code == 200
    rec = login("recepcion.bcn")
    assert rec.get(f"{API}/cases/{cid}/package.zip").status_code == 403


def test_bandeja_y_semilla(login, db):
    c = login("asesor.extranjeria.mad")
    r = c.get(f"{API}/inbox").json()
    assert r["cases"] and sum(r["counts"].values()) >= len(r["cases"])
    assert any(x["expiry_alert"] for x in r["cases"])  # la semilla incluye un pasaporte caducado y otro a punto
    r2 = c.get(f"{API}/inbox", params={"stage": "requerimiento"}).json()
    assert all(x["stage"] == "requerimiento" for x in r2["cases"])
    d = login("direccion.demo")
    assert len(d.get(f"{API}/inbox").json()["cases"]) >= len(r["cases"])
    _ = datetime.now(UTC)
