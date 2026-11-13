"""Lectura de extractos bancarios: Excel (.xlsx, .xls y el «.xls» en HTML que exportan muchos bancos), Norma 43
(AEB/CSB 43), ISO 20022 CAMT.053 y CSV con cabecera.

Reglas (criterio de Dirección: «mejor rechazar que inventar»):
- Nunca se adivina un importe ni una fecha: una línea ilegible se informa como error y no se importa.
- Cada movimiento recibe un identificador ESTABLE (`ext_id`): el del banco si existe; si no, una huella de sus datos
  más el orden de aparición entre movimientos idénticos. Reimportar el mismo extracto (o uno solapado) no duplica.
- Se devuelven saldo inicial y final cuando el formato los trae, para comprobar saldo inicial + movimientos = final.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html.parser import HTMLParser


class ParseError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class Line:
    booking_date: date
    value_date: date | None
    amount_cents: int
    description: str
    reference: str | None = None
    counterparty: str | None = None
    balance_after_cents: int | None = None
    bank_id: str | None = None
    ext_id: str = ""


@dataclass
class Statement:
    file_format: str
    currency: str = "EUR"
    account_hint: str | None = None  # últimos 4 dígitos de la cuenta según el fichero
    opening_cents: int | None = None
    closing_cents: int | None = None
    period_from: date | None = None
    period_to: date | None = None
    lines: list[Line] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    columns: dict[str, str] | None = None  # cabeceras reconocidas (tablas: CSV, Excel, HTML)


ISO_CCY = {"978": "EUR", "840": "USD", "826": "GBP", "170": "COP"}
# Conceptos comunes de la Norma 43 (AEB)
N43_CONCEPTS = {"01": "Talón/reintegro", "02": "Ingreso", "03": "Recibo domiciliado", "04": "Transferencia",
                "05": "Préstamo", "06": "Remesa de efectos", "07": "Suscripción", "08": "Dividendos", "09": "Bolsa",
                "10": "Cheque gasolina", "11": "Cajero", "12": "Tarjeta", "13": "Extranjero",
                "14": "Devolución/impagado", "15": "Nómina/seguros sociales", "16": "Timbres/corretaje",
                "17": "Intereses/comisiones", "98": "Anulación", "99": "Varios"}


def _clean(s: str | None, n: int = 300) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()[:n]


def _assign_ids(st: Statement) -> None:
    seen: dict[str, int] = {}
    for ln in st.lines:
        if ln.bank_id:
            ln.ext_id = f"b:{ln.bank_id}"[:80]
            continue
        base = "|".join([ln.booking_date.isoformat(), (ln.value_date or ln.booking_date).isoformat(),
                         str(ln.amount_cents), ln.description.upper(), (ln.reference or "").upper()])
        h = hashlib.sha256(base.encode()).hexdigest()[:40]
        seen[h] = seen.get(h, 0) + 1
        ln.ext_id = f"h:{h}:{seen[h]}"


def detect(data: bytes, name: str) -> str:
    head = data[:400].lstrip(b"\xef\xbb\xbf").lstrip()
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":  # Excel 97-2003 (.xls)
        return "xls"
    if head.startswith(b"<") and re.search(rb"<table", data[:200000], re.I):
        return "html_xls"  # muchos bancos exportan «.xls» que en realidad es una tabla HTML
    if head.startswith(b"<"):
        return "camt053"
    if re.match(rb"^11\d{18}\d{12}", head):
        return "n43"
    if name.lower().endswith((".csv", ".txt", ".xls")) and (b";" in head or b"," in head or b"\t" in head):
        return "csv"  # algunos bancos llaman «.xls» a un texto separado por tabuladores
    raise ParseError("Formato no reconocido. Use Excel (.xlsx o .xls), Norma 43 (AEB 43), CAMT.053 (XML) o CSV con cabecera.")


def parse(data: bytes, name: str) -> Statement:
    if not data:
        raise ParseError("El archivo está vacío.")
    if len(data) > 10 * 1024 * 1024:
        raise ParseError("El extracto supera 10 MB.")
    fmt = detect(data, name)
    st = {"n43": parse_n43, "camt053": parse_camt053, "csv": parse_csv, "xlsx": parse_xlsx, "xls": parse_xls,
          "html_xls": parse_html_table}[fmt](data)
    if not st.lines and not st.errors:
        raise ParseError("El extracto no contiene movimientos.")
    if st.lines:
        st.period_from = st.period_from or min(ln.booking_date for ln in st.lines)
        st.period_to = st.period_to or max(ln.booking_date for ln in st.lines)
    _assign_ids(st)
    return st


# ------------------------------------------------------------------ Norma 43
def _yymmdd(s: str) -> date:
    return datetime.strptime(s, "%y%m%d").date()


def _n43_amount(sign: str, digits: str) -> int:
    if not digits.isdigit() or sign not in "12":
        raise ValueError("importe ilegible")
    v = int(digits)
    return -v if sign == "1" else v  # 1 = debe (sale), 2 = haber (entra)


def parse_n43(data: bytes) -> Statement:
    text = data.decode("latin-1")
    st = Statement(file_format="n43")
    accounts = 0
    current: Line | None = None
    for i, raw in enumerate(text.splitlines(), start=1):
        r = raw.rstrip("\r\n")
        if not r.strip():
            continue
        r = r.ljust(80)
        code = r[:2]
        try:
            if code == "11":
                accounts += 1
                if accounts > 1:
                    raise ParseError("El fichero trae varias cuentas; importe un extracto por cuenta.")
                st.account_hint = r[16:20]
                st.period_from, st.period_to = _yymmdd(r[20:26]), _yymmdd(r[26:32])
                st.opening_cents = _n43_amount(r[32], r[33:47])
                st.currency = ISO_CCY.get(r[47:50], r[47:50])
            elif code == "22":
                current = Line(booking_date=_yymmdd(r[10:16]), value_date=_yymmdd(r[16:22]),
                               amount_cents=_n43_amount(r[27], r[28:42]),
                               description="", reference=_clean(r[52:64] + " " + r[64:80], 120) or None)
                doc = r[42:52].strip("0 ")
                current.description = _clean(N43_CONCEPTS.get(r[22:24], f"Concepto {r[22:24]}") + (f" doc {doc}" if doc else ""))
                st.lines.append(current)
            elif code == "23":
                if current is None:
                    raise ValueError("concepto complementario sin movimiento")
                extra = _clean(r[4:42] + " " + r[42:80])
                if r[2:4] == "01" and not current.counterparty:
                    current.counterparty = _clean(r[4:42], 140) or None
                current.description = _clean(f"{extra} · {current.description}" if r[2:4] == "01"
                                             else f"{current.description} {extra}")
            elif code == "33":
                st.closing_cents = _n43_amount(r[58], r[59:73])
                current = None
            elif code in ("88", "00"):
                current = None
            else:
                raise ValueError(f"registro desconocido «{code}»")
        except ParseError:
            raise
        except (ValueError, IndexError) as exc:
            st.errors.append({"linea": i, "error": str(exc)[:120]})
            if code == "22":
                current = None
    if accounts == 0:
        raise ParseError("Norma 43 sin registro de cabecera de cuenta (11).")
    return st


# ------------------------------------------------------------------ CAMT.053
def _strip_ns(root: ET.Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _txt(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    f = el.find(path)
    return f.text.strip() if f is not None and f.text else None


def _cents(s: str | None) -> int:
    if s is None:
        raise ValueError("falta el importe")
    d = Decimal(s)
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("importe con más de 2 decimales")
    return int(d * 100)


def parse_camt053(data: bytes) -> Statement:
    if re.search(rb"<!(DOCTYPE|ENTITY)", data[:4096], re.I):
        raise ParseError("XML con declaraciones no permitidas.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ParseError(f"XML ilegible: {exc}") from exc
    _strip_ns(root)
    stmts = root.findall(".//Stmt")
    if len(stmts) != 1:
        raise ParseError("El CAMT.053 debe traer exactamente un extracto (Stmt) de una cuenta.")
    s = stmts[0]
    st = Statement(file_format="camt053")
    iban = _txt(s, "Acct/Id/IBAN") or _txt(s, "Acct/Id/Othr/Id")
    st.account_hint = iban[-4:] if iban else None
    st.currency = _txt(s, "Acct/Ccy") or "EUR"
    for b in s.findall("Bal"):
        tp = _txt(b, "Tp/CdOrPrtry/Cd")
        amt_el = b.find("Amt")
        try:
            v = _cents(amt_el.text if amt_el is not None else None)
        except (ValueError, InvalidOperation):
            st.errors.append({"linea": "saldo", "error": f"saldo {tp} ilegible"})
            continue
        if _txt(b, "CdtDbtInd") == "DBIT":
            v = -v
        if tp in ("OPBD", "PRCD") and st.opening_cents is None:
            st.opening_cents = v
        elif tp == "CLBD":
            st.closing_cents = v
    fr, to = _txt(s, "FrToDt/FrDtTm"), _txt(s, "FrToDt/ToDtTm")
    if fr and to:
        st.period_from, st.period_to = date.fromisoformat(fr[:10]), date.fromisoformat(to[:10])
    for i, n in enumerate(s.findall("Ntry"), start=1):
        try:
            if (_txt(n, "Sts/Cd") or _txt(n, "Sts") or "BOOK") not in ("BOOK",):
                continue  # solo apuntes contabilizados
            amt_el = n.find("Amt")
            v = _cents(amt_el.text if amt_el is not None else None)
            ccy = amt_el.get("Ccy") if amt_el is not None else None
            if ccy and ccy != st.currency:
                raise ValueError(f"moneda {ccy} distinta de la cuenta")
            ind = _txt(n, "CdtDbtInd")
            if ind not in ("CRDT", "DBIT"):
                raise ValueError("sin indicador de cargo/abono")
            v = v if ind == "CRDT" else -v
            bd = _txt(n, "BookgDt/Dt") or (_txt(n, "BookgDt/DtTm") or "")[:10]
            vd = _txt(n, "ValDt/Dt") or (_txt(n, "ValDt/DtTm") or "")[:10] or None
            tx = n.find("NtryDtls/TxDtls")
            ustrd = " ".join(e.text.strip() for e in (tx.findall("RmtInf/Ustrd") if tx is not None else []) if e.text)
            desc = _clean(" ".join(x for x in [_txt(n, "AddtlNtryInf"), ustrd] if x)) or "(sin concepto)"
            party = (_txt(tx, "RltdPties/Dbtr/Nm") if v > 0 else _txt(tx, "RltdPties/Cdtr/Nm")) if tx is not None else None
            ref = (_txt(tx, "Refs/EndToEndId") if tx is not None else None)
            if ref in ("NOTPROVIDED",):
                ref = None
            st.lines.append(Line(booking_date=date.fromisoformat(bd), value_date=date.fromisoformat(vd) if vd else None,
                                 amount_cents=v, description=desc, reference=_clean(ref, 120) or None,
                                 counterparty=_clean(party, 140) or None,
                                 bank_id=_txt(n, "AcctSvcrRef") or _txt(n, "NtryRef")))
        except (ValueError, InvalidOperation) as exc:
            st.errors.append({"linea": f"apunte {i}", "error": str(exc)[:120]})
    return st


# ------------------------------------------------------------------ CSV
CSV_COLS = {
    "booking": ("fecha", "fecha operacion", "f operacion", "fecha de operacion", "fecha de la operacion", "fecha oper",
                "fecha contable", "f contable", "fecha movimiento"),
    "value": ("fecha valor", "f valor", "fecha de valor"),
    "desc": ("concepto", "descripcion", "detalle", "concepto descripcion", "movimiento", "concepto comun",
             "descripcion ampliada", "concepto propio"),
    "amount": ("importe", "cantidad", "importe eur", "importe euros"),
    "debit": ("cargo", "cargos", "debe", "debito", "salidas", "importe cargo"),
    "credit": ("abono", "abonos", "haber", "credito", "entradas", "importe abono"),
    "balance": ("saldo", "saldo disponible", "saldo eur", "saldo contable", "saldo euros"),
    "ref": ("referencia", "ref", "referencia 1", "mas datos"),
    "party": ("ordenante", "beneficiario", "contraparte", "ordenante beneficiario"),
    "id": ("id", "id movimiento", "numero movimiento", "n movimiento"),
}


def _norm_header(h) -> str:
    t = unicodedata.normalize("NFKD", str(h or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\((eur|€|euros)\)", " eur", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _csv_date(s: str) -> date:
    s = s.strip()
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(f"fecha ilegible «{s[:12]}»")


def _csv_amount(s: str) -> int:
    t = s.strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not re.fullmatch(r"[+-]?[\d.,]+", t):
        raise ValueError(f"importe ilegible «{s[:16]}»")
    if "," in t:  # formato español 1.234,56
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        raise ValueError(f"importe ambiguo «{s[:16]}»")
    return _cents(t)


def parse_csv(data: bytes) -> Statement:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    sample = text[:2000]
    delim = max((";", ",", "\t"), key=sample.count)
    rows = [list(r) for r in csv.reader(io.StringIO(text), delimiter=delim)]
    if not rows:
        raise ParseError("CSV vacío.")
    return parse_rows(rows, "csv")


def _xl_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # número de serie de Excel
        return (datetime(1899, 12, 30) + timedelta(days=int(v))).date()
    return _csv_date(str(v))


def _xl_amount(v) -> int:
    if isinstance(v, bool):
        raise ValueError("importe ilegible")
    if isinstance(v, (int, float)):
        return int((Decimal(str(v)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return _csv_amount(str(v))


def _filled(v) -> bool:
    return v is not None and str(v).strip() != ""


HEADER_SCAN = 40


def parse_rows(rows: list[list], fmt: str) -> Statement:
    """Tabla de movimientos (CSV, Excel o tabla HTML): busca la fila de cabecera entre las primeras 40 (los bancos
    ponen antes el titular, la cuenta y el periodo), reconoce las columnas por su nombre y NO adivina: una línea
    con fecha o importe ilegible se registra como error."""
    hrow = idx = None
    for n, row in enumerate(rows[:HEADER_SCAN]):
        header = [_norm_header(c) for c in row]
        found: dict[str, int] = {}
        for key, names in CSV_COLS.items():
            for jj, h in enumerate(header):
                if h in names and jj not in found.values():
                    found[key] = jj
                    break
        if "booking" in found and "desc" in found and ("amount" in found or {"debit", "credit"} <= found.keys()):
            hrow, idx = n, found
            break
    if idx is None:
        raise ParseError("No se encuentra la cabecera de movimientos: hacen falta columnas Fecha, Concepto e Importe "
                         "(o Cargo y Abono). Opcionales: Fecha valor, Saldo, Referencia, Ordenante, Id.")
    st = Statement(file_format=fmt)
    st.columns = {k: _clean(str(rows[hrow][jj]), 60) for k, jj in idx.items()}
    for row in rows[:hrow]:  # cuenta del extracto en las filas de título (para no importar en otra cuenta)
        m = re.search(r"\bES\d{2}[\s\d]{20,30}", " ".join(str(c or "") for c in row))
        if m:
            st.account_hint = re.sub(r"\s", "", m.group(0))[-4:]
            break
    for i, row in enumerate(rows[hrow + 1:], start=hrow + 2):
        if not any(_filled(c) for c in row):
            continue

        def col(k: str, row: list = row):
            jj = idx.get(k)
            return row[jj] if jj is not None and jj < len(row) and _filled(row[jj]) else None
        if col("booking") is None and col("amount") is None and col("debit") is None and col("credit") is None:
            continue  # filas de totales o notas al pie sin fecha ni importe
        try:
            if "amount" in idx:
                amount = _xl_amount(col("amount") if col("amount") is not None else "")
            else:
                deb, cre = col("debit"), col("credit")
                if (deb is None) == (cre is None):
                    raise ValueError("la línea debe tener cargo o abono (solo uno)")
                amount = -abs(_xl_amount(deb)) if deb is not None else abs(_xl_amount(cre))
            bal = col("balance")
            st.lines.append(Line(booking_date=_xl_date(col("booking") if col("booking") is not None else ""),
                                 value_date=_xl_date(col("value")) if col("value") is not None else None,
                                 amount_cents=amount,
                                 description=_clean(str(col("desc") or "")) or "(sin concepto)",
                                 reference=_clean(str(col("ref") or ""), 120) or None,
                                 counterparty=_clean(str(col("party") or ""), 140) or None,
                                 balance_after_cents=_xl_amount(bal) if bal is not None else None,
                                 bank_id=str(col("id")).strip() if col("id") is not None else None))
        except ValueError as exc:
            st.errors.append({"linea": i, "error": str(exc)[:120]})
    with_bal = [ln for ln in st.lines if ln.balance_after_cents is not None]
    if with_bal and len(with_bal) == len(st.lines):
        # Los bancos exportan en orden cronológico o inverso: se usa el que cuadre con los saldos.
        ordered = st.lines
        if not _running_ok(ordered):
            ordered = list(reversed(st.lines))
        if _running_ok(ordered):
            st.opening_cents = ordered[0].balance_after_cents - ordered[0].amount_cents
            st.closing_cents = ordered[-1].balance_after_cents
        else:
            st.errors.append({"linea": "saldos", "error": "los saldos de las líneas no cuadran con los importes"})
    return st


def parse_xlsx(data: bytes) -> Statement:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - archivo dañado o protegido
        raise ParseError("No se puede abrir el Excel (¿dañado o protegido con contraseña?).") from exc
    last: ParseError | None = None
    for ws in wb.worksheets:  # la primera hoja con cabecera de movimientos
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        try:
            return parse_rows(rows, "xlsx")
        except ParseError as exc:
            last = exc
    raise last or ParseError("El Excel no tiene hojas.")


def parse_xls(data: bytes) -> Statement:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=data)
    except Exception as exc:  # noqa: BLE001
        raise ParseError("No se puede abrir el Excel .xls (¿dañado o protegido con contraseña?).") from exc
    last: ParseError | None = None
    for sh in book.sheets():
        rows = []
        for r in range(sh.nrows):
            row = []
            for c in range(sh.ncols):
                cell = sh.cell(r, c)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                elif cell.ctype == xlrd.XL_CELL_EMPTY:
                    row.append(None)
                else:
                    row.append(cell.value)
            rows.append(row)
        try:
            return parse_rows(rows, "xls")
        except ParseError as exc:
            last = exc
    raise last or ParseError("El Excel no tiene hojas.")


class _TableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(_clean("".join(self._cell), 500))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, d):
        if self._cell is not None:
            self._cell.append(d)


def parse_html_table(data: bytes) -> Statement:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    p = _TableHTML()
    p.feed(text)
    if not p.rows:
        raise ParseError("El archivo no contiene ninguna tabla de movimientos.")
    st = parse_rows(p.rows, "xls")
    return st


def _running_ok(lines: list[Line]) -> bool:
    for a, b in zip(lines, lines[1:], strict=False):
        if a.balance_after_cents + b.amount_cents != b.balance_after_cents:
            return False
    return True


# ------------------------------------------------------------------ generador ficticio (solo desarrollo y pruebas)
def build_n43(*, bank: str, branch: str, account10: str, start: date, end: date, opening_cents: int,
              moves: list[tuple[date, int, str, str, str]]) -> bytes:
    """Genera un Norma 43 FICTICIO. moves: (fecha, importe con signo, concepto común, ref2, texto complementario)."""
    def amt(v: int) -> tuple[str, str]:
        return ("1" if v < 0 else "2"), f"{abs(v):014d}"
    out = []
    s, a = amt(opening_cents)
    out.append(f"11{bank}{branch}{account10}{start:%y%m%d}{end:%y%m%d}{s}{a}9783{'DESPACHO DEMO SL':<26}{'':3}")
    deb = cred = 0
    nd = nc = 0
    for d, v, common, ref2, text in moves:
        s, a = amt(v)
        if v < 0:
            deb, nd = deb + -v, nd + 1
        else:
            cred, nc = cred + v, nc + 1
        out.append(f"22    {branch}{d:%y%m%d}{d:%y%m%d}{common:0>2}000{s}{a}{'0' * 10}{'':12}{ref2[:16]:<16}")
        out.append(f"2301{text[:38]:<38}{text[38:76]:<38}")
    closing = opening_cents + cred - deb
    s, a = amt(closing)
    out.append(f"33{bank}{branch}{account10}{nd:05d}{deb:014d}{nc:05d}{cred:014d}{s}{a}978{'':4}")
    out.append(f"88{'9' * 18}{len(out) - 1:06d}{'':54}")
    return ("\r\n".join(r.ljust(80)[:80] for r in out) + "\r\n").encode("latin-1")
