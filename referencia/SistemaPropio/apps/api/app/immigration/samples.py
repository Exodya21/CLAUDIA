"""Documentos FICTICIOS de muestra para pruebas y demostración (F4.3): contrato, padrón, TIE y tasa.

Imitan la estructura de los modelos públicos (contrato del SEPE, certificado de empadronamiento, TIE con MRZ TD1,
modelo 790) con datos inventados y la marca «DOCUMENTO FICTICIO». No reproducen documentos de ninguna persona.
"""

from __future__ import annotations

import io
from datetime import date

from . import mrz

FICT = "DOCUMENTO FICTICIO — SIN VALOR"


def _pdf(lines: list[tuple[str, int]]) -> bytes:
    """PDF con capa de texto (como los que genera un programa), escrito a mano: Helvetica, WinAnsi, una página."""
    def esc(t: str) -> bytes:
        t = t.replace("—", "-").replace("€", "EUR")
        return t.encode("cp1252", "replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    ops, y = [], 800
    for text, size in lines:
        font = b"/F2" if size > 11 else b"/F1"
        ops.append(b"BT " + font + b" %d Tf 50 %d Td (" % (size, y) + esc(text) + b") Tj ET")
        y -= size + 9
    content = b"\n".join(ops)
    enc = b"/Encoding /WinAnsiEncoding"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica " + enc + b" >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold " + enc + b" >>",
    ]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def _scan(lines: list[tuple[str, int]]) -> bytes:
    """PDF escaneado (imagen sin texto): obliga a la lectura por OCR."""
    from PIL import Image, ImageDraw

    from ..seed_immigration import _font

    img = Image.new("RGB", (1654, 2339), (252, 252, 250))
    d = ImageDraw.Draw(img)
    y = 120
    for text, size in lines:
        d.text((110, y), text, fill=(15, 15, 15), font=_font(int(size * 2.4)))
        y += int(size * 2.4) + 26
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=200)
    return buf.getvalue()


def contrato(empresa="Construcciones Ficticias Demo SL", cif="B12345674", trabajador="Carla Ferrer Demo",
             nie="Y7654321G", scanned=False) -> bytes:
    lines = [
        (FICT, 10),
        ("CONTRATO DE TRABAJO INDEFINIDO", 14),
        ("Código de contrato: 100", 11),
        ("DATOS DE LA EMPRESA", 12),
        (f"NIF/CIF: {cif}", 11),
        (f"Nombre o razón social: {empresa}", 11),
        ("Domicilio social: C/ Inventada 10, 2º A, 28001 Madrid", 11),
        ("Cuenta de cotización: 28 1234567 89", 11),
        ("Actividad económica: Construcción de edificios", 11),
        ("CNAE: 4121", 11),
        ("Centro de trabajo: Avenida Demo 5, 28002 Madrid", 11),
        ("REUNIDOS", 12),
        ("De una parte D. Juan Prueba Ejemplo, con DNI 12345678Z, en representación de la empresa.", 10),
        (f"De otra parte D./Dña. {trabajador}, con NIE {nie}, como trabajador.", 10),
        ("CLÁUSULAS", 12),
        ("Puesto de trabajo: Peón de la construcción", 11),
        ("La jornada de trabajo será a tiempo completo, de lunes a viernes.", 10),
        ("La retribución total será de 18.000,00 euros brutos anuales.", 10),
    ]
    return _scan(lines) if scanned else _pdf(lines)


def padron(nie="Y7654321G", scanned=True) -> bytes:
    lines = [
        (FICT, 10),
        ("AYUNTAMIENTO DE GETAFE", 13),
        ("CERTIFICADO DE EMPADRONAMIENTO", 13),
        ("Nombre: Carla Ferrer Demo", 11),
        (f"Documento: {nie}", 11),
        ("Domicilio: Calle Ficticia 14, 3º B, 28901 Getafe", 11),
        ("Fecha de alta en el domicilio: 01/02/2024", 11),
        (f"Fecha de expedición: {date.today().strftime('%d/%m/%Y')}", 11),
    ]
    return _scan(lines) if scanned else _pdf(lines)


def tasa(nrc="0520000000000000000ABCD1") -> bytes:
    return _pdf([
        (FICT, 10),
        ("MODELO 790 - CÓDIGO 052 - TASA", 13),
        ("Tasa de tramitación de autorizaciones y documentos de identidad de extranjeros", 10),
        ("Importe: 38,28 €", 11),
        (f"NRC: {nrc}", 11),
    ])


def tie_image(nie="Y7654321G", surname="FERRER DEMO", given="CARLA", birth=date(1990, 3, 14),
              expiry=date(2030, 1, 1), sex="F") -> bytes:
    """Reverso de una TIE inventada con su MRZ TD1 (N.I.E. en el campo opcional)."""
    from PIL import Image, ImageDraw

    from ..seed_immigration import _font

    lines = mrz.build_td1("IR", "ESP", "E00000001", nie, birth, sex, expiry, "UTO", surname, given)
    img = Image.new("RGB", (1300, 820), (238, 242, 236))
    d = ImageDraw.Draw(img)
    d.text((40, 30), "TARJETA DE IDENTIDAD DE EXTRANJERO (FICTICIA)", fill=(30, 30, 30), font=_font(34))
    d.text((40, 90), f"NIE {nie}", fill=(30, 30, 30), font=_font(30))
    d.rectangle((0, 560, 1300, 820), fill=(255, 255, 255))
    for i, ln in enumerate(lines):
        d.text((40, 585 + i * 70), ln, fill=(0, 0, 0), font=_font(48))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
