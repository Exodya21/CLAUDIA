# Base contable del despacho en Odoo 20 Community (documento 19 §6, paso 1).
#
# Se ejecuta dentro de Odoo con su intérprete («shell»), sobre una base de datos que ya tenga instalados
# account, l10n_es, l10n_co y l10n_es_edi_verifactu:
#
#   odoo-bin shell -d <base> --addons-path=... < odoo/configuracion/base_contable.py
#
# Es IDEMPOTENTE: se puede ejecutar varias veces; busca antes de crear. Usa DATOS FICTICIOS (nombres, NIF y
# bancos de demostración). En la instalación real se cambian los valores del bloque CONFIGURACIÓN, nunca se suben
# datos reales al repositorio.
#
# Qué monta:
#   - Compañías: S.L. principal (España) y filial de Colombia. El autónomo del titular queda FUERA de Odoo
#     (AL-06, 13/11/2026): factura casi solo a la S.L., su contabilidad la lleva la gestoría y sus cuentas son
#     privadas. Sus facturas a la S.L. se registran en la S.L. como facturas de proveedor.
#   - Plan contable: PGC pymes (es_pymes) en España y plan colombiano (co) en Colombia. Monedas EUR y COP.
#   - Diarios de venta con series sin saltos: CIT (citas web) y EXP (expedientes), con rectificativas propias.
#   - Bancos A (Laboral), B (Extranjería) y C (Tesorería); cajas por sede (Barcelona, Madrid, Valencia).
#   - Cuentas propias: suplidos y fondos de clientes en mediación (pendientes de validar con la gestoría, T-40).
#   - Analítica con dos planes: Actividad (Laboral, Extranjería, Compartida) y Sede.
#   - Productos base de ejemplo: consultas de 50 € y 40 €, honorarios y suplido (el catálogo real lo da de alta
#     el despacho, charter 4.12).
#   - Verifactu activado en ENTORNO DE PRUEBAS en las compañías españolas. El certificado lo carga en Odoo la
#     persona autorizada; nunca va en el repositorio.

# ----------------------------------------------------------------------------------------------- CONFIGURACIÓN
COMPANIAS = [
    {"clave": "SL", "nombre": "Despacho S.L. (demo)", "pais": "ES", "plan": "es_pymes", "nif": "ESB12345674",
     "ciudad": "Barcelona", "sedes": ["Barcelona", "Madrid", "Valencia"], "factura": True},
    # AL-06 (13/11/2026): el autónomo NO va en Odoo. Se deja la entrada desactivada por si se decidiera lo contrario
    # («incluir»: True la vuelve a crear con sus series CIT/EXP y su Verifactu).
    {"incluir": False, "clave": "AUT", "nombre": "Autónomo del titular (demo)", "pais": "ES", "plan": "es_pymes", "nif": "ES00000000T",
     "ciudad": "Barcelona", "sedes": ["Barcelona"], "factura": True},
    {"clave": "CO", "nombre": "Filial Colombia (demo)", "pais": "CO", "plan": "co", "nif": False,
     "ciudad": "Bogotá", "sedes": [], "factura": False},
]
BANCOS = [("BCA", "Banco A · Laboral"), ("BCB", "Banco B · Extranjería"), ("BCC", "Banco C · Tesorería")]
SERIES_VENTA = [("CIT", "Facturas de citas web"), ("EXP", "Facturas de expedientes")]
CUENTAS_PROPIAS = [
    # código, nombre, tipo. Códigos provisionales del grupo 555 hasta cerrar el plan con la gestoría (T-40).
    ("555001", "Suplidos por cuenta de clientes", "asset_current"),
    ("555002", "Fondos de clientes en mediación (80 % cuota litis)", "liability_current"),
]
ANALITICA = {
    "Actividad": ["Laboral", "Extranjería", "Compartida"],
    "Sede": ["Barcelona", "Madrid", "Valencia", "Colombia"],
}
PRODUCTOS = [
    # nombre, precio, ¿IVA 21 %?, cuenta de ingresos propia (None = la del plan)
    ("Consulta inicial Laboral", 50.0, True, None),
    ("Consulta inicial Extranjería", 40.0, True, None),
    ("Honorarios de expediente", 0.0, True, None),
    ("Honorarios cuota litis (20 %)", 0.0, True, None),
    ("Suplido · tasa oficial", 0.0, False, "555001"),
]
# ----------------------------------------------------------------------------------------------------------------
COMPANIAS = [c for c in COMPANIAS if c.get("incluir", True)]

Company = env["res.company"].sudo()
log = []


def pais(codigo):
    return env["res.country"].search([("code", "=", codigo)], limit=1)


def moneda(codigo):
    cur = env["res.currency"].with_context(active_test=False).search([("name", "=", codigo)], limit=1)
    if not cur.active:
        cur.active = True
    return cur


def compania(cfg, primera):
    co = Company.search([("name", "=", cfg["nombre"])], limit=1)
    if not co and primera:
        # La compañía inicial de la base de datos pasa a ser la S.L. (aún no tiene asientos).
        co = Company.browse(1)
    vals = {"name": cfg["nombre"], "country_id": pais(cfg["pais"]).id, "city": cfg["ciudad"],
            "currency_id": moneda("EUR" if cfg["pais"] == "ES" else "COP").id}
    if cfg["nif"]:
        vals["vat"] = cfg["nif"]
    if co:
        if co.account_fiscal_country_id and co.chart_template != cfg["plan"] and \
                env["account.move"].search_count([("company_id", "=", co.id)]):
            raise ValueError(f"{co.name} ya tiene asientos con otro plan contable; no se cambia.")
        co.write(vals)
    else:
        # install_mode: no dejar que Odoo instale módulos de localización a mitad del script (recarga el registro y
        # rompe la transacción); el plan contable se carga después con try_loading.
        co = Company.with_context(install_mode=True).create(vals)
        env.user.company_ids |= co
    if co.chart_template != cfg["plan"]:
        env["account.chart.template"].try_loading(cfg["plan"], co, install_demo=False)
        log.append(f"{co.name}: plan contable {cfg['plan']}")
    return co


def diario(co, code, name, tipo, **extra):
    J = env["account.journal"].with_company(co)
    j = J.search([("company_id", "=", co.id), ("code", "=", code)], limit=1)
    if not j:
        j = J.create({"code": code, "name": name, "type": tipo, "company_id": co.id, **extra})
        log.append(f"{co.name}: diario {code} · {name}")
    return j


def cuenta(co, code, name, tipo):
    A = env["account.account"].with_company(co)
    a = A.search([("code", "=", code), ("company_ids", "in", co.id)], limit=1)
    if not a:
        a = A.create({"code": code, "name": name, "account_type": tipo, "company_ids": [(4, co.id)],
                      "reconcile": True})
        log.append(f"{co.name}: cuenta {code} · {name}")
    return a


def iva21_servicios(co):
    return env["account.tax"].search([("company_id", "=", co.id), ("type_tax_use", "=", "sale"),
                                      ("amount", "=", 21.0), ("name", "ilike", "S")], limit=1)


# 1. Compañías y planes contables
companias = {}
for i, cfg in enumerate(COMPANIAS):
    companias[cfg["clave"]] = compania(cfg, primera=(i == 0))
env.user.company_id = companias["SL"]
# Las búsquedas siguientes deben ver los datos de TODAS las compañías (reglas multicompañía de Odoo).
env = env(context=dict(env.context, allowed_company_ids=[c.id for c in companias.values()]))

# 2. Diarios, cuentas y Verifactu (compañías españolas)
for cfg in COMPANIAS:
    co = companias[cfg["clave"]]
    if cfg["pais"] != "ES":
        continue
    # Un despacho presta servicios: los ingresos van a 705000 «Prestaciones de servicios», no a 700000
    # «Ventas de mercaderías» (el plan pymes lo trae por defecto).
    servicios = env["account.account"].with_company(co).search([("code", "=", "705000"), ("company_ids", "in", co.id)], limit=1)
    for code, name in SERIES_VENTA:
        j = diario(co, code, name, "sale", refund_sequence=True)
        if servicios and j.default_account_id != servicios:
            j.default_account_id = servicios
    # En Odoo 20 la cuenta de ingresos por defecto es un campo de la compañía (income_account_id).
    if servicios and co.income_account_id != servicios:
        co.income_account_id = servicios
        log.append(f"{co.name}: ingresos de servicios en 705000")
    # El diario de ventas genérico (INV) se archiva para que solo se use CIT o EXP. Solo si no tiene asientos.
    generico = env["account.journal"].search([("company_id", "=", co.id), ("code", "=", "INV")], limit=1)
    if generico and not env["account.move"].search_count([("journal_id", "=", generico.id)]):
        generico.active = False
        log.append(f"{co.name}: diario genérico INV archivado (se factura solo con CIT y EXP)")
    # El banco que crea el plan contable pasa a ser el Banco A; se crean B y C.
    banco_inicial = env["account.journal"].search([("company_id", "=", co.id), ("type", "=", "bank"),
                                                   ("code", "not in", [b[0] for b in BANCOS])], limit=1)
    if banco_inicial and not env["account.journal"].search([("company_id", "=", co.id), ("code", "=", "BCA")]):
        banco_inicial.write({"code": "BCA", "name": BANCOS[0][1]})
    for code, name in BANCOS if cfg["clave"] == "SL" else BANCOS[:1]:
        diario(co, code, name, "bank")
    for sede in cfg["sedes"]:
        diario(co, "C" + sede[:3].upper(), f"Caja {sede}", "cash")
    for code, name, tipo in CUENTAS_PROPIAS:
        cuenta(co, code, name, tipo)
    if cfg["factura"] and not co.l10n_es_edi_verifactu_required:
        co.write({"l10n_es_edi_verifactu_required": True, "l10n_es_edi_verifactu_test_environment": True})
        log.append(f"{co.name}: Verifactu activado en ENTORNO DE PRUEBAS")

# 3. Analítica (compartida por todo el grupo)
Plan = env["account.analytic.plan"]
for plan_name, cuentas_an in ANALITICA.items():
    plan = Plan.search([("name", "=", plan_name)], limit=1) or Plan.create({"name": plan_name})
    for nombre in cuentas_an:
        if not env["account.analytic.account"].search([("plan_id", "=", plan.id), ("name", "=", nombre)]):
            env["account.analytic.account"].create({"name": nombre, "plan_id": plan.id, "company_id": False})
            log.append(f"Analítica {plan_name}: {nombre}")

# 4. Productos base (compartidos; impuestos y cuentas por compañía española)
Product = env["product.template"]
for nombre, precio, con_iva, cuenta_ingreso in PRODUCTOS:
    p = Product.search([("name", "=", nombre)], limit=1)
    if not p:
        p = Product.create({"name": nombre, "type": "service", "list_price": precio, "company_id": False,
                            "taxes_id": [(5, 0, 0)]})
        log.append(f"Producto: {nombre}")
    impuestos = env["account.tax"]
    for cfg in COMPANIAS:
        co = companias[cfg["clave"]]
        if cfg["pais"] != "ES":
            continue
        if con_iva:
            impuestos |= iva21_servicios(co)
        if cuenta_ingreso:
            acc = env["account.account"].with_company(co).search([("code", "=", cuenta_ingreso), ("company_ids", "in", co.id)], limit=1)
            p.with_company(co).property_account_income_id = acc
    p.taxes_id = [(6, 0, impuestos.ids)]

env.cr.commit()
print("\n".join(log) or "Nada que cambiar: la base contable ya estaba montada.")
print("Compañías:", ", ".join(f"{c.name} ({c.chart_template}, {c.currency_id.name})" for c in companias.values()))
