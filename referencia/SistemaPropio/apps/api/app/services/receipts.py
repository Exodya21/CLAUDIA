"""Justificantes de gasto: almacenamiento cifrado y lectura automática (OCR) con propuesta de campos.

- Almacén: archivos cifrados (Fernet, FIELD_ENCRYPTION_KEY) en RECEIPTS_DIR; en BD solo ruta, hash y tipo.
- Lectura: PDF con texto → pdftotext; imagen o PDF escaneado → Tesseract (español), todo DENTRO del servidor.
  Ningún justificante sale a servicios externos. Si el motor no está instalado, se dice y se rellena a mano.
- La lectura PROPONE campos con su confianza; la persona los revisa y confirma (I-079, Q-4.13, regla 7).
- `Extractor` es el punto de conexión para un proveedor de IA aprobado en el futuro (p. ej. el de Microsoft).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..config import get_settings
from ..security.credentials import _fernet

MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG"}


class ReceiptError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def sniff(data: bytes, declared: str | None) -> str:
    """Tipo real por la firma del archivo (no se confía en la extensión ni en lo que diga el navegador)."""
    if len(data) > MAX_BYTES:
        raise ReceiptError("El archivo supera 10 MB. Haga la foto con menos resolución o escanee en PDF.")
    for mime, magic in ALLOWED.items():
        if data.startswith(magic):
            return mime
    if data[8:12] == b"WEBP":
        raise ReceiptError("Formato WEBP no admitido. Use JPG, PNG o PDF.")
    raise ReceiptError("Formato no admitido. Use una foto JPG o PNG, o un PDF.")


def receipts_dir() -> Path:
    d = Path(os.environ.get("RECEIPTS_DIR") or get_settings().receipts_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def store(data: bytes) -> tuple[str, str]:
    """Cifra y guarda. Devuelve (ruta relativa, sha256 del original)."""
    sha = hashlib.sha256(data).hexdigest()
    name = f"{uuid.uuid4().hex}.bin"
    (receipts_dir() / name).write_bytes(_fernet().encrypt(data))
    return name, sha


def load(path: str) -> bytes:
    p = receipts_dir() / Path(path).name
    return _fernet().decrypt(p.read_bytes())


# ------------------------------------------------------------------ lectura
@dataclass
class Suggestion:
    engine: str
    text: str = ""
    fields: dict = field(default_factory=dict)  # campo -> {"value": ..., "confidence": "alta|media|baja"}
    message: str | None = None


class Extractor:
    name = "base"

    def text(self, data: bytes, mime: str) -> str:  # pragma: no cover - interfaz
        raise NotImplementedError


class LocalExtractor(Extractor):
    """pdftotext + Tesseract (spa) en el propio servidor."""

    name = "local-tesseract"

    @staticmethod
    def available() -> bool:
        return bool(shutil.which("tesseract") and shutil.which("pdftotext") and shutil.which("pdftoppm"))

    def _ocr_image(self, path: str) -> str:
        r = subprocess.run(["tesseract", path, "stdout", "-l", "spa", "--psm", "4"], capture_output=True, timeout=60)
        return r.stdout.decode("utf-8", "replace")

    def text(self, data: bytes, mime: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.pdf" if mime == "application/pdf" else "in.img")
            Path(src).write_bytes(data)
            if mime != "application/pdf":
                return self._ocr_image(src)
            r = subprocess.run(["pdftotext", "-layout", "-l", "3", src, "-"], capture_output=True, timeout=60)
            txt = r.stdout.decode("utf-8", "replace")
            if len(re.sub(r"\s", "", txt)) >= 20:
                return txt
            # PDF escaneado: rasterizar la primera página y leerla
            subprocess.run(["pdftoppm", "-r", "200", "-png", "-f", "1", "-l", "1", src, os.path.join(tmp, "p")],
                           capture_output=True, timeout=60)
            pages = sorted(Path(tmp).glob("p*.png"))
            return self._ocr_image(str(pages[0])) if pages else ""


    def ocr_pdf(self, data: bytes, dpi: int = 300, pages: int = 2) -> str:
        """Lee un PDF por OCR aunque traiga capa de texto (los escáneres a veces incrustan una muy mala)."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.pdf")
            Path(src).write_bytes(data)
            subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", str(pages), src, os.path.join(tmp, "p")],
                           capture_output=True, timeout=120)
            out = []
            for img in sorted(Path(tmp).glob("p*.png")):
                r = subprocess.run(["tesseract", str(img), "stdout", "-l", "spa", "--psm", "6"], capture_output=True, timeout=90)
                out.append(r.stdout.decode("utf-8", "replace"))
            return "\n".join(out)


def extractor() -> Extractor | None:
    return LocalExtractor() if LocalExtractor.available() else None


def read(data: bytes, mime: str) -> Suggestion:
    ex = extractor()
    if ex is None:
        return Suggestion(engine="ninguno", message="La lectura automática no está instalada en este servidor: rellene los datos a mano.")
    try:
        txt = ex.text(data, mime)
    except (subprocess.SubprocessError, OSError):
        return Suggestion(engine=ex.name, message="No se pudo leer el justificante. Rellene los datos a mano.")
    fields = parse(txt)
    msg = None if fields else "No se han reconocido datos en el justificante. Rellene los datos a mano."
    return Suggestion(engine=ex.name, text=txt[:20000], fields=fields, message=msg)


# ------------------------------------------------------------------ interpretación del texto
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.\s]\d{3})+|\d+)[,.](\d{2})(?!\d)")
_DATE = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})(?!\d)")
_TAX_ID = re.compile(r"(?<![A-Z0-9])([A-HJNP-SUVW][-\s]?\d{7}[-\s]?[0-9A-J]|\d{8}[-\s]?[A-Z]|[XYZ][-\s]?\d{7}[-\s]?[A-Z])(?![A-Z0-9])")
_SKIP_NAME = re.compile(r"factura|ticket|simplificada|fecha|hora|n[ºo°]\s|tel[eé]f|c/|calle|avda|www|http|@|nif|cif|iva", re.I)


def _cents(m: re.Match) -> int:
    return int(re.sub(r"[.\s]", "", m.group(1))) * 100 + int(m.group(2))


def _amounts(line: str) -> list[int]:
    return [_cents(m) for m in _AMOUNT.finditer(line)]


def _valid_cif(v: str) -> bool:
    letters = "JABCDEFGHI"
    digits = v[1:8]
    a = sum(int(d) for d in digits[1::2])
    b = sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
    ctrl = (10 - (a + b) % 10) % 10
    return v[8] in (str(ctrl), letters[ctrl])


def _valid_tax_id(v: str) -> bool:
    from ..validation import ValidationFailure, validate_identifier

    if v[0].isdigit() or v[0] in "XYZ":
        try:
            validate_identifier("DNI" if v[0].isdigit() else "NIE", v, "ES")
            return True
        except ValidationFailure:
            return False
    return _valid_cif(v)


def parse(text: str, today: date | None = None) -> dict:
    today = today or date.today()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict = {}

    # Fecha: la primera válida y no futura
    for m in _DATE.finditer(text):
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            dt = date(y, mth, d)
        except ValueError:
            continue
        if dt <= today and (today - dt).days < 730:
            out["expense_date"] = {"value": dt.isoformat(), "confidence": "alta"}
            break

    # NIF/CIF del proveedor (el primero válido)
    for m in _TAX_ID.finditer(text.upper()):
        v = re.sub(r"[-\s]", "", m.group(1))
        if _valid_tax_id(v):
            out["supplier_tax_id"] = {"value": v, "confidence": "alta"}
            break
        out.setdefault("supplier_tax_id", {"value": v, "confidence": "baja"})

    # Proveedor: primera línea con letras que no sea un rótulo genérico
    for ln in lines[:8]:
        letters = sum(c.isalpha() for c in ln)
        if letters >= 3 and not _SKIP_NAME.search(ln) and not _AMOUNT.search(ln):
            out["supplier_name"] = {"value": re.sub(r"\s{2,}", " ", ln)[:120], "confidence": "media"}
            break

    # Total: importe en líneas con TOTAL (no subtotal); si no, el mayor importe
    total = None
    for ln in lines:
        low = ln.lower()
        if re.search(r"\btotal\b", low) and "subtotal" not in low and not re.search(r"total\s+iva|iva\s+total", low):
            vals = _amounts(ln)
            if vals:
                total = max(vals) if total is None else max(total, max(vals))
    conf = "alta"
    if total is None:
        everything = _amounts(text)
        if everything:
            total, conf = max(everything), "baja"
    if total:
        out["amount_cents"] = {"value": total, "confidence": conf}

    # IVA: importe de la línea de cuota, o total − base
    vat = None
    base = None
    for ln in lines:
        low = ln.lower()
        vals = [v for v in _amounts(ln) if not total or v < total]
        if not vals:
            continue
        if re.search(r"\bbase\b", low):
            base = max(vals)
        elif re.search(r"\b(i\.?v\.?a|cuota)\b", low):
            pct = re.search(r"(\d{1,2})(?:[,.]\d+)?\s*%", ln)
            cand = [v for v in vals if not pct or v != int(pct.group(1)) * 100]
            if cand:
                vat = max(cand)
    if vat is None and base is not None and total and total > base:
        vat = total - base
    if vat is not None and total and vat < total:
        out["vat_cents"] = {"value": vat, "confidence": "media"}
    return out
