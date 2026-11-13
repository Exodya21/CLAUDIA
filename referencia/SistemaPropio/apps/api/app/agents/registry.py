"""Registro de agentes. Añadir un agente = una clase nueva aquí; el motor, la bandeja y la pantalla lo recogen solos.

Próximos (según `docs/producto/plan_motores_direccion.md`): recepción (cierre diario, DR-REC), RRHH (vencimientos,
DR-RH), proveedores y tesorería (DR-CON-4, 7, 8).
"""

from __future__ import annotations

from .base import Agent
from .conciliacion import ConciliacionAgent
from .contabilidad import ContabilidadAgent
from .mensajes import MensajesAgent
from .recepcion import RecepcionAgent
from .rrhh import RrhhAgent

AGENTS: list[Agent] = [ConciliacionAgent(), MensajesAgent(), RecepcionAgent(), RrhhAgent(), ContabilidadAgent()]
_BY_CODE = {a.code: a for a in AGENTS}


def by_code(code: str) -> Agent:
    return _BY_CODE[code]


def get(code: str) -> Agent | None:
    return _BY_CODE.get(code)
