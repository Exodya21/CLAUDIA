"""Plantillas de mensajes automáticos (DR-PLT-1…5 y seguimiento), textos de Dirección del 08/11/2026 adaptados al
portal propio (sin WhatsApp, T-31). Cada cambio de texto = nueva VERSION (queda en `comm_dispatch`).

- Las fechas, horas y lugares salen SIEMPRE de una tarea de la agenda del expediente (conciliación o señalamiento);
  si falta el lugar, no se envía: se pide completarlo (DR-MSG-5: «fecha y lugar verificados»).
- Sin datos sensibles (DR-MSG-9) y sin prometer resultados (U-15). Textos pendientes de validar (T-32).
"""

from __future__ import annotations

from datetime import datetime

from .templates import MADRID, TemplateError

VERSION = "2026-11-08.1"
FIRM = "Abogado Rafael Serrano"

# código -> (nombre, motor DR, tipo de tarea requerido o None, texto)
AUTO: dict[str, tuple[str, str, str | None, str]] = {
    "bienvenida_expediente": (
        "Bienvenida al abrir el expediente", "DR-PLT-1", None,
        "Buenos días, {nombre}. Le confirmamos que hemos abierto su expediente con referencia {expediente} en "
        f"{FIRM}. Para consultas relacionadas con su expediente, puede responder a este mensaje.",
    ),
    "aviso_fecha_conciliacion": (
        "Aviso de fecha de conciliación", "DR-PLT-2", "conciliacion",
        "Buenos días, {nombre}. Le informamos de que la conciliación correspondiente a su expediente {expediente} "
        "está señalada para el día {fecha}, a las {hora}, en {lugar}. Si se produce algún cambio, se lo comunicaremos.",
    ),
    "recordatorio_conciliacion_24h": (
        "Recordatorio de conciliación (día anterior)", "DR-PLT-3", "conciliacion",
        "Buenos días, {nombre}. Le recordamos que la conciliación de su expediente {expediente} está prevista para "
        "mañana, día {fecha}, a las {hora}, en {lugar}. Si tiene alguna incidencia para asistir, comuníquenoslo "
        "cuanto antes.",
    ),
    "aviso_fecha_juicio": (
        "Aviso de fecha de juicio", "DR-PLT-4", "senalamiento",
        "Buenos días, {nombre}. Le informamos de que el juicio correspondiente a su expediente {expediente} está "
        "señalado para el día {fecha}, a las {hora}, en {lugar}. Le avisaremos si se produce alguna modificación.",
    ),
    "recordatorio_juicio_24h": (
        "Recordatorio de juicio (día anterior)", "DR-PLT-5", "senalamiento",
        "Buenos días, {nombre}. Le recordamos que el juicio de su expediente {expediente} está previsto para mañana, "
        "día {fecha}, a las {hora}, en {lugar}. Si tiene alguna incidencia para asistir, comuníquenoslo cuanto antes.",
    ),
    "seguimiento_expediente": (
        "Seguimiento periódico", "DR-MSG-4", None,
        f"Buenos días. Le contactamos desde el despacho {FIRM}. Hemos comprobado que su expediente {{expediente}} "
        "continúa en trámite. Seguimos pendientes de novedades y le informaremos cuando se produzca alguna actuación "
        "relevante. Gracias por su confianza.",
    ),
}

# Por tipo de tarea: (aviso al crearse la fecha, recordatorio el día anterior)
BY_TASK_KIND = {"conciliacion": ("aviso_fecha_conciliacion", "recordatorio_conciliacion_24h"),
                "senalamiento": ("aviso_fecha_juicio", "recordatorio_juicio_24h")}
# T-47: solo estos pueden enviarse sin revisión, y solo si Dirección pone el agente en modo automático tras el piloto.
AUTOMATIC_ALLOWED = set(AUTO)


def task_values(task) -> dict:
    if not task.start_at:
        raise TemplateError("La tarea no tiene fecha y hora.")
    if not (task.location or "").strip():
        raise TemplateError("La tarea no tiene lugar: complételo en la agenda antes de avisar al cliente.")
    local: datetime = task.start_at.astimezone(MADRID)
    return {"fecha": local.strftime("%d/%m/%Y"), "hora": local.strftime("%H:%M"), "lugar": task.location.strip(),
            "start_at": task.start_at.isoformat()}


def render(code: str, *, nombre: str, expediente: str, task=None) -> str:
    if code not in AUTO:
        raise TemplateError("Plantilla automática desconocida.")
    _n, _dr, need, text = AUTO[code]
    values = {"nombre": nombre, "expediente": expediente}
    if need:
        if task is None or task.kind != need:
            raise TemplateError("La plantilla necesita la tarea de la agenda del tipo correcto.")
        values.update(task_values(task))
    return text.format(**values)


def catalog() -> list[dict]:
    return [{"code": c, "name": n, "dr": dr, "task_kind": k, "version": VERSION, "text": t}
            for c, (n, dr, k, t) in AUTO.items()]
