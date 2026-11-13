"""Puesta en marcha con datos de la empresa: alta de cuentas con IBAN, importación de varios extractos a la vez
reconociendo la cuenta, y alta de la primera persona administradora con sus sedes y departamentos. Datos FICTICIOS."""

from __future__ import annotations

import io
from datetime import datetime

from sqlalchemy import select

API = "/api/v1"


def _xlsx(rows) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _iban(bank: str, account10: str) -> str:
    from app.accounting.invoices import demo_iban

    return demo_iban(bank, "0001", account10)


def test_alta_de_cuenta_con_iban(login, ids, db):
    c = login("contabilidad.demo")
    body = {"organization_id": str(ids["es"]), "name": "Cuenta Demo Excel 1", "bank_name": "Banco Demo",
            "purpose": "otra", "activity": "compartida", "iban": "ES00 1234 5678 9012 3456 7890"}
    r = c.post(f"{API}/bank/accounts", json=body)
    assert r.status_code == 422 and "IBAN" in r.text
    iban = _iban("9998", "0000004321")
    r = c.post(f"{API}/bank/accounts", json=body | {"iban": " ".join(iban[i:i + 4] for i in range(0, 24, 4))})
    assert r.status_code == 201, r.text
    assert r.json()["iban_last4"] == "4321" and iban not in r.text
    from app.models_bank import BankAccount
    from app.services import textcrypt

    db.rollback()
    a = db.execute(select(BankAccount).where(BankAccount.name == "Cuenta Demo Excel 1")).scalar_one()
    assert textcrypt.dec(a.iban_enc) == iban  # completo solo cifrado
    assert login("recepcion.bcn").post(f"{API}/bank/accounts", json=body | {"iban": iban, "name": "Otra Demo"}).status_code == 403


def test_importar_varios_extractos_reconoce_la_cuenta(login, ids):
    c = login("contabilidad.demo")
    iban = _iban("9997", "0000008765")
    r = c.post(f"{API}/bank/accounts", json={"organization_id": str(ids["es"]), "name": "Cuenta Demo Lote", "bank_name": "Banco Demo 2",
                                               "purpose": "otra", "activity": "laboral", "iban": iban})
    assert r.status_code == 201, r.text
    good = _xlsx([["Cuenta", " ".join(iban[i:i + 4] for i in range(0, 24, 4))], ["Fecha", "Concepto", "Importe", "Saldo"],
                  [datetime(2026, 10, 1), "INGRESO LOTE DEMO", 50.0, 150.0], [datetime(2026, 10, 2), "CARGO LOTE DEMO", -20.0, 130.0]])
    unknown = _xlsx([["Cuenta", "ES00 9999 0001 1100 0000 0007"], ["Fecha", "Concepto", "Importe"], [datetime(2026, 10, 1), "X DEMO", 1.0]])
    no_account = _xlsx([["Fecha", "Concepto", "Importe"], [datetime(2026, 10, 1), "Y DEMO", 1.0]])
    files = [("files", ("lote_bueno.xlsx", good, "application/octet-stream")),
             ("files", ("cuenta_desconocida.xlsx", unknown, "application/octet-stream")),
             ("files", ("sin_cuenta.xlsx", no_account, "application/octet-stream")),
             ("files", ("roto.xlsx", b"esto no es un extracto", "application/octet-stream"))]
    r = c.post(f"{API}/bank/imports/auto", data={"organization_id": str(ids["es"])}, files=files)
    assert r.status_code == 200, r.text
    res = {x["file"]: x for x in r.json()["results"]}
    assert res["lote_bueno.xlsx"]["ok"] and res["lote_bueno.xlsx"]["account"] == "Cuenta Demo Lote" and res["lote_bueno.xlsx"]["new_lines"] == 2
    assert not res["cuenta_desconocida.xlsx"]["ok"] and "0007" in res["cuenta_desconocida.xlsx"]["error"]
    assert not res["sin_cuenta.xlsx"]["ok"] and "no indica la cuenta" in res["sin_cuenta.xlsx"]["error"]
    assert not res["roto.xlsx"]["ok"]
    # Repetir el mismo lote no duplica
    again = c.post(f"{API}/bank/imports/auto", data={"organization_id": str(ids["es"])}, files=files[:1]).json()
    assert not again["results"][0]["ok"] and "ya se importó" in again["results"][0]["error"]
    # Sin permiso
    rec = login("recepcion.bcn")
    assert rec.post(f"{API}/bank/imports/auto", data={"organization_id": str(ids["es"])}, files=files[:1]).status_code == 403


def test_primera_administracion_crea_sedes_y_departamentos(db):
    from app.models import Branch, Department, Organization
    from app.ops import primer_admin

    rc = primer_admin.main(["--crear-entidad", "--entidad", "Sociedad Ficticia Puesta en Marcha SL", "--sedes", "Sede Uno, Sede Dos",
                            "--usuario", "admin.ficticio", "--nombre", "Admin Ficticio", "--correo", "admin@ficticio.invalid"])
    assert rc == 0
    db.rollback()
    org = db.execute(select(Organization).where(Organization.name == "Sociedad Ficticia Puesta en Marcha SL")).scalar_one()
    assert {b.name for b in db.execute(select(Branch).where(Branch.organization_id == org.id)).scalars()} == {"Sede Uno", "Sede Dos"}
    assert {"LAB", "EXT", "CON", "DIR"} <= {d.code for d in db.execute(select(Department).where(Department.organization_id == org.id)).scalars()}
    # Solo una vez
    assert primer_admin.main(["--entidad", "Sociedad Ficticia Puesta en Marcha SL", "--usuario", "otro.ficticio",
                              "--nombre", "Otro", "--correo", "otro@ficticio.invalid"]) == 2
