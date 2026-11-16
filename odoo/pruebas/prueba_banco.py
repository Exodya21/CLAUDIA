# Escenario de banco con DATOS FICTICIOS (después de configuracion/banco.py). Se ejecuta una vez.
# Contabilidad importa dos extractos Norma 43 ficticios (Banco B y Banco C) con el asistente, el agente propone y se
# validan algunas propuestas; el resto queda para revisarlo en pantalla.
import base64
from datetime import date, timedelta

from odoo.addons.sp_banco.lectura.extractos import build_n43

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
c1 = env["res.users"].search([("login", "=", "contabilidad.1")], limit=1)
J = lambda code: env["account.journal"].search([("company_id", "=", co.id), ("code", "=", code)], limit=1)
P = env["res.partner"]
cli = P.search([("name", "=", "CLIENTE_05")], limit=1) or P.create({"name": "CLIENTE_05"})
cli6 = P.search([("name", "=", "CLIENTE_06")], limit=1) or P.create({"name": "CLIENTE_06"})
hoy = date.today()

# Factura de un expediente sin cobrar (el cliente paga por transferencia con la referencia)
fact = env["account.move"].create({"move_type": "out_invoice", "partner_id": cli.id, "journal_id": J("EXP").id,
    "invoice_line_ids": [(0, 0, {"name": "Honorarios trámite de extranjería", "quantity": 1, "price_unit": 300.0,
                                 "tax_ids": [(5, 0, 0)]})]})
fact.action_post()
# Cobro por Bizum registrado en recepción contra el Banco B
biz = env["account.payment"].create({"payment_type": "inbound", "partner_type": "customer", "partner_id": cli6.id,
                                     "amount": 40.0, "journal_id": J("BCB").id, "date": hoy - timedelta(days=1),
                                     "memo": "Bizum consulta"})
biz.action_post()
# Dos cobros con tarjeta en recepción el mismo día: el banco los liquida juntos descontando su comisión
tarjetas = env["account.payment"].create([
    {"payment_type": "inbound", "partner_type": "customer", "partner_id": cli6.id, "amount": a,
     "journal_id": J("BCB").id, "date": hoy - timedelta(days=2), "memo": "Tarjeta consulta"} for a in (70.0, 30.0)])
tarjetas.action_post()

d = lambda n: hoy - timedelta(days=n)
n43_b = build_n43(bank="2100", branch="0001", account10="0000022222", start=d(5), end=hoy, opening_cents=250000, moves=[
    (d(2), 30000, "04", "TRF", f"TRANSFERENCIA CLIENTE_05 {fact.name}"),
    (d(1), 4000, "02", "BIZ", "BIZUM CLIENTE_06"),
    (d(1), 9820, "02", "TPV", "LIQUIDACION TPV COMERCIO"),
    (d(1), -50000, "04", "TRS", "TRASPASO A BANCO C TESORERIA"),
    (d(0), -350, "17", "COM", "COMISION MANTENIMIENTO CUENTA"),
    (d(0), 9999, "02", "ING", "INGRESO SIN REFERENCIA"),
])
n43_c = build_n43(bank="2100", branch="0001", account10="0000033333", start=d(5), end=hoy, opening_cents=1000000, moves=[
    (d(1), 50000, "04", "TRS", "TRASPASO DESDE BANCO B EXTRANJERIA"),
])
adjuntos = env["ir.attachment"].with_user(c1).create([  # los sube la propia persona, como en pantalla
    {"name": "extracto_banco_B.n43", "raw": n43_b}, {"name": "extracto_banco_C.n43", "raw": n43_c}])
asistente = env["sp.banco.importar"].with_user(c1).create({"archivo_ids": [(6, 0, adjuntos.ids)]})
accion = asistente.action_importar()
imps = env["sp.banco.importacion"].search(accion["domain"])
for i in imps:
    print(f"Importado {i.name} → {i.journal_id.name}: {i.nuevos} nuevos, {i.duplicados} repetidos, saldos cuadran: {i.cuadra}")
movs = imps.statement_id.line_ids.sorted("date")
for m in movs:
    print(f"  {m.date} {m.journal_id.code} {m.amount:>9.2f}  {m.sp_estado:<10} {m.sp_regla or '':<24} {(m.sp_explicacion or '')[:110]}")
# Contabilidad valida la transferencia con referencia y el traspaso, y contabiliza la comisión
ref = movs.filtered(lambda m: m.sp_regla == "referencia")
ref.with_user(c1).action_sp_validar()
movs.filtered(lambda m: m.sp_regla == "traspaso" and m.amount > 0).with_user(c1).action_sp_validar()
com = movs.filtered(lambda m: m.sp_regla == "cargo_sin_justificar")
com.with_user(c1).write({"sp_nota": "Comisión de mantenimiento mensual", "sp_cuenta_id": env["account.account"].with_company(co).search([("code", "=", "626000")], limit=1).id})
com.with_user(c1).action_sp_contabilizar_en_cuenta()
# La liquidación del TPV llega con 1,80 € menos: se propone con la comisión a la 626 y Contabilidad la valida
movs.filtered(lambda m: m.sp_regla == "tpv_comision").with_user(c1).action_sp_validar()
env.cr.commit()
csv = env["sp.banco.exportar"].with_user(c1).create({"fecha_desde": d(5), "fecha_hasta": hoy}).action_exportar()
print("Exportación para la gestoría:", csv["url"])
print(f"Factura {fact.name}: {fact.payment_state} · estados: " + ", ".join(f"{m.sp_estado}" for m in movs))
