"""PDF de texto de varias páginas, sin dependencias (Helvetica, codificación WinAnsi). Para exportaciones."""

from __future__ import annotations

import textwrap

_W, _H, _M = 595, 842, 50


def _esc(t: str) -> bytes:
    t = t.replace("—", "-").replace("–", "-").replace("€", "EUR").replace("«", '"').replace("»", '"')
    return t.encode("cp1252", "replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(lines: list[tuple[str, str]], footer: str = "") -> bytes:
    """`lines`: (estilo, texto) con estilo «h» (título), «b» (negrita), «n» (normal), «s» (pequeño)."""
    size = {"h": 14, "b": 10, "n": 10, "s": 8}
    width = {"h": 70, "b": 95, "n": 95, "s": 120}
    pages: list[list[bytes]] = [[]]
    y = _H - _M
    for style, text in lines:
        for chunk in (textwrap.wrap(text, width[style]) or [""]) if text else [""]:
            if y < _M + 30:
                pages.append([])
                y = _H - _M
            font = b"/F2" if style in ("h", "b") else b"/F1"
            pages[-1].append(b"BT " + font + b" %d Tf %d %d Td (" % (size[style], _M, y) + _esc(chunk) + b") Tj ET")
            y -= size[style] + 4
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n)).encode()
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % n)
    font_ids = (3 + 2 * n, 4 + 2 * n)
    for i, ops in enumerate(pages):
        foot = f"{footer} · página {i + 1} de {n}" if footer else f"Página {i + 1} de {n}"
        ops = ops + [b"BT /F1 7 Tf %d 25 Td (" % _M + _esc(foot) + b") Tj ET"]
        content = b"\n".join(ops)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>" % (_W, _H, 4 + 2 * i, *font_ids))
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    enc = b"/Encoding /WinAnsiEncoding"
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica " + enc + b" >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold " + enc + b" >>")
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
