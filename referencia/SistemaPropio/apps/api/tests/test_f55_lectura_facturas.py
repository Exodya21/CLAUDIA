"""Lectura de facturas recibidas (lector v2) con formatos habituales en España. Textos FICTICIOS que reproducen la
FORMA de facturas reales (etiquetas, orden, OCR defectuoso), nunca sus datos:

- billete de transporte «Factura simplificada» con tabla de IVA y etiquetas «Nº factura», «Fecha emisión», «… EUR»;
- minuta de honorarios escaneada: «n*» por «nº», fecha «Sevilla, 5 de noviembre de 2026», puntos guía convertidos en
  basura por el OCR, etiquetas de IVA/IRPF ilegibles y el total en la línea siguiente;
- minuta con el bloque del cliente (el despacho) ANTES que el emisor y el NIF del emisor solo en la firma.
"""

from __future__ import annotations

from app.accounting.invoices import read_invoice, valid_tax_id


def _dni(n: int) -> str:
    return f"{n:08d}{'TRWAGMYFPDXBNJZSQVHLCKE'[n % 23]}"


OWN_CIF = "B12345674"  # CIF ficticio del despacho en las muestras


def test_factura_simplificada_de_transporte():
    text = """Factura simplificada
    TRANSPORTES FICTICIOS S.A.U.
    Calle Inventada, 10 2 planta
    28000 Madrid
    CIF/NIF: A11111119
    Nº factura          L2026000000001
    Fecha emisión       02/11/2026
    Descripción                       IVA %          Precio de venta     Descuento    Importe
    Código reserva X1Y2Z3             10,00                 45,00            3,00       42,00
    Total Factura EUR                       42,00
    Importe IVA                              3,82
    Base imponible EUR                      38,18
    Especificación importe IVA
    Identific. IVA          %          Base IVA        Importe IVA        Total EUR
    IVA 10               10,00          38,18              3,82             42,00
    """
    p = read_invoice(text)
    assert p["numero"] == "L2026000000001" and p["fecha"] == "2026-11-02" and p["cif"] == "A11111119"
    assert (p["base_cents"], p["iva_cents"], p["total_cents"]) == (3818, 382, 4200)
    assert p["cuadra"] is True and p["confianza"] == "alta"
    assert p["proveedor_nombre"].upper().startswith("TRANSPORTES FICTICIOS")


def test_minuta_escaneada_con_ocr_defectuoso():
    nif = _dni(12345678)
    assert valid_tax_id(nif)
    text = f"""Persona Ficticia Demo Avda. Inventada n*%12B-1G
    Abogada 41000 - Sevilla
    Móvil.: 600.00.00.00
    Factura n* 143/26
    Sevilla,5 de noviembre de 2026
    MINUTA DE HONORARIOS profesionales que formula la Letrada que suscribe,
    con NIF {nif[:2]}.{nif[2:5]}.{nif[5:8]}-{nif[8]}, por Acompañamiento CMAC a la mercantil DESPACHO DEMO
    SERRANO S.L. con CIF {OWN_CIF} y con domicilio en Calle Inventada 1 LOCAL 08900
    - Acompañamiento CMAC ¿ooccoccncnnccnnccnon 60,000
    21% deL WA cccocncicininononncnoocnccncononananonononnononor cn connrnannnos 12,60€
    “15% del RP E nccininccinnnonooorncnrrrccrarcna 9,00€
    TOTAL ...:
    63,60€
    Importa la presente minuta de honorarios profesionales los figurados SESENTA Y TRES EUROS s.e.u.o.
    C/C: ES91-2100-0418-45-0200051332.
    """
    p = read_invoice(text, {OWN_CIF})
    assert p["numero"] == "143/26" and p["fecha"] == "2026-11-05"
    assert p["cif"] == nif, p
    assert (p["base_cents"], p["iva_cents"], p["retencion_cents"], p["total_cents"]) == (6000, 1260, 900, 6360)
    assert p["deducido"] == ["base_imponible"] and p["confianza"] == "media"  # la base se ha deducido: a revisar
    assert p["iban"] == "ES9121000418450200051332"


def test_minuta_con_el_cliente_antes_que_el_emisor():
    nif = _dni(87654321)
    text = f"""Paseo Inventado 1 – 2º A
    23000 - Jaén
    FACTURA Nº 65/ 2026
    DESPACHO DEMO SERRANO, S.L.
    N.I.F: B-{OWN_CIF[1:]}
    C/ INVENTADA, 1, LOCAL
    Jaén, a 5 de noviembre de 2026
    Factura de Honorarios por su Asistencia al acto de conciliación celebrado el día 3 de noviembre de 2026.
    HONORARIOS
    Asistencia Acto de Conciliación                                           60,00
    Total, Honorarios                                                         60,00
    I.V.A. 21 % sobre Honorarios                                              12,60
    Total Factura                                                             72,60
    Líquido a mi favor (s.e.o.u.)                                             72,60
    Firmado digitalmente por PERSONA FICTICIA - {nif}
    Fdo.: Persona Ficticia Demo
    BANCO DEMO IBAN ES91 2100 0418 4502 0005 1332
    """
    # Con el nombre del despacho (en producción, el de la entidad) o su CIF en OWN_TAX_IDS, el CIF del cliente se descarta
    for p in (read_invoice(text, own_name="Despacho Demo Serrano S.L."), read_invoice(text, {OWN_CIF})):
        assert p["cif"] == nif, p
        assert p["numero"] == "65/2026" and p["fecha"] == "2026-11-05"  # la fecha del acto (día 3) no se confunde
        assert (p["base_cents"], p["iva_cents"], p["total_cents"]) == (6000, 1260, 7260) and p["cuadra"]
        assert p["proveedor_nombre"] == "Persona Ficticia Demo"
    # Sin esa información no se adivina: se ofrecen los dos para que la persona elija
    p = read_invoice(text)
    assert set(p["cif_candidatos"]) == {OWN_CIF, nif}


def test_no_inventa():
    p = read_invoice("Documento sin datos de factura\nGracias por su visita")
    assert {k for k in p if k not in ("confianza", "lector")} == set() and p["confianza"] == "baja"
    # Cifras que no encajan entre sí: no se reparten a ojo
    p = read_invoice("FACTURA Nº A-1\nFecha: 01/10/2026\nconcepto 10,00\notro 7,77\nTOTAL: 50,00")
    assert "base_cents" not in p and p["total_cents"] == 5000
