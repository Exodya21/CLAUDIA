"""Plantillas de mensajes al cliente (U-15: trato de usted, lenguaje claro, sin prometer resultados).

Las fechas de citaciones, juicios y plazos NUNCA las escribe ni las calcula el sistema: salen de una tarea del
expediente; si es un plazo legal, solo cuando un letrado lo ha validado (D-01, D-03, T-12). Textos pendientes de
validación por Dirección (T-32); el de bienvenida no afirma nada sobre plazos (D-10).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

WELCOME = (
    "Le damos la bienvenida al portal del despacho. A partir de ahora puede escribirnos aquí sobre su asunto, "
    "enviarnos documentos y consultar lo que le pidamos. Todo queda guardado en su expediente y lo verá el equipo "
    "que lo lleva. Le responderemos en horario de oficina. Si algo es urgente, se lo indicaremos con un aviso que "
    "le pediremos que confirme."
)

# código -> (nombre, nivel, tipo de tarea requerido o None, texto)
TEMPLATES: dict[str, tuple[str, str, str | None, str]] = {
    "solicitud_documentos": (
        "Solicitud de documentos", "importante", None,
        "Para continuar con su expediente {codigo} necesitamos que nos envíe la siguiente documentación: {lista}. "
        "Puede subirla desde este portal, en «Documentos que faltan». Si tiene alguna duda, escríbanos aquí.",
    ),
    "citacion_conciliacion": (
        "Citación de conciliación (CMAC)", "urgente", "conciliacion",
        "Le comunicamos que el acto de conciliación de su expediente {codigo} está señalado para el {fecha} a las "
        "{hora}{lugar}. Su abogado o abogada le indicará si debe asistir personalmente. Por favor, confirme que ha "
        "leído este aviso.",
    ),
    "senalamiento_juicio": (
        "Señalamiento de juicio", "urgente", "senalamiento",
        "Le comunicamos que el juicio de su expediente {codigo} está señalado para el {fecha} a las {hora}{lugar}. "
        "Nos pondremos en contacto con usted para prepararlo. Por favor, confirme que ha leído este aviso.",
    ),
    "requerimiento": (
        "Requerimiento con plazo", "urgente", "plazo",
        "Hemos recibido un requerimiento en su expediente {codigo}. Necesitamos que nos facilite la documentación "
        "que le indicaremos antes del {fecha}. Por favor, confirme que ha leído este aviso y contacte con nosotros.",
    ),
}


class TemplateError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _fmt_day(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def render(code: str, *, case_code: str, task=None, missing: list[str] | None = None) -> tuple[str, str]:
    """Devuelve (texto, nivel). Comprueba que la fecha venga de una tarea válida del expediente."""
    if code not in TEMPLATES:
        raise TemplateError("Plantilla desconocida.")
    _name, level, need_kind, text = TEMPLATES[code]
    values: dict[str, str] = {"codigo": case_code, "lugar": "", "lista": ""}
    if code == "solicitud_documentos":
        if not missing:
            raise TemplateError("No hay documentos pendientes en la lista del trámite.")
        values["lista"] = "; ".join(missing)
    if need_kind:
        if task is None:
            raise TemplateError("Esta plantilla necesita la tarea del expediente con la fecha.")
        if task.kind != need_kind:
            raise TemplateError("La tarea elegida no es del tipo que pide la plantilla.")
        if need_kind == "plazo":
            if task.legal_status != "validado" or not task.legal_deadline:
                raise TemplateError("El plazo legal de esa tarea no está validado por un letrado: no se puede comunicar.")
            values["fecha"] = _fmt_day(task.legal_deadline)
        else:
            if not task.start_at:
                raise TemplateError("La tarea no tiene fecha y hora.")
            local: datetime = task.start_at.astimezone(MADRID)
            values["fecha"], values["hora"] = _fmt_day(local.date()), local.strftime("%H:%M")
            if task.location:
                values["lugar"] = f", en {task.location}"
    return text.format(**values), level


def catalog() -> list[dict]:
    return [{"code": c, "name": n, "level": lv, "task_kind": k} for c, (n, lv, k, _t) in TEMPLATES.items()]
