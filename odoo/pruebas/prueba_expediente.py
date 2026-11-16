# Escenario de facturación y conciliación por expediente con DATOS FICTICIOS (después de configuracion/facturacion.py).
# Una empresa paga en dos transferencias con el número del expediente en el concepto; Contabilidad valida cada una con
# un clic: factura de anticipo, y con el último pago la factura final que descuenta los anticipos. Se ejecuta una vez.
from datetime import date, timedelta

from odoo.addons.sp_banco.lectura.extractos import build_n43

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
c1 = env["res.users"].search([("login", "=", "contabilidad.1")], limit=1)
atc = env["res.users"].search([("login", "=", "atc.demo")], limit=1) or c1
P = env["res.partner"]
emp = P.search([("name", "=", "EMPRESA_02 S.L.")], limit=1) or P.create({"name": "EMPRESA_02 S.L.", "vat": "ESB12345674"})
hoy = date.today()
d = lambda n: hoy - timedelta(days=n)
exp = env["sp.expediente"].with_user(atc).create({"area": "laboral", "partner_id": emp.id, "fecha_apertura": d(20),
                                                  "descripcion": "Despido · EXPEDIENTE_01"})
exp.with_user(atc).write({"sp_honorarios": 1500.0})
exp.with_user(atc).action_sp_fijar_honorarios()
print(f"Expediente {exp.name}: honorarios 1.500 € · retención {exp.sp_retencion} · total a pagar {exp.sp_total_pactado} €")
primero = round(exp.sp_total_pactado * 0.4, 2)
resto = round(exp.sp_total_pactado - primero, 2)
partido = f"{exp.name[:7]} {exp.name[7:]}"  # la Norma 43 a veces trocea el concepto
n43 = build_n43(bank="2100", branch="0001", account10="0000011111", start=d(10), end=hoy, opening_cents=500000, moves=[
    (d(8), int(primero * 100), "04", "TRF", f"TRANSF EMPRESA_02 HONORARIOS {partido}"),
    (d(1), int(resto * 100), "04", "TRF", f"TRANSF EMPRESA_02 RESTO {exp.name}"),
])
adj = env["ir.attachment"].with_user(c1).create({"name": "extracto_banco_A.n43", "raw": n43})
accion = env["sp.banco.importar"].with_user(c1).create({"archivo_ids": [(6, 0, adj.ids)]}).action_importar()
movs = env["sp.banco.importacion"].search(accion["domain"]).statement_id.line_ids.sorted("date")
for m in movs:
    print(f"  {m.date} {m.amount:>9.2f} {m.sp_estado:<10} {m.sp_regla or '':<12} {m.sp_explicacion}")
for m in movs:
    m.with_user(c1).action_sp_validar()
for f in exp.sp_factura_ids.sorted("id"):
    print(f"  Factura {f.name} del {f.invoice_date}: base {f.amount_untaxed} · impuestos {f.amount_tax} · "
          f"total {f.amount_total} · {f.payment_state}")
print(f"Expediente {exp.name}: {exp.sp_estado_cobro} · pendiente {exp.sp_pendiente} €")
env.cr.commit()
