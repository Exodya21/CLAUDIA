"""Motor de autorización. Denegar por defecto.

Niveles de acceso:
  expediente: 'full' (contenido) | 'metadata' (código, materia, estado) | None (invisible)
  contacto:   'full' (ficha completa) | 'minimal' (identidad enmascarada) | None (invisible)

La entidad legal (organization) es la frontera dura: sin pertenencia, el recurso no
existe para el usuario (404, sin revelar existencia). Dentro de la entidad, un acceso
no permitido a un expediente devuelve 403 y se audita.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ..models import AccessGrant, CaseAssignment, CaseFile, Contact
from .auth import Principal


@dataclass
class CaseScope:
    assigned_ids: set[uuid.UUID]
    granted_ids: set[uuid.UUID]


def load_case_scope(db: Session, p: Principal) -> CaseScope:
    now = datetime.now(UTC)
    assigned = set(
        db.execute(
            select(CaseAssignment.case_id).where(
                CaseAssignment.user_id == p.id,
                CaseAssignment.start_at <= now,
                or_(CaseAssignment.end_at.is_(None), CaseAssignment.end_at > now),
            )
        ).scalars()
    )
    granted = set(
        db.execute(
            select(AccessGrant.resource_id).where(
                AccessGrant.user_id == p.id,
                AccessGrant.resource_type == "case_file",
                AccessGrant.permission == "case.read",
                AccessGrant.revoked_at.is_(None),
                AccessGrant.expires_at > now,
                AccessGrant.organization_id.in_(p.org_ids() or {uuid.uuid4()}),
            )
        ).scalars()
    )
    return CaseScope(assigned, granted)


def case_level(p: Principal, case: CaseFile, scope: CaseScope) -> str | None:
    org = case.organization_id
    if org not in p.org_ids():
        return None
    if p.has(org, "case.read.all"):
        return "full"
    for m in p.memberships_with(org, "case.read.department"):
        if m.department_id == case.department_id and (m.branch_id is None or m.branch_id == case.branch_id):
            return "full"
    if p.has(org, "case.read.assigned") and case.id in scope.assigned_ids:
        return "full"
    if case.id in scope.granted_ids:
        return "full"
    if p.has(org, "case.metadata.read"):
        return "metadata"
    return None


def case_visibility_filter(p: Principal, scope: CaseScope, full_only: bool = False) -> ColumnElement[bool]:
    """Filtro SQL equivalente a case_level(...) is not None (o == 'full')."""
    conds: list[ColumnElement[bool]] = []
    for org in p.org_ids():
        if p.has(org, "case.read.all") or (not full_only and p.has(org, "case.metadata.read")):
            conds.append(CaseFile.organization_id == org)
            continue
        for m in p.memberships_with(org, "case.read.department"):
            c = and_(CaseFile.organization_id == org, CaseFile.department_id == m.department_id)
            if m.branch_id is not None:
                c = and_(c, CaseFile.branch_id == m.branch_id)
            conds.append(c)
        if p.has(org, "case.read.assigned") and scope.assigned_ids:
            conds.append(and_(CaseFile.organization_id == org, CaseFile.id.in_(scope.assigned_ids)))
    if scope.granted_ids:
        conds.append(CaseFile.id.in_(scope.granted_ids))
    return or_(*conds) if conds else false()


def contacts_with_full_case(db: Session, p: Principal, scope: CaseScope) -> set[uuid.UUID]:
    return set(
        db.execute(select(CaseFile.contact_id).where(case_visibility_filter(p, scope, full_only=True))).scalars()
    )


def contact_level(p: Principal, c: Contact, full_case_contacts: set[uuid.UUID]) -> str | None:
    org = c.organization_id
    if org not in p.org_ids():
        return None
    if p.has(org, "contact.read.all"):
        return "full"
    if p.has(org, "contact.read.own") and (c.created_by == p.id or c.id in full_case_contacts):
        return "full"
    if p.has(org, "contact.search"):
        return "minimal"
    return None
