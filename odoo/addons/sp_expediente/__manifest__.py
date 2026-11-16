{
    "name": "Despacho · Expedientes (base)",
    "summary": "Expediente mínimo con número por área (LAB-2026-0001, EXT-2026-0001), cliente y estado.",
    "description": """
Base de los expedientes (charter 6.2; decisión AL-07 del 16/11/2026: formato ÁREA-AÑO-NÚMERO, p. ej. LAB-2026-0001).

Es la pieza mínima que necesitan la facturación y la conciliación por expediente (sp_facturacion). El módulo de
expedientes de Laboral y Extranjería (fases, plazos, documentos, MN Program) crecerá sobre este modelo.

- Número correlativo sin saltos por área y año, que no se puede cambiar.
- Cliente, área, fecha de apertura, responsable y estado (abierto / cerrado).
""",
    "version": "20.0.1.0.0",
    "category": "Services",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["account", "mail"],
    "data": [
        "security/ir.access.csv",
        "data/secuencias.xml",
        "views/expediente_views.xml",
    ],
    "installable": True,
}
