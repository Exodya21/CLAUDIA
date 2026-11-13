"""Directorio de clientes (M01). Requisitos: I-003, Q-1.2, D-13, AT-02, AT-04."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..models import (
    Address,
    AuditEvent,
    Branch,
    CaseFile,
    Consent,
    Contact,
    ContactPoint,
    Department,
    DuplicateReview,
    Identifier,
    UserAccount,
)
from ..schemas import (
    AuditOut,
    CaseMeta,
    ContactCreate,
    ContactFull,
    ContactMinimal,
    ContactUpdate,
    DuplicateCheckIn,
    DuplicateCheckOut,
    IdentifierIn,
    Page,
)
from ..security.auth import Principal, get_principal
from ..security.policy import (
    case_level,
    case_visibility_filter,
    contact_level,
    contacts_with_full_case,
    load_case_scope,
)
from ..validation import (
    fold,
    mask_identifier,
    mask_phone,
    normalize_doc,
    normalize_phone,
    phone_search_digits,
    validate_identifier,
)
from .common import req_ctx

router = APIRouter(prefix="/contacts", tags=["clientes"])

MIN_QUERY = 3
MAX_PAGE = 50


def _display(c: Contact) -> str:
    return f"{c.given_name} {c.family_names}"


def _branch_name(db: Session, bid: uuid.UUID | None) -> str | None:
    if not bid:
        return None
    b = db.get(Branch, bid)
    return b.name if b else None


def to_minimal(db: Session, c: Contact) -> ContactMinimal:
    return ContactMinimal(
        id=c.id, access_level="minimal", organization_id=c.organization_id, display_name=_display(c),
        primary_branch=_branch_name(db, c.primary_branch_id),
        phones_masked=[mask_phone(p.value_normalized) for p in c.points if p.kind == "phone"],
        identifiers_masked=[f"{i.kind} {mask_identifier(i.number_normalized)}" for i in c.identifiers],
        possible_duplicate=c.possible_duplicate,
    )


def to_full(db: Session, c: Contact) -> ContactFull:
    base = to_minimal(db, c).model_dump()
    base["access_level"] = "full"
    return ContactFull(
        **base, given_name=c.given_name, family_names=c.family_names, birth_date=c.birth_date,
        nationality=c.nationality, preferred_language=c.preferred_language, origin=c.origin, status=c.status,
        is_synthetic=c.is_synthetic, version=c.version, created_at=c.created_at, updated_at=c.updated_at,
        identifiers=c.identifiers, points=c.points, addresses=c.addresses, consents=c.consents,
    )


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _visible_contact_or_404(db: Session, p: Principal, contact_id: uuid.UUID, request: Request) -> tuple[Contact, str]:
    c = db.get(Contact, contact_id)
    scope = load_case_scope(db, p)
    level = contact_level(p, c, contacts_with_full_case(db, p, scope)) if c else None
    if level is None:
        ctx = req_ctx(request)
        # Se audita sin revelar al usuario si el registro existe en otra entidad.
        audit.record_independent(actor_id=p.id, action="contact.read", resource_type="contact",
                                 resource_id=contact_id, outcome="denied",
                                 organization_id=c.organization_id if c else None,
                                 reason="fuera de ámbito o inexistente", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(404, "no_encontrado", "Contacto no encontrado.")
    return c, level


def _audit_ident(i: IdentifierIn | Identifier) -> dict:
    num = i.number_normalized if isinstance(i, Identifier) else normalize_doc(i.number)
    return {"kind": i.kind, "number": mask_identifier(num), "country": i.country}


# ---------------------------------------------------------------- búsqueda
@router.get("", response_model=Page[ContactMinimal | ContactFull])
def search_contacts(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
    search_orgs = p.orgs_with("contact.search")
    if not search_orgs:
        raise api_error(403, "prohibido", "Su rol no permite consultar el directorio de clientes.")
    scope = load_case_scope(db, p)
    full_case_contacts = contacts_with_full_case(db, p, scope)

    if q:
        if len(q) < MIN_QUERY:
            raise api_error(422, "validacion", f"Escriba al menos {MIN_QUERY} caracteres para buscar.")
        conds = [Contact.search_name.like(f"%{_escape_like(fold(q))}%", escape="\\")]
        doc = normalize_doc(q)
        conds.append(Contact.id.in_(select(Identifier.contact_id).where(Identifier.number_normalized == doc)))
        digits = phone_search_digits(q)
        if len(digits) >= 6:
            conds.append(Contact.id.in_(select(ContactPoint.contact_id).where(
                ContactPoint.kind == "phone", ContactPoint.value_normalized.like(f"%{digits}", escape="\\"))))
        if "@" in q:
            conds.append(Contact.id.in_(select(ContactPoint.contact_id).where(
                ContactPoint.kind == "email", ContactPoint.value_normalized == q.lower())))
        where = and_(Contact.organization_id.in_(search_orgs), or_(*conds))
        criterio = "documento" if any(ch.isdigit() for ch in doc) and len(digits) < 6 else (
            "telefono" if len(digits) >= 6 else "nombre")
    else:
        # Sin criterio: solo se listan los contactos con acceso completo (anti-enumeración).
        all_orgs = p.orgs_with("contact.read.all")
        own_orgs = p.orgs_with("contact.read.own") - all_orgs
        parts = []
        if all_orgs:
            parts.append(Contact.organization_id.in_(all_orgs))
        if own_orgs:
            parts.append(and_(Contact.organization_id.in_(own_orgs),
                              or_(Contact.created_by == p.id, Contact.id.in_(full_case_contacts or [uuid.uuid4()]))))
        if not parts:
            raise api_error(422, "validacion", f"Escriba al menos {MIN_QUERY} caracteres para buscar.")
        where = or_(*parts)
        criterio = "listado"

    total = db.execute(select(func.count()).select_from(Contact).where(where)).scalar_one()
    rows = db.execute(
        select(Contact).where(where).order_by(Contact.family_names, Contact.given_name, Contact.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    items = []
    for c in rows:
        lvl = contact_level(p, c, full_case_contacts)
        items.append(to_full(db, c) if lvl == "full" else to_minimal(db, c))
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="contact.search", resource_type="contact",
                 after={"criterio": criterio, "resultados": total, "pagina": page},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return Page(items=items, page=page, page_size=page_size, total=total)


# ---------------------------------------------------------------- duplicados
def _identifier_matches(db: Session, org_id: uuid.UUID, idents: list[IdentifierIn]) -> list[Contact]:
    if not idents:
        return []
    nums = [validate_identifier(i.kind, i.number, i.country) for i in idents]
    ids = select(Identifier.contact_id).where(Identifier.organization_id == org_id,
                                              Identifier.number_normalized.in_(nums))
    return list(db.execute(select(Contact).where(Contact.id.in_(ids))).scalars())


@router.post("/duplicate-check", response_model=DuplicateCheckOut)
def duplicate_check(body: DuplicateCheckIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not p.has(body.organization_id, "contact.create"):
        raise api_error(403, "prohibido", "Su rol no permite dar de alta contactos en esta entidad.")
    matches = _identifier_matches(db, body.organization_id, body.identifiers)
    visible = [m for m in matches if p.has(m.organization_id, "contact.search")]
    phones = [normalize_phone(x) for x in body.phones]
    shared = 0
    if phones:
        shared = db.execute(
            select(func.count(func.distinct(ContactPoint.contact_id)))
            .join(Contact, Contact.id == ContactPoint.contact_id)
            .where(Contact.organization_id == body.organization_id, ContactPoint.kind == "phone",
                   ContactPoint.value_normalized.in_(phones))
        ).scalar_one()
    return DuplicateCheckOut(identifier_matches=[to_minimal(db, m) for m in visible],
                             hidden_identifier_matches=len(matches) - len(visible),
                             shared_phone_contacts=shared)


# ---------------------------------------------------------------- alta
@router.post("", response_model=ContactFull, status_code=201)
def create_contact(body: ContactCreate, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    org = body.organization_id
    if org not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(org, "contact.create"):
        audit.record_independent(actor_id=p.id, action="contact.create", resource_type="contact",
                                 organization_id=org, outcome="denied", reason="sin permiso contact.create",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Su rol no permite dar de alta contactos.")
    if body.primary_branch_id:
        br = db.get(Branch, body.primary_branch_id)
        if not br or br.organization_id != org:
            raise api_error(422, "validacion", "La sede no pertenece a la entidad seleccionada.",
                            [{"field": "primary_branch_id", "message": "Sede no válida"}])

    norm_ids = [(i, validate_identifier(i.kind, i.number, i.country)) for i in body.identifiers]
    if len({n for _, n in norm_ids}) != len(norm_ids):
        raise api_error(422, "validacion", "Hay documentos repetidos en el formulario.")
    phones = [(ph, normalize_phone(ph.number)) for ph in body.phones]

    matches = _identifier_matches(db, org, body.identifiers)
    if matches and not body.confirm_possible_duplicate:
        raise api_error(409, "posible_duplicado",
                        "Ya existe un contacto con el mismo documento. Revise antes de continuar.",
                        {"candidates": [to_minimal(db, m).model_dump(mode="json") for m in matches]})
    if matches and len((body.duplicate_justification or "").strip()) < 10:
        raise api_error(422, "validacion", "Indique un motivo (mín. 10 caracteres) para crear un posible duplicado.",
                        [{"field": "duplicate_justification", "message": "Motivo obligatorio"}])

    c = Contact(
        organization_id=org, primary_branch_id=body.primary_branch_id, given_name=body.given_name,
        family_names=body.family_names, search_name=fold(f"{body.given_name} {body.family_names}"),
        birth_date=body.birth_date, nationality=body.nationality, preferred_language=body.preferred_language,
        origin=body.origin, created_by=p.id, possible_duplicate=bool(matches),
    )
    db.add(c)
    db.flush()
    for i, n in norm_ids:
        db.add(Identifier(contact_id=c.id, organization_id=org, kind=i.kind, number_normalized=n,
                          country=i.country, valid_until=i.valid_until))
    for idx, (ph, e164) in enumerate(phones):
        db.add(ContactPoint(contact_id=c.id, kind="phone", value_normalized=e164, label=ph.label,
                            is_primary=ph.is_primary or idx == 0))
    for idx, em in enumerate(body.emails):
        db.add(ContactPoint(contact_id=c.id, kind="email", value_normalized=str(em.email).lower(),
                            is_primary=em.is_primary or idx == 0))
    for a in body.addresses:
        db.add(Address(contact_id=c.id, **a.model_dump()))
    for cs in body.consents:
        db.add(Consent(contact_id=c.id, purpose=cs.purpose, granted=cs.granted, source=cs.source,
                       recorded_by=p.id))
    for m in matches:
        m.possible_duplicate = True
        db.add(DuplicateReview(organization_id=org, contact_id=c.id, candidate_contact_id=m.id,
                               reason="mismo_documento", justification=body.duplicate_justification or "",
                               created_by=p.id))
    after = {
        "nombre": f"{c.given_name} {c.family_names}", "sede": str(c.primary_branch_id) if c.primary_branch_id else None,
        "documentos": [_audit_ident(i) for i, _ in norm_ids], "telefonos": [e for _, e in phones],
        "emails": [str(e.email).lower() for e in body.emails], "consentimientos": [cs.model_dump() for cs in body.consents],
    }
    audit.record(db, actor_id=p.id, action="contact.create", resource_type="contact", resource_id=c.id,
                 organization_id=org, after=after, ip=ctx.ip, request_id=ctx.request_id)
    if matches:
        audit.record(db, actor_id=p.id, action="contact.duplicate_flagged", resource_type="contact",
                     resource_id=c.id, organization_id=org, reason=body.duplicate_justification,
                     after={"candidatos": [str(m.id) for m in matches]}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    db.refresh(c)
    return to_full(db, c)


# ---------------------------------------------------------------- detalle
@router.get("/{contact_id}", response_model=ContactFull | ContactMinimal)
def get_contact(contact_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)):
    c, level = _visible_contact_or_404(db, p, contact_id, request)
    if level == "minimal":
        return to_minimal(db, c)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="contact.read", resource_type="contact", resource_id=c.id,
                 organization_id=c.organization_id, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return to_full(db, c)


@router.patch("/{contact_id}", response_model=ContactFull)
def update_contact(contact_id: uuid.UUID, body: ContactUpdate, request: Request,
                   p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ctx = req_ctx(request)
    c, level = _visible_contact_or_404(db, p, contact_id, request)
    org = c.organization_id
    needs_ident = bool(body.add_identifiers)
    if level != "full" or not p.has(org, "contact.update") or (needs_ident and not p.has(org, "contact.identifier.manage")):
        audit.record_independent(actor_id=p.id, action="contact.update", resource_type="contact", resource_id=c.id,
                                 organization_id=org, outcome="denied", reason="permiso insuficiente",
                                 ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(403, "prohibido", "Su rol no permite modificar estos datos del contacto.")
    # Bloqueo de fila + control de versión para no pisar cambios concurrentes.
    db.execute(select(Contact).where(Contact.id == c.id).with_for_update())
    db.refresh(c)
    if c.version != body.version:
        raise api_error(409, "conflicto_version", "El contacto ha cambiado desde que lo abrió. Recargue la ficha.")

    before: dict = {}
    after: dict = {}
    for f in ("given_name", "family_names", "birth_date", "nationality", "preferred_language"):
        val = getattr(body, f)
        if val is not None and val != getattr(c, f):
            before[f], after[f] = getattr(c, f), val
            setattr(c, f, val)
    if "given_name" in after or "family_names" in after:
        c.search_name = fold(f"{c.given_name} {c.family_names}")
    for ph in body.add_phones:
        e164 = normalize_phone(ph.number)
        db.add(ContactPoint(contact_id=c.id, kind="phone", value_normalized=e164, label=ph.label, is_primary=False))
        after.setdefault("telefonos_añadidos", []).append(e164)
    for em in body.add_emails:
        db.add(ContactPoint(contact_id=c.id, kind="email", value_normalized=str(em.email).lower(), is_primary=False))
        after.setdefault("emails_añadidos", []).append(str(em.email).lower())
    for i in body.add_identifiers:
        n = validate_identifier(i.kind, i.number, i.country)
        db.add(Identifier(contact_id=c.id, organization_id=org, kind=i.kind, number_normalized=n,
                          country=i.country, valid_until=i.valid_until))
        after.setdefault("documentos_añadidos", []).append(_audit_ident(i))
    if not after:
        raise api_error(422, "validacion", "No hay cambios que guardar.")
    c.version += 1
    audit.record(db, actor_id=p.id, action="contact.update", resource_type="contact", resource_id=c.id,
                 organization_id=org, reason=body.reason, before={k: str(v) for k, v in before.items()} or None,
                 after={k: (v if isinstance(v, list) else str(v)) for k, v in after.items()},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    db.refresh(c)
    return to_full(db, c)


# ---------------------------------------------------------------- expedientes del contacto
def case_meta(db: Session, cf: CaseFile, level: str, contact_name: str | None) -> CaseMeta:
    full = level == "full"
    inactive = (datetime.now(UTC) - cf.last_activity_at).days if full and cf.last_activity_at else None
    return CaseMeta(
        id=cf.id, organization_id=cf.organization_id, access_level=level, code=cf.code, materia=cf.materia, status=cf.status,
        branch=db.get(Branch, cf.branch_id).name, department=db.get(Department, cf.department_id).name,
        contact_id=cf.contact_id, contact_name=contact_name, created_at=cf.created_at,
        last_activity_at=cf.last_activity_at if full else None, inactive_days=inactive,
    )


@router.get("/{contact_id}/cases", response_model=list[CaseMeta])
def contact_cases(contact_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)):
    c, level = _visible_contact_or_404(db, p, contact_id, request)
    scope = load_case_scope(db, p)
    rows = db.execute(
        select(CaseFile).where(CaseFile.contact_id == c.id, case_visibility_filter(p, scope))
        .order_by(CaseFile.created_at.desc())
    ).scalars()
    name = _display(c)
    return [case_meta(db, cf, case_level(p, cf, scope), name) for cf in rows]


@router.get("/{contact_id}/history", response_model=list[AuditOut])
def contact_history(contact_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)):
    c, _ = _visible_contact_or_404(db, p, contact_id, request)
    if not p.has(c.organization_id, "audit.read"):
        raise api_error(403, "prohibido", "El historial de auditoría solo está disponible para perfiles autorizados.")
    rows = db.execute(
        select(AuditEvent, UserAccount.username).outerjoin(UserAccount, UserAccount.id == AuditEvent.actor_user_id)
        .where(AuditEvent.resource_type == "contact", AuditEvent.resource_id == str(c.id))
        .order_by(AuditEvent.id.desc()).limit(200)
    ).all()
    out = []
    for ev, uname in rows:
        o = AuditOut.model_validate(ev)
        o.actor_username = uname
        out.append(o)
    return out
