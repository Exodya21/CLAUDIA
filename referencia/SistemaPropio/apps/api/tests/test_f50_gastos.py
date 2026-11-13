"""F5.0 — Gastos de empresa con justificante: lectura propuesta, confirmación humana, revisión de Contabilidad,
caja y conciliación con el extracto de la tarjeta. Tickets FICTICIOS generados en la prueba."""

from __future__ import annotations

import io
import shutil
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from .conftest import denied_events

OCR = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no instalado")


@pytest.fixture(autouse=True)
def _receipts_dir(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path_factory.getbasetemp() / "justificantes"))


def ticket(lines: list[str]) -> bytes:
    import glob

    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(glob.glob("/usr/share/fonts/**/DejaVuSansMono.ttf", recursive=True)[0], 28)
    img = Image.new("RGB", (720, 60 + 45 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((30, 30 + 45 * i), ln, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _lines(day: date, total: str = "18,00", vat: str = "1,64", base: str = "16,36", extra: str = "") -> list[str]:
    return ["TAXI FICTICIO BCN", "NIF: 12345678Z", f"Fecha: {day.strftime('%d/%m/%Y')}", f"Trayecto juzgado {extra}",
            f"BASE         {base}", f"IVA 10%       {vat}", f"TOTAL        {total} EUR"]


def _upload(c, data: bytes, name="ticket.jpg"):
    h = {k: v for k, v in c.headers.items() if k.lower() != "content-type"}
    return c.post("/api/v1/expenses", files={"file": (name, data, "image/jpeg")}, headers=h)


def _complete(c, e, **kw):
    body = {"category": "desplazamiento", "payment_method": "personal", "version": e["version"], **kw}
    r = c.patch(f"/api/v1/expenses/{e['id']}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@OCR
def test_lectura_propone_y_la_persona_confirma(login):
    c = login("asesor.laboral.bcn")
    day = date.today() - timedelta(days=2)
    r = _upload(c, ticket(_lines(day, extra=uuid.uuid4().hex[:4])))
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["status"] == "borrador" and e["has_receipt"]
    # Propuesta, no decisión: queda en borrador hasta que la persona revisa
    assert e["amount_cents"] == 1800 and e["vat_cents"] == 164 and e["expense_date"] == day.isoformat()
    assert e["supplier_tax_id"] == "12345678Z" and e["ocr"]["engine"] == "local-tesseract"
    assert e["ocr"]["suggestion"]["fields"]["amount_cents"]["confidence"] == "alta"
    # Sin completar el concepto y la forma de pago no se puede enviar
    assert c.post(f"/api/v1/expenses/{e['id']}/submit").status_code == 422
    e = _complete(c, e)
    r = c.post(f"/api/v1/expenses/{e['id']}/submit")
    assert r.json()["status"] == "enviado"
    # Enviado: ya no se modifica
    assert c.patch(f"/api/v1/expenses/{e['id']}", json={"amount_cents": 1, "version": r.json()["version"]}).status_code == 409


@OCR
def test_justificante_duplicado_rechazado(login):
    c = login("asesor.laboral.bcn")
    data = ticket(_lines(date.today(), extra=uuid.uuid4().hex[:4]))
    assert _upload(c, data).status_code == 201
    r = login("gestor.laboral.vlc").post("/api/v1/expenses", files={"file": ("otro.jpg", data, "image/jpeg")},
                                          headers={"X-Requested-With": "sistema-propio"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "justificante_duplicado"
    assert r.json()["error"]["details"]["expense_id"] is None  # no revela el gasto ajeno


def test_formato_no_admitido(login):
    c = login("asesor.laboral.bcn")
    r = c.post("/api/v1/expenses", files={"file": ("x.exe", b"MZ\x90\x00binario", "image/jpeg")},
               headers={"X-Requested-With": "sistema-propio"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "justificante_no_valido"


@OCR
def test_gastos_ajenos_y_autorrevision_prohibidos(login, db):
    c = login("asesor.laboral.bcn")
    e = _complete(c, _upload(c, ticket(_lines(date.today(), extra=uuid.uuid4().hex[:4]))).json())
    other = login("recepcion.bcn")
    assert other.get(f"/api/v1/expenses/{e['id']}").status_code == 403
    assert other.get(f"/api/v1/expenses/{e['id']}/receipt").status_code == 403
    assert denied_events(db, "expense.read", e["id"])
    c.post(f"/api/v1/expenses/{e['id']}/submit")
    assert c.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "aprobar"}).status_code == 403
    # Contabilidad ve el justificante (y queda registrado)
    r = login("contabilidad.demo").get(f"/api/v1/expenses/{e['id']}/receipt")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:3] == b"\xff\xd8\xff"


@OCR
def test_contabilidad_devuelve_con_motivo_y_la_persona_corrige(login):
    c = login("asesor.laboral.bcn")
    e = _complete(c, _upload(c, ticket(_lines(date.today(), extra=uuid.uuid4().hex[:4]))).json())
    c.post(f"/api/v1/expenses/{e['id']}/submit")
    conta = login("contabilidad.demo")
    assert conta.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "devolver"}).status_code == 422
    r = conta.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "devolver", "note": "Falta indicar el expediente en la descripción"})
    assert r.json()["status"] == "devuelto"
    e = c.get(f"/api/v1/expenses/{e['id']}").json()
    e = _complete(c, e, description="Juzgado Social nº 1, expediente LAB-2026-0001")
    assert c.post(f"/api/v1/expenses/{e['id']}/submit").json()["status"] == "enviado"
    r = conta.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "aprobar"})
    assert r.json()["status"] == "aprobado"
    r = conta.post(f"/api/v1/expenses/{e['id']}/reconcile", json={"reference": "Reembolso nómina noviembre (ficticio)"})
    assert r.json()["status"] == "conciliado"


@OCR
def test_efectivo_descuenta_de_la_caja_y_anular_lo_devuelve(login):
    c = login("asesor.laboral.bcn")
    conta = login("contabilidad.demo")
    caja = lambda: next(x for x in conta.get("/api/v1/economy/cash").json() if x["branch"] == "Barcelona")["balance_cents"]  # noqa: E731
    before = caja()
    e = _complete(c, _upload(c, ticket(_lines(date.today(), total="9,50", vat="0,00", base="9,50",
                                               extra=uuid.uuid4().hex[:4]))).json(), payment_method="efectivo_caja")
    c.post(f"/api/v1/expenses/{e['id']}/submit")
    assert caja() == before - 950
    r = conta.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "anular", "note": "Gasto personal, no de empresa"})
    assert r.json()["status"] == "anulado" and caja() == before
    e2 = _complete(c, _upload(c, ticket(_lines(date.today(), total="7,00", vat="0,64", base="6,36",
                                                extra=uuid.uuid4().hex[:4]))).json(), payment_method="efectivo_caja")
    c.post(f"/api/v1/expenses/{e2['id']}/submit")
    r = conta.post(f"/api/v1/expenses/{e2['id']}/review", json={"action": "aprobar"})
    assert r.json()["status"] == "conciliado" and r.json()["reconcile_ref"] == "Caja de la sede"


@OCR
def test_tarjeta_de_empresa_y_extracto(login, db):
    c = login("asesor.laboral.bcn")
    conta = login("contabilidad.demo")
    cat = c.get("/api/v1/expenses/catalog").json()
    card = cat["my_cards"][0]
    day = date.today() - timedelta(days=1)
    e = _complete(c, _upload(c, ticket(_lines(day, total="23,45", vat="2,13", base="21,32",
                                               extra=uuid.uuid4().hex[:4]))).json(),
                  payment_method="tarjeta_empresa", card_id=card["id"])
    # Una tarjeta ajena no se puede usar
    otra = login("gestor.laboral.vlc")
    eo = otra.post("/api/v1/expenses", files={"file": ("t.jpg", ticket(_lines(day, extra=uuid.uuid4().hex[:6])), "image/jpeg")},
                   headers={"X-Requested-With": "sistema-propio"}).json()
    r = otra.patch(f"/api/v1/expenses/{eo['id']}", json={"payment_method": "tarjeta_empresa", "card_id": card["id"],
                                                         "version": eo["version"]})
    assert r.status_code == 422
    c.post(f"/api/v1/expenses/{e['id']}/submit")
    conta.post(f"/api/v1/expenses/{e['id']}/review", json={"action": "aprobar"})
    # Extracto CSV del banco (ficticio): un cargo que cuadra, uno sin justificante y una línea rota
    csv = (f"fecha;concepto;importe;tarjeta\n{day.strftime('%d/%m/%Y')};TAXI FICTICIO BCN;23,45;0042\n"
           f"{day.strftime('%d/%m/%Y')};GASOLINERA FICTICIA;61,20;0042\nmal;linea\n")
    h = {"X-Requested-With": "sistema-propio"}
    files = {"file": ("extracto.csv", csv.encode(), "text/csv")}
    data = {"organization_id": e["organization_id"]}
    r = conta.post("/api/v1/expenses/cards/import", files=files, data=data, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2 and r.json()["with_suggestion"] == 1 and len(r.json()["errors"]) == 1
    # Reimportar el mismo extracto no duplica
    r = conta.post("/api/v1/expenses/cards/import", files={"file": ("extracto.csv", csv.encode(), "text/csv")}, data=data, headers=h)
    assert r.json()["imported"] == 0 and r.json()["duplicates"] == 2
    txs = conta.get("/api/v1/expenses/cards/transactions").json()
    t = next(x for x in txs if x["description"] == "TAXI FICTICIO BCN" and x["amount_cents"] == 2345)
    assert t["suggestions"][0]["id"] == e["id"]
    gas = next(x for x in txs if x["description"] == "GASOLINERA FICTICIA")
    assert gas["suggestions"] == []  # cargo sin justificante: queda a la vista de Contabilidad
    # Importe distinto: no concilia
    assert conta.post(f"/api/v1/expenses/{e['id']}/reconcile", json={"card_transaction_id": gas["id"]}).status_code == 422
    r = conta.post(f"/api/v1/expenses/{e['id']}/reconcile", json={"card_transaction_id": t["id"]})
    assert r.json()["status"] == "conciliado"
    # El asesor no importa extractos
    assert c.post("/api/v1/expenses/cards/import", files={"file": ("x.csv", b"a", "text/csv")}, data=data, headers=h).status_code == 403


@OCR
def test_resumen_mensual_y_exportacion(login, db):
    month = date.today().strftime("%Y-%m")
    assert login("asesor.laboral.bcn").get("/api/v1/expenses/summary/month", params={"month": month}).status_code == 403
    conta = login("contabilidad.demo")
    s = conta.get("/api/v1/expenses/summary/month", params={"month": month}).json()
    assert s["total"]["n"] >= 1 and set(s["grupos"]) == {"empleado", "sede", "concepto", "forma_pago"}
    assert s["cargos_tarjeta_sin_justificante"] >= 1
    r = conta.get("/api/v1/expenses/summary/month.csv", params={"month": month})
    assert r.status_code == 200 and r.content.startswith("﻿Fecha;Empleado".encode())
    from app.models import AuditEvent

    db.rollback()
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "expense.export")).first()


def test_parser_de_tickets():
    from app.services.receipts import parse

    t = """BAR RESTAURANTE INVENTADO
CIF B12345674
Fecha 28-10-26 13:05
2 MENU 25,80
BASE IMPONIBLE 23,45
CUOTA IVA 10% 2,35
TOTAL A PAGAR 25,80"""
    f = parse(t, today=date(2026, 11, 3))
    assert f["expense_date"]["value"] == "2026-10-28"
    assert f["amount_cents"]["value"] == 2580 and f["vat_cents"]["value"] == 235
    assert f["supplier_name"]["value"] == "BAR RESTAURANTE INVENTADO"
    # Fecha futura o NIF con letra mal: no se proponen con confianza alta
    f = parse("TIENDA X\nNIF 12345678A\n01/01/2099\nTOTAL 3,00", today=date(2026, 11, 3))
    assert "expense_date" not in f and f["supplier_tax_id"]["confidence"] == "baja"


def test_sin_motor_de_lectura_se_rellena_a_mano(login, monkeypatch):
    from app.services import receipts

    monkeypatch.setattr(receipts.LocalExtractor, "available", staticmethod(lambda: False))
    c = login("asesor.laboral.bcn")
    data = b"%PDF-1.4\n% ficticio " + uuid.uuid4().hex.encode()
    r = c.post("/api/v1/expenses", files={"file": ("f.pdf", data, "application/pdf")}, headers={"X-Requested-With": "sistema-propio"})
    assert r.status_code == 201
    assert r.json()["ocr"]["engine"] == "ninguno" and "a mano" in r.json()["ocr"]["suggestion"]["message"]
    assert r.json()["amount_cents"] is None
