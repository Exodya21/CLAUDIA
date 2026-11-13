# Copiado de Sistema Propio F5.6c (referencia/SistemaPropio/apps/api/app/accounting/invoices.py, lector v2) sin
# cambios en la lógica, salvo lo marcado como «Cambio respecto a Sistema Propio». Python puro: no depende de Odoo. Si se mejora, mejorarlo aquí y anotarlo en 11 · Changelog.
"""Facturas recibidas: lectura (propone), IBAN y muestras FICTICIAS (DR-CON-1, DR-CON-4).

La lectura propone número, CIF, fechas, base, IVA, retención y total; comprueba que base + IVA − retención = total.
NUNCA calcula el IVA: si la factura no lo trae, queda vacío y una persona lo confirma. Mejor vacío que equivocado.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from .identificadores import valid_cif, valid_dni, valid_nie

CATEGORIES = {"alquiler": "Alquiler", "suministros": "Suministros", "software": "Software y licencias",
              "telefonia": "Telefonía e internet", "gestoria": "Gestoría y asesoría", "marketing": "Marketing",
              "material": "Material de oficina", "limpieza": "Limpieza", "seguros": "Seguros",
              "tasas": "Tasas y suplidos", "formacion": "Formación", "otros": "Otros"}


def valid_tax_id(v: str) -> bool:
    v = re.sub(r"[\s\-.]", "", (v or "").upper())
    return valid_cif(v) or valid_dni(v) or valid_nie(v)


def normalize_tax_id(v: str) -> str:
    return re.sub(r"[\s\-.]", "", (v or "").upper())


def normalize_iban(v: str) -> str:
    return re.sub(r"\s", "", (v or "").upper())


def valid_iban(v: str) -> bool:
    s = normalize_iban(v)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    if s.startswith("ES") and len(s) != 24:
        return False
    moved = s[4:] + s[:4]
    digits = "".join(str(int(ch, 36)) for ch in moved)
    return int(digits) % 97 == 1


def _fold(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


MONTHS = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
          "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
# Importe: 1.234,56 · 234,56 · 63.60 (punto decimal solo con 2 decimales) · opcional € / EUR. Nunca «60,000».
AMOUNT_RX = re.compile(r"(?<![\d.,])(-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}|-?\d+\.\d{2})(?![\d,]|\.\d)\s*(?:€|EUR\b|EUROS\b)?")
TAXID_RX = re.compile(r"(?<![A-Z0-9])([A-Z]?(?:[ .\-]?\d){7,8}[ .\-]?[A-Z0-9])(?![A-Z0-9])")
IBAN_RX = re.compile(r"\bES\s?\d{2}(?:[\s\-]?\d){20}\b")
STD_VAT = (21, 10, 5, 4)          # solo para RECONOCER qué cifra es cuál; el IVA es siempre el de la factura
STD_WITHHOLDING = (15, 7, 19, 1, 2)
OWN_CONTEXT = ("MERCANTIL", "CLIENTE", "DESTINATARIO", "FACTURAR A", "DATOS DEL CLIENTE", "A LA ATENCION")
READER_VERSION = 2


def _num(s: str) -> int:
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return int((Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date(s: str) -> date | None:
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def _clean_lines(text: str) -> list[str]:
    """Texto en mayúsculas sin tildes, sin «puntos guía» ni la basura que deja el OCR en ellos."""
    out = []
    for ln in text.splitlines():
        ln = re.sub(r"[a-z¿“]{16,}", lambda m: " " if sum(ch in "cnoiru" for ch in m.group(0)) >= 0.85 * len(m.group(0)) else m.group(0), ln)  # puntos guía mal leídos por el OCR («cocnninnn…»)
        ln = re.sub(r"\b[Nn]\s?[*º°]", "NUM ", ln)  # «Nº», «N°» y el «n*» del OCR (antes de quitar tildes: º → o)
        ln = _fold(ln)
        ln = re.sub(r"\.{3,}|_{3,}|-{4,}", " ", ln)
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        if ln:
            out.append(ln)
    # «TOTAL …:» con la cifra en la línea siguiente (frecuente en el OCR): se unen
    merged: list[str] = []
    for ln in out:
        if merged and re.fullmatch(r"-?[\d.,]+\s*(?:€|EUR)?", ln) and not AMOUNT_RX.search(merged[-1]) \
                and re.search(r"TOTAL|BASE|IVA|IRPF|RETENCION|LIQUIDO|IMPORTE|:$", merged[-1]):
            merged[-1] = f"{merged[-1]} {ln}"
        else:
            merged.append(ln)
    return merged


def _amounts(line: str) -> list[int]:
    return [abs(_num(m.group(1))) for m in AMOUNT_RX.finditer(line)]


def _pcts(line: str) -> list[int]:
    return [int(x) for x in re.findall(r"(?<![\d,.])(\d{1,2})(?:[,.]0+)?\s*%", line)]


def _taxids(lines: list[str], own: set[str], own_words: set[str]) -> list[str]:
    """CIF/NIF/NIE válidos (letra o dígito de control correcto), en orden, sin los del despacho."""
    found: list[str] = []
    for k, ln in enumerate(lines):
        if "IBAN" in ln or re.search(r"\bES\s?\d{2}[\s\-]?\d{4}", ln):
            continue
        for m in TAXID_RX.finditer(ln):
            ctx = (lines[k - 1] if k else "") + " " + ln[max(0, m.start() - 60):m.start()]
            cand = re.sub(r"[ .\-]", "", m.group(1))
            if not valid_tax_id(cand) or cand in own or cand in found:
                continue
            if any(w in ctx for w in OWN_CONTEXT) or (own_words and sum(w in ctx for w in own_words) >= min(2, len(own_words))):
                own.add(cand)  # es el cliente de la factura (el despacho), no el proveedor
                continue
            found.append(cand)
    return found


def _number(lines: list[str]) -> str | None:
    for ln in lines[:25]:
        # Cambio respecto a Sistema Propio (13/11/2026): «N.º», «Nº», «N°» (ya plegados a «N.O», «NO»…) = NÚMERO.
        ln = re.sub(r"\bN\s*\.?\s*[O°º]\s*\.?(?=\s|:|$)", "NUMERO", ln)
        m = (re.search(r"FACTURA\s*(?:NUM(?:ERO)?\.?|NO\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-_. ]{0,30})", ln)
             or re.search(r"(?:(?:NUM(?:ERO)?|NO)\.?\s*(?:DE\s+)?FACTURA)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-_. ]{0,30})", ln)
             or re.search(r"^FACTURA\s*[:\-]?\s*([A-Z]{0,4}[\-/]?\d[A-Z0-9/\-_.]{1,30})", ln))
        if not m:
            continue
        val = re.sub(r"\s*/\s*", "/", m.group(1)).split("  ")[0].strip(" .")
        val = val.split(" ")[0] if not re.match(r"^\d+/\s?\d+$", val) else val
        if re.search(r"\d", val) and not _date(val) and len(val) >= 2:
            return val
    return None


def _dates(lines: list[str]) -> tuple[date | None, date | None]:
    issue = due = None
    for ln in lines:
        if due is None:
            m = re.search(r"VENCIMIENTO\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})", ln)
            if m:
                due = _date(m.group(1))
        if issue is None:
            m = re.search(r"FECHA(?:\s+DE)?(?:\s+(?:LA\s+)?(?:FACTURA|EMISION|EXPEDICION))?\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})", ln)
            if m:
                issue = _date(m.group(1))
    if issue is None:  # «Sevilla, 9 de noviembre de 2026» / «Jaén, a 5 de noviembre de 2026»
        for ln in lines[:30]:
            m = re.search(r"(?:^|[A-Z],)\s*(?:A\s+)?(\d{1,2})\s+DE\s+([A-Z]+)\s+DE(?:L)?\s+(\d{4})", ln)
            if m and m.group(2) in MONTHS:
                try:
                    issue = date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
                    break
                except ValueError:
                    pass
    if issue is None:
        for ln in lines[:15]:
            m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", ln)
            if m and _date(m.group(1)):
                issue = _date(m.group(1))
                break
    return issue, due


def _labelled(lines: list[str]) -> dict:
    """Importes por su etiqueta. Si una línea tiene varias cifras (tablas), se toma la última."""
    out: dict = {}

    def put(key: str, val: int, prio: int) -> None:
        if key not in out or prio > out[key][1]:
            out[key] = (val, prio)
    for ln in lines:
        am = _amounts(ln)
        if not am:
            continue
        last = am[-1]
        if re.search(r"\bLIQUIDO\b|TOTAL A PAGAR|IMPORTE A PAGAR|TOTAL A ABONAR", ln):
            put("total", last, 4)
        elif re.search(r"TOTAL\s*(?:DE\s*LA\s*)?FACTURA|IMPORTE TOTAL|TOTAL\s*(?:EUR|€)", ln):
            put("total", last, 3)
        elif re.search(r"^[\-•* ]*TOTAL\b\W*(?:[:]|$|\d)", ln) and not re.search(r"SUBTOTAL|TOTAL\W+(?:HONORARIOS|BASE|IVA|IMPONIBLE|BRUTO|NETO)", ln):
            put("total", last, 2)
        if re.search(r"BASE\s*IMPONIBLE|^BASE\b|SUBTOTAL|IMPORTE NETO|TOTAL\W+(?:HONORARIOS|BRUTO|NETO)", ln) and "IVA %" not in ln:
            put("base", am[0] if re.search(r"BASE\s*IMPONIBLE", ln) and len(am) > 1 and "IVA" in ln else last, 3)
        if re.search(r"\bIRPF\b|RETENCION|\bRET\.", ln):
            put("ret", last, 3)
        elif re.search(r"IMPORTE\s*(?:DEL?\s*)?I\.?V\.?A|CUOTA\s*(?:DEL?\s*)?I\.?V\.?A|TOTAL\s*I\.?V\.?A", ln):
            put("iva", last, 4)
        elif re.search(r"\bI\.?\s?V\.?\s?A\.?\b", ln) and not re.search(r"BASE\s*I\.?V\.?A|IVA\s*%\s*$|INCLUIDO|EXENTO", ln):
            put("iva", last if len(am) == 1 else am[-1], 2)
    return {k: v[0] for k, v in out.items()}


def _reconcile(lines: list[str], got: dict) -> tuple[dict, list[str]]:
    """Cuando las etiquetas no se leen (PDF escaneado), identifica qué cifra es la base, el IVA y la retención porque
    base + IVA − retención = total con un tipo habitual. No calcula impuestos: usa SOLO cifras impresas en la factura,
    salvo la base, que puede deducirse si IVA y retención la confirman a la vez. Si hay más de una solución, nada."""
    total = got.get("total")
    if total is None:
        return got, []
    nums: list[tuple[int, list[int]]] = []
    for ln in lines:
        am = _amounts(ln)
        if len(am) == 1 and am[0] != total and not re.search(r"IBAN|C/C|TEL|MOVIL|FAX", ln):
            nums.append((am[0], _pcts(ln)))
    vals = [v for v, _ in nums]
    sols = set()
    for b in vals:
        for vat in [0, *vals]:
            for wh in [0, *vals]:
                if len({b, vat, wh} - {0}) < len([x for x in (b, vat, wh) if x]) or b + vat - wh != total:
                    continue
                if vat and not any(abs(vat - b * r / 100) <= 1 for r in STD_VAT):
                    continue
                if wh and not any(abs(wh - b * r / 100) <= 1 for r in STD_WITHHOLDING):
                    continue
                sols.add((b, vat, wh))
    deduced: list[str] = []
    if len(sols) == 1:
        b, vat, wh = sols.pop()
        return {**got, "base": b, "iva": vat, "ret": wh}, deduced
    if not sols:  # base ilegible: se deduce SOLO si IVA y retención impresos encajan a la vez con ella
        cands = set()
        for vat in vals:
            for wh in [0, *vals]:
                if wh == vat:
                    continue
                b = total - vat + wh
                if b <= 0:
                    continue
                if any(abs(vat - b * r / 100) <= 1 for r in STD_VAT) and (not wh or any(abs(wh - b * r / 100) <= 1 for r in STD_WITHHOLDING)):
                    cands.add((b, vat, wh))
        if len(cands) == 1:
            b, vat, wh = cands.pop()
            return {**got, "base": b, "iva": vat, "ret": wh}, ["base_imponible"]
    return got, deduced


def _supplier_name(lines: list[str], own: set[str], own_words: set[str]) -> str | None:
    company = re.compile(r"\b(S\.?\s?L\.?U?|S\.?\s?A\.?U?|S\.?\s?COOP\.?|S\.?\s?C\.?P\.?)\s*$")
    for k, ln in enumerate(lines[:12]):
        core = re.split(r"\s+(?:CIF|NIF|N\.I\.F)\b", ln)[0].strip(" ,.-")
        near = re.sub(r"[ .\-]", "", " ".join(lines[k:k + 3]))
        if any(o in near for o in own):  # el bloque del cliente (el despacho), no el emisor
            continue
        if company.search(core) and not (own_words and sum(w in core for w in own_words) >= min(2, len(own_words))) and len(core) <= 80:
            return core.title()
    for ln in lines:
        m = re.search(r"\bFDO\.?\s*:?\s*([A-Z][A-Z ]{5,60})$", ln)
        if m:
            return m.group(1).strip().title()
    first = lines[0] if lines else ""
    first = re.split(r"\s+(?:AVDA|AVENIDA|CALLE|C/|PASEO|PLAZA|PZA|CTRA|CAMINO)\b", first)[0].strip(" ,.-")
    if first and not re.search(r"\d|FACTURA", first) and 5 <= len(first) <= 60:
        return first.title()
    return None


def read_invoice(text: str, own_tax_ids: set[str] | None = None, own_name: str | None = None) -> dict:
    """Propone los datos de una factura recibida a partir de su texto. No inventa: lo que no encuentra, no lo pone."""
    lines = _clean_lines(text)
    own = {normalize_tax_id(x) for x in (own_tax_ids or set()) if x}
    own_words = {w for w in re.findall(r"[A-Z]{5,}", _fold(own_name or "")) if w not in {"DESPACHO", "ABOGADOS", "ABOGADO"}}
    out: dict = {}
    if (num := _number(lines)):
        out["numero"] = num
    cifs = _taxids(lines, own, own_words)
    if cifs:
        out["cif"] = cifs[0]
        out["cif_candidatos"] = cifs[:4]
    issue, due = _dates(lines)
    if issue:
        out["fecha"] = issue.isoformat()
    if due:
        out["vencimiento"] = due.isoformat()
    got = _labelled(lines)
    if not ({"base", "total"} <= got.keys() and got.get("base", 0) + got.get("iva", 0) - got.get("ret", 0) == got.get("total")):
        got, deduced = _reconcile(lines, got)
        if deduced:
            out["deducido"] = deduced
    for k, key in (("base", "base_cents"), ("iva", "iva_cents"), ("ret", "retencion_cents"), ("total", "total_cents")):
        if got.get(k) is not None:
            out[key] = got[k]
    for ln in lines:
        m = IBAN_RX.search(ln)
        if m and valid_iban(re.sub(r"[\s\-]", "", m.group(0))):
            out["iban"] = normalize_iban(re.sub(r"[\s\-]", "", m.group(0)))
            break
    if (name := _supplier_name(lines, own, own_words)):
        out["proveedor_nombre"] = name
    if {"base_cents", "total_cents"} <= out.keys():
        out["cuadra"] = out["base_cents"] + out.get("iva_cents", 0) - out.get("retencion_cents", 0) == out["total_cents"]
    found = sum(1 for k in ("numero", "cif", "fecha", "base_cents", "total_cents") if k in out)
    out["confianza"] = ("alta" if found == 5 and out.get("cuadra") and not out.get("deducido")
                        else "media" if found >= 3 else "baja")
    out["lector"] = READER_VERSION
    return out
