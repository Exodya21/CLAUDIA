{
    "name": "Despacho · Gastos de empleados",
    "summary": "Gastos con lectura del ticket en el servidor y forma de pago del despacho: efectivo de la caja de la "
               "sede, tarjeta de empresa o pagado por la persona.",
    "description": """
Gastos de empleados (documento 19 §3.2; charter 4.13 y 4.14). Referencia: Sistema Propio F5.0
(apps/api/app/services/receipts.py, copiado en lectura/tickets.py).

- Sobre «Gastos» estándar de Odoo 20 Community (hr_expense): la persona sube el ticket, el responsable aprueba y
  Contabilidad contabiliza.
- Lectura del ticket EN EL SERVIDOR (sin servicios externos ni créditos de pago): fecha, comercio, NIF, total e
  IVA. PROPONE y solo rellena lo vacío. El IVA es el del ticket: se elige el impuesto cuyo tipo lo reproduce.
- Forma de pago del despacho:
    · Efectivo de la caja de la sede → se paga desde la caja de la sede de la persona (cuenta 570…): la caja baja
      al contabilizar y entra en su cierre diario (sp_recepcion).
    · Tarjeta de empresa → pagado por la empresa con el banco que se elija.
    · Pagado por la persona → se le reembolsa.
""",
    "version": "20.0.1.0.0",
    "category": "Human Resources/Expenses",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["hr_expense", "sp_recepcion", "sp_contabilidad"],
    "data": [
        "views/hr_expense_views.xml",
    ],
    "installable": True,
}
