"""Mapa revisado a mano del EX-10 (arraigos y circunstancias excepcionales): el PDF oficial no tiene capa de texto,
así que las etiquetas no se pueden leer automáticamente. Numeración comprobada sobre el modelo con los campos
superpuestos (05/11/2026). Escribe apps/api/app/immigration/ex_forms/manual.json."""

import json
from pathlib import Path

T = "Texto{}".format
C = "Casilla de verificación{}".format
PERSON = ["pasaporte", ("nie", "1"), ("nie", "2"), ("nie", "3"), "apellido1", "apellido2", "nombre",
          ("fecha_nacimiento", "d"), ("fecha_nacimiento", "m"), ("fecha_nacimiento", "y"), "lugar_nacimiento",
          "pais_nacimiento", "nacionalidad", "padre", "madre", "domicilio", "numero", "piso", "localidad", "cp",
          "provincia", "telefono", "email", "rl_nombre", "rl_doc", "rl_titulo"]
FAM = ["pasaporte", ("nie", "1"), ("nie", "2"), ("nie", "3"), "apellido1", "apellido2", "nombre",
       ("fecha_nacimiento", "d"), ("fecha_nacimiento", "m"), ("fecha_nacimiento", "y"), "pais_nacimiento",
       "nacionalidad", "padre", "madre", "domicilio", "numero", "piso", "localidad", "cp", "provincia", "vinculo"]
ENTITY = ["nombre", "doc", "domicilio", "numero", "piso", "localidad", "cp", "provincia", "telefono", "email",
          "rl_nombre", "rl_doc", "rl_titulo"]
NOTIF = ["nombre", "doc", "domicilio", "numero", "piso", "localidad", "cp", "provincia", "telefono", "email"]
EMP = ["nombre", "doc", "actividad", "cnae", "cno", "domicilio", "numero", "piso", "localidad", "cp", "provincia",
       "telefono", "email", "rl_nombre", "rl_doc", "rl_titulo"]


def seq(role, keys, start, out):
    for i, k in enumerate(keys):
        key, part = (k if isinstance(k, tuple) else (k, None))
        out[T(start + i)] = {"key": f"{role}.{key}", **({"part": part} if part else {})}


fields: dict = {}
seq("ext", PERSON, 1, fields)          # 1-26
seq("fam", FAM, 27, fields)            # 27-47
seq("rep", ENTITY, 48, fields)         # 48-60
seq("notif", NOTIF, 61, fields)        # 61-70
seq("emp", EMP, 71, fields)            # 71-86
for i, k in enumerate(["sol.firma_lugar", "sol.firma_dia", "sol.firma_mes", "sol.firma_anio"]):
    fields[T(149 + i)] = {"key": k}
fields[T(154)] = {"key": "sol.dirigida_a"}
fields[T(155)] = {"key": "sol.dir3"}
fields[T(156)] = {"key": "sol.dirigida_provincia"}
for n, v in zip(range(96, 99), "XHM", strict=True):
    fields[C(n)] = {"key": "ext.sexo", "part": v, "on": "Yes"}
for n, v in zip(range(99, 104), ["S", "C", "V", "D", "Sp"], strict=True):
    fields[C(n)] = {"key": "ext.estado_civil", "part": v, "on": "Yes"}
for n, v in zip(range(104, 107), "XHM", strict=True):
    fields[C(n)] = {"key": "fam.sexo", "part": v, "on": "Yes"}
for n, v in zip(range(107, 112), ["S", "C", "V", "D", "Sp"], strict=True):
    fields[C(n)] = {"key": "fam.estado_civil", "part": v, "on": "Yes"}
fields[C(261)] = {"key": "notif.consiento_dehu", "part": "si", "on": "Yes"}

FORMACION = ["Denominación de la entidad que imparte la formación", "Denominación de la formación", "Código del curso",
             "NIF/CIF de la entidad que la imparte", "Dirección completa de la entidad", "Provincia",
             "Duración (horas)", "Fecha inicio", "Fecha fin"]
extra = [{"field": T(87 + i), "label": lab, "section": "6) CENTRO DE FORMACIÓN (arraigo socioformativo)"}
         for i, lab in enumerate(FORMACION)]
OPTS = [
    (112, "Formación: Educación secundaria postobligatoria", "6"), (113, "Formación: Obtención de certificado profesional", "6"),
    (114, "Formación: Oferta presencial de enseñanzas obligatorias para personas adultas", "6"),
    (115, "Formación: Promovida por los Servicios Públicos de Empleo", "6"),
    (116, "Modalidad: Presencial", "6"), (117, "Modalidad: A distancia", "6"), (118, "Modalidad: Mixta", "6"),
    (119, "TIPO DE SOLICITUD", "7"), (120, "Residencia inicial", "7"), (121, "Prórroga", "7"), (122, "Provisional", "7"),
    (123, "TIPO DE AUTORIZACIÓN", "7"),
    (124, "Arraigo de segunda oportunidad (art. 127.a)", "7"), (125, "Arraigo sociolaboral (art. 127.b)", "7"),
    (126, "Arraigo social (art. 127.c)", "7"), (127, "Arraigo socioformativo (art. 127.d)", "7"),
    (128, "Arraigo familiar (art. 127.e)", "7"),
    (129, "Razones humanitarias – Víctimas de determinados delitos (art. 128.2)", "7"),
    (130, "Razones humanitarias – Enfermedad sobrevenida de carácter grave (art. 128.3.1º)", "7"),
    (131, "Razones humanitarias – Progenitor de menor con enfermedad sobrevenida grave (art. 128.3.2º)", "7"),
    (132, "Razones humanitarias – Peligro para su seguridad o la de su familia (art. 128.4)", "7"),
    (133, "Colaboración con autoridades – ajenas a redes organizadas (art. 129.1)", "7"),
    (134, "Razones de interés público o seguridad nacional (art. 129.1)", "7"),
    (135, "Colaboración con autoridad laboral/judicial – trabajo en situación irregular (art. 129.2)", "7"),
    (136, "Mujer extranjera víctima de violencia de género (art. 133.1)", "7"),
    (137, "Hijo menor o discapacitado o menor tutelado de víctima de violencia de género (art. 134.2)", "7"),
    (138, "Padre/madre de víctima de violencia de género (art. 134.2)", "7"),
    (139, "Víctimas extranjeras de violencia sexual (art. 137.2)", "7"),
    (140, "Hijo menor o discapacitado o menor tutelado de víctima de violencia sexual (art. 138.2)", "7"),
    (141, "Padre/madre de víctima de violencia sexual (art. 138.2)", "7"),
    (142, "Adulto responsable de víctima de violencia sexual menor de edad (art. 141.2)", "7"),
    (143, "Colaboración contra redes organizadas – víctima, perjudicada o testigo (art. 143)", "7"),
    (144, "Víctima de trata – colaboración en la investigación (art. 152.1)", "7"),
    (145, "Víctima de trata – situación personal (art. 152.1)", "7"),
    (146, "Hijo menor o discapacitado, tutelado o padre/madre de víctima de trata (art. 152.1)", "7"),
    (147, "Circunstancias excepcionales no previstas en el RD 1155/2024 (DA 2ª)", "7"),
    (148, "Circunstancias excepcionales DANA 2024 (Prórroga)", "7"),
]
options = [{"field": C(n), "label": lab, "section": "6) CENTRO DE FORMACIÓN" if s == "6" else "7) TIPO DE AUTORIZACIÓN SOLICITADA",
            "page": 2 if s == "6" else 3} for n, lab, s in OPTS]
data = {"title": "Solicitud de autorización de residencia por circunstancias excepcionales", "fields": fields,
        "options": options, "extra_text": extra,
        "unmapped": [{"field": T(153), "section": "Firma", "label": "Firma del solicitante (se deja en blanco)", "right": ""}]}
out = Path(__file__).resolve().parents[1] / "apps/api/app/immigration/ex_forms/manual.json"
out.write_text(json.dumps({"EX10": data}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"EX10: {len(fields)} campos, {len(options)} opciones")
