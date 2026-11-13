# Configuración de Gastos (módulo sp_gastos) con DATOS FICTICIOS. Requiere recepcion.py ya ejecutado.
#   odoo-bin shell -d <base> ... < odoo/configuracion/gastos.py
# Idempotente. Crea:
#   - Categorías de gasto (productos «se puede incluir en gastos») con su cuenta de gasto del PGC. Las cuentas son
#     PROVISIONALES hasta cerrar el plan de cuentas con la gestoría (T-40, cuestionario).
#   - Fichas de empleado para los usuarios de demostración; aprueba los gastos Contabilidad 1 (demo).

CATEGORIAS = [
    # nombre, cuenta (PGC pymes), xmlid del IVA soportado por defecto o None
    ("Desplazamientos (taxi, tren, parking)", "629000", None),
    ("Dietas y comidas", "629000", None),
    ("Material de oficina", "629000", "account_tax_template_p_iva21_bc"),
    ("Mensajería y correos", "629000", None),
    ("Tasas y suplidos pagados por cuenta de clientes", "555001", None),
    ("Servicios de profesionales", "623000", "account_tax_template_p_iva21_sc"),
    ("Publicidad y marketing", "627000", "account_tax_template_p_iva21_sc"),
    ("Suministros", "628000", "account_tax_template_p_iva21_sc"),
    ("Otros gastos", "629000", None),
]

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
log = []
for nombre, cuenta, iva in CATEGORIAS:
    p = env["product.product"].search([("name", "=", nombre), ("can_be_expensed", "=", True)], limit=1)
    if not p:
        acc = env["account.account"].with_company(co).search([("code", "=", cuenta), ("company_ids", "in", co.id)], limit=1)
        tax = env["account.chart.template"].with_company(co).ref(iva, raise_if_not_found=False) if iva else None
        p = env["product.product"].create({
            "name": nombre, "type": "service", "can_be_expensed": True, "standard_price": 0, "company_id": False,
            "supplier_taxes_id": [(6, 0, tax.ids)] if tax else [(5, 0, 0)]})
        p.with_company(co).property_account_expense_id = acc
        log.append(f"Categoría de gasto: {nombre} → {cuenta}")

aprobador = env["res.users"].search([("login", "=", "contabilidad.1")], limit=1)
aprobador_2 = env["res.users"].search([("login", "=", "contabilidad.2")], limit=1)  # aprueba los de Contabilidad 1
# Los responsables de Contabilidad aprueban gastos de su equipo (grupo «Aprobador de equipo»), nunca los suyos.
for u in (aprobador, aprobador_2):
    u.group_ids = [(4, env.ref("hr_expense.group_hr_expense_team_approver").id)]
for login in ("recepcion.bcn", "recepcion.mad", "recepcion.vlc", "contabilidad.1", "contabilidad.2", "atc.demo",
              "letrado.demo"):
    u = env["res.users"].search([("login", "=", login)], limit=1)
    if not u:
        continue
    jefe = (aprobador_2 if login == "contabilidad.1" else aprobador)
    emp = env["hr.employee"].search([("user_id", "=", u.id)], limit=1)
    if not emp:
        env["hr.employee"].create({"name": u.name, "user_id": u.id, "company_id": co.id, "expense_manager_id": jefe.id})
        log.append(f"Empleado de demostración: {u.name}")
    elif emp.expense_manager_id != jefe:
        emp.expense_manager_id = jefe
        log.append(f"Aprobador de gastos de {u.name}: {jefe.name}")
env.cr.commit()
print("\n".join(log) or "Nada que cambiar: Gastos ya estaba configurado.")
