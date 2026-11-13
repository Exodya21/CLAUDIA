{
    "name": "Despacho · Recepción y cajas",
    "summary": "Cobros de recepción con justificante no fiscal por sede, aviso de cobros repetidos, "
               "confirmación por Contabilidad y cierre de caja diario validado por otra persona.",
    "description": """
Recepción y cajas del despacho (documento 19 §3.1). Referencia funcional: Sistema Propio F5.2
(referencia/SistemaPropio/apps/api/app/reception/service.py).

- Sedes con su caja (diario de efectivo) y su numeración de justificantes (REC-BCN-2026-000001…).
- Cobro de recepción = pago de cliente de Odoo con sede, tipo (consulta, provisión, servicio, otro).
- Al registrarlo se buscan cobros parecidos (mismo cliente, importe y forma de pago en ±2 días, o la misma
  referencia en 90 días). Si los hay, solo se registra explicando el motivo, y Contabilidad recibe una actividad.
- Justificante en PDF, numerado por sede y año, generado una sola vez: NO es una factura.
- Contabilidad confirma el cobro. Anular exige motivo y no se puede si la caja de ese día ya está validada.
- Cada persona de Recepción solo ve y registra cobros y cierres de sus sedes; Contabilidad, todos.
- Devoluciones: registrada → revisión (Atención al cliente) → [letrado] → aprobada/rechazada (Contabilidad, nunca
  quien la solicitó) → pagada (rectificativa y pago, o pago de salida si no hay factura).
- Cierre de caja diario por sede: una persona cuenta, otra distinta valida. La diferencia exige motivo y se
  contabiliza como ajuste al validar. Un cierre validado no se modifica.
""",
    "version": "20.0.1.1.0",
    "category": "Accounting/Accounting",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/sp_recepcion_security.xml",
        "security/ir.access.csv",
        "data/sp_devolucion_data.xml",
        "report/justificante.xml",
        "wizard/anular_cobro_views.xml",
        "views/sede_views.xml",
        "views/account_payment_views.xml",
        "views/cierre_caja_views.xml",
        "views/devolucion_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
