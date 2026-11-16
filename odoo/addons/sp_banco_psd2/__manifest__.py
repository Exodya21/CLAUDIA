{
    "name": "Despacho · Conexión directa con el banco (PSD2)",
    "summary": "Descarga automática de los movimientos de las cuentas del despacho a través de un agregador PSD2 "
               "autorizado (Enable Banking), con el consentimiento del despacho en cada banco cada 180 días.",
    "description": """
Conexión directa con el banco (paso 4 del orden de trabajo, 16/11/2026; charter 4.5; documento 19 §3.3).

Leer cuentas por PSD2 exige ser proveedor autorizado (AISP) por el Banco de España o de otro país de la UE: el
despacho no lo es, así que se usa un agregador autorizado (Enable Banking, AISP supervisado en Finlandia con pasaporte
en el EEE) que solo lee las cuentas del propio despacho con su consentimiento. Es una EXTERNALIZACIÓN parcial
(documento 18 §2): salen los movimientos de las cuentas del despacho hacia el agregador; hay que firmar el encargo
del tratamiento (RGPD art. 28) antes de usarlo con datos reales.

- Conexión por banco: «Autorizar en el banco» abre la banca del despacho; al volver, Odoo crea la sesión, lee las
  cuentas y las une al diario cuyo IBAN coincide EXACTAMENTE (si no, se elige a mano; nunca se adivina).
- Sincronización periódica (y a demanda): solo movimientos CONTABILIZADOS; se registran por el mismo camino que la
  Norma 43 (sin duplicar, original cifrado, propuestas de conciliación que valida Contabilidad).
- Consentimiento: máximo 180 días; aviso a Contabilidad 15 días antes; al caducar la conexión se marca y se pide
  renovar. «Revocar» cierra la sesión en el agregador.
- Credenciales de la aplicación FUERA de la base de datos (SP_EB_APP_ID y SP_EB_CLAVE, ruta del .pem en el
  servidor). La sesión y los IBAN se guardan cifrados (sp_cifrado).
- Si el banco limita las consultas (429), se reintenta en la siguiente vuelta.
""",
    "version": "20.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["sp_banco", "sp_cifrado"],
    "external_dependencies": {"python": ["cryptography", "requests"]},
    "data": [
        "security/ir.access.csv",
        "data/cron.xml",
        "views/conexion_views.xml",
    ],
    "installable": True,
}
