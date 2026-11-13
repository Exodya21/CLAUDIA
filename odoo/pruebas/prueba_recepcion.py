# Prueba de Recepción y cajas en la base de pruebas (DATOS FICTICIOS), como lo harían las personas:
# Recepción Barcelona cobra, Contabilidad confirma, Recepción cuenta la caja y otra persona la valida.
# Se ejecuta UNA vez sobre una base recién montada (crea cobros y el cierre de caja de hoy).
from odoo.exceptions import UserError

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
U = lambda login: env["res.users"].search([("login", "=", login)], limit=1)
rec, c1, c2 = U("recepcion.bcn"), U("contabilidad.1"), U("contabilidad.2")
sede = env["sp.sede"].search([("code", "=", "BCN"), ("company_id", "=", co.id)], limit=1)
P = env["res.partner"]
cli = P.search([("name", "=", "CLIENTE_03")], limit=1) or P.create({"name": "CLIENTE_03"})
cli4 = P.search([("name", "=", "CLIENTE_04")], limit=1) or P.create({"name": "CLIENTE_04"})
ok = True
def comprueba(cond, texto):
    global ok
    print(("OK   " if cond else "FALLO") + " " + texto); ok = ok and cond

Pay = env["account.payment"].with_user(rec).with_context(sp_recepcion=True)
def cobro(cliente, importe, tipo, memo=""):
    return Pay.create({"payment_type": "inbound", "partner_type": "customer", "partner_id": cliente.id,
                       "amount": importe, "journal_id": sede.journal_id.id, "sp_tipo": tipo, "memo": memo})

a = cobro(cli, 50, "consulta", "Consulta laboral"); a.action_post()
b = cobro(cli4, 200, "provision", "Provisión EXPEDIENTE_03"); b.action_post()
comprueba(a.sp_justificante_numero.startswith("REC-BCN-"), f"Justificantes {a.sp_justificante_numero} y {b.sp_justificante_numero}")
adj = env["ir.attachment"].sudo().search([("res_model", "=", "account.payment"), ("res_id", "=", a.id),
                                          ("name", "like", "Justificante")])
comprueba(bool(adj) and adj[0].mimetype == "application/pdf", f"Justificante guardado en PDF: {adj[:1].name}")
rep = cobro(cli, 50, "consulta")
try:
    rep.action_post(); comprueba(False, "Debía avisar de cobro repetido")
except UserError:
    comprueba(True, "Aviso de posible cobro repetido")
rep.sp_motivo_duplicado = "Segunda consulta del mismo cliente para otro asunto"
rep.action_post()
a.with_user(c1).action_sp_confirmar()
comprueba(a.sp_estado == "confirmado", "Contabilidad confirma el cobro")
cierre = env["sp.cierre.caja"].with_user(rec).create({"sede_id": sede.id, "contado": 295, "notas": "Faltan 5 € del cambio"})
cierre.action_contar()
comprueba((cierre.esperado, cierre.diferencia) == (300.0, -5.0), f"Recuento: registros {cierre.esperado} €, contado 295 €, diferencia {cierre.diferencia} €")
cierre.with_user(c2).action_validar()
comprueba(cierre.estado == "validado" and bool(cierre.ajuste_move_id), f"Cierre validado por otra persona, ajuste {cierre.ajuste_move_id.name}")
env.cr.commit()
print("RESULTADO:", "todo correcto" if ok else "hay fallos")
