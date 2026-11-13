# Validación de DNI, NIE y CIF españoles (letra o dígito de control).
# Copiado de Sistema Propio F5.6c (apps/api/app/immigration/extract.py).
import re

NIE_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def valid_dni(v: str) -> bool:
    m = re.fullmatch(r"(\d{8})([A-Z])", v)
    return bool(m) and NIE_LETTERS[int(m.group(1)) % 23] == m.group(2)


def valid_nie(v: str) -> bool:
    m = re.fullmatch(r"([XYZ])(\d{7})([A-Z])", v)
    return bool(m) and NIE_LETTERS[int(str("XYZ".index(m.group(1))) + m.group(2)) % 23] == m.group(3)


def valid_cif(v: str) -> bool:
    m = re.fullmatch(r"([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-J])", v)
    if not m:
        return False
    d = m.group(2)
    even = sum(int(d[i]) for i in (1, 3, 5))
    odd = sum(sum(divmod(int(d[i]) * 2, 10)) for i in (0, 2, 4, 6))
    c = (10 - (even + odd) % 10) % 10
    return m.group(3) in (str(c), "JABCDEFGHI"[c])
