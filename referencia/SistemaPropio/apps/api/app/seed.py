"""Carga datos FICTICIOS para desarrollo y pruebas.

    python -m app.seed

- Se niega a ejecutarse con APP_ENV=production o staging.
- Nombres generados por combinación; documentos de tipo PASAPORTE con prefijo ZZDEMO y
  país 'XX' (código ISO 3166 reservado para uso privado: no corresponde a ningún país).
- Correos en el dominio reservado .invalid (RFC 2606): nunca se pueden entregar.
- Idempotente: si ya existe la entidad demo, no duplica nada.
"""

from __future__ import annotations

import random
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import get_settings
from .db import get_sessionmaker
from .models import (
    Address,
    Branch,
    CaseAssignment,
    CaseCodeCounter,
    CaseFile,
    Consent,
    Contact,
    ContactPoint,
    Department,
    Identifier,
    Membership,
    Organization,
    Role,
    UserAccount,
)
from .security.catalog_sync import sync_roles
from .validation import fold

ORG_ES = "Despacho Demo España S.L. (ficticia)"
ORG_ES2 = "Entidad Demo Autónomo (ficticia)"
ORG_CO = "Soporte Demo Colombia S.A.S. (ficticia)"

DEPARTMENTS = [
    ("LAB", "Laboral", True), ("EXT", "Extranjería", True), ("NAC", "Nacionalidad", True),
    ("ATC", "Atención al cliente", False), ("REC", "Recepción", False), ("MKT", "Marketing", False),
    ("CON", "Contabilidad", False), ("RRHH", "Recursos Humanos", False), ("DIR", "Dirección", False),
]
GIVEN = ["Lucía", "Mateo", "Valentina", "Samuel", "Camila", "Hugo", "Daniela", "Iker", "Martina", "Andrés",
         "Paula", "Bruno", "Sofía", "Omar", "Nerea", "Yusuf", "Elena", "Rubén", "Aitana", "Kevin", "Irene",
         "Mohamed", "Noa", "Joel", "Alba", "Santiago", "Carla", "Thiago", "Marta", "Ismael"]
FAMILY = ["Ferrer Demo", "Quintero Ficticio", "Albarrán Prueba", "Montoya Demo", "Esteve Ficticia",
          "Rojas Prueba", "Castañeda Demo", "Llorente Ficticio", "Benítez Prueba", "Arango Demo",
          "Sorní Ficticia", "Pardo Prueba", "Núñez Demo", "Gallardo Ficticio", "Trujillo Prueba"]

# usuario, nombre, rol, entidad, sede, departamento
USERS = [
    ("direccion.demo", "Dirección (demo)", "direccion", ORG_ES, None, "DIR"),
    ("direccion.demo", "Dirección (demo)", "direccion", ORG_ES2, None, None),
    ("socio.demo", "Socio Director (demo)", "direccion", ORG_ES, None, "DIR"),
    ("recepcion.bcn", "Recepción Barcelona (demo)", "recepcion", ORG_ES, "Barcelona", "REC"),
    ("atc.demo", "Atención al cliente (demo)", "atc", ORG_ES, "Madrid", "ATC"),
    ("asesor.laboral.bcn", "Asesor Laboral Barcelona (demo)", "asesor_laboral", ORG_ES, "Barcelona", "LAB"),
    ("asesor.extranjeria.mad", "Asesora Extranjería Madrid (demo)", "asesor_extranjeria", ORG_ES, "Madrid", "EXT"),
    ("lider.extranjeria", "Líder Extranjería (demo)", "lider_extranjeria", ORG_ES, None, "EXT"),
    ("gestor.laboral.vlc", "Gestor Laboral Valencia (demo)", "gestor_laboral", ORG_ES, "Valencia", "LAB"),
    ("lider.laboral", "Líder Laboral (demo)", "lider_laboral", ORG_ES, None, "LAB"),
    ("contabilidad.demo", "Contabilidad (demo)", "contabilidad", ORG_ES, None, "CON"),
    ("recepcion.mad", "Recepción Madrid (demo)", "recepcion", ORG_ES, "Madrid", "REC"),
    ("rrhh.demo", "Recursos Humanos (demo)", "rrhh", ORG_ES, None, "RRHH"),
    ("rrhh.demo", "Recursos Humanos (demo)", "rrhh", ORG_CO, None, None),
    ("soporte.colombia", "Soporte Colombia (demo)", "soporte_colombia", ORG_CO, "Bogotá (soporte)", "ATC"),
    ("asesor.laboral.autonomo", "Asesor Laboral otra entidad (demo)", "asesor_laboral", ORG_ES2, "Barcelona", "LAB"),
]


def next_case_code(db: Session, org_id: uuid.UUID, prefix: str, year: int) -> str:
    """Código consecutivo por entidad/prefijo/año, con bloqueo de fila: nunca se reutiliza (Q-6.2)."""
    row = db.execute(
        select(CaseCodeCounter).where(CaseCodeCounter.organization_id == org_id, CaseCodeCounter.prefix == prefix,
                                      CaseCodeCounter.year == year).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = CaseCodeCounter(organization_id=org_id, prefix=prefix, year=year, last_value=0)
        db.add(row)
    row.last_value += 1
    db.flush()
    return f"{prefix}-{year}-{row.last_value:04d}"


def _roles(db: Session) -> dict[str, Role]:
    return sync_roles(db)


def _org(db: Session, name: str, country: str, currency: str, branches: list[tuple[str, str, str, str]],
         deps: list[tuple[str, str, bool]]) -> tuple[Organization, dict[str, Branch], dict[str, Department]]:
    org = Organization(name=name, country=country, currency=currency)
    db.add(org)
    db.flush()
    bmap = {}
    for bname, city, tz, kind in branches:
        b = Branch(organization_id=org.id, name=bname, city=city, country=country, timezone=tz, kind=kind)
        db.add(b)
        bmap[bname] = b
    dmap = {}
    for code, dname, legal in deps:
        d = Department(organization_id=org.id, code=code, name=dname, is_legal=legal)
        db.add(d)
        dmap[code] = d
    db.flush()
    return org, bmap, dmap


def _contact(db: Session, rnd: random.Random, org: Organization, branch: Branch | None, creator: UserAccount,
             n: int, given: str | None = None, family: str | None = None, phone: str | None = None) -> Contact:
    g = given or rnd.choice(GIVEN)
    f = family or rnd.choice(FAMILY)
    c = Contact(organization_id=org.id, primary_branch_id=branch.id if branch else None, given_name=g,
                family_names=f, search_name=fold(f"{g} {f}"), nationality="XX", is_synthetic=True,
                origin=rnd.choice(["presencial", "telefono", "web", "redes_sociales"]), created_by=creator.id)
    db.add(c)
    db.flush()
    db.add(Identifier(contact_id=c.id, organization_id=org.id, kind="PASAPORTE",
                      number_normalized=f"ZZDEMO{n:05d}", country="XX"))
    db.add(ContactPoint(contact_id=c.id, kind="phone", is_primary=True, label="movil",
                        value_normalized=phone or f"+346{rnd.randint(10, 99)}{n:06d}"))
    db.add(ContactPoint(contact_id=c.id, kind="email", is_primary=True,
                        value_normalized=f"{fold(g).replace(' ', '')}.{n}@ejemplo.invalid"))
    db.add(Address(contact_id=c.id, kind="postal", line1=f"Calle Ficticia {n}, {rnd.randint(1, 9)}º",
                   postal_code=f"0{rnd.randint(1000, 9999)}", municipality=branch.city if branch else "Ciudad Demo",
                   country="ES"))
    db.add(Consent(contact_id=c.id, purpose="gestion_expediente", granted=True, source="presencial",
                   recorded_by=creator.id))
    return c


def seed(db: Session) -> bool:
    """Carga incremental e idempotente: base F0.1, roles al día y datos de F1.2/F2 si faltan.

    Devuelve True si se creó la base (primera ejecución)."""
    created = _seed_base(db)
    _roles(db)
    from .seed_work import seed_work

    seed_work(db)
    from .seed_economy import seed_economy

    seed_economy(db)
    from .seed_immigration import seed_immigration

    seed_immigration(db)
    from .seed_comm import seed_comm

    seed_comm(db)
    from .seed_bank import seed_bank

    seed_bank(db)
    from .seed_hr import seed_hr

    seed_hr(db)
    from .seed_accounting import seed_accounting, seed_routine_owners

    seed_accounting(db)
    seed_routine_owners(db)
    return created


def _seed_base(db: Session) -> bool:
    if db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none():
        return False
    rnd = random.Random(2026)
    roles = _roles(db)
    es, es_b, es_d = _org(db, ORG_ES, "ES", "EUR", [
        ("Barcelona", "Barcelona", "Europe/Madrid", "sede"), ("Madrid", "Madrid", "Europe/Madrid", "sede"),
        ("Valencia", "Valencia", "Europe/Madrid", "sede")], DEPARTMENTS)
    es2, es2_b, es2_d = _org(db, ORG_ES2, "ES", "EUR", [("Barcelona", "Barcelona", "Europe/Madrid", "sede")],
                             [("LAB", "Laboral", True), ("DIR", "Dirección", False)])
    co, co_b, co_d = _org(db, ORG_CO, "CO", "COP", [("Bogotá (soporte)", "Bogotá", "America/Bogota", "soporte")],
                          [("ATC", "Atención al cliente", False)])
    orgs = {ORG_ES: (es, es_b, es_d), ORG_ES2: (es2, es2_b, es2_d), ORG_CO: (co, co_b, co_d)}

    users: dict[str, UserAccount] = {}
    for uname, full, role, oname, bname, dcode in USERS:
        u = users.get(uname)
        if u is None:
            u = UserAccount(username=uname, full_name=full, email=f"{uname}@demo.invalid", is_demo=True)
            db.add(u)
            db.flush()
            users[uname] = u
        org, bmap, dmap = orgs[oname]
        db.add(Membership(user_id=u.id, organization_id=org.id, branch_id=bmap[bname].id if bname else None,
                          department_id=dmap[dcode].id if dcode else None, role_id=roles[role].id))
    db.flush()

    rec = users["recepcion.bcn"]
    n = 1
    es_contacts: list[Contact] = []
    shared_phone = "+34611000999"  # teléfono compartido por dos personas distintas (no se fusionan)
    for i in range(36):
        br = es_b[["Barcelona", "Madrid", "Valencia"][i % 3]]
        es_contacts.append(_contact(db, rnd, es, br, rec, n, phone=shared_phone if i in (4, 5) else None))
        n += 1
    lucia = _contact(db, rnd, es, es_b["Barcelona"], rec, n, "Lucía", "Ferrer Demo")
    n += 1
    es2_contacts = [_contact(db, rnd, es2, es2_b["Barcelona"], users["asesor.laboral.autonomo"], n + i)
                    for i in range(6)]
    n += 6
    co_contacts = [_contact(db, rnd, co, co_b["Bogotá (soporte)"], users["soporte.colombia"], n + i)
                   for i in range(3)]
    db.flush()

    year = datetime.now(UTC).year

    def case(org, bmap, dmap, contact, materia, dcode, bname, title, summary, assignee=None):
        prefix = {"laboral": "LAB", "extranjeria": "EXT", "nacionalidad": "NAC"}[materia]
        cf = CaseFile(organization_id=org.id, branch_id=bmap[bname].id, department_id=dmap[dcode].id,
                      contact_id=contact.id, code=next_case_code(db, org.id, prefix, year), materia=materia,
                      title=title, status=rnd.choice(["abierto", "en_tramite"]),
                      confidential_summary=f"[FICTICIO] {summary}", created_by=users["direccion.demo"].id)
        db.add(cf)
        db.flush()
        if assignee:
            db.add(CaseAssignment(case_id=cf.id, user_id=users[assignee].id, role_in_case="responsable"))
        return cf

    for i, c in enumerate(es_contacts[:12]):
        bname = "Barcelona" if i % 2 == 0 else "Valencia"
        who = "asesor.laboral.bcn" if bname == "Barcelona" else "gestor.laboral.vlc"
        case(es, es_b, es_d, c, "laboral", "LAB", bname, "Reclamación laboral (ficticia)",
             "Estrategia procesal y valoración de pruebas de un caso inventado.", who if i < 10 else None)
    for i, c in enumerate(es_contacts[12:22]):
        case(es, es_b, es_d, c, "extranjeria", "EXT", "Madrid", "Trámite de extranjería (ficticio)",
             "Documentación personal y valoración de requisitos de un caso inventado.",
             "asesor.extranjeria.mad" if i < 8 else None)
    for c in es_contacts[22:25]:
        case(es, es_b, es_d, c, "nacionalidad", "NAC", "Barcelona", "Expediente de nacionalidad (ficticio)",
             "Requisitos pendientes de validación letrada (D-01).")
    # Una misma persona con dos expedientes de ramas distintas: prueba de aislamiento.
    case(es, es_b, es_d, lucia, "laboral", "LAB", "Barcelona", "Despido (ficticio)",
         "Notas confidenciales laborales.", "asesor.laboral.bcn")
    case(es, es_b, es_d, lucia, "extranjeria", "EXT", "Madrid", "Renovación de autorización (ficticia)",
         "Notas confidenciales de extranjería.", "asesor.extranjeria.mad")
    for c in es2_contacts[:3]:
        case(es2, es2_b, es2_d, c, "laboral", "LAB", "Barcelona", "Reclamación otra entidad (ficticia)",
             "Caso inventado de otra entidad legal.", "asesor.laboral.autonomo")
    _ = co_contacts
    audit.record(db, actor_id=None, action="seed.load", resource_type="system",
                 after={"entidades": 3, "usuarios": len(users), "contactos": len(es_contacts) + 1 + 6 + 3})
    return True


def main() -> int:
    s = get_settings()
    if s.app_env not in ("development", "test"):
        print(f"Semilla prohibida con APP_ENV={s.app_env}.", file=sys.stderr)
        return 2
    db = get_sessionmaker()()
    try:
        created = seed(db)
        db.commit()
        print("Datos ficticios cargados." if created else "Base ficticia existente: roles y datos de módulos nuevos actualizados.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
