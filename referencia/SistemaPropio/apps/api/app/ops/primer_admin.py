"""Alta de la PRIMERA persona administradora de una entidad (instalación nueva, sin datos ficticios).

  python -m app.ops.primer_admin --usuario rserrano --nombre "Nombre Apellidos" --correo x@despacho.es \
      --entidad "Nombre de la sociedad" [--crear-entidad --pais ES --moneda EUR]

Se niega si la entidad ya tiene alguien que administre usuarios: a partir de ahí, las altas se hacen
desde la pantalla de Administración y quedan auditadas. Imprime una contraseña provisional (solo una vez).
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from .. import audit
from ..db import get_sessionmaker
from ..models import Branch, Department, Membership, Organization, Role, UserAccount
from ..routers.admin import _admins_left
from ..security import credentials as cred
from ..security.catalog_sync import sync_roles


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.ops.primer_admin")
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--correo", required=True)
    ap.add_argument("--entidad", required=True)
    ap.add_argument("--crear-entidad", action="store_true")
    ap.add_argument("--pais", default="ES")
    ap.add_argument("--moneda", default="EUR")
    ap.add_argument("--sedes", default="", help="Sedes separadas por comas al crear la entidad (p. ej. Barcelona,Madrid,Valencia)")
    a = ap.parse_args(argv)
    db = get_sessionmaker()()
    try:
        sync_roles(db)
        org = db.execute(select(Organization).where(Organization.name == a.entidad)).scalar_one_or_none()
        if org is None:
            if not a.crear_entidad:
                print("La entidad no existe. Añada --crear-entidad para crearla.", file=sys.stderr)
                return 2
            org = Organization(name=a.entidad, country=a.pais.upper()[:2], currency=a.moneda.upper()[:3])
            db.add(org)
            db.flush()
            from ..seed import DEPARTMENTS  # solo la lista de departamentos; no carga ningún dato ficticio
            for code, dname, legal in DEPARTMENTS:
                db.add(Department(organization_id=org.id, code=code, name=dname, is_legal=legal))
            for sede in [x.strip() for x in a.sedes.split(",") if x.strip()]:
                db.add(Branch(organization_id=org.id, name=sede, city=sede, country=org.country, timezone="Europe/Madrid"
                              if org.country == "ES" else "America/Bogota", kind="sede"))
            db.flush()
        if _admins_left(db, org.id) > 0:
            print("Esta entidad ya tiene administración. Use la pantalla de Administración.", file=sys.stderr)
            return 2
        username = a.usuario.strip().lower()
        if db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none():
            print("Ese nombre de usuario ya existe.", file=sys.stderr)
            return 2
        temp = cred.temporary_password()
        u = UserAccount(username=username, full_name=a.nombre.strip(), email=a.correo.strip().lower(), status="activo",
                        is_demo=False, password_hash=cred.hash_password(temp), must_change_password=True)
        db.add(u)
        db.flush()
        role = db.execute(select(Role).where(Role.code == "direccion")).scalar_one()
        db.add(Membership(user_id=u.id, organization_id=org.id, role_id=role.id, status="activa"))
        audit.record(db, actor_id=None, action="admin.bootstrap", resource_type="user", resource_id=u.id,
                     organization_id=org.id, reason="primera persona administradora (consola)",
                     after={"username": username, "rol": "direccion", "entidad": org.name})
        db.commit()
        print(f"Usuario {username} creado con rol Dirección en «{org.name}».")
        print(f"Contraseña provisional (se muestra una sola vez): {temp}")
        print("En el primer acceso deberá cambiarla y activar la doble verificación.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
