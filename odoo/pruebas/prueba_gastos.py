# Escenario de gasto con DATOS FICTICIOS: Recepción Barcelona sube el ticket de una comida pagada en efectivo de la
# caja, Odoo lo lee, Contabilidad 1 lo aprueba y lo contabiliza; la caja de Barcelona baja. Se ejecuta una vez.
from odoo.addons.sp_contabilidad.tests.test_facturas_proveedor import factura_pdf
from odoo.addons.sp_gastos.tests.test_gastos import TICKET

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
U = lambda login: env["res.users"].search([("login", "=", login)], limit=1)
rec, c1 = U("recepcion.bcn"), U("contabilidad.1")
cat = env["product.product"].search([("name", "=", "Dietas y comidas")], limit=1)
adj = env["ir.attachment"].with_user(rec).create({"name": "ticket_comida.pdf", "raw": factura_pdf(TICKET),
                                                   "mimetype": "application/pdf", "res_model": "hr.expense"})
ids = env["hr.expense"].with_user(rec).create_expense_from_attachments(adj.ids)
g = env["hr.expense"].browse(ids)
g.with_user(rec).write({"product_id": cat.id, "sp_forma_pago": "efectivo"})
print(f"Leído: {g.name} · {g.date} · {g.total_amount_currency} € · IVA ticket {g.sp_iva_ticket} · impuesto "
      f"{g.tax_ids.name} ({g.tax_amount}) · proveedor {g.vendor_id.vat} · caja {g.payment_method_line_id.journal_id.name}")
g.with_user(rec).action_submit()
g.with_user(c1).sudo().action_approve()
g.account_move_id.action_post()
env.cr.commit()
print(f"Aprobado y contabilizado: {g.state} · asiento {g.account_move_id.name}")
