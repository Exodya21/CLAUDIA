"""Administración de usuarios, pertenencias y sesiones (F0.2). Permiso `admin.users.manage`.

Reglas:
- Solo se gestionan usuarios con pertenencia en una entidad donde el actor administra; el resto → 404.
- Desactivar o restablecer credenciales exige que TODAS las pertenencias vigentes del usuario estén en
  entidades que el actor administra (no se pisa a otra sociedad).
- Nadie se desactiva ni se retira a sí mismo la administración, y cada entidad conserva al menos
  una persona administradora activa.
- Un cambio de rol es fin de pertenencia + pertenencia nueva: el historial no se reescribe.
- Todo cambio se audita con antes/después y motivo; la contraseña provisional nunca se registra.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import Branch, Department, Membership, Organization, Role, RolePermission, UserAccount
from ..models_security import BackupRun, UserSession
from ..schemas import (
    AdminMembershipOut,
    AdminUserCreate,
    AdminUserDetail,
    AdminUserOut,
    AdminUserUpdate,
    BackupRunOut,
    MembershipAddIn,
    MembershipIn,
    ReasonIn,
    SessionOut,
    TempPasswordOut,
)
from ..security import credentials as cred
from ..security.auth import Principal, get_principal, revoke_sessions, session_state
from .auth import session_out
from .common import ReqCtx, req_ctx

router = APIRouter(prefix="/admin", tags=["administración"])
ADMIN_PERM = "admin.users.manage"
TEMP_NOTICE = ("Entregue esta contraseña provisional en persona o por un canal seguro. Solo se muestra ahora. "
               "En el primer acceso la persona la cambiará y activará la doble verificación con su móvil.")


def _now() -> datetime:
    return datetime.now(UTC)


def _admin_orgs(p: Principal, request: Request, action: str) -> set[uuid.UUID]:
    orgs = p.orgs_with(ADMIN_PERM)
    if not orgs:
        ctx = req_ctx(request)
        audit.record_independent(actor_id=p.id, action=action, resource_type="user", outcome="denied",
                                 reason=f"sin {ADMIN_PERM}", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Solo Dirección administra usuarios.")
    return orgs


def _is_current(m: Membership, now: datetime) -> bool:
    return m.status == "activa" and m.valid_from <= now and (m.valid_to is None or m.valid_to > now)


def _memberships(db: Session, user_id: uuid.UUID) -> list[Membership]:
    return list(db.execute(select(Membership).where(Membership.user_id == user_id)
                           .order_by(Membership.valid_from.desc())).scalars())


def _user_visible(db: Session, user_id: uuid.UUID, orgs: set[uuid.UUID]) -> UserAccount:
    u = db.get(UserAccount, user_id)
    if u is None or not any(m.organization_id in orgs for m in _memberships(db, user_id)):
        raise api_error(404, "no_encontrado", "Usuario no encontrado.")
    return u


def _fully_managed(db: Session, user_id: uuid.UUID, orgs: set[uuid.UUID]) -> bool:
    now = _now()
    return all(m.organization_id in orgs for m in _memberships(db, user_id) if _is_current(m, now))


def _admins_left(db: Session, org_id: uuid.UUID, *, without_user: uuid.UUID | None = None,
                 without_membership: uuid.UUID | None = None) -> int:
    now = _now()
    q = (select(func.count(func.distinct(Membership.user_id)))
         .join(UserAccount, UserAccount.id == Membership.user_id)
         .join(RolePermission, RolePermission.role_id == Membership.role_id)
         .where(Membership.organization_id == org_id, Membership.status == "activa", Membership.valid_from <= now,
                or_(Membership.valid_to.is_(None), Membership.valid_to > now), RolePermission.permission == ADMIN_PERM,
                UserAccount.status == "activo"))
    if without_user:
        q = q.where(Membership.user_id != without_user)
    if without_membership:
        q = q.where(Membership.id != without_membership)
    return db.execute(q).scalar_one()


def _m_out(db: Session, m: Membership, orgs: set[uuid.UUID]) -> AdminMembershipOut:
    org = db.get(Organization, m.organization_id)
    br = db.get(Branch, m.branch_id) if m.branch_id else None
    dep = db.get(Department, m.department_id) if m.department_id else None
    now = _now()
    status = m.status if m.status != "activa" or _is_current(m, now) else ("caducada" if m.valid_to else "futura")
    return AdminMembershipOut(id=m.id, organization_id=org.id, organization=org.name, branch_id=m.branch_id,
                              branch=br.name if br else None, department_id=m.department_id,
                              department=dep.name if dep else None, role_code=m.role.code, role_name=m.role.name,
                              status=status, valid_from=m.valid_from, valid_to=m.valid_to,
                              manageable=m.organization_id in orgs)


def _active_sessions(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    rows = db.execute(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None),
                                                UserSession.expires_at > _now())).scalars()
    return [s for s in rows if session_state(s) == "activa"]


def _u_out(db: Session, u: UserAccount, orgs: set[uuid.UUID]) -> AdminUserOut:
    ms = [m for m in _memberships(db, u.id) if m.organization_id in orgs]
    return AdminUserOut(id=u.id, username=u.username, full_name=u.full_name, email=u.email, status=u.status,
                        is_demo=u.is_demo, has_password=bool(u.password_hash), mfa_enrolled=bool(u.totp_confirmed_at),
                        must_change_password=u.must_change_password, last_login_at=u.last_login_at,
                        created_at=u.created_at, memberships=[_m_out(db, m, orgs) for m in ms],
                        active_sessions=len(_active_sessions(db, u.id)))


def _snapshot(u: UserAccount) -> dict:
    return {"username": u.username, "full_name": u.full_name, "email": u.email, "status": u.status,
            "mfa": bool(u.totp_confirmed_at), "contraseña_provisional": u.must_change_password}


def _validate_membership(db: Session, body: MembershipIn, orgs: set[uuid.UUID]) -> Role:
    if body.organization_id not in orgs:
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    role = db.execute(select(Role).where(Role.code == body.role_code)).scalar_one_or_none()
    if role is None:
        raise api_error(422, "validacion", "Rol desconocido.", [{"field": "role_code", "message": "Rol desconocido"}])
    if body.branch_id:
        b = db.get(Branch, body.branch_id)
        if b is None or b.organization_id != body.organization_id:
            raise api_error(422, "validacion", "La sede no pertenece a la entidad.",
                            [{"field": "branch_id", "message": "Sede de otra entidad"}])
    if body.department_id:
        d = db.get(Department, body.department_id)
        if d is None or d.organization_id != body.organization_id:
            raise api_error(422, "validacion", "El departamento no pertenece a la entidad.",
                            [{"field": "department_id", "message": "Departamento de otra entidad"}])
    if body.valid_to and body.valid_to.replace(tzinfo=body.valid_to.tzinfo or UTC) <= _now():
        raise api_error(422, "validacion", "La fecha de fin debe ser futura.",
                        [{"field": "valid_to", "message": "Debe ser futura"}])
    return role


def _m_audit(db: Session, m: Membership) -> dict:
    org = db.get(Organization, m.organization_id)
    return {"pertenencia": str(m.id), "entidad": org.name, "rol": db.get(Role, m.role_id).code,
            "sede": str(m.branch_id) if m.branch_id else None,
            "departamento": str(m.department_id) if m.department_id else None,
            "hasta": m.valid_to.isoformat() if m.valid_to else None, "estado": m.status}


def _audit(db: Session, p: Principal, ctx: ReqCtx, action: str, user_id: uuid.UUID, org_id: uuid.UUID | None,
           reason: str | None, before: dict | None = None, after: dict | None = None) -> None:
    audit.record(db, actor_id=p.id, action=action, resource_type="user", resource_id=user_id, organization_id=org_id,
                 reason=reason, before=before, after=after, ip=ctx.ip, request_id=ctx.request_id)


def _deny(p: Principal, ctx: ReqCtx, action: str, user_id: uuid.UUID, reason: str, org_id: uuid.UUID | None = None):
    audit.record_independent(actor_id=p.id, action=action, resource_type="user", resource_id=user_id,
                             organization_id=org_id, outcome="denied", reason=reason, ip=ctx.ip,
                             request_id=ctx.request_id)


def _first_org(db: Session, user_id: uuid.UUID, orgs: set[uuid.UUID]) -> uuid.UUID | None:
    return next((m.organization_id for m in _memberships(db, user_id) if m.organization_id in orgs), None)


# ------------------------------------------------------------------ catálogo para formularios
@router.get("/catalog")
def catalog(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    orgs = _admin_orgs(p, request, "admin.catalog")
    out = []
    for org in db.execute(select(Organization).where(Organization.id.in_(orgs)).order_by(Organization.name)).scalars():
        out.append({
            "id": str(org.id), "name": org.name, "country": org.country,
            "branches": [{"id": str(b.id), "name": b.name, "kind": b.kind} for b in db.execute(
                select(Branch).where(Branch.organization_id == org.id).order_by(Branch.name)).scalars()],
            "departments": [{"id": str(d.id), "name": d.name, "code": d.code} for d in db.execute(
                select(Department).where(Department.organization_id == org.id).order_by(Department.name)).scalars()],
        })
    roles = [{"code": r.code, "name": r.name, "description": r.description,
              "permissions": sorted(rp.permission for rp in r.permissions)}
             for r in db.execute(select(Role).order_by(Role.name)).scalars()]
    return {"organizations": out, "roles": roles}


# ------------------------------------------------------------------ usuarios
@router.get("/users", response_model=list[AdminUserOut])
def list_users(request: Request, q: str | None = Query(None, max_length=80), status: str | None = Query(None),
               p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list[AdminUserOut]:
    orgs = _admin_orgs(p, request, "admin.users.list")
    ids = select(Membership.user_id).where(Membership.organization_id.in_(orgs))
    stmt = select(UserAccount).where(UserAccount.id.in_(ids))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(UserAccount.username).like(like), func.lower(UserAccount.full_name).like(like),
                              func.lower(UserAccount.email).like(like)))
    if status in ("activo", "inactivo"):
        stmt = stmt.where(UserAccount.status == status)
    users = db.execute(stmt.order_by(UserAccount.full_name).limit(300)).scalars()
    return [_u_out(db, u, orgs) for u in users]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(user_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)) -> AdminUserDetail:
    orgs = _admin_orgs(p, request, "admin.users.read")
    u = _user_visible(db, user_id, orgs)
    sessions = db.execute(select(UserSession).where(UserSession.user_id == u.id)
                          .order_by(UserSession.created_at.desc()).limit(30)).scalars()
    return AdminUserDetail(**_u_out(db, u, orgs).model_dump(), sessions=[session_out(s, p.session_id) for s in sessions])


@router.post("/users", response_model=TempPasswordOut, status_code=201)
def create_user(body: AdminUserCreate, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> TempPasswordOut:
    orgs = _admin_orgs(p, request, "admin.users.create")
    ctx = req_ctx(request)
    role = _validate_membership(db, body.membership, orgs)
    username = body.username.lower()
    if db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none():
        raise api_error(409, "conflicto", "Ese nombre de usuario ya existe.",
                        [{"field": "username", "message": "Ya existe"}])
    temp = cred.temporary_password()
    u = UserAccount(username=username, full_name=body.full_name.strip(), email=body.email.strip().lower(),
                    status="activo", is_demo=False, password_hash=cred.hash_password(temp),
                    must_change_password=True, created_by=p.id)
    db.add(u)
    db.flush()
    m = Membership(user_id=u.id, organization_id=body.membership.organization_id, branch_id=body.membership.branch_id,
                   department_id=body.membership.department_id, role_id=role.id, valid_to=body.membership.valid_to,
                   status="activa")
    db.add(m)
    db.flush()
    _audit(db, p, ctx, "admin.user_create", u.id, m.organization_id, body.reason,
           after={**_snapshot(u), **_m_audit(db, m)})
    db.commit()
    return TempPasswordOut(user=_u_out(db, u, orgs), temporary_password=temp, notice=TEMP_NOTICE)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: uuid.UUID, body: AdminUserUpdate, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> AdminUserOut:
    orgs = _admin_orgs(p, request, "admin.users.update")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    if not _fully_managed(db, u.id, orgs):
        _deny(p, ctx, "admin.user_update", u.id, "usuario con pertenencias en otra entidad")
        raise api_error(403, "prohibido", "Este usuario también pertenece a otra entidad que usted no administra.")
    before = _snapshot(u)
    if body.full_name:
        u.full_name = body.full_name.strip()
    if body.email:
        u.email = body.email.strip().lower()
    _audit(db, p, ctx, "admin.user_update", u.id, _first_org(db, u.id, orgs), body.reason, before, _snapshot(u))
    db.commit()
    return _u_out(db, u, orgs)


def _guard_last_admin(db: Session, p: Principal, ctx: ReqCtx, u: UserAccount, action: str,
                      membership: Membership | None = None) -> None:
    now = _now()
    targets = [membership] if membership else [m for m in _memberships(db, u.id) if _is_current(m, now)]
    for m in targets:
        if ADMIN_PERM not in {rp.permission for rp in m.role.permissions}:
            continue
        left = (_admins_left(db, m.organization_id, without_membership=m.id) if membership
                else _admins_left(db, m.organization_id, without_user=u.id))
        if left == 0:
            _deny(p, ctx, action, u.id, "dejaría la entidad sin administración", m.organization_id)
            raise api_error(422, "ultimo_administrador",
                            "La entidad se quedaría sin ninguna persona que administre usuarios. Asigne antes otra.")


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
def deactivate(user_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> AdminUserOut:
    orgs = _admin_orgs(p, request, "admin.user_deactivate")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    if u.id == p.id:
        raise api_error(422, "validacion", "No puede desactivar su propia cuenta.")
    if not _fully_managed(db, u.id, orgs):
        _deny(p, ctx, "admin.user_deactivate", u.id, "usuario con pertenencias en otra entidad")
        raise api_error(403, "prohibido", "Este usuario también pertenece a otra entidad que usted no administra.")
    if u.status != "activo":
        return _u_out(db, u, orgs)
    _guard_last_admin(db, p, ctx, u, "admin.user_deactivate")
    before = _snapshot(u)
    u.status = "inactivo"
    n = revoke_sessions(db, u.id, by=p.id, reason="usuario desactivado")
    _audit(db, p, ctx, "admin.user_deactivate", u.id, _first_org(db, u.id, orgs), body.reason, before,
           {**_snapshot(u), "sesiones_cerradas": n})
    db.commit()
    return _u_out(db, u, orgs)


@router.post("/users/{user_id}/reactivate", response_model=AdminUserOut)
def reactivate(user_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> AdminUserOut:
    orgs = _admin_orgs(p, request, "admin.user_reactivate")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    if not _fully_managed(db, u.id, orgs):
        _deny(p, ctx, "admin.user_reactivate", u.id, "usuario con pertenencias en otra entidad")
        raise api_error(403, "prohibido", "Este usuario también pertenece a otra entidad que usted no administra.")
    if u.status == "activo":
        return _u_out(db, u, orgs)
    before = _snapshot(u)
    u.status = "activo"
    _audit(db, p, ctx, "admin.user_reactivate", u.id, _first_org(db, u.id, orgs), body.reason, before, _snapshot(u))
    db.commit()
    return _u_out(db, u, orgs)


@router.post("/users/{user_id}/reset-credentials", response_model=TempPasswordOut)
def reset_credentials(user_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                      db: Session = Depends(get_db)) -> TempPasswordOut:
    """Contraseña provisional nueva + doble verificación a configurar de nuevo; cierra todas sus sesiones."""
    orgs = _admin_orgs(p, request, "admin.user_reset")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    if u.id == p.id:
        raise api_error(422, "validacion", "Para sus propias credenciales use Ajustes → Seguridad.")
    if not _fully_managed(db, u.id, orgs):
        _deny(p, ctx, "admin.user_reset", u.id, "usuario con pertenencias en otra entidad")
        raise api_error(403, "prohibido", "Este usuario también pertenece a otra entidad que usted no administra.")
    if u.status != "activo":
        raise api_error(422, "validacion", "Reactive primero al usuario.")
    before = _snapshot(u)
    temp = cred.temporary_password()
    u.password_hash = cred.hash_password(temp)
    u.password_changed_at = _now()
    u.must_change_password = True
    u.totp_secret_enc = None
    u.totp_confirmed_at = None
    u.totp_last_step = None
    n = revoke_sessions(db, u.id, by=p.id, reason="credenciales restablecidas")
    _audit(db, p, ctx, "admin.user_reset", u.id, _first_org(db, u.id, orgs), body.reason, before,
           {**_snapshot(u), "sesiones_cerradas": n})
    db.commit()
    return TempPasswordOut(user=_u_out(db, u, orgs), temporary_password=temp, notice=TEMP_NOTICE)


# ------------------------------------------------------------------ pertenencias (rol, sede, departamento)
@router.post("/users/{user_id}/memberships", response_model=AdminUserOut, status_code=201)
def add_membership(user_id: uuid.UUID, body: MembershipAddIn, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> AdminUserOut:
    orgs = _admin_orgs(p, request, "admin.membership_add")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    role = _validate_membership(db, body, orgs)
    now = _now()
    dup = [m for m in _memberships(db, u.id) if _is_current(m, now) and m.organization_id == body.organization_id
           and m.role_id == role.id and m.branch_id == body.branch_id and m.department_id == body.department_id]
    if dup:
        raise api_error(409, "conflicto", "Ya tiene esa pertenencia vigente.")
    m = Membership(user_id=u.id, organization_id=body.organization_id, branch_id=body.branch_id,
                   department_id=body.department_id, role_id=role.id, valid_to=body.valid_to, status="activa")
    db.add(m)
    db.flush()
    _audit(db, p, ctx, "admin.membership_add", u.id, m.organization_id, body.reason, None, _m_audit(db, m))
    db.commit()
    return _u_out(db, u, orgs)


@router.post("/memberships/{membership_id}/end", response_model=AdminUserOut)
def end_membership(membership_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> AdminUserOut:
    orgs = _admin_orgs(p, request, "admin.membership_end")
    ctx = req_ctx(request)
    m = db.get(Membership, membership_id)
    if m is None or m.organization_id not in orgs:
        raise api_error(404, "no_encontrado", "Pertenencia no encontrada.")
    u = db.get(UserAccount, m.user_id)
    if not _is_current(m, _now()):
        raise api_error(422, "validacion", "Esa pertenencia ya no está vigente.")
    if u.id == p.id and ADMIN_PERM in {rp.permission for rp in m.role.permissions}:
        raise api_error(422, "validacion", "No puede retirarse a sí mismo la administración.")
    _guard_last_admin(db, p, ctx, u, "admin.membership_end", membership=m)
    before = _m_audit(db, m)
    m.status = "finalizada"
    m.valid_to = _now()
    _audit(db, p, ctx, "admin.membership_end", u.id, m.organization_id, body.reason, before, _m_audit(db, m))
    db.commit()
    return _u_out(db, u, orgs)


# ------------------------------------------------------------------ sesiones
@router.post("/sessions/{session_id}/revoke", response_model=SessionOut)
def revoke_session(session_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> SessionOut:
    orgs = _admin_orgs(p, request, "admin.session_revoke")
    ctx = req_ctx(request)
    sess = db.get(UserSession, session_id)
    if sess is None:
        raise api_error(404, "no_encontrado", "Sesión no encontrada.")
    _user_visible(db, sess.user_id, orgs)
    if sess.revoked_at is None:
        sess.revoked_at = _now()
        sess.revoked_by = p.id
        sess.revoke_reason = body.reason[:200]
        _audit(db, p, ctx, "session.revoke", sess.user_id, _first_org(db, sess.user_id, orgs), body.reason,
               None, {"sesion": str(sess.id)})
        db.commit()
    return session_out(sess, p.session_id)


@router.post("/users/{user_id}/revoke-sessions")
def revoke_all(user_id: uuid.UUID, body: ReasonIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    orgs = _admin_orgs(p, request, "admin.session_revoke")
    ctx = req_ctx(request)
    u = _user_visible(db, user_id, orgs)
    n = revoke_sessions(db, u.id, by=p.id, reason=body.reason, except_id=p.session_id)
    _audit(db, p, ctx, "session.revoke", u.id, _first_org(db, u.id, orgs), body.reason, None, {"sesiones_cerradas": n})
    db.commit()
    return {"sesiones_cerradas": n}


# ------------------------------------------------------------------ copias de seguridad (AT-29)
@router.get("/backups", response_model=list[BackupRunOut])
def backups(request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not p.orgs_with("admin.backups.read"):
        ctx = req_ctx(request)
        audit.record_independent(actor_id=p.id, action="admin.backups", resource_type="backup", outcome="denied",
                                 reason="sin admin.backups.read", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Solo Dirección consulta las copias de seguridad.")
    rows = db.execute(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(50)).scalars()
    return [BackupRunOut.model_validate(r) for r in rows]
