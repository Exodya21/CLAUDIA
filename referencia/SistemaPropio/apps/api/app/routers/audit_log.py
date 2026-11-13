from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import AuditEvent, Membership, UserAccount
from ..schemas import AuditOut, Page
from ..security.auth import Principal, get_principal

router = APIRouter(prefix="/audit-events", tags=["auditoría"])


@router.get("", response_model=Page[AuditOut])
def list_events(
    action: str | None = Query(default=None, max_length=80),
    outcome: str | None = Query(default=None, pattern="^(ok|denied)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    orgs = p.orgs_with("audit.read")
    if not orgs:
        raise api_error(403, "prohibido", "Solo perfiles autorizados consultan la auditoría.")
    # Eventos de sus entidades, más los de actores que pertenecen a ellas (p. ej. intentos fuera de ámbito).
    members = select(Membership.user_id).where(Membership.organization_id.in_(orgs))
    where = or_(AuditEvent.organization_id.in_(orgs),
                and_(AuditEvent.organization_id.is_(None), AuditEvent.actor_user_id.in_(members)))
    q = select(AuditEvent, UserAccount.username).outerjoin(UserAccount, UserAccount.id == AuditEvent.actor_user_id).where(where)
    if action:
        q = q.where(AuditEvent.action == action)
    if outcome:
        q = q.where(AuditEvent.outcome == outcome)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(q.order_by(AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for ev, uname in rows:
        o = AuditOut.model_validate(ev)
        o.actor_username = uname
        items.append(o)
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/verify")
def verify(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    if not p.orgs_with("audit.read"):
        raise api_error(403, "prohibido", "Solo perfiles autorizados consultan la auditoría.")
    ok, n, broken = audit.verify_chain(db)
    return {"integra": ok, "eventos_verificados": n, "primer_evento_alterado": broken}
