"""Datos para la ficha del formulario sacados de cada documento leído (F4.3).

Cada función recibe el texto ya leído (pdftotext u OCR local) y, si lo hay, la MRZ, y devuelve
{clave de la ficha: valor}. Son PROPUESTAS: aparecen en la ficha con su origen y una persona las confirma.
Patrones construidos sobre los modelos oficiales públicos (contrato SEPE, certificado de empadronamiento, TIE,
tasa 790) y probados con documentos inventados. Nada de esto decide validez jurídica.
"""

from __future__ import annotations

import contextvars
import re
import unicodedata

from .forms import country

# Prefijo del código postal → provincia (INE)
CP_PROVINCIA = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alicante/Alacant", "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Illes Balears", "08": "Barcelona", "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón/Castelló",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca", "17": "Girona", "18": "Granada",
    "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León", "25": "Lleida",
    "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga", "30": "Murcia", "31": "Navarra", "32": "Ourense",
    "33": "Asturias", "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra", "37": "Salamanca",
    "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia", "41": "Sevilla", "42": "Soria", "43": "Tarragona",
    "44": "Teruel", "45": "Toledo", "46": "Valencia/València", "47": "Valladolid", "48": "Bizkaia", "49": "Zamora",
    "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}
VIAS = {"calle": "Calle", "c/": "Calle", "cl": "Calle", "avenida": "Avenida", "avda": "Avenida", "av": "Avenida",
        "plaza": "Plaza", "pza": "Plaza", "pl": "Plaza", "paseo": "Paseo", "pº": "Paseo", "camino": "Camino",
        "carretera": "Carretera", "ctra": "Carretera", "travesia": "Travesía", "ronda": "Ronda", "rambla": "Rambla",
        "glorieta": "Glorieta", "urbanizacion": "Urbanización", "urb": "Urbanización", "pasaje": "Pasaje",
        "via": "Vía", "carrer": "Carrer", "avinguda": "Avinguda", "placa": "Plaça", "passeig": "Passeig"}
NIE_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _plain(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


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


def find_ids(text: str) -> dict[str, list[str]]:
    """NIE, DNI y CIF válidos (con su letra o dígito de control) que aparecen en el texto, en orden."""
    t = text.upper()
    out: dict[str, list[str]] = {"nie": [], "dni": [], "cif": []}
    for m in re.finditer(r"(?<![A-Z0-9])([XYZ])[\s.-]?(\d{7})[\s.-]?([A-Z])(?![A-Z0-9])", t):
        v = "".join(m.groups())
        if valid_nie(v) and v not in out["nie"]:
            out["nie"].append(v)
    for m in re.finditer(r"(?<![A-Z0-9])(\d{8})[\s.-]?([A-Z])(?![A-Z0-9])", t):
        v = "".join(m.groups())
        if valid_dni(v) and v not in out["dni"]:
            out["dni"].append(v)
    for m in re.finditer(r"(?<![A-Z0-9])([ABCDEFGHJNPQRSUVW])[\s.-]?(\d{7})[\s.-]?([0-9A-J])(?![A-Z0-9])", t):
        v = "".join(m.groups())
        if valid_cif(v) and v not in out["cif"]:
            out["cif"].append(v)
    return out


def _lines(text: str) -> list[str]:
    return [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]


def after(text: str, label: str, max_len: int = 90) -> str | None:
    """Valor escrito tras una etiqueta («Domicilio social: …») en la misma línea o, si está vacía, en la siguiente."""
    lines = _lines(text)
    rx = re.compile(rf"(?i)(?:^|\b|\s){label}\s*[:.]?\s*(.*)$")
    for i, ln in enumerate(lines):
        m = rx.search(_plain(ln))
        if not m:
            continue
        start = len(ln) - len(m.group(1))
        value = ln[start:].strip(" :.-")
        if not value and i + 1 < len(lines):
            value = lines[i + 1].strip(" :.-")
        # corta en la siguiente etiqueta de la misma línea (formato tabla: «… Municipio: …»)
        value = re.split(r"\s{2,}|\s(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [a-záéíóúñ]+)?\s?:)", value)[0].strip(" ,.;")
        if value:
            return value[:max_len]
    return None


def split_address(addr: str) -> dict[str, str]:
    """«C/ Mayor 12, 3º B, 28013 Madrid» → tipo de vía, vía, número, piso, letra, CP, municipio y provincia."""
    out: dict[str, str] = {}
    a = re.sub(r"\s+", " ", addr).strip(" ,.")
    cp = re.search(r"(?<!\d)(\d{5})(?!\d)", a)
    if cp:
        out["cp"] = cp.group(1)
        if cp.group(1)[:2] in CP_PROVINCIA:
            out["provincia"] = CP_PROVINCIA[cp.group(1)[:2]]
        rest = a[cp.end():].strip(" ,-()")
        town = re.split(r"[,(]|\s-\s", rest)[0].strip()
        if town and not re.search(r"\d", town):
            out["municipio"] = town.title() if town.isupper() else town
        a = a[: cp.start()].strip(" ,-")
    first = _plain(a.split()[0]).rstrip(".") if a.split() else ""
    if first in VIAS or first + "/" in VIAS or a.lower().startswith("c/"):
        out["tipo_via"] = VIAS.get(first, VIAS.get(first + "/", "Calle"))
        a = re.sub(r"(?i)^(c/|[a-zº]+\.?)\s*", "", a, count=1)
    m = re.search(r"(?i)(?:,\s*|\s)(?:n[º°o.]?\s*|num(?:ero)?\.?\s*)?(\d{1,4})\s*(?:,|$|\s)(.*)$", a)
    if m:
        out["numero"] = m.group(1)
        street = a[: m.start()].strip(" ,")
        tail = m.group(2)
        p = (re.search(r"(?i)(?:piso|planta|pl\.)\s*(\d{1,2}|bajo|bj|[aá]tico|entlo|entresuelo)\s*[º°o]?\s*-?\s*([A-Z](?![a-z])|izq\w*|dch\w*|der\w*)?", tail)
             or re.search(r"(?i)(?<![\w.])(\d{1,2})\s*[º°]\s*-?\s*([A-Z](?![a-z])|izq\w*|dch\w*)?", tail)
             or re.search(r"(?i)\b(bajo|bj|[aá]tico|entresuelo|entlo)\b\s*-?\s*([A-Z](?![a-z]))?", tail))
        if p:
            floor = p.group(1)
            out["piso"] = {"bajo": "BJ", "bj": "BJ", "atico": "AT", "ático": "AT"}.get(floor.lower(), floor.upper())
            if p.group(2):
                out["letra"] = p.group(2)[:4].upper()
        esc = re.search(r"(?i)esc(?:alera)?\.?\s*([A-Z0-9])\b", tail)
        if esc:
            out["escalera"] = esc.group(1).upper()
    else:
        street = a
    if street:
        out["domicilio"] = street[:45]
    return out


# ------------------------------------------------------------------ por tipo de documento
def from_mrz(mrz_data: dict | None) -> dict[str, str]:
    """Datos de la MRZ. Si algún dígito de control falla (escaneo borroso) se usan solo las partes cuyo control
    sí cuadra; nombre, sexo y nacionalidad solo si cuadran al menos dos controles."""
    if not mrz_data:
        return {}
    checks = mrz_data.get("checks") or {}
    if not mrz_data.get("valid"):
        if sum(bool(v) for v in checks.values()) < 2:
            return {}
        partial = {**mrz_data, "valid": True}
        full = from_mrz(partial)
        drop = set()
        if not checks.get("numero"):
            drop |= {"ext.pasaporte", "ext.nie"}
        if not checks.get("nacimiento"):
            drop.add("ext.fecha_nacimiento")
        return {k: v for k, v in full.items() if k not in drop}
    out: dict[str, str] = {}
    surname = (mrz_data.get("surname") or "").split()
    if surname:
        out["ext.apellido1"] = surname[0].title()
        if len(surname) > 1:
            out["ext.apellido2"] = " ".join(surname[1:]).title()
    if mrz_data.get("given_names"):
        out["ext.nombre"] = mrz_data["given_names"].title()
    if mrz_data.get("sex") in ("F", "M"):
        out["ext.sexo"] = "M" if mrz_data["sex"] == "F" else "H"
    if mrz_data.get("birth_date"):
        out["ext.fecha_nacimiento"] = mrz_data["birth_date"]
    nat = country(mrz_data.get("nationality"))
    if nat:
        out["ext.nacionalidad"] = nat
    if mrz_data.get("format") == "TD3":
        out["ext.pasaporte"] = mrz_data.get("document_number", "")
    else:
        opt = re.sub(r"<", "", mrz_data.get("optional") or "")
        if valid_nie(opt):
            out["ext.nie"] = opt
    return {k: v for k, v in out.items() if v}


def tie(text: str, mrz_data: dict | None) -> dict[str, str]:
    out = from_mrz(mrz_data)
    if mrz_data and not mrz_data.get("valid"):
        # MRZ con algún control fallido: solo se aprovecha el N.I.E. del campo opcional, que lleva su propia letra
        opt = (mrz_data.get("optional") or "").replace("<", "")
        if valid_nie(opt):
            out["ext.nie"] = opt
    if "ext.nie" not in out:
        nies = find_ids(text)["nie"]
        if nies:
            out["ext.nie"] = nies[0]
    return out


def contrato(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    ids = find_ids(text)
    p = _plain(text)
    name = (after(text, r"nombre o razon social") or after(text, r"razon social") or after(text, r"denominacion social")
            or after(text, r"empresa"))
    if not name:
        m = re.search(r"(?i)representaci[oó]n de (?:la empresa |la entidad |la sociedad )?([^,\n]{3,70}?),?\s+(?:con\s+)?(?:c\.?i\.?f|n\.?i\.?f)", text)
        name = m.group(1) if m else None
    if name:
        out["emp.nombre"] = name.strip(" ,.")
    if ids["cif"]:
        out["emp.doc"] = ids["cif"][0]
    elif ids["dni"]:  # empleador persona física
        out["emp.doc"] = ids["dni"][0]
    ccc = re.search(r"(?i)(?:cuenta de cotizaci[oó]n|c\.?c\.?c\.?|c[oó]digo de cuenta)\D{0,25}(\d{2})[\s/.-]?(\d{7,9})[\s/.-]?(\d{2})?", text)
    if ccc:
        out["con.ccc"] = "".join(x for x in ccc.groups() if x)
    addr = after(text, r"domicilio social") or after(text, r"domicilio de la empresa") or after(text, r"con domicilio en")
    if addr:
        for k, v in split_address(addr).items():
            out[f"emp.{k}"] = v
    centro = after(text, r"centro de trabajo") or after(text, r"domicilio del centro")
    if centro:
        parts = split_address(centro)
        for k in ("domicilio", "numero", "piso", "localidad", "cp", "provincia"):
            if parts.get(k if k != "localidad" else "municipio"):
                out[f"con.centro_{k}"] = parts[k if k != "localidad" else "municipio"]
    for k, label in (("emp.municipio", r"municipio"), ("emp.cp", r"codigo postal"), ("emp.actividad", r"actividad economica"),
                     ("emp.cnae", r"c\.?n\.?a\.?e\.?"), ("emp.telefono", r"telefono")):
        if k not in out:
            v = after(text, label, 60)
            if v:
                out[k] = v
    if "emp.cp" in out and "emp.provincia" not in out and out["emp.cp"][:2] in CP_PROVINCIA:
        out["emp.provincia"] = CP_PROVINCIA[out["emp.cp"][:2]]
    puesto = (after(text, r"puesto de trabajo") or after(text, r"categoria profesional") or after(text, r"grupo profesional")
              or after(text, r"ocupacion"))
    if puesto:
        out["con.puesto"] = puesto
    code = re.search(r"(?i)c[oó]digo\s+(?:del?\s+)?contrato\D{0,15}(\d{3})", text) or re.search(r"(?m)^\s*(\d{3})\s*$", text)
    if code:
        out["con.contrato_codigo"] = code.group(1)
    tipo = []
    if re.search(r"indefinid", p):
        tipo.append("Indefinido")
    elif re.search(r"duracion determinada|temporal", p):
        tipo.append("Temporal")
    if re.search(r"jornada (completa|a tiempo completo)|tiempo completo", p):
        tipo.append("a tiempo completo")
    elif re.search(r"tiempo parcial|jornada parcial", p):
        tipo.append("a tiempo parcial")
    if tipo:
        out["con.contrato_nombre"] = " ".join(tipo)
    sal = re.search(r"(?i)(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d{3,6}(?:,\d{2})?)\s*(?:€|euros)\s*(?:brutos?)?\s*(?:anuales|al año|/año|mensuales|al mes|/mes)?", text)
    if sal:
        unit = re.search(r"(anual|al a[nñ]o|/a[nñ]o|mensual|al mes|/mes)", text[sal.start(): sal.end() + 20], re.I)
        out["con.retribucion"] = sal.group(1) + (f" € {unit.group(1).lower()}" if unit else " €")
    # Representante de la empresa que firma
    rl = re.search(r"(?i)(?:D\.|Dª|Dña\.?|Don|Doña)\s+([A-ZÁÉÍÓÚÑ][^\n,]{3,60}?),?\s+con\s+(?:D\.?N\.?I|N\.?I\.?E|N\.?I\.?F)\D{0,10}([0-9XYZ][0-9]{7}[A-Z])\D{0,80}representaci", text)
    if rl:
        out["emp.rl_nombre"], out["emp.rl_doc"] = rl.group(1).strip(), rl.group(2)
        out["emp.rl_titulo"] = "Representante de la empresa"
    # NIE del trabajador si aparece y no es el del representante
    others = [n for n in ids["nie"] if n != out.get("emp.rl_doc")]
    if others:
        out["ext.nie"] = others[0]
    return {k: v for k, v in out.items() if v}


def _address_candidates(text: str) -> list[str]:
    """Líneas que parecen una dirección: empiezan por un tipo de vía o llevan un C.P. válido (con la línea siguiente
    si la vía y el C.P. están partidos en dos líneas)."""
    lines = _lines(text)
    out = []
    for i, ln in enumerate(lines):
        body = re.sub(r"(?i)^(domicilio|direcci[oó]n|calle|inscrit[oa] en)\s*[:.]?\s*", "", ln).strip()
        first = _plain(body.split()[0]).rstrip(".") if body.split() else ""
        has_via = first in VIAS or body.lower().startswith("c/")
        has_cp = bool(re.search(r"(?<!\d)(0[1-9]|[1-4]\d|5[0-2])\d{3}(?!\d)", body))
        if has_via:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not has_cp and re.match(r"^\s*(0[1-9]|[1-4]\d|5[0-2])\d{3}\b", nxt):
                body = f"{body}, {nxt}"
            out.append(body)
    return out


def padron(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    # Primero las líneas que empiezan por un tipo de vía; la etiqueta «Domicilio» solo si su valor parece una dirección
    cands = _address_candidates(text)
    labeled = after(text, r"domicilio") or after(text, r"direccion")
    if labeled and labeled not in cands:
        cands.append(labeled)
    for addr in cands:
        parts = sanitize({f"ext.{k}": v for k, v in split_address(addr).items()})
        if parts.get("ext.domicilio") and (parts.get("ext.numero") or parts.get("ext.cp") or parts.get("ext.tipo_via")):
            out.update(parts)
            break
    m = re.search(r"(?i)ayuntamiento\s+de\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñü' -]{1,40}?)(?:\s*[\n,.(]|\s{2,}|$)", text)
    if m and "ext.municipio" not in out:
        mun = m.group(1).strip()
        out["ext.municipio"] = mun.title() if mun.isupper() else mun
    if "ext.cp" in out:
        out["ext.provincia"] = CP_PROVINCIA.get(out["ext.cp"][:2], out.get("ext.provincia", ""))
    if "ext.municipio" in out:
        out.setdefault("ext.localidad", out["ext.municipio"])
    nies = find_ids(text)["nie"]
    if nies:
        out["ext.nie"] = nies[0]
    return sanitize(out)


def tasa(text: str) -> dict[str, str]:
    """Tasa 790: no rellena la ficha; deja constancia del NRC (justificante de pago) y del importe."""
    info: dict[str, str] = {}
    nrc = re.search(r"(?i)(?:\bN\.?\s?R\.?\s?C\.?\b|referencia\s+completo)[^0-9A-Z]{0,30}((?:[0-9A-Z][\s-]?){20,24})", text)
    if nrc:
        v = re.sub(r"[\s-]", "", nrc.group(1).upper())
        if 20 <= len(v) <= 24 and re.search(r"\d", v):
            info["nrc"] = v
    imp = re.search(r"(?i)importe\D{0,30}(\d{1,4}[.,]\d{2})", text)
    if imp:
        info["importe"] = imp.group(1).replace(".", ",")
    cod = re.search(r"(?i)c[oó]digo\D{0,10}(0\d{2})\b", text)
    if cod:
        info["codigo"] = cod.group(1)
    return info


def vida_laboral(text: str) -> dict[str, str]:
    info: dict[str, str] = {}
    m = re.search(r"(?i)total\D{0,40}?(\d{1,5})\s*d[ií]as", text)
    if m:
        info["dias_cotizados"] = m.group(1)
    if re.search(r"(?i)situaci[oó]n de alta|\balta\b", text):
        info["alta"] = "sí"
    return info


# ------------------------------------------------------------------ control de lo leído
# Lo que no pasa estas comprobaciones NO se propone: es mejor un campo vacío que un texto equivocado.
_STOP = re.compile(r"fecha|pasaporte|nacimiento|document|certific|inscri|hoja|aparece|origen|residencia|expedi|firma|"
                   r"padron|habitante|nacionalidad|sexo|sello|verifica|pagina|codigo seguro|csv|telefono|correo|"
                   r"apellido|nombre|alta|baja|desnormaliz|normaliz|declar|consta|segun|vigente|titular")
_BAD_CHARS = re.compile(r"[\'\";:=<>{}\[\]|@#*_\\]")
_PROVINCIAS = {_plain(v.split("/")[0]): v for v in CP_PROVINCIA.values()} | {_plain(v.split("/")[-1]): v for v in CP_PROVINCIA.values()}
_PROVINCIAS |= {"alava": "Araba/Álava", "baleares": "Illes Balears", "islas baleares": "Illes Balears", "la coruna": "A Coruña",
                "coruna": "A Coruña", "guipuzcoa": "Gipuzkoa", "vizcaya": "Bizkaia", "gerona": "Girona", "lerida": "Lleida",
                "orense": "Ourense", "tenerife": "Santa Cruz de Tenerife", "castellon": "Castellón/Castelló",
                "alicante": "Alicante/Alacant", "valencia": "Valencia/València"}
_VIA_VALUES = set(VIAS.values())


def _words_ok(v: str, max_len: int, max_words: int, digits: bool = False) -> bool:
    return (0 < len(v) <= max_len and len(v.split()) <= max_words and not _BAD_CHARS.search(v)
            and not _STOP.search(_plain(v)) and (digits or not re.search(r"\d", v)) and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", v) is not None)


def _check(field: str, v: str) -> str | None:
    v = re.sub(r"\s+", " ", str(v)).strip(" ,.;:-")
    if not v:
        return None
    if field == "provincia":
        return _PROVINCIAS.get(_plain(v))
    if field in ("cp", "centro_cp"):
        return v if re.fullmatch(r"\d{5}", v) and v[:2] in CP_PROVINCIA else None
    if field == "centro_provincia":
        return _PROVINCIAS.get(_plain(v))
    if field == "tipo_via":
        return v if v in _VIA_VALUES else None
    if field in ("municipio", "localidad", "centro_localidad"):
        return v if _words_ok(v, 40, 6) else None
    if field in ("domicilio", "centro_domicilio"):
        return v if _words_ok(v, 50, 8, digits=True) else None
    if field in ("numero", "centro_numero"):
        return v.upper() if re.fullmatch(r"(?i)\d{1,4}\s?[A-Z]?|s/?n", v) else None
    if field in ("piso", "centro_piso"):
        return v.upper() if re.fullmatch(r"(?i)\d{1,2}|bj|at|en|ss|pr", v) else None
    if field in ("letra", "escalera", "bloque"):
        return v.upper() if re.fullmatch(r"(?i)[A-Z0-9]{1,3}|izq\w*|dch\w*|der\w*", v) else None
    if field == "nie":
        return v if valid_nie(v) else None
    if field in ("doc", "rl_doc"):
        return v if valid_nie(v) or valid_dni(v) or valid_cif(v) else None
    if field == "pasaporte":
        return v if re.fullmatch(r"[A-Z0-9]{5,12}", v) else None
    if field in ("nombre", "apellido1", "apellido2", "rl_nombre"):
        return v if 0 < len(v) <= 60 and not _BAD_CHARS.search(v) and not re.search(r"\d", v) else None
    if field == "ccc":
        return v if re.fullmatch(r"\d{11}", v) else None
    if field == "cnae":
        return v if re.fullmatch(r"\d{2,4}", v) else None
    if field == "contrato_codigo":
        return v if re.fullmatch(r"\d{3}", v) else None
    if field == "telefono":
        d = re.sub(r"\D", "", v)[-9:]
        return d if re.fullmatch(r"[6789]\d{8}", d) else None
    if field == "fecha_nacimiento":
        return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None
    if field in ("sexo", "nacionalidad", "rl_titulo", "contrato_nombre", "retribucion"):
        return v if len(v) <= 60 and not _BAD_CHARS.search(v) else None
    return v if len(v) <= 90 and not _BAD_CHARS.search(v) and not _STOP.search(_plain(v)) else None


_REJECTED: contextvars.ContextVar[set | None] = contextvars.ContextVar("rejected", default=None)


def sanitize(props: dict[str, str]) -> dict[str, str]:
    """Quita las propuestas que no tienen forma de dato (texto de otra parte del documento, restos de OCR…)."""
    out = {}
    bag = _REJECTED.get()
    for k, v in props.items():
        field = k.split(".", 1)[1] if "." in k else k
        c = _check(field, v)
        if c:
            out[k] = c
        elif bag is not None and str(v).strip():
            bag.add(k)
    return out


def for_document(doc_type: str | None, text: str, mrz_data: dict | None) -> tuple[dict[str, str], dict[str, str]]:
    """(propuestas para la ficha, información del documento) según el tipo."""
    text = text or ""
    if doc_type == "pasaporte":
        return sanitize(from_mrz(mrz_data)), {}
    if doc_type == "tie_nie":
        return sanitize(tie(text, mrz_data)), {}
    if doc_type == "contrato_trabajo":
        return sanitize(contrato(text)), {}
    if doc_type == "empadronamiento":
        return padron(text), {}
    if doc_type == "tasa_790":
        return {}, tasa(text)
    if doc_type == "vida_laboral":
        return {}, vida_laboral(text)
    return {}, {}


# ------------------------------------------------------------------ diagnóstico sin datos
# Palabras de formulario que se dejan ver; todo lo demás se enmascara (letras → x/X, cifras → 9). Sirve para que el
# despacho pueda enviar la ESTRUCTURA de un documento real (etiquetas y orden) sin nombres, números ni direcciones.
_KEEP = set("""
a al ante aparece aparecen apellido apellidos alta baja ayuntamiento bloque calle certificado certifico certifica
codigo cod c p cp cuenta cotizacion contrato contratacion centro trabajo trabajador trabajadora empresa empleador
empleadora razon social nombre nif cif nie dni pasaporte documento documentos identidad domicilio direccion
via tipo numero num piso planta puerta letra escalera esc portal provincia municipio localidad poblacion
pais nacionalidad nacimiento fecha fechas lugar sexo hombre mujer varon estado civil padre madre hijo hija
padron municipal habitantes inscripcion inscripciones inscrito inscrita hoja dia dias mes meses ano anos
que segun consta constan datos del de la las los el en y o con por para sin su sus se es son hasta desde
expedicion expedido expedida caducidad validez vigente firma firmado sello secretario secretaria alcalde alcaldia
excmo excma ilmo ilma sr sra don dona d dna tasa modelo importe euros eur ingreso nrc justificante autoliquidacion
referencia completo pago pagado banco entidad oficina fecha epigrafe tramitacion autorizacion residencia trabajo
extranjeros extranjero extranjera tarjeta permiso puesto categoria grupo profesional ocupacion jornada completa
parcial indefinido indefinida temporal duracion determinada salario retribucion bruto brutos bruta anual anuales
mensual mensuales horas semana semanales semanal convenio colectivo actividad economica cnae cno telefono correo
electronico email representante representacion legal reunidos clausulas clausula partes parte otra una uno
informe vida laboral situacion regimen general total cotizados periodo periodos efectos alta baja tiempo
verificacion seguro csv pagina url sede electronica emitido emision origen motivo variacion cambio nacionalidad
urbanizacion urb avenida avda plaza paseo camino carretera travesia ronda glorieta pasaje c calle cl
izq izquierda dcha derecha bajo atico entresuelo
""".split())


def mask_text(text: str) -> str:
    def word(m: re.Match) -> str:
        w = m.group(0)
        if _plain(w) in _KEEP:
            return w
        return re.sub(r"[a-záéíóúñü]", "x", re.sub(r"[A-ZÁÉÍÓÚÑÜ]", "X", re.sub(r"\d", "9", w)))
    return re.sub(r"[0-9A-Za-zÁÉÍÓÚÑÜáéíóúñü]+", word, text or "")


# ------------------------------------------------------------------ revisión automática de la lectura (sin datos)
# Datos que cada tipo de documento debería aportar a la ficha; si faltan, la revisión lo señala.
EXPECTED = {
    "pasaporte": ["ext.pasaporte", "ext.apellido1", "ext.nombre", "ext.sexo", "ext.fecha_nacimiento", "ext.nacionalidad"],
    "tie_nie": ["ext.nie", "ext.apellido1", "ext.nombre", "ext.fecha_nacimiento"],
    "contrato_trabajo": ["emp.nombre", "emp.doc", "con.ccc", "emp.domicilio", "emp.cp", "con.puesto", "con.contrato_codigo",
                         "con.centro_domicilio"],
    "empadronamiento": ["ext.tipo_via", "ext.domicilio", "ext.numero", "ext.cp", "ext.municipio", "ext.provincia"],
}
EXPECTED_INFO = {"tasa_790": ["nrc", "importe"], "vida_laboral": ["dias_cotizados"]}


def review(doc_type: str | None, text: str, mrz_data: dict | None) -> dict:
    """Qué se ha leído, qué falta y qué se ha descartado (solo nombres de campo, nunca valores)."""
    token = _REJECTED.set(set())
    try:
        ficha, info = for_document(doc_type, text, mrz_data)
        rejected = sorted(_REJECTED.get() - set(ficha))
    finally:
        _REJECTED.reset(token)
    missing = [k for k in EXPECTED.get(doc_type or "", []) if k not in ficha]
    missing += [k for k in EXPECTED_INFO.get(doc_type or "", []) if k not in info]
    return {"leidos": sorted(ficha), "info": sorted(info), "faltan": missing, "descartados": rejected,
            "caracteres_texto": len((text or "").strip())}
