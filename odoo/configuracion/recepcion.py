# Configuración de Recepción y cajas (módulo sp_recepcion) con DATOS FICTICIOS.
# Requiere: base_contable.py ya ejecutado y el módulo sp_recepcion instalado.
#   odoo-bin shell -d <base> ... < odoo/configuracion/recepcion.py
# Idempotente. Crea:
#   - Una sede por cada caja de la S.L. (Caja Barcelona → sede Barcelona, código BCN…).
#   - Usuarios de DEMOSTRACIÓN para probar la separación de funciones: una persona de Recepción por sede (solo ve
#     su sede), dos de Contabilidad, una de Atención al cliente y un letrado. Contraseña = usuario. SOLO para la base de pruebas: en la real se crean las personas de verdad.

SEDES = [("CBAR", "Barcelona", "BCN"), ("CMAD", "Madrid", "MAD"), ("CVAL", "Valencia", "VLC")]
USUARIOS_DEMO = [
    ("recepcion.bcn", "Recepción Barcelona (demo)", "sp_recepcion.group_sp_recepcion", "BCN"),
    ("recepcion.mad", "Recepción Madrid (demo)", "sp_recepcion.group_sp_recepcion", "MAD"),
    ("recepcion.vlc", "Recepción Valencia (demo)", "sp_recepcion.group_sp_recepcion", "VLC"),
    ("contabilidad.1", "Contabilidad 1 (demo)", "sp_recepcion.group_sp_responsable", "BCN"),
    ("contabilidad.2", "Contabilidad 2 (demo)", "sp_recepcion.group_sp_responsable", "BCN"),
    ("atc.demo", "Atención al cliente (demo)", "sp_recepcion.group_sp_devolucion_revision", "BCN"),
    ("letrado.demo", "Letrado (demo)", "sp_recepcion.group_sp_devolucion_letrado", "BCN"),
]

co = env["res.company"].search([("name", "=", "Despacho S.L. (demo)")], limit=1)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
log = []
sedes = {}
for code_diario, nombre, codigo in SEDES:
    caja = env["account.journal"].search([("company_id", "=", co.id), ("code", "=", code_diario)], limit=1)
    sede = env["sp.sede"].search([("company_id", "=", co.id), ("code", "=", codigo)], limit=1)
    if not sede and caja:
        sede = env["sp.sede"].create({"name": nombre, "code": codigo, "journal_id": caja.id, "company_id": co.id})
        log.append(f"Sede {nombre} ({codigo}) con {caja.name}")
    sedes[codigo] = sede

for login, nombre, grupo, sede in USUARIOS_DEMO:
    u = env["res.users"].with_context(active_test=False).search([("login", "=", login)], limit=1)
    if not u:
        u = env["res.users"].create({"login": login, "name": nombre, "password": login,
                                     "company_id": co.id, "company_ids": [(6, 0, co.ids)],
                                     "group_ids": [(4, env.ref("base.group_user").id), (4, env.ref(grupo).id)]})
        log.append(f"Usuario de demostración {login}")
    u.sp_sede_id = sedes.get(sede)

# El administrador de la base de pruebas también es responsable, para poder verlo todo.
env.ref("base.user_admin").group_ids = [(4, env.ref("sp_recepcion.group_sp_responsable").id)]
env.ref("base.user_admin").sp_sede_id = sedes.get("BCN")
env.cr.commit()
print("\n".join(log) or "Nada que cambiar: Recepción ya estaba configurada.")
