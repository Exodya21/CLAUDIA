"""F4.2 — Ficha de datos del modelo EX, borrador del PDF oficial, datos del despacho y código para la extensión
de Mercurio. Todo con datos ficticios."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime, timedelta

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from .conftest import denied_events
from .test_f41_extranjeria import _new_case

API = "/api/v1/immigration"


def _with_passport(db, cid, number="ZZ1234567", sex="F", nat="UTO", birth="1990-03-14"):
    """Pasaporte ficticio ya revisado con su MRZ (sin pasar por la lectura, que se prueba en F4.1)."""
    from app.models import UserAccount
    from app.models_immigration import ImmigDocument

    uid = db.execute(select(UserAccount.id).where(UserAccount.username == "asesor.extranjeria.mad")).scalar_one()
    cf = db.execute(text("SELECT organization_id FROM case_file WHERE id = :c"), {"c": cid}).scalar_one()
    db.add(ImmigDocument(organization_id=cf, case_id=cid, status="valido", doc_type="pasaporte", original_name="p.png",
                         mime="image/png", size_bytes=10, sha256=uuid.uuid4().hex * 2, file_path="x.bin",
                         extracted={"mrz": {"valid": True, "document_number": number, "sex": sex, "nationality": nat,
                                            "birth_date": birth}},
                         uploaded_by=uid, reviewed_by=uid, reviewed_at=datetime.now(UTC)))
    db.commit()


# ------------------------------------------------------------------ modelos
def test_dieciseis_modelos_con_mapa_y_pdf_relleno():
    from app.immigration import forms

    av = forms.available()
    assert set(av) == {"EX00", "EX01", "EX02", "EX03", "EX04", "EX06", "EX07", "EX09", "EX10", "EX11", "EX13",
                       "EX15", "EX16", "EX17", "EX18", "EX20"}
    for code, data in av.items():
        keys = {m["key"] for m in data["fields"].values()}
        assert {"ext.apellido1", "ext.nombre", "ext.pasaporte", "rep.nombre", "notif.domicilio"} <= keys, code
        parts = sorted(m.get("part") for m in data["fields"].values() if m["key"] == "ext.nie")
        assert parts == ["1", "2", "3"], code
    vals = {"ext.apellido1": "PRUEBA", "ext.nombre": "ANA", "ext.nie": "X-1234567-L", "ext.fecha_nacimiento": "1990-03-14",
            "ext.sexo": "M", "rep.nombre": "Despacho ficticio"}
    opt = forms.spec("EX10")["options"]
    social = next(o["field"] for o in opt if o["label"].startswith("Arraigo social"))
    pdf = forms.fill_pdf("EX10", vals, [social], {})
    f = pypdf.PdfReader(io.BytesIO(pdf)).get_fields()
    got = {k: str(v.get("/V")) for k, v in f.items() if v.get("/V") not in (None, "", "/Off")}
    assert got["Texto5"] == "PRUEBA" and got["Texto7"] == "ANA"
    assert (got["Texto2"], got["Texto3"], got["Texto4"]) == ("X", "1234567", "L")
    assert (got["Texto8"], got["Texto9"], got["Texto10"]) == ("14", "03", "1990")
    assert got["Casilla de verificación98"] == "/Yes"  # sexo M
    assert got[social] == "/Yes"
    assert "Texto153" not in got  # la firma queda en blanco


# ------------------------------------------------------------------ ficha
def test_ficha_propone_desde_pasaporte_y_despacho_y_solo_guarda_lo_confirmado(login, db):
    cid = _new_case(db, procedure="ARR-SOCIAL", given="Ana", family="Prueba Ficticia")
    _with_passport(db, cid)
    c = login("asesor.extranjeria.mad")
    r = c.get(f"{API}/cases/{cid}/form").json()
    assert r["available"] and r["model"] == "EX10" and r["values"] == {} and r["version"] is None
    pr = r["proposals"]
    assert pr["ext.pasaporte"] == {"value": "ZZ1234567", "source": "pasaporte"}
    assert pr["ext.sexo"]["value"] == "M" and pr["ext.apellido1"]["value"] == "Prueba"
    assert pr["rep.nombre"]["source"] == "despacho" and pr["notif.nombre"]["source"] == "despacho"
    assert pr["sol.firma_anio"]["value"] == str(date.today().year)
    # Validación
    bad = c.put(f"{API}/cases/{cid}/form", json={"model": "EX10", "values": {
        "ext.nie": "123", "ext.fecha_nacimiento": (date.today() + timedelta(days=3)).isoformat(),
        "ext.inventado": "x", "ext.sexo": "Z"}})
    assert bad.status_code == 422
    fields = {d["field"] for d in bad.json()["error"]["details"]}
    assert {"ext.nie", "ext.fecha_nacimiento", "ext.inventado", "ext.sexo"} <= fields
    values = {k: v["value"] for k, v in pr.items()} | {"ext.nie": "x-1234567-l", "ext.estado_civil": "S"}
    opts = [o["field"] for o in r["spec"]["options"] if o["label"].startswith("Arraigo social")]
    r = c.put(f"{API}/cases/{cid}/form", json={"model": "EX10", "values": values, "options": opts})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["values"]["ext.nie"] == "X-1234567-L" and body["proposals"] == {} and body["version"] == 1
    assert c.put(f"{API}/cases/{cid}/form", json={"model": "EX10", "values": values, "version": 7}).status_code == 409
    # La auditoría guarda las claves cambiadas, nunca los valores
    from app.models import AuditEvent

    db.rollback()
    ev = db.execute(select(AuditEvent).where(AuditEvent.action == "immig.form.save",
                                             AuditEvent.resource_id == str(cid))).scalars().first()
    blob = str(ev.after)
    assert "ext.pasaporte" in blob and "ZZ1234567" not in blob and "1234567" not in blob


def test_borrador_pdf_y_permisos(login, db):
    cid = _new_case(db, procedure="REN-RT-CA", given="Omar", family="Rojas Demo")
    c = login("asesor.extranjeria.mad")
    assert c.get(f"{API}/cases/{cid}/form.pdf").status_code == 409  # sin ficha guardada
    r = c.get(f"{API}/cases/{cid}/form").json()
    assert r["model"] == "EX03"
    c.put(f"{API}/cases/{cid}/form", json={"model": "EX03", "values": {"ext.nombre": "Omar", "ext.apellido1": "Rojas",
                                                                       "emp.nombre": "Empresa Ficticia SL"}})
    pdf = c.get(f"{API}/cases/{cid}/form.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert "VISTA_PREVIA_EX-03" in pdf.headers["content-disposition"]
    vals = {str(v.get("/V")) for v in pypdf.PdfReader(io.BytesIO(pdf.content)).get_fields().values()}
    assert {"Omar", "Rojas", "Empresa Ficticia SL"} <= vals
    assert login("asesor.laboral.bcn").get(f"{API}/cases/{cid}/form").status_code == 403
    assert denied_events(db, "immig.form.read", cid)
    rec = login("recepcion.bcn")
    assert rec.get(f"{API}/cases/{cid}/form.pdf").status_code == 403
    assert rec.put(f"{API}/cases/{cid}/form", json={"model": "EX03", "values": {}}).status_code == 403
    assert login("asesor.laboral.autonomo").get(f"{API}/cases/{cid}/form").status_code == 404


def test_datos_del_despacho_solo_direccion_o_lider(login, ids):
    org = str(ids["es"])
    a = login("asesor.extranjeria.mad")
    office = a.get(f"{API}/office").json()["offices"][0]
    assert office["can_edit"] is False and office["data"]["rep.nombre"]
    assert a.put(f"{API}/office/{org}", json={"data": {"rep.nombre": "X"}}).status_code == 403
    lider = login("lider.extranjeria")
    cur = lider.get(f"{API}/office").json()["offices"][0]
    data = cur["data"] | {"rep.email": "no-es-correo"}
    assert lider.put(f"{API}/office/{org}", json={"data": data, "version": cur["version"]}).status_code == 422
    data["rep.email"] = "otra@demo.invalid"
    r = lider.put(f"{API}/office/{org}", json={"data": data, "version": cur["version"]})
    assert r.status_code == 200 and r.json()["data"]["rep.email"] == "otra@demo.invalid"
    assert lider.put(f"{API}/office/{org}", json={"data": {"rep.otro": "x"}}).status_code == 422
    assert login("asesor.laboral.bcn").get(f"{API}/office").status_code == 403


# ------------------------------------------------------------------ código para la extensión
def test_codigo_para_extension(app, login, db):
    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Lucas", family="Demo Prueba")
    c = login("asesor.extranjeria.mad")
    assert c.post(f"{API}/cases/{cid}/fill-token").status_code == 409  # sin ficha
    c.put(f"{API}/cases/{cid}/form", json={"model": "EX10", "values": {"ext.nombre": "Lucas", "ext.sexo": "H"}})
    r = c.post(f"{API}/cases/{cid}/fill-token")
    assert r.status_code == 201
    code = r.json()["code"]
    assert len(code) == 14 and code.count("-") == 2
    ext = TestClient(app)  # sin sesión, como la extensión
    data = ext.get(f"{API}/fill/{code.lower()}").json()
    assert data["values"] == {"ext.nombre": "Lucas", "ext.sexo": "H"} and data["model"] == "EX-10"
    assert data["choices"]["ext.sexo"]["H"] == "Hombre" and data["uses_left"] == 9
    assert "notice" in data and data["case_code"].startswith("EXT-")
    # Código inventado → 404 registrado
    assert ext.get(f"{API}/fill/AAAA-BBBB-CCCC").status_code == 404
    # Agotado y caducado
    from app.models_immigration import ImmigFillToken

    db.rollback()
    t = db.execute(select(ImmigFillToken).where(ImmigFillToken.case_id == cid)).scalar_one()
    t.uses = t.max_uses
    db.commit()
    assert ext.get(f"{API}/fill/{code}").status_code == 404
    t.uses, t.expires_at = 0, datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert ext.get(f"{API}/fill/{code}").status_code == 404
    assert db.execute(select(ImmigFillToken.token_hash).where(ImmigFillToken.case_id == cid)).scalar_one() != code
    # Recepción no puede generar códigos
    assert login("recepcion.bcn").post(f"{API}/cases/{cid}/fill-token").status_code == 403


@pytest.mark.parametrize("code", ["EX02", "EX03", "EX11"])
def test_spec_agrupa_por_apartado(code):
    from app.immigration import forms

    sp = forms.spec(code)
    roles = [r["role"] for r in sp["roles"]]
    assert roles[0] == "ext" and "rep" in roles and "notif" in roles
    assert all(f["label"] for r in sp["roles"] for f in r["fields"])


def test_mapa_de_campos_reproducible():
    """Los EXnn.json del repositorio salen tal cual del script a partir de los PDF oficiales."""
    pytest.importorskip("pdfplumber")
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("exb", root / "scripts/ex_forms_build.py")
    exb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exb)
    for code in ("EX02", "EX03", "EX11"):
        pdf = exb.FORMS / "pdf" / f"{code}.pdf"
        data = exb.assign(exb.analyze(pdf))
        saved = json.loads((exb.FORMS / f"{code}.json").read_text(encoding="utf-8"))
        assert data["fields"] == saved["fields"], code


def test_ficha_general_para_modelos_sin_pdf(login, db):
    """MOD-RT se presenta con el EX-26, cuyo editable no está cargado: la ficha usa los datos comunes de Mercurio."""
    cid = _new_case(db, procedure="MOD-RT", given="Irene", family="Prueba Demo")
    c = login("asesor.extranjeria.mad")
    r = c.get(f"{API}/cases/{cid}/form").json()
    assert r["model"] == "GENERAL" and r["spec"]["pdf"] is False and r["procedure_model"].startswith("EX-26")
    keys = {f["key"] for role in r["spec"]["roles"] for f in role["fields"]}
    assert {"ext.tipo_via", "ext.municipio", "ext.escalera", "ext.rl_doc_tipo", "emp.nombre", "notif.cp"} <= keys
    r = c.put(f"{API}/cases/{cid}/form", json={"model": "GENERAL", "values": {"ext.nombre": "Irene", "ext.rl_doc_tipo": "NIE"}})
    assert r.status_code == 200
    assert c.get(f"{API}/cases/{cid}/form.pdf").status_code == 409
    assert c.post(f"{API}/cases/{cid}/fill-token").status_code == 201


def test_domicilio_compuesto_en_el_pdf():
    from app.immigration import forms

    pdf = forms.fill_pdf("EX03", {"ext.tipo_via": "Calle", "ext.domicilio": "Inventada", "ext.escalera": "B",
                                  "ext.piso": "3", "ext.letra": "A", "ext.municipio": "Getafe"}, [], {})
    vals = {str(v.get("/V")) for v in pypdf.PdfReader(io.BytesIO(pdf)).get_fields().values()}
    assert "Calle Inventada, Esc. B" in vals and "3 A" in vals and "Getafe" in vals
