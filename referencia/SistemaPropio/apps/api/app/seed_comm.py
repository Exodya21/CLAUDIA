"""Datos ficticios de F2.3: acceso al portal y conversaciones de ejemplo (idempotente)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .comm import core, templates
from .models import CaseFile, Consent, Contact, ContactPoint, Organization, UserAccount
from .models_comm import CommMessage, PortalAccount
from .services import textcrypt


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def _email(db: Session, c: Contact) -> str | None:
    return db.execute(select(ContactPoint.value_normalized).where(ContactPoint.contact_id == c.id,
                                                                  ContactPoint.kind == "email")).scalar()


def _msg(db: Session, t, text: str, at: datetime, *, user=None, portal=None, visibility="cliente", level="normal",
         kind="texto") -> None:
    db.add(CommMessage(organization_id=t.organization_id, thread_id=t.id, author_user_id=user.id if user else None,
                       author_portal_id=portal.id if portal else None, kind=kind, visibility=visibility, level=level,
                       body_enc=textcrypt.enc(text), created_at=at))
    t.last_message_at = max(t.last_message_at or at, at)
    if portal:
        t.last_client_message_at = at


def seed_comm(db: Session) -> None:
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None or db.execute(select(func.count()).select_from(PortalAccount)).scalar_one() > 0:
        return
    asesor = _u(db, "asesor.extranjeria.mad") or _u(db, "direccion.demo")
    now = datetime.now(UTC)
    ext = db.execute(select(CaseFile).where(CaseFile.organization_id == es.id, CaseFile.code == "EXT-2026-0001")).scalar_one_or_none()
    if ext is not None:
        # Cliente invitado que aún no ha entrado (el recorrido de pruebas entra con su correo y acepta las condiciones).
        c = db.get(Contact, ext.contact_id)
        email = _email(db, c)
        if email:
            acc = PortalAccount(organization_id=es.id, contact_id=c.id, email=email, invited_by=asesor.id,
                                invited_at=now - timedelta(days=1))
            db.add(acc)
            db.flush()
            g = core.general_thread(db, c)
            _msg(db, g, templates.WELCOME, now - timedelta(days=1), kind="sistema")
            t = core.case_thread(db, ext)
            _msg(db, t, "Buenos días. Hemos abierto su expediente de arraigo. En cuanto entre en el portal verá la lista "
                        "de documentos que nos faltan; puede enviárnoslos desde ahí mismo.",
                 now - timedelta(hours=20), user=asesor)
            _msg(db, t, "Nota: la clienta prefiere que la llamemos por la tarde.", now - timedelta(hours=19),
                 user=asesor, visibility="interna")
    lab = db.execute(select(CaseFile).where(CaseFile.organization_id == es.id, CaseFile.materia == "laboral")
                     .order_by(CaseFile.created_at)).scalars().first()
    if lab is not None:
        gestor = db.get(UserAccount, core._responsible(db, lab, (_u(db, "lider.laboral") or asesor).id))
        # Cliente que ya usa el portal: ha aceptado las condiciones y ha escrito.
        c = db.get(Contact, lab.contact_id)
        email = _email(db, c)
        if email and not db.execute(select(PortalAccount).where(PortalAccount.contact_id == c.id)).first():
            cons = Consent(contact_id=c.id, purpose="portal_comunicaciones", granted=True, source="portal_cliente",
                           recorded_by=gestor.id)
            db.add(cons)
            db.flush()
            acc = PortalAccount(organization_id=es.id, contact_id=c.id, email=email, invited_by=gestor.id,
                                invited_at=now - timedelta(days=6), status="activa", terms_accepted_at=now - timedelta(days=6),
                                consent_id=cons.id, last_login_at=now - timedelta(days=2))
            db.add(acc)
            db.flush()
            g = core.general_thread(db, c)
            _msg(db, g, templates.WELCOME, now - timedelta(days=6), kind="sistema")
            t = core.case_thread(db, lab)
            _msg(db, t, "Buenas tardes. ¿Me pueden decir si necesitan algo más para mi caso?", now - timedelta(days=2),
                 portal=acc)
            _msg(db, t, "Le escribimos en cuanto revisemos la documentación. Gracias por su paciencia.",
                 now - timedelta(days=2, hours=-1), user=gestor, level="importante")
            _msg(db, t, "De acuerdo, muchas gracias.", now - timedelta(hours=3), portal=acc)
    db.flush()
