# Lectura de tickets de gasto: interpretación del texto. Copiado de Sistema Propio F5.6c
# (referencia/SistemaPropio/apps/api/app/services/receipts.py, función parse y auxiliares) sin cambios en la lógica.
# El texto se obtiene con sp_contabilidad.lectura.extraer (pdftotext / Tesseract en el servidor).
import re
from datetime import date

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
    # Cambio respecto a Sistema Propio: DNI y NIE con el validador de sp_contabilidad (misma regla de la letra).
    from odoo.addons.sp_contabilidad.lectura.identificadores import valid_dni, valid_nie

    if v[0].isdigit():
        return valid_dni(v)
    if v[0] in "XYZ":
        return valid_nie(v)
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
