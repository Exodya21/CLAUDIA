"""Lectura de documentos de extranjería: texto (OCR local), MRZ, tipo propuesto y fechas visibles.

Todo propone; nada decide. El tipo, las fechas y la validez los confirma una persona (regla 7, A-10).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

from ..services import receipts
from . import extract, mrz

# Orden = prioridad. (tipo, patrón sobre texto sin acentos y en minúsculas)
RULES: list[tuple[str, str]] = [
    ("requerimiento", r"\brequerimiento\b.*\b(plazo|subsan|aport)"),
    ("resolucion", r"\bresuelv[eo]\b|\bresolucion\b.*\b(conceder|denegar|estimar|desestimar|archiv)"),
    ("resguardo_presentacion", r"justificante de presentacion|resguardo de presentacion|registro electronico|\bgeiser\b"),
    ("tasa_790", r"modelo 790|\b790\b.*\btasa\b|\btasa\b.*\b790\b"),
    ("formulario_ex", r"\bex[- ]?(00|02|03|10|11|26|32)\b|solicitud de autorizacion de residencia"),
    ("antecedentes_origen", r"antecedentes penales|criminal record|police clearance"),
    ("empadronamiento", r"empadronamiento|padron municipal|certificado de padron|volante de padron"),
    ("informe_esfuerzo", r"esfuerzo de integracion"),
    ("informe_integracion", r"informe de (integracion|arraigo)"),
    ("dele_ccse", r"instituto cervantes|\bdele\b|\bccse\b"),
    ("contrato_trabajo", r"contrato de trabajo|contrato laboral"),
    ("nominas", r"\bnomina\b|recibo individual justificativo del pago de salarios"),
    ("vida_laboral", r"vida laboral"),
    ("seguro_medico", r"seguro.*(salud|enfermedad|medico)|poliza.*asistencia sanitaria"),
    ("vivienda", r"vivienda adecuada|habitabilidad"),
    ("certificado_nacimiento", r"(acta|certificado|partida|certificacion) de nacimiento|birth certificate"),
    ("vinculo_familiar", r"matrimonio|pareja de hecho|marriage certificate"),
    ("representacion", r"designacion de representante|otorga su representacion|autoriza.*represent"),
    ("matricula_formacion", r"\bmatricula\b"),
    ("vulnerabilidad", r"vulnerabilidad"),
]

_DATE = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?!\d)")
_ISSUE = re.compile(r"(fecha de (expedicion|emision)|expedid[oa] (el|en)|a fecha de|emitido el|dated?)\D{0,20}"
                    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def ocr_text(data: bytes, mime: str) -> tuple[str, str]:
    ex = receipts.extractor()
    if ex is None:
        return "", "ninguno"
    try:
        return ex.text(data, mime), ex.name
    except (subprocess.SubprocessError, OSError):
        return "", ex.name


# Cambia cuando mejora la lectura: los documentos leídos con una versión anterior se señalan para «Volver a leer»
READER_VERSION = "2026-11-05.2"
MRZ_WHITELIST = "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"


def _mrz_ocr_image(path: str) -> str:
    r = subprocess.run(["tesseract", path, "stdout", "--psm", "6", "-c", MRZ_WHITELIST], capture_output=True, timeout=60)
    return r.stdout.decode("utf-8", "replace")


def _osd_rotation(path: str) -> int:
    """Giro que necesita la página según tesseract (0, 90, 180 o 270). 0 si no lo sabe (página en blanco…)."""
    try:
        r = subprocess.run(["tesseract", path, "stdout", "--psm", "0"], capture_output=True, timeout=30)
        m = re.search(r"Rotate:\s*(\d+)", r.stdout.decode("utf-8", "replace"))
        return int(m.group(1)) if m else 0
    except Exception:  # noqa: BLE001
        return 0


def _best(found: dict | None, txt: str, best: tuple[int, str]) -> tuple[int, str]:
    """Puntúa una lectura: MRZ válida > MRZ con algún control fallido > nada."""
    if not found:
        return best
    score = 2 + sum(found["checks"].values()) if found["valid"] else 1 + sum(found["checks"].values()) / 10
    return (score, txt) if score > best[0] else best


def _mrz_in_pages(pages: list[str]) -> str:
    """Busca la MRZ en todas las páginas: primero derechas y, si no aparece, giradas según la orientación del texto
    (escaneos de lado o boca abajo). Devuelve el texto de la mejor lectura (válida si la hay)."""
    from PIL import Image

    best: tuple[int, str] = (0, "")
    hints: dict[str, int] = {}
    for page in pages:
        txt = _mrz_ocr_image(page)
        hints[page] = txt.count("<")
        best = _best(mrz.parse(txt), txt, best)
        if best[0] >= 2:
            return best[1]
    # Segunda vuelta con giros, empezando por las páginas con más «<» (restos de una MRZ torcida o boca abajo)
    for page in sorted(pages, key=lambda pg: -hints[pg]):
        rot = _osd_rotation(page)
        angles = [rot] if rot else []
        angles += [a for a in (180, 90, 270) if a not in angles][: 3 if len(pages) <= 3 else 1]
        for a in angles:
            rp = f"{page}.r{a}.png"
            Image.open(page).rotate(a, expand=True).save(rp)  # «Rotate» de tesseract = grados en sentido antihorario
            txt = _mrz_ocr_image(rp)
            best = _best(mrz.parse(txt), txt, best)
            if best[0] >= 2:
                return best[1]
    return best[1]


def ocr_mrz_pdf(data: bytes, max_pages: int = 40) -> str:
    """PDF escaneado (pasaporte completo de muchas páginas, TIE por las dos caras): busca la MRZ en todas las páginas."""
    if receipts.extractor() is None:
        return ""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.pdf")
            Path(src).write_bytes(data)
            subprocess.run(["pdftoppm", "-r", "250", "-gray", "-png", "-f", "1", "-l", str(max_pages), src,
                            os.path.join(tmp, "p")], capture_output=True, timeout=240)
            return _mrz_in_pages([str(p) for p in sorted(Path(tmp).glob("p*.png"))])
    except Exception:  # noqa: BLE001 - ayuda opcional
        return ""


def ocr_mrz(data: bytes, mime: str) -> str:
    """Segunda pasada solo para la MRZ: franja inferior de la imagen con el alfabeto de la MRZ."""
    if mime == "application/pdf":
        return ocr_mrz_pdf(data)
    if mime not in ("image/jpeg", "image/png") or receipts.extractor() is None:
        return ""
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("L")
        w, h = img.size
        band = img.crop((0, int(h * 0.62), w, h))
        if band.width < 1000:
            band = band.resize((band.width * 2, band.height * 2))
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "mrz.png")
            band.save(p)
            txt = _mrz_ocr_image(p)
            found = mrz.parse(txt)
            if found and found["valid"]:
                return txt
            # Foto de lado o boca abajo, o la MRZ no está en la parte de abajo: imagen entera con giros
            full = os.path.join(tmp, "full.png")
            (img.resize((img.width * 2, img.height * 2)) if img.width < 1200 else img).save(full)
            other = _mrz_in_pages([full])
            return other if mrz.parse(other) and (not found or mrz.parse(other)["valid"]) else txt
    except Exception:  # noqa: BLE001 - la segunda pasada es una ayuda; si falla se sigue sin ella
        return ""


def classify(text: str, mrz_data: dict | None) -> tuple[str | None, str | None]:
    if mrz_data:
        code = mrz_data["document_code"]
        if mrz_data["format"] == "TD3" and code.startswith("P"):
            return "pasaporte", "alta" if mrz_data["valid"] else "media"
        if mrz_data["format"] == "TD1":
            return "tie_nie", "alta" if mrz_data["valid"] else "media"
    t = norm(text)
    if "tarjeta de identidad de extranjero" in t:
        return "tie_nie", "media"
    for code, pat in RULES:
        if re.search(pat, t, re.S):
            return code, "media"
    return None, None


def issue_date(text: str, today: date | None = None) -> str | None:
    today = today or date.today()
    t = norm(text)
    for m in _ISSUE.finditer(t):
        try:
            d = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        except ValueError:
            continue
        if d <= today:
            return d.isoformat()
    return None


def read(data: bytes, mime: str, today: date | None = None) -> dict:
    text, engine = ocr_text(data, mime)
    # Primero la pasada específica de la franja MRZ (alfabeto restringido, más fiable); si no supera los dígitos de
    # control, la lectura general del documento.
    mrz_data = mrz.parse(ocr_mrz(data, mime), today)
    if not (mrz_data and mrz_data["valid"]):
        general = mrz.parse(text, today)
        if general and (general["valid"] or not mrz_data):
            mrz_data = general
    doc_type, conf = classify(text, mrz_data)
    out: dict = {"engine": engine, "text": text[:30000], "suggested_type": doc_type, "confidence": conf,
                 "fields": {"lector": READER_VERSION}}
    if mrz_data:
        out["fields"]["mrz"] = {k: v for k, v in mrz_data.items() if k != "lines"}
        out["fields"]["mrz_lines"] = mrz_data["lines"]
        if mrz_data.get("expiry_date"):
            out["fields"]["expires_on"] = mrz_data["expiry_date"]
    iss = issue_date(text, today)
    if iss:
        out["fields"]["issued_on"] = iss
    # Datos para la ficha del formulario (propuestas) e información del documento (NRC de la tasa, días cotizados…)
    ficha, info = extract.for_document(doc_type, text, mrz_data)
    if ficha:
        out["fields"]["ficha"] = ficha
    if info:
        out["fields"]["info"] = info
    if engine == "ninguno":
        out["message"] = "La lectura automática no está instalada en este servidor: indique el tipo a mano."
    elif not doc_type:
        out["message"] = "No se ha reconocido el tipo de documento: indíquelo a mano."
    return out


def name_matches(contact_given: str, contact_family: str, mrz_data: dict | None) -> bool | None:
    """¿Coincide el titular del documento con el cliente? None si no hay datos para comparar."""
    if not mrz_data:
        return None
    a = set(norm(f"{contact_given} {contact_family}").replace("-", " ").split())
    b = set(norm(f"{mrz_data.get('given_names', '')} {mrz_data.get('surname', '')}").split())
    if not a or not b:
        return None
    return len(a & b) >= 2 or a <= b or b <= a


def safe_name(s: str) -> str:
    s = norm(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return (s or "documento")[:60].upper()


__all__ = ["read", "classify", "name_matches", "Path"]
