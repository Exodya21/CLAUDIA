# Escenario de devolución con DATOS FICTICIOS (después de configuracion/recepcion.py). Se ejecuta una vez.
# Recepción la solicita, Atención al cliente la revisa y la escala, el letrado informa, Contabilidad la aprueba y la paga.
co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
U = lambda login: env["res.users"].search([("login", "=", login)], limit=1)
rec, atc, letrado, c1 = U("recepcion.bcn"), U("atc.demo"), U("letrado.demo"), U("contabilidad.1")
sede = env["sp.sede"].search([("code", "=", "BCN"), ("company_id", "=", co.id)], limit=1)
cli = env["res.partner"].search([("name", "=", "CLIENTE_03")], limit=1) or env["res.partner"].create({"name": "CLIENTE_03"})
d = env["sp.devolucion"].with_user(rec).create({
    "partner_id": cli.id, "importe": 50, "sede_id": sede.id,
    "motivo": "El cliente pide la devolución de la consulta porque no pudo asistir y avisó con 48 horas"})
d.with_user(atc).action_revisar()
d.with_user(atc).informe_revision = "Consta el aviso por correo con 48 horas de antelación"
d.with_user(atc).action_escalar()
d.with_user(letrado).opinion_legal = "Según las condiciones de la cita, procede devolver el importe íntegro"
d.with_user(letrado).action_informe_letrado()
d.with_user(c1).action_aprobar()
d.with_user(c1).diario_pago_id = sede.journal_id
d.with_user(c1).action_pagar()
env.cr.commit()
print(f"{d.name}: {d.estado} · pago {d.pago_id.name} de {d.pago_id.amount} € desde {d.pago_id.journal_id.name}")
