"""Autorizaciones puntuales y temporales (permiso 'S' de la matriz). Auditadas (AT-03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import AccessGrant, CaseFile, Membership, Organization, UserAccount
from ..schemas import GrantCreate, GrantOut
from ..security.auth import Principal, get_principal
from .common import req_ctx

router = APIRouter(prefix="/grants", tags=["autorizaciones"])
MAX_GRANT_DAYS = 30


def _out(g: AccessGrant, db: Session) -> GrantOut:
    u = db.get(UserAccount, g.user_id)
    cf = db.get(CaseFile, g.resource_id)
    return GrantOut(id=g.id, user_id=g.user_id, username=u.username, case_id=g.resource_id, case_code=cf.code,
                    reason=g.reason, created_at=g.created_at, expires_at=g.expires_at, revoked_at=g.revoked_at)


@router.get("", response_model=list[GrantOut])
def list_grants(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    orgs = p.orgs_with("grant.manage")
    if not orgs:
        raise api_error(403, "prohibido", "Solo perfiles autorizados gestionan autorizaciones.")
    rows = db.execute(select(AccessGrant).where(AccessGrant.organization_id.in_(orgs))
                      .order_by(AccessGrant.created_at.desc()).limit(200)).scalars()
    return [_out(g, db) for g in rows]


@router.get("/lookup")
def lookup(code: str = Query(min_length=3, max_length=40), p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> dict:
    """Para el formulario de alta: localiza un expediente por código y lista a quién puede concederse.

    El código es consecutivo POR ENTIDAD: con varias entidades puede haber más de una coincidencia.
    """
    orgs = p.orgs_with("grant.manage")
    if not orgs:
        raise api_error(403, "prohibido", "Solo perfiles autorizados gestionan autorizaciones.")
    cases = db.execute(select(CaseFile).where(CaseFile.code == code.strip().upper(),
                                              CaseFile.organization_id.in_(orgs))
                       .order_by(CaseFile.organization_id)).scalars().all()
    if not cases:
        raise api_error(404, "no_encontrado", "No hay ningún expediente con ese código en sus entidades.")
    matches = []
    for cf in cases:
        users = db.execute(select(UserAccount).join(Membership, Membership.user_id == UserAccount.id)
                           .where(Membership.organization_id == cf.organization_id, Membership.status == "activa",
                                  UserAccount.status == "activo").distinct().order_by(UserAccount.full_name)).scalars()
        matches.append({"case_id": str(cf.id), "code": cf.code, "materia": cf.materia, "status": cf.status,
                        "organization": db.get(Organization, cf.organization_id).name,
                        "candidates": [{"id": str(u.id), "username": u.username, "full_name": u.full_name}
                                       for u in users]})
    return {"max_days": MAX_GRANT_DAYS, "matches": matches}


@router.post("", response_model=GrantOut, status_code=201)
def create_grant(body: GrantCreate, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    cf = db.get(CaseFile, body.case_id)
    if cf is None or cf.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    if not p.has(cf.organization_id, "grant.manage"):
        audit.record_independent(actor_id=p.id, action="grant.create", resource_type="case_file", resource_id=cf.id,
                                 organization_id=cf.organization_id, outcome="denied", reason="sin grant.manage",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Su rol no permite conceder autorizaciones.")
    now = datetime.now(UTC)
    exp = body.expires_at if body.expires_at.tzinfo else body.expires_at.replace(tzinfo=UTC)
    if exp <= now or exp > now + timedelta(days=MAX_GRANT_DAYS):
        raise api_error(422, "validacion", f"La caducidad debe estar entre ahora y {MAX_GRANT_DAYS} días.")
    member = db.execute(select(Membership).where(Membership.user_id == body.user_id,
                                                 Membership.organization_id == cf.organization_id,
                                                 Membership.status == "activa")).first()
    if not member:
        # D-17: no se concede acceso a personas sin pertenencia a la entidad (p. ej. otra sociedad).
        raise api_error(422, "validacion", "El usuario no pertenece a la entidad del expediente.")
    g = AccessGrant(user_id=body.user_id, organization_id=cf.organization_id, resource_type="case_file",
                    resource_id=cf.id, permission="case.read", reason=body.reason, granted_by=p.id, expires_at=exp)
    db.add(g)
    db.flush()
    audit.record(db, actor_id=p.id, action="grant.create", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, reason=body.reason,
                 after={"grant_id": str(g.id), "user_id": str(body.user_id), "permiso": "case.read",
                        "caduca": exp.isoformat()}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(g, db)


@router.post("/{grant_id}/revoke", response_model=GrantOut)
def revoke_grant(grant_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    g = db.get(AccessGrant, grant_id)
    if g is None or not p.has(g.organization_id, "grant.manage"):
        raise api_error(404, "no_encontrado", "Autorización no encontrada.")
    if g.revoked_at:
        return _out(g, db)
    g.revoked_at = datetime.now(UTC)
    g.revoked_by = p.id
    audit.record(db, actor_id=p.id, action="grant.revoke", resource_type="case_file", resource_id=g.resource_id,
                 organization_id=g.organization_id, before={"grant_id": str(g.id), "estado": "vigente"},
                 after={"estado": "revocada"}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _out(g, db)
