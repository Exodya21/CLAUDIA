"""F4.3 — Lectura de contrato, padrón, TIE, tasa y pasaporte para proponer datos a la ficha del formulario.

Todo con documentos FICTICIOS generados en `app/immigration/samples.py` (empresa, CIF y N.I.E. inventados pero con
letra de control válida). La lectura propone; solo lo que una persona marca «válido» llega a la ficha, y la ficha
solo se usa cuando la persona la guarda."""

from __future__ import annotations

import io
from datetime import date

import pytest

from .test_f41_extranjeria import _new_case, _review, _upload

API = "/api/v1/immigration"
PDF = "application/pdf"


# ------------------------------------------------------------------ unitarias
def test_validadores_de_documentos_espanoles():
    from app.immigration import extract as x

    assert x.valid_dni("12345678Z") and not x.valid_dni("12345678A")
    assert x.valid_nie("Y7654321G") and x.valid_nie("X1234567L") and not x.valid_nie("Y7654321A")
    assert x.valid_cif("B12345674") and not x.valid_cif("B12345670")
    ids = x.find_ids("CIF: B-12345674 · trabajador NIE Y-7654321-G · otro 12345678Z · basura Y7654321A")
    assert ids["cif"] == ["B12345674"] and ids["nie"] == ["Y7654321G"] and ids["dni"] == ["12345678Z"]


@pytest.mark.parametrize("raw,expect", [
    ("C/ Mayor 12, 3º B, 28013 MADRID",
     {"tipo_via": "Calle", "domicilio": "Mayor", "numero": "12", "piso": "3", "letra": "B", "cp": "28013",
      "provincia": "Madrid", "municipio": "Madrid"}),
    ("Avenida de la Constitución, nº 45, Esc. 2, piso 4 izq, 08001 Barcelona",
     {"tipo_via": "Avenida", "numero": "45", "escalera": "2", "piso": "4", "cp": "08001", "provincia": "Barcelona"}),
    ("PLAZA ESPAÑA 3 BAJO, 41001 SEVILLA (SEVILLA)", {"tipo_via": "Plaza", "numero": "3", "cp": "41001", "provincia": "Sevilla"}),
])
def test_domicilio_se_descompone_como_lo_pide_mercurio(raw, expect):
    from app.immigration.extract import split_address

    got = split_address(raw)
    for k, v in expect.items():
        assert got.get(k) == v, (k, got)


def test_contrato_texto_y_escaneado():
    from app.immigration import reader, samples

    for scanned in (False, True):
        r = reader.read(samples.contrato(scanned=scanned), PDF)
        f = r["fields"]["ficha"]
        assert r["suggested_type"] == "contrato_trabajo"
        assert f["emp.nombre"] == "Construcciones Ficticias Demo SL" and f["emp.doc"] == "B12345674"
        assert f["con.ccc"] == "28123456789" and f["emp.cnae"] == "4121"
        assert (f["emp.tipo_via"], f["emp.domicilio"], f["emp.numero"], f["emp.cp"]) == ("Calle", "Inventada", "10", "28001")
        assert f["con.centro_cp"] == "28002" and f["con.puesto"] == "Peón de la construcción"
        assert f["con.contrato_codigo"] == "100" and f["emp.rl_doc"] == "12345678Z" and f["ext.nie"] == "Y7654321G"
        assert "18.000" in f["con.retribucion"]


def test_padron_escaneado_tasa_y_tie():
    from app.immigration import reader, samples

    p = reader.read(samples.padron(), PDF)
    assert p["suggested_type"] == "empadronamiento"
    assert {k: p["fields"]["ficha"].get(k) for k in ("ext.domicilio", "ext.numero", "ext.cp", "ext.municipio", "ext.provincia")} == {
        "ext.domicilio": "Ficticia", "ext.numero": "14", "ext.cp": "28901", "ext.municipio": "Getafe", "ext.provincia": "Madrid"}
    t = reader.read(samples.tasa(), PDF)
    assert t["suggested_type"] == "tasa_790" and t["fields"]["info"]["nrc"] == "0520000000000000000ABCD1"
    tie = reader.read(samples.tie_image(), "image/png")
    assert tie["suggested_type"] == "tie_nie"
    assert tie["fields"]["ficha"]["ext.nie"] == "Y7654321G" and tie["fields"]["ficha"]["ext.apellido1"] == "Ferrer"


def test_pasaporte_en_pdf_escaneado_de_varias_paginas():
    """Los pasaportes llegan como PDF escaneado de muchas páginas: la MRZ se busca página a página."""
    from PIL import Image

    from app.immigration import reader
    from app.seed_immigration import passport_image

    png, _ = passport_image("Prueba Demo", "Ana", "ZZ1234567", date(1992, 5, 20), date(2031, 1, 1))
    pages = [Image.new("RGB", (1654, 2339), "white"), Image.open(io.BytesIO(png)).convert("RGB")]
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=200)
    r = reader.read(buf.getvalue(), PDF)
    assert r["suggested_type"] == "pasaporte" and r["fields"]["ficha"]["ext.pasaporte"] == "ZZ1234567"


def test_mrz_q_por_cero_en_el_numero():
    from app.immigration import mrz

    assert mrz._repair_number("EQ0000001", mrz.check_digit("E00000001")) == "E00000001"


# ------------------------------------------------------------------ flujo con la API
def _docs(r):
    assert r.status_code == 201, r.text
    return {d["original_name"]: d for d in r.json()["case"]["documents"]}


def test_datos_leidos_solo_pasan_a_la_ficha_al_validar_el_documento(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Carla", family="Ferrer Demo")
    c = login("asesor.extranjeria.mad")
    up = _upload(c, cid, ("contrato.pdf", samples.contrato(), PDF), ("padron.pdf", samples.padron(), PDF))
    docs = _docs(up)
    k = docs["contrato.pdf"]
    assert k["extracted"]["ficha"]["emp.doc"] == "B12345674" and k["status"] == "pendiente_revision"
    # Antes de revisar: nada del contrato en la ficha
    form = c.get(f"{API}/cases/{cid}/form").json()
    assert "emp.nombre" not in form["proposals"]
    # Validado: propuesta con su origen
    after = _review(c, k, "contrato_trabajo")
    _review(c, {d["original_name"]: d for d in after["documents"]}["padron.pdf"], "empadronamiento")
    form = c.get(f"{API}/cases/{cid}/form").json()
    pr = form["proposals"]
    assert pr["emp.nombre"] == {"value": "Construcciones Ficticias Demo SL", "source": "documento: Contrato de trabajo"}
    assert pr["con.ccc"]["value"] == "28123456789" and pr["con.puesto"]["value"] == "Peón de la construcción"
    assert pr["ext.cp"]["value"] == "28901" and pr["ext.cp"]["source"] == "documento: Certificado de empadronamiento"
    # Nada queda guardado hasta que la persona confirma
    assert form["values"] == {}
    vals = {k2: v["value"] for k2, v in pr.items()}
    ok = c.put(f"{API}/cases/{cid}/form", json={"model": form["model"], "values": vals, "options": [], "extra": {}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["values"]["emp.doc"] == "B12345674"


def test_documentos_que_se_contradicen_quedan_a_la_vista(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Carla", family="Ferrer Demo")
    c = login("asesor.extranjeria.mad")
    up = _upload(c, cid, ("tie.png", samples.tie_image(nie="Y7654321G"), "image/png"),
                 ("contrato.pdf", samples.contrato(nie="X1234567L"), PDF))
    docs = _docs(up)
    r = _review(c, docs["tie.png"], "tie_nie")
    _review(c, {d["original_name"]: d for d in r["documents"]}["contrato.pdf"], "contrato_trabajo")
    form = c.get(f"{API}/cases/{cid}/form").json()
    nie = form["proposals"]["ext.nie"]
    values = {nie["value"]} | {o["value"] for o in nie.get("others", [])}
    assert values == {"Y7654321G", "X1234567L"}
    # Guardado un valor, un documento confirmado que diga otra cosa se avisa sin cambiar nada
    saved = c.put(f"{API}/cases/{cid}/form", json={"model": form["model"], "values": {"ext.nie": "Y7654321G"},
                                                    "options": [], "extra": {}}).json()
    assert saved["values"]["ext.nie"] == "Y7654321G"
    assert saved["differs"]["ext.nie"] == {"value": "X1234567L", "source": "documento: Contrato de trabajo"}


def test_tipo_corregido_vuelve_a_extraer_y_tasa_sin_nrc_avisa(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIAL")
    c = login("asesor.extranjeria.mad")
    up = _upload(c, cid, ("tasa.pdf", samples.tasa(nrc=""), PDF), ("doc.pdf", samples.contrato(), PDF))
    docs = _docs(up)
    assert any("NRC" in w for w in docs["tasa.pdf"]["warnings"])
    # La persona dice que «doc.pdf» es otra cosa: la propuesta de contrato desaparece
    r = _review(c, docs["doc.pdf"], "nominas")
    d = {x["original_name"]: x for x in r["documents"]}["doc.pdf"]
    assert "ficha" not in (d["extracted"] or {})
    form = c.get(f"{API}/cases/{cid}/form").json()
    assert "emp.doc" not in form["proposals"]


def test_la_auditoria_no_guarda_lo_leido(login, db):
    from sqlalchemy import text

    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL")
    c = login("asesor.extranjeria.mad")
    up = _upload(c, cid, ("contrato.pdf", samples.contrato(), PDF))
    _review(c, _docs(up)["contrato.pdf"], "contrato_trabajo")
    rows = db.execute(text("SELECT coalesce(before::text,'') || coalesce(after::text,'') FROM audit_event "
                           "WHERE resource_id = :c"), {"c": str(cid)}).scalars().all()
    assert rows and not any("B12345674" in r or "Y7654321G" in r for r in rows)


def test_documento_de_otra_persona_no_propone_datos_personales(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Nerea", family="Pardo Prueba")
    c = login("asesor.extranjeria.mad")
    up = _upload(c, cid, ("tie.png", samples.tie_image(), "image/png"))
    tie = _docs(up)["tie.png"]
    assert any("no coincide" in w for w in tie["warnings"])
    _review(c, tie, "tie_nie")
    form = c.get(f"{API}/cases/{cid}/form").json()
    assert form["proposals"].get("ext.nie", {}).get("source", "").startswith("documento:") is False


# ------------------------------------------------------------------ correcciones tras la prueba con documentos reales
PADRON_TABLA = """EXCMO. AYUNTAMIENTO DE VILLAFICTICIA
CERTIFICADO DE EMPADRONAMIENTO
CERTIFICO: que según los datos que aparecen en el día de la fecha y en la hoja que se indica las inscripciones
Municipio
que constan en el Padrón Municipal de Habitantes
Provincia
RESIDENCIA origen': 'D02 - ALBACETE'; 'M
Domicilio
Fecha alta Pasaporte/Desnormalizada
URBANIZACION LOS PINOS FICTICIOS 12
45999 VILLAFICTICIA (TOLEDO)
Y7654321G 01/02/2024
"""


def test_padron_en_tabla_no_propone_texto_que_no_es_direccion():
    """Formato en el que etiquetas y valores van separados: antes se proponía texto del certificado como domicilio,
    provincia y municipio. Ahora se toma la línea que sí es una dirección y lo que no tiene forma de dato se descarta."""
    from app.immigration.extract import padron, sanitize

    got = padron(PADRON_TABLA)
    assert got["ext.tipo_via"] == "Urbanización" and got["ext.domicilio"] == "LOS PINOS FICTICIOS"
    assert got["ext.numero"] == "12" and got["ext.cp"] == "45999" and got["ext.provincia"] == "Toledo"
    assert got["ext.municipio"] == "Villaficticia"
    basura = {"ext.domicilio": "Fecha alta Pasaporte/Desnormalizada", "ext.provincia": "RESIDENCIA origen': 'D02 - ALBACETE'; 'M",
              "ext.municipio": "aparecen en el día de la fecha y en la hoja que se indica las inscripciones",
              "ext.cp": "99999", "ext.nie": "Y7654321A", "con.ccc": "12"}
    assert sanitize(basura) == {}


def test_datos_mal_leidos_ya_guardados_no_se_proponen(login, db):
    """Documentos leídos con la versión anterior: lo que no tiene forma de dato no llega a la ficha."""
    import uuid as _uuid
    from datetime import UTC, datetime

    from sqlalchemy import select, text

    from app.models import UserAccount
    from app.models_immigration import ImmigDocument

    cid = _new_case(db, procedure="ARR-SOCIAL", given="Carla", family="Ferrer Demo")
    uid = db.execute(select(UserAccount.id).where(UserAccount.username == "asesor.extranjeria.mad")).scalar_one()
    org = db.execute(text("SELECT organization_id FROM case_file WHERE id = :c"), {"c": cid}).scalar_one()
    db.add(ImmigDocument(organization_id=org, case_id=cid, status="valido", doc_type="empadronamiento", original_name="p.pdf",
                         mime="application/pdf", size_bytes=10, sha256=_uuid.uuid4().hex * 2, file_path="x.bin",
                         extracted={"ficha": {"ext.domicilio": "Fecha alta Pasaporte/Desnormalizada", "ext.cp": "45999",
                                              "ext.provincia": "RESIDENCIA origen': 'D02'"}},
                         uploaded_by=uid, reviewed_by=uid, reviewed_at=datetime.now(UTC)))
    db.commit()
    pr = login("asesor.extranjeria.mad").get(f"{API}/cases/{cid}/form").json()["proposals"]
    assert pr["ext.cp"]["value"] == "45999"
    assert "ext.domicilio" not in pr or pr["ext.domicilio"]["source"] != "documento: Certificado de empadronamiento"
    assert "ext.provincia" not in pr or "RESIDENCIA" not in pr["ext.provincia"]["value"]


def _pasaporte_escaneado(rot: int, n: int, where: int) -> bytes:
    from PIL import Image, ImageDraw

    from app.seed_immigration import _font, passport_image

    png, _ = passport_image("Ferrer Demo", "Carla", "ZZ1234567", date(1990, 3, 14), date(2031, 1, 1))
    pp = Image.open(io.BytesIO(png)).convert("L")
    pp = pp.resize((int(pp.width * 0.8), int(pp.height * 0.8)))
    pages = []
    for i in range(n):
        im = Image.new("L", (1654, 2339), 245)
        ImageDraw.Draw(im).text((200, 300), f"VISAS PAGINA {i} SELLO", fill=90, font=_font(50))
        if i == where:
            im.paste(pp, (120, 1300))
            im = im.rotate(rot, expand=True, fillcolor=245)
        pages.append(im)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=200)
    return buf.getvalue()


@pytest.mark.parametrize("rot", [90, 180])
def test_pasaporte_completo_con_la_hoja_de_datos_girada_y_mas_alla_de_la_pagina_5(rot):
    from app.immigration import reader

    r = reader.read(_pasaporte_escaneado(rot, n=9, where=7), PDF)
    assert r["suggested_type"] == "pasaporte"
    assert r["fields"]["ficha"]["ext.pasaporte"] == "ZZ1234567" and r["fields"]["ficha"]["ext.apellido1"] == "Ferrer"


def test_mrz_con_un_control_fallido_aprovecha_lo_que_cuadra():
    from app.immigration.extract import from_mrz

    m = {"format": "TD3", "valid": False, "surname": "FERRER DEMO", "given_names": "CARLA", "sex": "F",
         "nationality": "UTO", "document_number": "ZZ1234567", "birth_date": "1990-03-14",
         "checks": {"numero": False, "nacimiento": True, "caducidad": True, "compuesto": False}}
    got = from_mrz(m)
    assert got["ext.apellido1"] == "Ferrer" and got["ext.fecha_nacimiento"] == "1990-03-14"
    assert "ext.pasaporte" not in got
    assert from_mrz({**m, "checks": {"numero": False, "nacimiento": True, "caducidad": False, "compuesto": False}}) == {}


def test_no_se_duplica_un_archivo_y_aviso_agrupado(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Carla", family="Ferrer Demo")
    c = login("asesor.extranjeria.mad")
    _docs(_upload(c, cid, ("tasa.pdf", samples.tasa(), PDF)))
    r = _upload(c, cid, ("tasa_otra_vez.pdf", samples.tasa(), PDF))
    assert r.status_code == 201
    assert r.json()["results"][0]["ok"] is False and "Ya estaba subido" in r.json()["results"][0]["error"]
    assert [d["original_name"] for d in r.json()["case"]["documents"]] == ["tasa.pdf"]


def test_volver_a_leer_y_diagnostico_sin_datos(login, db):
    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Carla", family="Ferrer Demo")
    c = login("asesor.extranjeria.mad")
    d = _docs(_upload(c, cid, ("contrato.pdf", samples.contrato(), PDF)))["contrato.pdf"]
    db.execute(__import__("sqlalchemy").text("UPDATE immig_document SET extracted = NULL WHERE id = :d"), {"d": d["id"]})
    db.commit()
    r = c.post(f"{API}/documents/{d['id']}/reread")
    assert r.status_code == 200, r.text
    again = {x["original_name"]: x for x in r.json()["documents"]}["contrato.pdf"]
    assert again["extracted"]["ficha"]["emp.doc"] == "B12345674" and again["status"] == "pendiente_revision"
    diag = c.get(f"{API}/documents/{d['id']}/diagnostic").json()
    assert "Cuenta de cotización" in diag["texto"] or "cotización" in diag["texto"]
    for secreto in ("B12345674", "Y7654321G", "Construcciones", "Ficticias", "Carla", "Ferrer", "28123456789"):
        assert secreto not in diag["texto"], secreto
    # Recepción no puede
    assert login("recepcion.bcn").get(f"{API}/documents/{d['id']}/diagnostic").status_code in (403, 404)


def test_revision_automatica_de_la_lectura_sin_datos(login, db):
    """El sistema señala solo lo que falla (pasaporte sin MRZ, datos que faltan o descartados, lectura antigua)
    y el informe para soporte no lleva ningún dato personal."""
    from sqlalchemy import text

    from app.immigration import samples

    cid = _new_case(db, procedure="ARR-SOCIOLABORAL", given="Carla", family="Ferrer Demo")
    c = login("asesor.extranjeria.mad")
    docs = _docs(_upload(c, cid, ("contrato.pdf", samples.contrato(), PDF), ("padron.pdf", samples.padron(), PDF),
                         ("pasaporte_sin_hoja_de_datos.pdf", samples.tasa(nrc=""), PDF)))
    # El tercero es en realidad otra cosa: la persona lo marca como pasaporte y el sistema avisa de que no hay MRZ
    _review(c, docs["pasaporte_sin_hoja_de_datos.pdf"], "pasaporte")
    # Un documento leído con la versión anterior
    db.execute(text("UPDATE immig_document SET extracted = extracted - 'lector' WHERE id = :d"), {"d": docs["padron.pdf"]["id"]})
    db.commit()
    r = c.get(f"{API}/cases/{cid}/reading-review")
    assert r.status_code == 200, r.text
    out = r.json()
    by = {d["tipo"]: d for d in out["documentos"]}
    pas = by["Pasaporte completo (todas las hojas)"]
    assert any(p["level"] == "error" and "zona de lectura mecánica" in p["text"] for p in pas["problemas"])
    assert "Primer apellido" in pas["faltan"]
    assert out["antiguos"] == [docs["padron.pdf"]["id"]]
    assert any("Volver a leer" in p["text"] for p in by["Certificado de empadronamiento"]["problemas"])
    contrato = by["Contrato de trabajo"]
    assert "Código de cuenta de cotización" in contrato["leidos"] and contrato["faltan"] == []
    for secreto in ("B12345674", "Y7654321G", "Construcciones", "Carla", "Ferrer", "28123456789", "Getafe", "Ficticia 14"):
        assert secreto not in r.text, secreto
    assert login("recepcion.bcn").get(f"{API}/cases/{cid}/reading-review").status_code in (403, 404)
