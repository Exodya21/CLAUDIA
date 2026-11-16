{
    "name": "Despacho · Facturación por expediente",
    "summary": "Honorarios pactados por expediente; cada pago con el número de expediente en el concepto prepara su "
               "factura de anticipo (IVA y retención) y el último, la factura final que descuenta los anticipos.",
    "description": """
Facturación por expediente y conciliación por número de expediente (documento 19 §3.7; decisiones del 16/11/2026:
AL-12 «Contabilidad con un clic», factura final que descuenta los anticipos, AL-07 formato LAB-2026-0001).

Usa el estándar de Odoo 20 Community (pedido de venta con anticipos y factura final, módulo «sale»): este módulo solo
lo PREPARA. La numeración, el registro y el envío Verifactu de cada factura los hace el estándar al emitirla (AL-03).

- En el expediente se fijan los honorarios (base) y si el cliente practica retención de IRPF (empresa o profesional).
  Se crea un pedido de venta confirmado con IVA 21 % (y −15 % IRPF), serie EXP.
- Banco: si el concepto de un ingreso trae el número de un expediente (LAB-2026-0001, tolerante a espacios y trozos
  de la Norma 43), se propone «pago del expediente» con el desglose (base, IVA, retención) y lo que quedará pendiente.
- Contabilidad valida con un clic: se emite la factura de anticipo por el importe cobrado (IVA y retención incluidos)
  y se concilia el movimiento. Si con ese pago el expediente queda pagado, se emite además la factura final con los
  honorarios y los anticipos descontados (total 0 €). Si un único pago cubre todo, se emite una sola factura normal.
- Pagos de más, expedientes inexistentes o sin honorarios: excepción con su motivo. Nunca se emite nada sin validar.
""",
    "version": "20.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["sale", "l10n_es", "sp_expediente", "sp_banco"],
    "data": [
        "views/expediente_views.xml",
        "views/statement_line_views.xml",
    ],
    "installable": True,
}
