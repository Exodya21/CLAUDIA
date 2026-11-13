"""Sincroniza roles y permisos con el catálogo del código (cualquier entorno, idempotente).

El catálogo (`catalog.py`) es la única fuente de verdad de qué permite cada rol. Se ejecuta en
cada arranque: `python -m app.security.catalog_sync`.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Role, RolePermission
from .catalog import ROLES


def sync_roles(db: Session) -> dict[str, Role]:
    out = {}
    for code, (name, desc, perms) in ROLES.items():
        r = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
        if r is None:
            r = Role(code=code, name=name, description=desc)
            db.add(r)
            db.flush()
        r.name, r.description = name, desc
        existing = {rp.permission for rp in r.permissions}
        for perm in set(perms) - existing:
            db.add(RolePermission(role_id=r.id, permission=perm))
        for rp in list(r.permissions):
            if rp.permission not in perms:
                db.delete(rp)
        db.flush()
        db.expire(r)
        out[code] = r
    db.flush()
    return out


def main() -> int:
    from ..db import get_sessionmaker

    db = get_sessionmaker()()
    try:
        roles = sync_roles(db)
        from ..immigration.sync import sync_procedures

        n = sync_procedures(db)
        db.commit()
        print(f"Catálogo de permisos sincronizado: {len(roles)} roles. Trámites de extranjería nuevos o cambiados: {n}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
