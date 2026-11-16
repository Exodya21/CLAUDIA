# Configuración de Banco (módulo sp_banco) con DATOS FICTICIOS: un IBAN ficticio (formato válido) para cada banco de
# la S.L., para que cada extracto vaya solo a su cuenta por los últimos dígitos. En la instalación real se ponen los
# IBAN de verdad directamente en Odoo (Contabilidad → Configuración → Diarios), nunca en el repositorio.
#   odoo-bin shell -d <base> ... < odoo/configuracion/banco.py

BANCOS = [("BCA", "2100", "0001", "0000011111"), ("BCB", "2100", "0001", "0000022222"), ("BCC", "2100", "0001", "0000033333")]


def iban_es(entidad, oficina, cuenta10):
    def dc(s):
        pesos = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]
        r = 11 - sum(int(c) * p for c, p in zip(s.zfill(10), pesos)) % 11
        return {10: 1, 11: 0}.get(r, r)
    ccc = f"{entidad}{oficina}{dc('00' + entidad + oficina)}{dc(cuenta10)}{cuenta10}"
    control = 98 - int(ccc + "142800") % 97  # E=14, S=28
    return f"ES{control:02d}{ccc}"


co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
for code, ent, ofi, cta in BANCOS:
    j = env["account.journal"].search([("company_id", "=", co.id), ("code", "=", code)], limit=1)
    if j and not j.bank_account_id:
        iban = iban_es(ent, ofi, cta)
        j.bank_account_id = env["res.partner.bank"].create({"account_number": iban, "partner_id": co.partner_id.id})
        print(f"{j.name}: IBAN ficticio {iban}")
    # Odoo 20 no emite facturas que muestren una cuenta propia sin verificar («de confianza»). En la instalación real
    # la verifica una persona autorizada después de comprobar el IBAN con el banco.
    if j and j.bank_account_id and not j.bank_account_id.allow_out_payment:
        j.bank_account_id.with_context(install_mode=True).allow_out_payment = True  # el script corre como superusuario
        print(f"{j.name}: cuenta propia verificada")
env.cr.commit()
print("Banco configurado.")
