"""Texto de un PDF o de una imagen, leído EN EL SERVIDOR (sin servicios externos).

pdftotext (capa de texto) y, si el PDF es escaneado o es una imagen, Tesseract en español. Mismo criterio que
Sistema Propio (services/receipts.py · LocalExtractor). Las herramientas vienen en la imagen odoo/Dockerfile.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def disponible() -> bool:
    return bool(shutil.which("pdftotext") and shutil.which("pdftoppm") and shutil.which("tesseract"))


def _ocr_imagen(ruta: str, psm: str = "4") -> str:
    r = subprocess.run(["tesseract", ruta, "stdout", "-l", "spa", "--psm", psm], capture_output=True, timeout=90)
    return r.stdout.decode("utf-8", "replace")


def texto(datos: bytes, mimetype: str) -> str:
    """Texto del documento. PDF con capa de texto → pdftotext -layout; escaneado o imagen → OCR (300 ppp)."""
    if not disponible():
        raise RuntimeError("Faltan pdftotext/tesseract en el servidor (ver odoo/Dockerfile).")
    with tempfile.TemporaryDirectory() as tmp:
        es_pdf = mimetype == "application/pdf" or datos[:5] == b"%PDF-"
        src = os.path.join(tmp, "in.pdf" if es_pdf else "in.img")
        Path(src).write_bytes(datos)
        if not es_pdf:
            return _ocr_imagen(src)
        r = subprocess.run(["pdftotext", "-layout", "-l", "3", src, "-"], capture_output=True, timeout=60)
        txt = r.stdout.decode("utf-8", "replace")
        if len(re.sub(r"\s", "", txt)) >= 20:
            return txt
        subprocess.run(["pdftoppm", "-r", "300", "-png", "-f", "1", "-l", "2", src, os.path.join(tmp, "p")],
                       capture_output=True, timeout=120)
        return "\n".join(_ocr_imagen(str(p), "6") for p in sorted(Path(tmp).glob("p*.png")))
