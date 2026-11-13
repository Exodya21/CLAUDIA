"""Extractos bancarios en Excel: .xlsx, .xls (Excel 97-2003) y el «.xls» que en realidad es una tabla HTML.

Formato típico de la banca electrónica española: filas de título (titular, cuenta, periodo) antes de la cabecera,
fechas como fecha de Excel, importes como número o con coma decimal, a veces columnas Cargo/Abono en lugar de Importe.
Todo FICTICIO: cuenta de la entidad 9999 que no existe.
"""

from __future__ import annotations

import io
from datetime import datetime

import pytest
from sqlalchemy import select

from app.bank import parsers

API = "/api/v1"
TITLE = [["Movimientos de la cuenta (FICTICIO)"], ["Cuenta", "ES00 9999 0001 1100 0000 1111"], ["Periodo", "01/10/2026 - 31/10/2026"], []]


def _xlsx(rows) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xls(rows) -> bytes:
    xlwt = pytest.importorskip("xlwt")
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Movimientos")
    datefmt = xlwt.easyxf(num_format_str="dd/mm/yyyy")
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            if isinstance(v, datetime):
                ws.write(i, j, v, datefmt)
            elif v is not None:
                ws.write(i, j, v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_con_titulo_fechas_de_excel_y_saldos():
    rows = TITLE + [["Fecha operación", "Fecha valor", "Concepto", "Importe (EUR)", "Saldo (EUR)"],
                    [datetime(2026, 10, 2), datetime(2026, 10, 2), "TRANSFERENCIA DEMO REF LAB-2026-0001", 150.0, 1150.0],
                    [datetime(2026, 10, 5), datetime(2026, 10, 6), "COMISION MANTENIMIENTO DEMO", -12.5, 1137.5],
                    [None, None, "Total movimientos: 2", None, None]]
    st = parsers.parse(_xlsx(rows), "Movimientos octubre.xlsx")
    assert st.file_format == "xlsx" and st.account_hint == "1111"
    assert [ln.amount_cents for ln in st.lines] == [15000, -1250]
    assert st.lines[1].value_date.isoformat() == "2026-10-06"
    assert (st.opening_cents, st.closing_cents) == (100000, 113750) and not st.errors


def test_xls_antiguo_con_cargo_y_abono_y_orden_inverso():
    rows = TITLE + [["F. Operación", "Concepto", "Cargo", "Abono", "Saldo"],
                    [datetime(2026, 10, 9), "RECIBO SEGURO DEMO", 40.0, None, 1060.0],
                    [datetime(2026, 10, 3), "BIZUM RECIBIDO DEMO", None, 100.0, 1100.0]]
    st = parsers.parse(_xls(rows), "Movimientos - octubre.xls")
    assert st.file_format == "xls"
    assert [(ln.booking_date.day, ln.amount_cents) for ln in st.lines] == [(9, -4000), (3, 10000)]
    assert (st.opening_cents, st.closing_cents) == (100000, 106000)


def test_xls_que_es_una_tabla_html():
    html = ("<html><body><table><tr><td>Cuenta ES00 9999 0001 1100 0000 1111</td></tr>"
            "<tr><th>Fecha</th><th>Concepto</th><th>Importe</th><th>Saldo</th></tr>"
            "<tr><td>02/10/2026</td><td>TRANSFERENCIA DEMO</td><td>1.234,56</td><td>2.234,56</td></tr>"
            "<tr><td>03/10/2026</td><td>CARGO TARJETA DEMO</td><td>-34,56</td><td>2.200,00</td></tr>"
            "</table></body></html>").encode("latin-1")
    st = parsers.parse(html, "Movimientos.xls")
    assert st.account_hint == "1111" and [ln.amount_cents for ln in st.lines] == [123456, -3456]
    assert st.opening_cents == 100000


def test_no_adivina():
    # Cabecera desconocida → se rechaza explicando qué columnas hacen falta
    with pytest.raises(parsers.ParseError, match="Fecha, Concepto e Importe"):
        parsers.parse(_xlsx([["Día", "Texto", "Dinero"], ["02/10/2026", "x", 1.0]]), "raro.xlsx")
    # Línea con fecha ilegible → error de esa línea, el resto se lee
    st = parsers.parse(_xlsx([["Fecha", "Concepto", "Importe"], ["02/10/2026", "A DEMO", 10.0], ["mañana", "B DEMO", 5.0]]), "x.xlsx")
    assert len(st.lines) == 1 and st.errors and st.errors[0]["linea"] == 3
    # Cargo y abono a la vez en la misma línea → error
    st = parsers.parse(_xlsx([["Fecha", "Concepto", "Cargo", "Abono"], ["02/10/2026", "A DEMO", 1.0, 2.0]]), "x.xlsx")
    assert not st.lines and "cargo o abono" in st.errors[0]["error"]
    # Un archivo que no es Excel con nombre .xlsx
    with pytest.raises(parsers.ParseError):
        parsers.parse(b"PK\x03\x04no es un excel", "falso.xlsx")


def test_importar_excel_en_la_cuenta(login, db):
    from app.models_bank import BankAccount

    db.rollback()
    acc = db.execute(select(BankAccount).where(BankAccount.purpose == "A_laboral")).scalars().first()
    rows = [["Cuenta", f"ES00 9999 0001 1100 0000 {acc.iban_last4}"], [],
            ["Fecha", "Concepto", "Importe", "Saldo"],
            [datetime(2026, 9, 1), "INGRESO EXCEL DEMO 1", 10.0, 510.0],
            [datetime(2026, 9, 2), "INGRESO EXCEL DEMO 2", 20.0, 530.0]]
    data = _xlsx(rows)
    c = login("contabilidad.demo")
    r = c.post(f"{API}/bank/accounts/{acc.id}/imports", files={"file": ("Movimientos - septiembre.xlsx", data,
                                                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code in (200, 201), r.text
    assert r.json()["format"] == "xlsx" and r.json()["new_lines"] == 2
    # Excel de otra cuenta → se rechaza
    other = _xlsx([["Cuenta", "ES00 9999 0001 1100 0000 9876"], ["Fecha", "Concepto", "Importe"], [datetime(2026, 9, 3), "X DEMO", 1.0]])
    r = c.post(f"{API}/bank/accounts/{acc.id}/imports", files={"file": ("otra.xlsx", other, "application/octet-stream")})
    assert r.status_code in (409, 422) and "9876" in r.text


def test_comprobar_sin_importar_no_guarda_nada(login, db):
    """Para probar el formato de un banco real en una instalación de pruebas: lee en memoria y no guarda nada."""
    from sqlalchemy import func

    from app.models import AuditEvent
    from app.models_bank import BankAccount, BankImport, BankMovement

    db.rollback()
    acc = db.execute(select(BankAccount).where(BankAccount.purpose == "B_extranjeria")).scalars().first()
    counts = lambda: (db.execute(select(func.count()).select_from(BankImport)).scalar_one(),  # noqa: E731
                      db.execute(select(func.count()).select_from(BankMovement)).scalar_one())
    before = counts()
    data = _xlsx([["Cuenta", "ES00 9999 0001 1100 0000 6184"], ["F. Operación", "Concepto", "Cargo", "Abono", "Saldo"],
                  [datetime(2026, 10, 3), "BIZUM RECIBIDO DEMO", None, 100.0, 1100.0],
                  [datetime(2026, 10, 9), "RECIBO SEGURO DEMO", 40.0, None, 1060.0],
                  ["mal", "LINEA ROTA DEMO", 1.0, None, None]])
    c = login("contabilidad.demo")
    r = c.post(f"{API}/bank/accounts/{acc.id}/check", files={"file": ("Movimientos - octubre.xlsx", data, "application/octet-stream")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["saved"] is False and j["format"] == "xlsx" and j["lines"] == 2 and j["errors_total"] == 1
    assert j["account_hint"] == "6184" and j["account_matches"] is False
    assert {x["field"] for x in j["columns"]} >= {"Fecha", "Concepto", "Cargo", "Abono", "Saldo"}
    assert j["credits"] == {"num": 1, "cents": 10000} and j["debits"] == {"num": 1, "cents": -4000}
    db.rollback()
    assert counts() == before
    ev = db.execute(select(AuditEvent).where(AuditEvent.action == "bank.statement.check").order_by(AuditEvent.occurred_at.desc())).scalars().first()
    assert ev is not None and "BIZUM" not in str(ev.after)
    # Formato desconocido: explica qué columnas faltan
    bad = c.post(f"{API}/bank/accounts/{acc.id}/check", files={"file": ("x.xlsx", _xlsx([["Día", "Texto"]]), "application/octet-stream")})
    assert bad.status_code == 422 and "Fecha, Concepto e Importe" in bad.text
    assert login("recepcion.bcn").post(f"{API}/bank/accounts/{acc.id}/check",
                                       files={"file": ("x.xlsx", data, "application/octet-stream")}).status_code in (403, 404)
