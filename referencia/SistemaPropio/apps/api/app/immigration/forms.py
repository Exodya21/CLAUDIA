"""Ficha de datos del modelo EX y relleno del PDF oficial (F4.2).

- Las claves de la ficha (ext.apellido1, rep.email…) son las mismas para el PDF y para la extensión de Mercurio.
- `ex_forms/EXnn.json` dice qué campo del PDF oficial corresponde a cada clave (lo genera scripts/ex_forms_build.py).
- La ficha propone valores (cliente, pasaporte leído, datos del despacho) pero solo se usan los que una persona guarda.
- El PDF resultante es un BORRADOR para revisar: no se firma ni se presenta desde aquí.
"""

from __future__ import annotations

import io
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent / "ex_forms"

ROLES = {
    "ext": "Persona extranjera solicitante",
    "fam": "Familiar / reagrupante / titular de los recursos",
    "emp": "Empleador/a o actividad",
    "ent": "Entidad o centro (estudios, prácticas, acogida)",
    "con": "Contrato de trabajo",
    "rep": "Representante a efectos de presentación (despacho)",
    "notif": "Domicilio a efectos de notificaciones",
    "sol": "Lugar, fecha y oficina de destino",
}
PERSON = {
    "pasaporte": "Pasaporte", "nie": "NIE (X-1234567-L)", "apellido1": "Primer apellido", "apellido2": "Segundo apellido",
    "nombre": "Nombre", "sexo": "Sexo", "fecha_nacimiento": "Fecha de nacimiento", "lugar_nacimiento": "Lugar de nacimiento",
    "pais_nacimiento": "País de nacimiento", "nacionalidad": "Nacionalidad", "estado_civil": "Estado civil",
    "padre": "Nombre del padre", "madre": "Nombre de la madre",
}
ADDRESS = {"tipo_via": "Tipo de vía (calle, avenida…)", "domicilio": "Domicilio (nombre de la vía)", "numero": "Número",
           "piso": "Piso", "letra": "Letra / puerta", "escalera": "Escalera", "bloque": "Bloque", "provincia": "Provincia",
           "municipio": "Municipio", "localidad": "Localidad", "cp": "Código postal", "telefono": "Teléfono móvil",
           "telefono_fijo": "Teléfono fijo", "email": "Correo electrónico"}
LEGAL_REP = {"rl_nombre": "Representante legal (en su caso)", "rl_doc_tipo": "Tipo de documento del representante legal",
             "rl_doc": "Número de documento del representante legal",
             "rl_titulo": "Título de la representación"}
ENTITY = {"nombre": "Nombre o razón social", "doc": "NIF/NIE/DNI", "actividad": "Actividad", "cnae": "CNAE", "cno": "CNO SEPE"}
FIELDS: dict[str, dict[str, str]] = {
    "ext": {**PERSON, **ADDRESS, **LEGAL_REP, "hijos_escolarizacion": "Hijos/as a cargo en edad de escolarización",
            "autorizacion_titular": "Autorización de la que es titular"},
    "fam": {**PERSON, **ADDRESS, **LEGAL_REP, "vinculo": "Vínculo / parentesco",
            "autorizacion_titular": "Autorización de la que es titular", "autorizacion_doc": "DNI/NIE/PAS",
            "autorizacion_titulo": "Título"},
    "emp": {**ENTITY, **ADDRESS, **LEGAL_REP},
    "ent": {**ENTITY, **ADDRESS, **LEGAL_REP},
    "con": {"puesto": "Denominación del puesto", "grupo_cotizacion": "Grupo de cotización", "cno": "CNO SEPE 2011",
            "convenio_codigo": "Código del convenio", "convenio_nombre": "Denominación del convenio",
            "contrato_codigo": "Código del contrato", "contrato_nombre": "Denominación del contrato",
            "ccc": "Código de cuenta de cotización", "retribucion": "Retribución total bruta (euros)",
            "centro_domicilio": "Dirección del centro de trabajo", "centro_numero": "Número", "centro_piso": "Piso",
            "centro_localidad": "Localidad", "centro_cp": "Código postal", "centro_provincia": "Provincia"},
    "rep": {"nombre": "Nombre o razón social", "doc": "DNI/NIE/PAS", **ADDRESS, **LEGAL_REP},
    "notif": {"nombre": "Nombre o razón social", "doc": "DNI/NIE/PAS", **ADDRESS,
              "consiento_dehu": "Consiente notificaciones electrónicas en DEHú"},
    "sol": {"firma_lugar": "Lugar de firma", "firma_dia": "Día", "firma_mes": "Mes", "firma_anio": "Año",
            "dirigida_a": "Dirigida a (oficina)", "dir3": "Código DIR3", "dirigida_provincia": "Provincia de la oficina"},
}
CHOICES = {
    "sexo": {"H": "Hombre", "M": "Mujer", "X": "X (no binario)"},
    "estado_civil": {"S": "Soltero/a", "C": "Casado/a", "V": "Viudo/a", "D": "Divorciado/a", "Sp": "Separado/a"},
    "hijos_escolarizacion": {"si": "Sí", "no": "No"},
    "consiento_dehu": {"si": "Sí consiente"},
    "rl_doc_tipo": {"DNI": "DNI", "NIE": "NIE", "PAS": "Pasaporte"},
}
GENERAL = "GENERAL"  # ficha sin PDF: para modelos que Mercurio pide y cuyo editable no está cargado (p. ej. EX-26)
GENERAL_ROLES = ("ext", "fam", "emp", "rep", "notif")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
# Nacionalidades frecuentes (ISO 3166 alfa-2 y alfa-3) → nombre en español. El resto se escribe a mano.
COUNTRIES = {
    "CO": "Colombia", "COL": "Colombia", "VE": "Venezuela", "VEN": "Venezuela", "MA": "Marruecos", "MAR": "Marruecos",
    "PE": "Perú", "PER": "Perú", "HN": "Honduras", "HND": "Honduras", "EC": "Ecuador", "ECU": "Ecuador",
    "AR": "Argentina", "ARG": "Argentina", "BO": "Bolivia", "BOL": "Bolivia", "PY": "Paraguay", "PRY": "Paraguay",
    "DO": "República Dominicana", "DOM": "República Dominicana", "CU": "Cuba", "CUB": "Cuba", "NI": "Nicaragua",
    "NIC": "Nicaragua", "SV": "El Salvador", "SLV": "El Salvador", "GT": "Guatemala", "GTM": "Guatemala",
    "MX": "México", "MEX": "México", "CL": "Chile", "CHL": "Chile", "UY": "Uruguay", "URY": "Uruguay",
    "BR": "Brasil", "BRA": "Brasil", "CN": "China", "CHN": "China", "PK": "Pakistán", "PAK": "Pakistán",
    "IN": "India", "IND": "India", "BD": "Bangladés", "BGD": "Bangladés", "SN": "Senegal", "SEN": "Senegal",
    "DZ": "Argelia", "DZA": "Argelia", "NG": "Nigeria", "NGA": "Nigeria", "GH": "Ghana", "GHA": "Ghana",
    "GM": "Gambia", "GMB": "Gambia", "ML": "Malí", "MLI": "Malí", "UA": "Ucrania", "UKR": "Ucrania",
    "RU": "Rusia", "RUS": "Rusia", "GE": "Georgia", "GEO": "Georgia", "PH": "Filipinas", "PHL": "Filipinas",
    "GB": "Reino Unido", "GBR": "Reino Unido", "US": "Estados Unidos", "USA": "Estados Unidos",
    "UTO": "Utopía (ficticio)", "XX": "",
}


def country(code: str | None) -> str:
    return COUNTRIES.get((code or "").upper(), code or "")


def model_code(ex_form: str | None) -> str | None:
    m = re.search(r"EX\s*-?\s*(\d{2})", ex_form or "", re.I)
    return f"EX{m.group(1)}" if m else None


@lru_cache
def available() -> dict[str, dict]:
    out = {}
    for f in sorted(DIR.glob("EX*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def spec(code: str) -> dict:
    if code == GENERAL:
        return {"model": "General", "code": GENERAL, "title": "Datos comunes de las pantallas de Mercurio (sin modelo PDF)",
                "roles": [{"role": r, "label": ROLES[r], "fields": [{"key": f"{r}.{k}", "label": lab,
                                                                     "choices": CHOICES.get(k)} for k, lab in FIELDS[r].items()]}
                          for r in GENERAL_ROLES], "options": [], "extra_text": [], "pdf": False}
    data = available()[code]
    roles: dict[str, str] = {}
    for m in data["fields"].values():
        roles.setdefault(m["key"].split(".")[0], "")
    if "emp" in roles:
        roles.setdefault("con", "")  # Mercurio pide en la pantalla del empleador los datos del puesto y del centro (F4.3)
    present = {m["key"] for m in data["fields"].values()}
    # Todos los datos que Mercurio pide en los apartados que tiene el modelo (también los que el PDF junta en una
    # casilla, como tipo de vía, escalera o municipio), en el orden de la ficha.
    keys = [f"{r}.{k}" for r, ks in FIELDS.items() for k in ks if r in roles]
    keys += sorted(k for k in present if k not in keys)
    return {"model": data["model"], "code": code, "title": data.get("title", ""),
            "roles": [{"role": r, "label": ROLES.get(r, r),
                       "fields": [{"key": k, "label": FIELDS.get(r, {}).get(k.split(".", 1)[1], k.split(".", 1)[1]),
                                   "choices": CHOICES.get(k.split(".", 1)[1])}
                                  for k in keys if k.startswith(r + ".")]}
                      for r in ROLES if r in roles],
            "options": data.get("options", []), "extra_text": data.get("extra_text", []), "pdf": True}


def _split_names(family: str) -> tuple[str, str]:
    parts = (family or "").split()
    return (parts[0], " ".join(parts[1:])) if parts else ("", "")


def proposals(contact, identifiers, addresses, points, mrz: dict | None, office: dict, province: str | None,
              today: date | None = None) -> dict[str, dict]:
    """Valores propuestos con su origen. Nunca se guardan sin que una persona los confirme."""
    today = today or date.today()
    p: dict[str, dict] = {}

    def put(k, v, src):
        if v not in (None, ""):
            p[k] = {"value": str(v), "source": src}

    a1, a2 = _split_names(contact.family_names)
    put("ext.nombre", contact.given_name, "cliente")
    put("ext.apellido1", a1, "cliente")
    put("ext.apellido2", a2, "cliente")
    if contact.birth_date:
        put("ext.fecha_nacimiento", contact.birth_date.isoformat(), "cliente")
    put("ext.nacionalidad", country(contact.nationality), "cliente")
    for i in identifiers:
        if i.kind == "PASAPORTE":
            put("ext.pasaporte", i.number_normalized, "cliente")
        elif i.kind == "NIE":
            put("ext.nie", i.number_normalized, "cliente")
    for a in addresses[:1]:
        put("ext.domicilio", a.line1, "cliente")
        put("ext.localidad", a.municipality, "cliente")
        put("ext.municipio", a.municipality, "cliente")
        put("ext.cp", a.postal_code, "cliente")
        put("ext.provincia", a.province, "cliente")
    for pt in points:
        if pt.kind == "phone" and "ext.telefono" not in p:
            put("ext.telefono", pt.value_normalized, "cliente")
        if pt.kind == "email" and "ext.email" not in p:
            put("ext.email", pt.value_normalized, "cliente")
    if mrz:
        put("ext.pasaporte", mrz.get("document_number"), "pasaporte")
        put("ext.nacionalidad", country(mrz.get("nationality")), "pasaporte")
        if mrz.get("sex") in ("F", "M"):
            put("ext.sexo", "M" if mrz["sex"] == "F" else "H", "pasaporte")
        put("ext.fecha_nacimiento", mrz.get("birth_date"), "pasaporte")
    for k, v in (office or {}).items():
        if k.startswith(("rep.", "notif.", "sol.")):
            put(k, v, "despacho")
    if office and not any(k.startswith("notif.") for k in office):  # por defecto, notificaciones al despacho
        for k, v in office.items():
            if k.startswith("rep.") and k[4:] in FIELDS["notif"]:
                put("notif." + k[4:], v, "despacho")
    put("sol.firma_dia", str(today.day), "hoy")
    put("sol.firma_mes", MONTHS[today.month - 1], "hoy")
    put("sol.firma_anio", str(today.year), "hoy")
    put("sol.dirigida_provincia", province, "expediente")
    return p


def _part(value: str, key: str, part: str | None) -> str:
    if part is None:
        return value
    if key.endswith(".nie"):
        m = re.fullmatch(r"\s*([XYZ])\W*(\d{7})\W*([A-Z])\s*", value.upper())
        if not m:
            return value if part == "2" else ""
        return {"1": m.group(1), "2": m.group(2), "3": m.group(3)}[part]
    if key.endswith("fecha_nacimiento"):
        try:
            d = date.fromisoformat(value)
        except ValueError:
            return ""
        return {"d": f"{d.day:02d}", "m": f"{d.month:02d}", "y": str(d.year)}[part]
    return value


def fill_pdf(code: str, values: dict[str, str], options: list[str], extra: dict[str, str]) -> bytes:
    """Rellena el PDF oficial con los valores confirmados. Devuelve un BORRADOR sin firma."""
    import pypdf
    from pypdf.generic import NameObject

    data = available()[code]
    reader = pypdf.PdfReader(str(DIR / "pdf" / f"{code}.pdf"))
    writer = pypdf.PdfWriter(clone_from=reader)
    text: dict[str, str] = {}
    checks: dict[str, str] = {}
    values = dict(values)
    for k in [k for k in values if k.endswith(".domicilio")]:
        role = k.split(".")[0]
        if values.get(f"{role}.tipo_via"):
            values[k] = f"{values[f'{role}.tipo_via']} {values[k]}"
        extra_addr = " ".join(x for x in (values.get(f"{role}.escalera") and f"Esc. {values[f'{role}.escalera']}",
                                          values.get(f"{role}.bloque") and f"Bl. {values[f'{role}.bloque']}") if x)
        if extra_addr:
            values[k] += f", {extra_addr}"
        if values.get(f"{role}.letra"):
            values[f"{role}.piso"] = f"{values.get(f'{role}.piso', '')} {values[f'{role}.letra']}".strip()
        if not values.get(f"{role}.localidad") and values.get(f"{role}.municipio"):
            values[f"{role}.localidad"] = values[f"{role}.municipio"]
    for field, m in data["fields"].items():
        v = values.get(m["key"])
        if v in (None, ""):
            continue
        if "on" in m:  # casilla
            if str(v) == m.get("part"):
                checks[field] = m["on"]
        else:
            text[field] = _part(str(v), m["key"], m.get("part"))
    for o in data.get("options", []):
        if o["field"] in options:
            checks[o["field"]] = "Yes"
    for e in data.get("extra_text", []):
        if extra.get(e["field"]):
            text[e["field"]] = extra[e["field"]]
    for page in writer.pages:
        writer.update_page_form_field_values(page, {k: v for k, v in text.items() if v}, auto_regenerate=False)
        for a in page.get("/Annots") or []:
            a = a.get_object()
            name = a.get("/T") or (a["/Parent"].get_object().get("/T") if a.get("/Parent") else None)
            if name in checks:
                on = checks[name]
                states = list((a.get("/AP") or {}).get("/N", {}).keys()) if a.get("/AP") else []
                state = NameObject(f"/{on}") if f"/{on}" in states or not states else NameObject(next(s for s in states if s != "/Off"))
                a[NameObject("/AS")] = state
                target = a["/Parent"].get_object() if a.get("/Parent") and not a.get("/T") else a
                target[NameObject("/V")] = state
    writer.set_need_appearances_writer(True)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def known_keys() -> set[str]:
    return {f"{r}.{k}" for r, ks in FIELDS.items() for k in ks}
