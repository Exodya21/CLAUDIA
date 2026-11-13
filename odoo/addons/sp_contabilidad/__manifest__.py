{
    "name": "Despacho · Contabilidad (facturas de proveedores)",
    "summary": "Lectura de facturas recibidas en el propio servidor, cuadre con el total de la factura y aviso de "
               "facturas repetidas.",
    "description": """
Facturas de proveedores (documento 19 §3.4; charter 4.17). Referencia: Sistema Propio F5.4/F5.5
(apps/api/app/accounting/invoices.py, lector v2, copiado en lectura/facturas.py).

- Al subir el PDF o la foto de una factura (o con el botón «Leer factura»), se lee EN EL SERVIDOR (pdftotext y, si
  es escaneada, Tesseract) y se PROPONE: proveedor por su CIF (lo da de alta si no existe), número, fechas, base,
  IVA, retención y total. Se descarta el CIF del propio despacho. Lo que no encuentra, no lo inventa.
- El IVA es el que figura en la factura: se elige el impuesto del tipo que lo reproduce y, si hay céntimos de
  diferencia, se ajusta a mano. Solo se registra si el total de Odoo coincide con el total de la factura.
- Facturas repetidas (mismo proveedor y número, o mismo proveedor, importe y fecha, o el mismo archivo): solo se
  registran explicando el motivo.
- La imputación por Actividad y Sede se hace con los modelos de distribución analítica estándar de Odoo (por
  proveedor).
""",
    "version": "20.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["account", "l10n_es"],
    "external_dependencies": {"bin": ["pdftotext", "pdftoppm", "tesseract"]},
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
}
