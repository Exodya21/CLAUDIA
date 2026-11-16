{
    "name": "Despacho · Banco y conciliación",
    "summary": "Importación de extractos (Norma 43, CAMT.053, CSV, Excel) y propuestas de conciliación explicadas que "
               "valida Contabilidad.",
    "description": """
Banco y conciliación (documento 19 §3.3; charter 4.5). Referencia: Sistema Propio F5.1/F5.4c/F5.6
(apps/api/app/bank/parsers.py, copiado en lectura/extractos.py; reglas de bank/matcher.py adaptadas).

Odoo 20 Community no trae importación de extractos ni pantalla de conciliación, y los módulos de la OCA aún no están
en la 20.0: este módulo cubre ambas cosas (decisión AL-01/AL-02).

- Importar uno o varios extractos: cada uno va a la cuenta cuyo IBAN termina igual; si no se sabe, no se adivina.
  «Comprobar sin importar». Reimportar no duplica (identificador estable). Se comprueba saldo inicial + movimientos =
  saldo final. El original queda adjunto.
- Agente de conciliación: propone con reglas deterministas y explica por qué (traspaso entre cuentas propias,
  referencia de factura o justificante, Bizum, TPV, devolución pagada, pago o factura de proveedor, importe y fecha).
  Lo que no cuadra queda como excepción con su motivo. Nunca concilia solo.
- Contabilidad valida (concilia), rechaza con motivo, contabiliza en una cuenta con motivo (comisiones, Seguridad
  Social…) o ignora con motivo. Un traspaso nunca cuenta como ingreso.
- Liquidación de TPV con la comisión del banco descontada: la comisión va a la 626.
- Elegir apuntes a mano: propuesta normal, pago parcial de un apunte o diferencia a una cuenta con motivo.
- Exportación CSV de los movimientos para la gestoría (sin IBAN).
- El extracto original se guarda cifrado (sp_cifrado); solo Contabilidad lo descarga en claro y se comprueba su huella.
""",
    "version": "20.0.1.2.0",
    "category": "Accounting/Accounting",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["account", "sp_recepcion", "sp_cifrado"],
    "data": [
        "security/sp_banco_security.xml",
        "security/ir.access.csv",
        "data/cron.xml",
        "views/importacion_views.xml",
        "views/statement_line_views.xml",
        "views/exportar_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
