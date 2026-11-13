"""Entrega los correos pendientes de la cola y escala los avisos urgentes sin confirmar.

Uso (programador de tareas, cada 5 minutos):  python -m app.ops.outbox
"""

from __future__ import annotations

from ..comm.core import sweep_urgent
from ..db import get_sessionmaker
from ..services.notify import dispatch_pending


def main() -> None:
    db = get_sessionmaker()()
    try:
        n = sweep_urgent(db)
        db.commit()
    finally:
        db.close()
    r = dispatch_pending(500)
    print(f"Avisos urgentes escalados: {n} · correos enviados: {r['enviados']} · errores: {r['errores']} · "
          f"sin correo configurado: {r['no_configurado']}")


if __name__ == "__main__":
    main()
