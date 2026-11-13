# Escenario de factura de proveedor con DATOS FICTICIOS: se sube el PDF como con el botón «Subir» de Facturas de
# proveedor, Odoo la lee en el servidor, se comprueba que cuadra y se registra. Requiere sp_contabilidad.
from odoo.addons.sp_contabilidad.tests.test_facturas_proveedor import factura_pdf, FACTURA

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
compras = env["account.journal"].search([("company_id", "=", co.id), ("type", "=", "purchase")], limit=1)
adjunto = env["ir.attachment"].create({"name": "factura_proveedor_ficticia.pdf", "raw": factura_pdf(FACTURA),
                                       "mimetype": "application/pdf"})
accion = compras.with_context(default_move_type="in_invoice").create_document_from_attachment(adjunto.ids)
move = env["account.move"].browse(accion.get("res_id") or accion["domain"][0][2][0])
print(f"Leída: proveedor {move.partner_id.name} ({move.partner_id.vat}) · nº {move.ref} · fecha {move.invoice_date} · "
      f"base {move.amount_untaxed} · total Odoo {move.amount_total} · total factura {move.sp_total_documento} · "
      f"confianza {move.sp_lectura_confianza}")
an = env["account.analytic.account"]
dist = {str(an.search([("plan_id.name", "=", "Actividad"), ("name", "=", "Compartida")], limit=1).id): 100,
        str(an.search([("plan_id.name", "=", "Sede"), ("name", "=", "Barcelona")], limit=1).id): 100}
move.invoice_line_ids.analytic_distribution = dist
move.action_post()
env.cr.commit()
print(f"Registrada: {move.name} · estado {move.state}")
