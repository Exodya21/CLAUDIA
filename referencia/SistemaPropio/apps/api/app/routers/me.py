from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Branch, Department, Organization
from ..schemas import BranchOut, MembershipOut, MeOut, OrganizationOut, OrgRef
from ..security.auth import Principal, get_principal

router = APIRouter(tags=["perfil"])


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> MeOut:
    out = []
    for m in p.memberships:
        org = db.get(Organization, m.organization_id)
        br = db.get(Branch, m.branch_id) if m.branch_id else None
        dep = db.get(Department, m.department_id) if m.department_id else None
        out.append(MembershipOut(
            organization=OrgRef(id=org.id, name=org.name, country=org.country),
            branch=br.name if br else None, department=dep.name if dep else None,
            role_code=m.role.code, role_name=m.role.name,
        ))
    return MeOut(
        id=p.id, username=p.user.username, full_name=p.user.full_name, email=p.user.email,
        memberships=out, permissions={str(o): sorted(p.perms(o)) for o in p.org_ids()},
        auth_mode=p.auth_method, environment=get_settings().app_env,
        has_password=bool(p.user.password_hash),
    )


@router.get("/organizations", response_model=list[OrganizationOut])
def organizations(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[OrganizationOut]:
    """Solo las entidades donde el usuario tiene pertenencia vigente."""
    res = []
    for org in db.execute(select(Organization).where(Organization.id.in_(p.org_ids() or [None])).order_by(Organization.name)).scalars():
        branches = db.execute(select(Branch).where(Branch.organization_id == org.id).order_by(Branch.name)).scalars()
        res.append(OrganizationOut(
            id=org.id, name=org.name, country=org.country,
            branches=[BranchOut(id=b.id, name=b.name, city=b.city, kind=b.kind) for b in branches],
            can_create_contacts=p.has(org.id, "contact.create"),
        ))
    return res


@router.get("/permissions")
def permission_catalog(p: Principal = Depends(get_principal)) -> dict[str, str]:
    """Descripción legible de cada permiso (para la pantalla de permisos efectivos)."""
    from ..security.catalog import PERMISSIONS

    return PERMISSIONS
