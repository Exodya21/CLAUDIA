# Prueba de la base contable con DATOS FICTICIOS (se ejecuta en «odoo-bin shell» después de base_contable.py).
# Crea y publica facturas de prueba en la S.L. y comprueba series, IVA, retención, suplido, rectificativa,
# cobro parcial y el registro de Verifactu (entorno de pruebas; sin certificado no se envía nada a la AEAT).
from odoo import fields

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
J = lambda code: env["account.journal"].search([("company_id", "=", co.id), ("code", "=", code)], limit=1)
P = lambda name: env["product.product"].search([("name", "=", name)], limit=1)
tax = lambda name: env["account.tax"].search([("company_id", "=", co.id), ("name", "=", name)], limit=1)
an = lambda plan, name: env["account.analytic.account"].search([("plan_id.name", "=", plan), ("name", "=", name)], limit=1)
ok = True

def comprueba(cond, texto):
    global ok
    print(("OK   " if cond else "FALLO") + " " + texto)
    ok = ok and cond

Partner = env["res.partner"]
cliente = Partner.search([("name", "=", "CLIENTE_01")], limit=1) or Partner.create(
    {"name": "CLIENTE_01", "country_id": env.ref("base.es").id, "vat": "00000001R", "city": "Barcelona"})
empresa = Partner.search([("name", "=", "EMPRESA_01 S.L.")], limit=1) or Partner.create(
    {"name": "EMPRESA_01 S.L.", "is_company": True, "country_id": env.ref("base.es").id, "vat": "ESB87654323"})
dist = {an("Actividad", "Extranjería").id: 100, an("Sede", "Madrid").id: 100}

# 1. Cita web: 40 € + IVA, serie CIT
cita = env["account.move"].create({"move_type": "out_invoice", "partner_id": cliente.id, "journal_id": J("CIT").id,
    "invoice_line_ids": [(0, 0, {"product_id": P("Consulta inicial Extranjería").id, "quantity": 1,
                                 "analytic_distribution": dist})]})
cita.action_post()
comprueba(cita.name.startswith("CIT/"), f"Serie de citas: {cita.name}")
comprueba(round(cita.amount_total, 2) == 48.40, f"Consulta 40 € + IVA 21 % = {cita.amount_total} €")

# 2. Expediente de extranjería: honorarios con IVA + suplido (tasa) sin IVA, serie EXP
exp = env["account.move"].create({"move_type": "out_invoice", "partner_id": cliente.id, "journal_id": J("EXP").id,
    "ref": "EXPEDIENTE_01", "invoice_line_ids": [
        (0, 0, {"product_id": P("Honorarios de expediente").id, "name": "Honorarios trámite (EXPEDIENTE_01)",
                "quantity": 1, "price_unit": 400.0, "analytic_distribution": dist}),
        (0, 0, {"product_id": P("Suplido · tasa oficial").id, "name": "Suplido: tasa oficial (EXPEDIENTE_01)",
                "quantity": 1, "price_unit": 38.28, "tax_ids": [(5, 0, 0)]})]})
exp.action_post()
comprueba(exp.name.startswith("EXP/"), f"Serie de expedientes: {exp.name}")
comprueba(round(exp.amount_total, 2) == 522.28, f"400 € + IVA 84 € + suplido 38,28 € = {exp.amount_total} €")
linea_suplido = exp.line_ids.filtered(lambda l: l.name and l.name.startswith("Suplido"))
comprueba(linea_suplido.account_id.code == "555001", f"El suplido va a la cuenta {linea_suplido.account_id.code}")
linea_hon = exp.invoice_line_ids.filtered(lambda l: l.name.startswith("Honorarios"))
comprueba(linea_hon.account_id.code == "705000", f"Los honorarios van a la cuenta {linea_hon.account_id.code} (prestaciones de servicios)")

# 3. Cobro parcial de 200 € por banco (factura global con varios cobros)
pago = env["account.payment.register"].with_context(active_model="account.move", active_ids=exp.ids).create(
    {"amount": 200.0, "journal_id": J("BCB").id})._create_payments()
comprueba(exp.payment_state == "partial", f"Cobro parcial: estado {exp.payment_state}, pendiente {exp.amount_residual} €")

# 4. Empresa: honorarios con IVA 21 % y retención de IRPF 15 %
ret = env["account.move"].create({"move_type": "out_invoice", "partner_id": empresa.id, "journal_id": J("EXP").id,
    "invoice_line_ids": [(0, 0, {"product_id": P("Honorarios de expediente").id, "quantity": 1, "price_unit": 1200.0,
                                 "tax_ids": [(6, 0, (tax("21% S") | tax("15% Ret IRPF")).ids)]})]})
ret.action_post()
comprueba(round(ret.amount_total, 2) == 1272.0, f"1.200 € + IVA 252 € − IRPF 180 € = {ret.amount_total} €")

# 5. Rectificativa de la cita (serie propia)
rev = cita._reverse_moves([{"ref": "Devolución de la consulta"}])
rev.action_post()
comprueba(rev.name.startswith("RCIT/"), f"Rectificativa con serie propia: {rev.name}")

# 6. Verifactu. Solo en el ENTORNO DE PRUEBAS se carga el certificado de pruebas PÚBLICO de la AEAT que trae el
#    propio Odoo (l10n_es_edi_verifactu/demo/certificates, entidad ficticia «ENTIDAD PRUEBAS»). Nunca un certificado
#    real: el real lo carga en Odoo la persona autorizada del despacho.
import base64
from odoo.tools import file_open, BinaryBytes
if co.l10n_es_edi_verifactu_test_environment and not co.l10n_es_edi_verifactu_certificate_ids:
    with file_open("l10n_es_edi_verifactu/demo/certificates/"
                   "Certificado_RPJ_A39200019_CERTIFICADO_ENTIDAD_PRUEBAS_5_Pre.p12", "rb") as f:
        env["certificate.certificate"].create({"name": "Certificado de PRUEBAS de la AEAT (ficticio)",
            "content": BinaryBytes(f.read()), "pkcs12_password": "1234", "scope": "verifactu",
            "company_id": co.id})
# Se genera el registro (lo que haría «Enviar») SIN mandarlo a la AEAT (no hay certificado y es una
#    prueba). Se comprueba que se crea un registro encadenado por factura.
docs = (cita | exp | ret | rev)._l10n_es_edi_verifactu_create_documents()
sin_red = False
for m, d in zip((cita, exp, ret, rev), docs.values()):
    err = d.errors or ""
    if "Error de red" in err:
        sin_red = True
        estado = "sin conexión con la AEAT (la huella se calcula, pero el documento necesita el WSDL de la AEAT)"
    elif d.state == "invalid":
        estado = "no válido: " + err.replace("<p>", "").replace("</p>", " ").replace("<ul><li>", "").replace("</li></ul>", "")
    else:
        estado = f"{d.state} · eslabón {d.chain_index}"
    print(f"     Verifactu {m.name}: {estado}")
comprueba(len(docs) == 4, "Se intenta un registro Verifactu por factura (no se envía nada)")
if sin_red:
    print("AVISO Verifactu no se ha podido completar: este equipo no llega a prewww2.aeat.es. Repetir la prueba en un"
          " equipo con salida a Internet (entorno de pruebas de la AEAT).")
env.cr.commit()
print("RESULTADO:", "todo correcto" if ok else "hay fallos")
