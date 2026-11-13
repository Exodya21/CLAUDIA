"""Lectura de la zona legible por máquina (MRZ, ICAO 9303) de pasaportes (TD3) y tarjetas (TD1, p. ej. TIE).

Es lectura determinista: los dígitos de control dicen si la lectura es fiable. Con todos los controles correctos
la confianza es «alta»; si alguno falla, los datos se proponen con confianza «baja» para que una persona revise.
"""

from __future__ import annotations

import re
from datetime import date

_W = (7, 3, 1)


def _val(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    return ord(c) - 55  # A=10 … Z=35


def check_digit(s: str) -> str:
    return str(sum(_val(c) * _W[i % 3] for i, c in enumerate(s)) % 10)


def _date(yymmdd: str, kind: str, today: date | None = None) -> date | None:
    if not re.fullmatch(r"\d{6}", yymmdd):
        return None
    today = today or date.today()
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    if kind == "birth":
        year = 1900 + yy if yy > today.year % 100 else 2000 + yy
    else:  # caducidad: siempre en este siglo salvo que quede a más de 50 años vista
        year = 2000 + yy
        if year - today.year > 50:
            year -= 100
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def _names(field: str) -> tuple[str, str]:
    parts = field.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    return surname, re.sub(r"\s+", " ", given)


def _clean(line: str) -> str:
    line = line.strip().upper().replace(" ", "")
    # Confusiones típicas del OCR en la MRZ
    return line.replace("«", "<").replace("‹", "<").replace("{", "<").replace("(", "<").replace("[", "<")


_ALPHA = str.maketrans("0158", "OISB")


def _alpha(s: str) -> str:
    """Campos solo alfabéticos (país, nombres): el OCR confunde O/0, I/1, S/5 y B/8."""
    return s.translate(_ALPHA)


_DIGIT = str.maketrans("OIDSBQ", "010580")


def _digits(s: str) -> str:
    """Campos solo numéricos (fechas, dígitos de control)."""
    return s.translate(_DIGIT)


def _repair_number(num: str, check: str) -> str:
    """El número de documento mezcla letras y cifras: si no supera el control, prueba las confusiones O/0 e I/1
    y se queda con la única variante que lo supere. Si hay varias o ninguna, devuelve el original."""
    if check_digit(num) == check:
        return num
    # «Q» por «0» (la cola del cero en fuentes OCR-B): corrección en un solo sentido
    if "Q" in num and check_digit(num.replace("Q", "0")) == check:
        return num.replace("Q", "0")
    pos = [i for i, ch in enumerate(num) if ch in "O0I1"]
    if not pos or len(pos) > 6:
        return num
    swap = {"O": "0", "0": "O", "I": "1", "1": "I"}
    hits = set()
    for mask in range(1, 1 << len(pos)):
        cand = list(num)
        for k, i in enumerate(pos):
            if mask >> k & 1:
                cand[i] = swap[cand[i]]
        c = "".join(cand)
        if check_digit(c) == check:
            hits.add(c)
    return hits.pop() if len(hits) == 1 else num


def find_lines(text: str) -> list[str]:
    cands = [_clean(x) for x in text.splitlines()]
    return [c for c in cands if re.fullmatch(r"[A-Z0-9<]{28,46}", c) and c.count("<") >= 2]


def _fix_td3(b: str) -> str:
    b = b.ljust(44, "<")[:44]
    b = (b[0:9] + _digits(b[9]) + _alpha(b[10:13]) + _digits(b[13:20]) + b[20] + _digits(b[21:28]) + b[28:42]
         + _digits(b[42:44]))
    return _repair_number(b[0:9], b[9]) + b[9:]


def _td3_ok(b: str) -> bool:
    return (check_digit(b[0:9]) == b[9] and check_digit(b[13:19]) == b[19] and check_digit(b[21:27]) == b[27]
            and check_digit(b[0:10] + b[13:20] + b[21:43]) == b[43])


def _best_td3_line(raw: str) -> str:
    """El OCR a veces añade o pierde un carácter. Prueba la línea tal cual y con un carácter de más quitado (o uno
    de menos añadido como «<») y se queda con la única variante que supera TODOS los dígitos de control."""
    cands = [raw]
    if len(raw) > 44:
        cands += [raw[:i] + raw[i + 1:] for i in range(len(raw))]
    if len(raw) < 44:
        cands += [raw[:i] + "<" + raw[i:] for i in range(28, len(raw) + 1)]
    good = {f for f in (_fix_td3(c) for c in cands) if _td3_ok(f)}
    return good.pop() if len(good) == 1 else _fix_td3(raw)


def parse(text: str, today: date | None = None) -> dict | None:
    lines = find_lines(text)
    # TD3: dos líneas de 44
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        # La línea de nombres puede perder rellenos «<» en el OCR: basta con que la segunda línea esté completa,
        # porque los dígitos de control solo dependen de ella.
        if a.startswith("P") and len(a) >= 30 and len(b) >= 42:
            a = a.ljust(44, "<")[:44]
            b = _best_td3_line(b)
            surname, given = _names(_alpha(a[5:]))
            checks = {
                "numero": check_digit(b[0:9]) == b[9],
                "nacimiento": check_digit(b[13:19]) == b[19],
                "caducidad": check_digit(b[21:27]) == b[27],
                "compuesto": check_digit(b[0:10] + b[13:20] + b[21:43]) == b[43],
            }
            return {
                "format": "TD3", "document_code": a[0:2].replace("<", ""), "issuing_state": _alpha(a[2:5]).replace("<", ""),
                "surname": surname, "given_names": given, "document_number": b[0:9].replace("<", ""),
                "nationality": _alpha(b[10:13]).replace("<", ""), "birth_date": _iso(_date(b[13:19], "birth", today)),
                "sex": b[20].replace("<", "X"), "expiry_date": _iso(_date(b[21:27], "expiry", today)),
                "checks": checks, "valid": all(checks.values()), "lines": [a, b],
            }
    # TD1: tres líneas de 30
    for i in range(len(lines) - 2):
        a, b, c = lines[i], lines[i + 1], lines[i + 2]
        if all(28 <= len(x) <= 32 for x in (a, b, c)) and a[0] in "IAC":
            a, b, c = (x.ljust(30, "<")[:30] for x in (a, b, c))
            a = a[0:5] + _repair_number(a[5:14], _digits(a[14])) + _digits(a[14]) + a[15:]
            b = _digits(b[0:7]) + b[7] + _digits(b[8:15]) + b[15:29] + _digits(b[29])
            surname, given = _names(_alpha(c))
            checks = {
                "numero": check_digit(a[5:14]) == a[14],
                "nacimiento": check_digit(b[0:6]) == b[6],
                "caducidad": check_digit(b[8:14]) == b[14],
                "compuesto": check_digit(a[5:30] + b[0:7] + b[8:15] + b[18:29]) == b[29],
            }
            return {
                "format": "TD1", "document_code": a[0:2].replace("<", ""), "issuing_state": _alpha(a[2:5]).replace("<", ""),
                "surname": surname, "given_names": given, "document_number": a[5:14].replace("<", ""),
                "optional": a[15:30].replace("<", ""), "nationality": _alpha(b[15:18]).replace("<", ""),
                "birth_date": _iso(_date(b[0:6], "birth", today)), "sex": b[7].replace("<", "X"),
                "expiry_date": _iso(_date(b[8:14], "expiry", today)), "checks": checks,
                "valid": all(checks.values()), "lines": [a, b, c],
            }
    return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def build_td3(doc_type: str, state: str, surname: str, given: str, number: str, nationality: str, birth: date,
              sex: str, expiry: date, optional: str = "") -> list[str]:
    """Genera una MRZ correcta (solo para documentos FICTICIOS de pruebas y datos de demostración)."""
    def f(s: str, n: int) -> str:
        return re.sub(r"[^A-Z0-9<]", "<", s.upper().replace(" ", "<"))[:n].ljust(n, "<")

    l1 = f(doc_type, 2) + f(state, 3) + f(f"{surname}<<{given}", 39)
    num = f(number, 9)
    bd, ed = birth.strftime("%y%m%d"), expiry.strftime("%y%m%d")
    opt = f(optional, 14)
    body = num + check_digit(num) + f(nationality, 3) + bd + check_digit(bd) + sex + ed + check_digit(ed) + opt + check_digit(opt)
    comp = check_digit(body[0:10] + body[13:20] + body[21:43])
    return [l1, body + comp]


def build_td1(doc_type: str, state: str, number: str, optional: str, birth: date, sex: str, expiry: date,
              nationality: str, surname: str, given: str) -> list[str]:
    """MRZ de tarjeta (TD1, 3×30), como la TIE: el N.I.E. va en el campo opcional. Solo para documentos FICTICIOS."""
    def f(s: str, n: int) -> str:
        return re.sub(r"[^A-Z0-9<]", "<", s.upper().replace(" ", "<"))[:n].ljust(n, "<")

    num = f(number, 9)
    l1 = f(doc_type, 2) + f(state, 3) + num + check_digit(num) + f(optional, 15)
    bd, ed = birth.strftime("%y%m%d"), expiry.strftime("%y%m%d")
    l2 = bd + check_digit(bd) + sex + ed + check_digit(ed) + f(nationality, 3) + f("", 11)
    comp = check_digit(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29])
    l2 += comp
    l3 = f(f"{surname}<<{given}", 30)
    return [l1, l2, l3]
