# Facturación por expediente (sp_facturacion). Se ejecuta después de base_contable.py. Idempotente.
# - Los anticipos van a la 438 «Anticipos de clientes» (PGC): la factura de anticipo abona la 438 y la factura final
#   la carga y abona la 705. PROVISIONAL hasta que conteste la gestoría (T-40, cuestionario del plan de cuentas).
log = []
for co in env["res.company"].search([("chart_template", "like", "es_%")]):
    cuenta = env["account.account"].with_company(co).search([("code", "=like", "438%"), ("company_ids", "in", co.id)],
                                                            limit=1)
    if cuenta and co.downpayment_account_id != cuenta:
        co.downpayment_account_id = cuenta
        log.append(f"{co.name}: anticipos de clientes a la cuenta {cuenta.code}")
# La tarifa «Por defecto» se crea al instalar Odoo, antes de cargar el plan contable, en la moneda de entonces (USD).
# Si existe (al instalar Ventas) y no coincide con la moneda de la compañía, se corrige.
if "product.pricelist" in env:
    for co in env["res.company"].search([]):
        for t in env["product.pricelist"].search([("company_id", "=", co.id), ("currency_id", "!=", co.currency_id.id)]):
            t.currency_id = co.currency_id
            log.append(f"{co.name}: tarifa «{t.name}» pasa a {co.currency_id.name}")
env.cr.commit()
print("\n".join(log) or "Facturación por expediente: nada que cambiar.")
