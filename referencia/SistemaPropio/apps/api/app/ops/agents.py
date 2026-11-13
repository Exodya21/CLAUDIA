"""Trabajo de los agentes fuera de las peticiones: reparte eventos pendientes y lanza su calendario.

Uso (programador de tareas, cada 5 minutos, junto a `app.ops.outbox`):  python -m app.ops.agents
"""

from __future__ import annotations

from ..agents.engine import dispatch_events, run_scheduled
from ..db import get_sessionmaker


def main() -> None:
    n = dispatch_events(1000)
    db = get_sessionmaker()()
    try:
        runs = run_scheduled(db)
        db.commit()
    finally:
        db.close()
    errors = sum(1 for r in runs if r.status == "error")
    print(f"Eventos repartidos: {n} · agentes ejecutados: {len(runs)} · con error: {errors}")


if __name__ == "__main__":
    main()
