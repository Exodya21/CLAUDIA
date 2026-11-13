"""Catálogo de trámites de extranjería y nacionalidad (F4.1).

Fuente de cada trámite: la hoja informativa OFICIAL del Ministerio de Inclusión, Seguridad Social y Migraciones
(o la página del Ministerio de Justicia para nacionalidad), con su fecha de actualización tal como consta en ella.
Consultadas el 05/11/2026. Las hojas son orientativas: rige la normativa vigente al presentar.

ESTADO: «pendiente de validación». Ninguna lista se da por aprobada hasta que la valida Legal Extranjería en la
pantalla de catálogo (`immig.catalog.approve`); mientras tanto la interfaz lo muestra en cada expediente.
El sistema NO decide si un documento es suficiente: comprueba que existe, su tipo y sus fechas visibles.
"""

from __future__ import annotations

# Tipos de documento: código -> (nombre, ¿tiene caducidad propia?)
DOC_TYPES: dict[str, str] = {
    "pasaporte": "Pasaporte completo (todas las hojas)",
    "tie_nie": "TIE / NIE / tarjeta de residencia",
    "formulario_ex": "Impreso de solicitud (modelo EX)",
    "tasa_790": "Justificante de la tasa (modelo 790)",
    "representacion": "Designación de representante / autorización",
    "empadronamiento": "Certificado de empadronamiento",
    "permanencia": "Prueba de permanencia en España (padrón, sanidad, otros)",
    "antecedentes_origen": "Certificado de antecedentes penales (país de origen o residencia)",
    "informe_integracion": "Informe de integración social",
    "informe_esfuerzo": "Informe de esfuerzo de integración",
    "contrato_trabajo": "Contrato de trabajo",
    "empleador_nif": "NIF del empleador / escrituras / poder",
    "solvencia_empresa": "Solvencia del empleador (IRPF, IVA, IS o VILE)",
    "nominas": "Nóminas",
    "vida_laboral": "Informe de vida laboral",
    "cualificacion": "Títulos / cualificación profesional",
    "medios_economicos": "Medios económicos",
    "seguro_medico": "Seguro de enfermedad",
    "vivienda": "Informe o prueba de vivienda adecuada",
    "vinculo_familiar": "Prueba del vínculo familiar (matrimonio, nacimiento, pareja)",
    "certificado_nacimiento": "Certificado de nacimiento",
    "documento_ue": "Documento de identidad del ciudadano UE/EEE/Suiza",
    "escolarizacion": "Informe de escolarización de menores",
    "matricula_formacion": "Matrícula o admisión en la formación",
    "titulo_estudios": "Certificación de estudios superados",
    "no_beca": "Certificado de no haber recibido beca (o declaración)",
    "certificado_medico": "Certificado médico",
    "vulnerabilidad": "Certificado de vulnerabilidad (Anexo II)",
    "convivencia": "Prueba de convivencia",
    "actividad_laboral": "Actividad laboral, oferta de empleo o declaración de cuenta propia",
    "dele_ccse": "Diplomas DELE (A2 o superior) y CCSE",
    "prestacion": "Concesión de prestación (desempleo o asistencial)",
    "declaracion_responsable": "Declaración responsable",
    "requerimiento": "Requerimiento de la Administración",
    "resolucion": "Resolución",
    "resguardo_presentacion": "Resguardo de presentación (Mercurio / registro)",
    "otros": "Otros",
}

# Requisitos comunes a casi todos los trámites presentados con representante del despacho.
_REPRESENTACION = ("representacion", "Autorización / designación del despacho como representante", "condicional",
                   "Cuando presenta el despacho en nombre del cliente")

_EXT_NOTA = ("Documentos extranjeros: traducción jurada y legalización o apostilla, salvo exención (hoja 61).")


def _req(code: str, label: str | None = None, kind: str = "obligatorio", note: str | None = None) -> dict:
    return {"doc_type": code, "label": label or DOC_TYPES[code], "kind": kind, "note": note}


# Cada trámite: code, family, materia, name, sheet, source_url, source_updated, legal_basis, ex_form, fee,
# mercurio, resolution, silence, requirements
PROCEDURES: list[dict] = [
    {
        "code": "ARR-SOCIAL", "family": "arraigo", "materia": "extranjeria", "name": "Arraigo social",
        "sheet": "Hoja 28", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/web/migraciones/w/autorizacion-residencia-temporal-por-circunstancias-excepcionales.-arraigo-social",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 arts. 124-127 y 130-132; Instrucciones SEM 1/2025",
        "ex_form": "EX-10", "fee": "790 código 052, epígrafe 2.3.1", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-10 firmado"), _req("pasaporte"),
            _req("permanencia", "Permanencia continuada de al menos 2 años", note="Preferentemente documentos de una Administración española (padrón, sanidad)"),
            _req("antecedentes_origen", note="Países de residencia en los 5 años anteriores a la entrada en España"),
            _req("vinculo_familiar", "Vínculos familiares o, en su lugar, informe de integración social", "alternativo", "Vínculos (matrimonio, pareja, nacimiento) o informe de la CA/Ayuntamiento"),
            _req("informe_integracion", kind="alternativo", note="Alternativa a los vínculos familiares"),
            _req("medios_economicos", note="Según la hoja: 200 % IPREM (100 % familiar + 100 % solicitante) o actividad por cuenta propia"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "ARR-SOCIOLABORAL", "family": "arraigo", "materia": "extranjeria", "name": "Arraigo sociolaboral",
        "sheet": "Hoja 29", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/web/migraciones/w/29.-autorizacion-de-residencia-temporal-por-circunstancias-excepcionales.-arraigo-sociolaboral.",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 arts. 124-127",
        "ex_form": "EX-10", "fee": "790 código 052, epígrafe 2.3.1", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-10 firmado"), _req("pasaporte"),
            _req("permanencia", "Permanencia continuada de al menos 2 años"),
            _req("antecedentes_origen", note="Países de residencia en los 5 años anteriores a la entrada en España"),
            _req("contrato_trabajo", "Contrato(s) de trabajo firmados", note="Mínimo 20 h/semana en total y al menos el SMI o convenio, proporcional a la jornada"),
            _req("empleador_nif", note="NIF y, en su caso, estatutos o escrituras que acrediten al firmante"),
            _req("solvencia_empresa"),
            _req("cualificacion", kind="condicional", note="Si el puesto exige cualificación o profesión regulada"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "ARR-SOCIOFORMATIVO", "family": "arraigo", "materia": "extranjeria", "name": "Arraigo socioformativo",
        "sheet": "Hoja 30", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/30.-autorizacion-residencia-temporal-por-circunstancias-excepcionales.-arraigo-socioformativo",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 arts. 125-127.d y 128-130",
        "ex_form": "EX-10", "fee": "790 código 052, epígrafe 2.3.1", "mercurio": False,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-10 firmado"), _req("pasaporte"),
            _req("permanencia", "Permanencia continuada de al menos 2 años"),
            _req("antecedentes_origen"), _req("informe_integracion"),
            _req("declaracion_responsable", "Compromiso de realizar la formación", "condicional", "Formación promovida por los Servicios Públicos de Empleo"),
            _req("matricula_formacion"), _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "ARR-FAMILIAR", "family": "arraigo", "materia": "extranjeria", "name": "Arraigo familiar",
        "sheet": "Hoja 31", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/autorizacion-residencia-temporal-por-circunstancias-excepcionales.-arraigo-familiar",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 arts. 124-127 y 130-132; Instrucción DGM 8/2020",
        "ex_form": "EX-10", "fee": "790 código 052, epígrafe 2.3.1", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-10 firmado"), _req("pasaporte"), _req("antecedentes_origen"),
            _req("certificado_nacimiento", "Certificado de nacimiento del menor o documento de tutela", "condicional", "Progenitor o tutor de menor nacional UE/EEE/Suiza"),
            _req("vinculo_familiar", "Discapacidad, apoyo, cargo y convivencia", "condicional", "Quien presta apoyo a persona con discapacidad UE/EEE/Suiza"),
            _req("documento_ue"), _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "ARR-SEGUNDA-OP", "family": "arraigo", "materia": "extranjeria", "name": "Arraigo de segunda oportunidad",
        "sheet": "Hoja 27", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/web/migraciones/w/autorizacion-residencia-temporal-por-circunstancias-excepcionales.-arraigo-laboral",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 arts. 124-132",
        "ex_form": "EX-10", "fee": "790 código 052, epígrafe 2.3.1", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-10 firmado"), _req("pasaporte"),
            _req("permanencia", "Permanencia continuada de al menos 2 años"), _req("antecedentes_origen"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "ARR-EXTRAORDINARIO", "family": "arraigo", "materia": "extranjeria",
        "name": "Arraigo extraordinario (regularización 2026)", "sheet": "Hoja 28 ter", "source_updated": "26/04/2026",
        "source_url": "https://www.inclusion.gob.es/web/migraciones/w/28-ter.-autorizacion-de-residencia-por-circunstancias-excepcionales-por-razon-de-arraigo-extraordinario",
        "legal_basis": "LO 4/2000 art. 31.3; RD 1155/2024 DA 21ª; RD 316/2026; Orden PJC/617/2025",
        "ex_form": "EX-32", "fee": "790 código 052, epígrafe 2.3.1 (sin NIE: se paga cuando se requiera)", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Formulario EX-32 firmado"),
            _req("pasaporte", "Pasaporte completo, en vigor o caducado (todas las hojas)"),
            _req("antecedentes_origen"),
            _req("permanencia", "Estancia en España antes del 01/01/2026 y 5 meses ininterrumpidos"),
            _req("actividad_laboral", kind="alternativo", note="Modalidad con actividad laboral"),
            _req("vinculo_familiar", kind="alternativo", note="Modalidad unidad familiar (con convivencia)"),
            _req("convivencia", kind="alternativo", note="Modalidad unidad familiar"),
            _req("vulnerabilidad", kind="alternativo", note="Modalidad vulnerabilidad (Anexo II)"),
            _req("escolarizacion", kind="condicional", note="Si hay menores a cargo"),
            _req("tasa_790", kind="condicional", note="Sin NIE: no se paga hasta que se requiera"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "REN-RT-CA", "family": "renovacion", "materia": "extranjeria",
        "name": "Renovación de residencia temporal y trabajo por cuenta ajena", "sheet": "Hoja 13", "source_updated": "mayo 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/renovacion-de-la-autorizacion-de-residencia-temporal-y-trabajo-por-cuenta-ajena",
        "legal_basis": "LO 4/2000 arts. 36, 38 y 40; RD 1155/2024 arts. 80-81",
        "ex_form": "EX-03", "fee": "790 código 052, epígrafe 2.2.3 (trabajador) + código 062, epígrafe 3.2.2 (empleador)",
        "mercurio": True, "resolution": "3 meses", "silence": "estimatorio",
        "window": "Dos meses antes de caducar y hasta tres meses después (según la hoja)",
        "requirements": [
            _req("formulario_ex", "Impreso EX-03 firmado"), _req("pasaporte"), _req("tie_nie", kind="condicional", note="Tarjeta actual"),
            _req("escolarizacion", kind="condicional", note="Menores en edad de escolarización obligatoria a cargo"),
            _req("informe_esfuerzo", kind="condicional", note="Si no se cumple algún requisito"),
            _req("contrato_trabajo", "Contrato vigente o nuevo contrato", "alternativo", "Según el supuesto invocado"),
            _req("prestacion", kind="alternativo", note="Supuesto de prestación contributiva o asistencial"),
            _req("vida_laboral", kind="condicional", note="Supuestos de actividad mínima o 9 meses en 12"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "MOD-RT", "family": "modificacion", "materia": "extranjeria",
        "name": "Modificación desde residencia que habilita a trabajar", "sheet": "Hoja 55", "source_updated": "agosto 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/55.-modificacion-desde-situaciones-de-autorizaciones-de-residencia-temporal-que-habilitan-a-trabajar",
        "legal_basis": "LO 4/2000 arts. 36-38; RD 1155/2024 art. 191",
        "ex_form": "EX-26", "fee": "790 código 052, epígrafe 2.5.2 (+ 062 según supuesto)", "mercurio": True,
        "resolution": "3 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-26 firmado"), _req("pasaporte"), _req("tie_nie", kind="condicional"),
            _req("contrato_trabajo", kind="condicional", note="Cuenta ajena"), _req("empleador_nif", kind="condicional", note="Cuenta ajena"),
            _req("solvencia_empresa", kind="condicional", note="Cuenta ajena"), _req("cualificacion", kind="condicional"),
            _req("escolarizacion", kind="condicional"), _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "MOD-ESTUDIOS", "family": "modificacion", "materia": "extranjeria",
        "name": "Modificación desde estancia por estudios", "sheet": "Hoja 58", "source_updated": "abril 2026",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/58.-modificaciones-desde-autorizaciones-de-estancia-por-estudios-superiores-ensenanza-secundaria-actividades-formativas-o-formacion-sanitaria-especializada",
        "legal_basis": "LO 4/2000 arts. 36-38; RD 1155/2024 arts. 56 y 190",
        "ex_form": "EX-26", "fee": "790 código 052, epígrafe 2.5 (+ 062, epígrafe 3.2.1 en trabajo)", "mercurio": True,
        "resolution": "3 meses (2 meses o 20 días según supuesto)", "silence": "según supuesto",
        "requirements": [
            _req("formulario_ex", "Impreso EX-26 firmado"), _req("pasaporte"), _req("titulo_estudios"),
            _req("no_beca", kind="condicional", note="Trabajo por cuenta ajena o propia"),
            _req("antecedentes_origen", kind="condicional"), _req("contrato_trabajo", kind="condicional", note="Cuenta ajena"),
            _req("empleador_nif", kind="condicional"), _req("solvencia_empresa", kind="condicional"),
            _req("seguro_medico", kind="condicional"), _req("medios_economicos", kind="condicional"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "REAG-FAM", "family": "reagrupacion", "materia": "extranjeria",
        "name": "Residencia temporal por reagrupación familiar", "sheet": "Hoja 8", "source_updated": "mayo 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/autorizacion-de-residencia-temporal-por-reagrupacion-familiar",
        "legal_basis": "Directiva 2003/86/CE; LO 4/2000 arts. 16-19; RD 1155/2024 arts. 65-68",
        "ex_form": "EX-02", "fee": "790 código 052, epígrafe 2.1.2", "mercurio": True,
        "resolution": "2 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-02 firmado (reagrupante)"),
            _req("pasaporte", "Pasaporte del reagrupante"), _req("pasaporte", "Pasaporte del familiar reagrupado"),
            _req("contrato_trabajo", "Recursos: contrato y nóminas de 6 meses, IRPF o medios", "alternativo"),
            _req("nominas", kind="alternativo"), _req("medios_economicos", kind="alternativo"),
            _req("vivienda", note="Informe de la CA o sustitutorio; antigüedad máxima de 6 meses según la hoja"),
            _req("seguro_medico"), _req("vinculo_familiar"),
            _req("declaracion_responsable", "Declaración de no convivencia con otro cónyuge o pareja", "condicional", "Cónyuge o pareja"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "LD-NACIONAL", "family": "larga_duracion", "materia": "extranjeria",
        "name": "Residencia de larga duración (nacional)", "sheet": "Hoja 49", "source_updated": "mayo 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/49.-autorizacion-de-residencia-de-larga-duracion-nacional",
        "legal_basis": "LO 4/2000 art. 32; RD 1155/2024 arts. 182-185",
        "ex_form": "EX-11", "fee": "790 código 052, epígrafe 2.6", "mercurio": True,
        "resolution": "3 meses", "silence": "estimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-11 firmado"), _req("pasaporte"), _req("tie_nie", kind="condicional"),
            _req("escolarizacion", kind="condicional"), _req("antecedentes_origen", kind="condicional"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "LD-UE", "family": "larga_duracion", "materia": "extranjeria",
        "name": "Residencia de larga duración UE", "sheet": "Hoja 50", "source_updated": "mayo 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/50.-autorizacion-de-residencia-de-larga-duracion-ue",
        "legal_basis": "Directiva 2003/109/CE; LO 4/2000 art. 32; RD 1155/2024 arts. 175-178",
        "ex_form": "EX-11", "fee": "790 código 052, epígrafe 2.6", "mercurio": True,
        "resolution": "3 meses", "silence": "estimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-11 firmado"), _req("tasa_790"), _req("pasaporte"),
            _req("medios_economicos", note="Recursos fijos y regulares (IPREM según la hoja)"),
            _req("seguro_medico"), _req("antecedentes_origen", kind="condicional"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "EST-ESTUDIOS", "family": "estancia", "materia": "extranjeria",
        "name": "Estancia por estudios (solicitud en España)", "sheet": "Hoja 1", "source_updated": "noviembre 2025",
        "source_url": "https://www.inclusion.gob.es/en/web/migraciones/w/estancia-por-estudios",
        "legal_basis": "Directiva (UE) 2016/801; LO 4/2000 arts. 25 bis y 33; RD 1155/2024 arts. 34-36 y 52-58",
        "ex_form": "EX-00", "fee": "Tasa de tramitación (la hoja no indica código)", "mercurio": True,
        "resolution": "2 meses", "silence": "desestimatorio",
        "requirements": [
            _req("formulario_ex", "Impreso EX-00 firmado"), _req("pasaporte", note="Validez mínima de un año según la hoja"),
            _req("certificado_medico", kind="condicional"), _req("medios_economicos"), _req("seguro_medico"),
            _req("matricula_formacion", "Admisión y pago de matrícula"),
            _req("antecedentes_origen", kind="condicional", note="Estancia de más de 6 meses y mayor de edad penal"),
            _req("tasa_790"), _req(*_REPRESENTACION),
        ],
    },
    {
        "code": "NAC-RESIDENCIA", "family": "nacionalidad", "materia": "nacionalidad",
        "name": "Nacionalidad española por residencia", "sheet": "Ministerio de Justicia", "source_updated": "09/12/2020 (fecha de la página)",
        "source_url": "https://www.mjusticia.gob.es/es/ciudadania/nacionalidad/informacion-nacionalidad",
        "legal_basis": "Código Civil art. 22; RD 1004/2015 (verificar vigencia con Legal)",
        "ex_form": "Modelo normalizado de solicitud", "fee": "790 código 026", "mercurio": False,
        "resolution": "(no indicado en la página)", "silence": "(no indicado en la página)",
        "requirements": [
            _req("formulario_ex", "Modelo de solicitud normalizado"), _req("tie_nie"),
            _req("pasaporte", "Pasaporte completo en vigor (y el anterior si el plazo lo exige)"),
            _req("certificado_nacimiento", note="Traducido y legalizado"),
            _req("antecedentes_origen", note="O certificado consular de conducta; traducido y legalizado"),
            _req("dele_ccse", note="Exenciones para nacionales de países de habla hispana y otros supuestos"),
            _req("empadronamiento", kind="condicional", note="Casado/a o viudo/a de español/a: convivencia"),
            _req("tasa_790", "Tasa modelo 790 código 026"), _req(*_REPRESENTACION),
        ],
    },
]

for _p in PROCEDURES:
    _p.setdefault("window", None)
    _p["note"] = _EXT_NOTA

# Fases del flujo de extranjería (lámina «Flujo integral de gestión de extranjería» del despacho).
STAGES: dict[str, str] = {
    "consulta": "Consulta y encargo",
    "documentacion": "Recogida de documentación",
    "preparacion": "Preparación de la solicitud",
    "lista_presentar": "Lista para presentar",
    "presentado": "Presentado",
    "requerimiento": "Requerimiento recibido",
    "requerimiento_respondido": "Requerimiento respondido",
    "resolucion_favorable": "Resolución favorable",
    "resolucion_desfavorable": "Resolución desfavorable",
    "tie": "Tarjeta (TIE) en trámite",
    "recurso": "Impugnación / recurso",
    "cerrado": "Cerrado",
}
# Fases que solo registra quien puede tomar decisiones jurídicas (case.transition.legal).
LEGAL_STAGES = {"resolucion_favorable", "resolucion_desfavorable", "recurso", "cerrado"}
STAGE_FLOW: dict[str, set[str]] = {
    "consulta": {"documentacion"},
    "documentacion": {"preparacion", "cerrado"},
    "preparacion": {"documentacion", "lista_presentar"},
    "lista_presentar": {"preparacion", "presentado"},
    "presentado": {"requerimiento", "resolucion_favorable", "resolucion_desfavorable"},
    "requerimiento": {"requerimiento_respondido"},
    "requerimiento_respondido": {"requerimiento", "resolucion_favorable", "resolucion_desfavorable"},
    "resolucion_favorable": {"tie", "cerrado"},
    "resolucion_desfavorable": {"recurso", "cerrado"},
    "tie": {"cerrado"},
    "recurso": {"resolucion_favorable", "resolucion_desfavorable", "cerrado"},
    "cerrado": set(),
}

# Límites de Mercurio según su manual de usuario (Plataforma de Extranjería, SGAD; copia del ICAB).
MERCURIO_MAX_BYTES = 6 * 1024 * 1024
MERCURIO_FORMATS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/tiff": "tif", "image/gif": "gif"}
MERCURIO_SOURCE = ("https://www.icab.es/export/sites/icab/.galleries/documents-noticies/"
                   "plataforma-de-extranjeria.-mercurio-iniciales.-manual-de-usuario.pdf")
