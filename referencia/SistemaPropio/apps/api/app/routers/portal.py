"""Portal del cliente (F2.3 + M12 fase 1). Trato de usted (U-15). Solo ve sus asuntos, sin notas internas.

El cliente no ve el resultado de una resolución por el sistema: su abogado o abogada se lo comunica (regla 7).
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..comm import core
from ..config import get_settings
from ..db import get_db
from ..errors import api_error
from ..models import CaseFile, Consent
from ..models_comm import (
    CommAttachment,
    CommConfirmation,
    CommMessage,
    CommMessageVersion,
    CommThread,
    PortalAccount,
)
from ..models_immigration import ImmigCase, ImmigProcedure
from ..security import ratelimit
from ..security.portal_auth import COOKIE as PORTAL_COOKIE
from ..security.portal_auth import (
    PortalUser,
    check_code,
    get_portal_user,
    new_code,
    norm_email,
    require_terms,
    set_cookie,
    start,
)
from ..services import notify, textcrypt, vault
from .comm import MAX_FILES, _missing_requirements, store_attachments
from .common import req_ctx

router = APIRouter(prefix="/portal", tags=["portal del cliente"])

MATERIAS = {"laboral": "Laboral", "extranjeria": "Extranjería", "nacionalidad": "Nacionalidad"}
# Fase visible para el cliente: sin resultados de resoluciones (se los comunica su abogado/a).
CLIENT_STAGE = {
    "consulta": "Estudiando su caso", "documentacion": "Reuniendo la documentación",
    "preparacion": "Preparando su solicitud", "lista_presentar": "Preparando su solicitud",
    "presentado": "En trámite ante la Administración", "requerimiento": "En trámite: le escribiremos si necesitamos algo",
    "requerimiento_respondido": "En trámite ante la Administración", "tie": "En trámite: tarjeta de identidad",
    "resolucion_favorable": "Su abogado o abogada le informará", "resolucion_desfavorable": "Su abogado o abogada le informará",
    "recurso": "Su abogado o abogada le informará", "cerrado": "Cerrado",
}
DOC_STATE = {"falta": "Pendiente de enviar", "por_revisar": "Recibido, lo estamos revisando",
             "caducado": "Caducado: hay que enviar uno vigente"}
GENERIC = ("Si su correo está registrado en el despacho, recibirá un código de acceso en unos minutos. "
           "Revise también la carpeta de correo no deseado.")


def _audit(db: Session, u: PortalUser | None, action: str, request: Request, resource_type: str, rid, org,
           after: dict | None = None, outcome: str = "ok") -> None:
    ctx = req_ctx(request)
    payload = {"cuenta_portal": str(u.id)} if u else {}
    audit.record(db, actor_id=None, action=action, resource_type=resource_type, resource_id=rid, organization_id=org,
                 outcome=outcome, after={**payload, **(after or {})}, ip=ctx.ip, request_id=ctx.request_id)


# ------------------------------------------------------------------ acceso
class CodeIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)


@router.post("/auth/request-code")
def request_code(body: CodeIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    email = norm_email(body.email)
    ip = req_ctx(request).ip
    out: dict = {"message": GENERIC}
    if ratelimit.blocked_for(f"portal:{email}", ip):
        return out
    accs = list(db.execute(select(PortalAccount).where(PortalAccount.email == email,
                                                       PortalAccount.status != "bloqueada")).scalars())
    if len(accs) != 1:
        ratelimit.record_attempt(f"portal:{email}", ip, "portal_code", False)
        return out
    acc = accs[0]
    code = new_code(db, acc, ip)
    if code:
        sent = notify.enqueue(db, organization_id=acc.organization_id, purpose="codigo_acceso", to=acc.email,
                              subject="Su código de acceso al portal",
                              body=(f"Su código de acceso al portal del despacho es: {code}\n\nCaduca en "
                                    f"{get_settings().portal_code_minutes} minutos. No lo comparta con nadie: el despacho "
                                    "nunca se lo pedirá por teléfono."),
                              idem_key=f"codigo:{acc.id}:{uuid.uuid4().hex}", portal_account_id=acc.id)
        _audit(db, None, "portal.code.request", request, "portal_account", acc.id, acc.organization_id)
        db.commit()
        background.add_task(notify.dispatch_pending)
        s = get_settings()
        if s.app_env in ("development", "test") and sent is not None and sent.status == "no_configurado":
            out["dev_code"] = code  # solo pruebas: sin correo configurado no habría forma de entrar
    return out


class VerifyIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    code: str = Field(min_length=6, max_length=6)


@router.post("/auth/verify")
def verify(body: VerifyIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    email = norm_email(body.email)
    ctx = req_ctx(request)
    wait = ratelimit.blocked_for(f"portal:{email}", ctx.ip)
    if wait:
        raise api_error(429, "demasiados_intentos", f"Demasiados intentos. Espere {max(1, wait // 60)} minutos.")
    acc = db.execute(select(PortalAccount).where(PortalAccount.email == email,
                                                 PortalAccount.status != "bloqueada")).scalar_one_or_none()
    ok = bool(acc and check_code(db, acc, body.code))
    db.commit()
    ratelimit.record_attempt(f"portal:{email}", ctx.ip, "portal_code", ok)
    if not ok:
        raise api_error(401, "codigo_incorrecto", "El código no es correcto o ha caducado. Pida uno nuevo.")
    token, ttl = start(db, acc, ctx.ip, ctx.user_agent)
    _audit(db, None, "portal.login", request, "portal_account", acc.id, acc.organization_id)
    db.commit()
    set_cookie(response, token, ttl)
    return {"ok": True, "needs_terms": acc.terms_accepted_at is None}


@router.post("/auth/logout")
def logout(request: Request, response: Response, u: PortalUser = Depends(get_portal_user),
           db: Session = Depends(get_db)) -> dict:
    from ..models_comm import PortalSession

    s = db.get(PortalSession, u.session_id)
    s.revoked_at = core.now()
    _audit(db, u, "portal.logout", request, "portal_account", u.id, u.org)
    db.commit()
    response.delete_cookie(PORTAL_COOKIE, path="/")
    return {"ok": True}


TERMS = (
    "Este portal es el canal del despacho para comunicarse con usted sobre sus asuntos. Lo que escriba y los "
    "documentos que envíe se guardan en su expediente, cifrados y en servidores de la Unión Europea, y solo los ve el "
    "equipo que lleva su asunto. Los mensajes no se borran: forman parte del historial de su expediente. Los avisos "
    "que le enviemos por correo electrónico no incluyen el contenido; para leerlo debe entrar aquí. Puede pedir una "
    "copia de su historial o ejercer sus derechos de protección de datos escribiéndonos por este mismo portal."
)


@router.get("/me")
def me(u: PortalUser = Depends(get_portal_user)) -> dict:
    return {"name": u.contact.given_name, "full_name": f"{u.contact.given_name} {u.contact.family_names}",
            "email": u.account.email, "needs_terms": u.account.terms_accepted_at is None,
            "terms": TERMS if u.account.terms_accepted_at is None else None}


class TermsIn(BaseModel):
    accept: bool


@router.post("/terms")
def accept_terms(body: TermsIn, request: Request, u: PortalUser = Depends(get_portal_user),
                 db: Session = Depends(get_db)) -> dict:
    if not body.accept:
        raise api_error(422, "validacion", "Para usar el portal debe aceptar las condiciones.")
    if u.account.terms_accepted_at is None:
        # El consentimiento lo da el cliente en el portal; queda a nombre de quien le invitó (responsable del alta).
        c = Consent(contact_id=u.contact.id, purpose="portal_comunicaciones", granted=True, source="portal_cliente",
                    recorded_by=u.account.invited_by)
        db.add(c)
        db.flush()
        u.account.terms_accepted_at, u.account.consent_id, u.account.status = core.now(), c.id, "activa"
        u.account.version += 1
        _audit(db, u, "portal.terms.accept", request, "portal_account", u.id, u.org, {"consentimiento": str(c.id)})
        db.commit()
    return me(u)


# ------------------------------------------------------------------ asuntos y conversaciones
def _case_info(db: Session, cf: CaseFile | None) -> dict | None:
    if cf is None:
        return None
    info = {"code": cf.code, "materia": MATERIAS.get(cf.materia, cf.materia), "stage": None, "procedure": None}
    ic = db.get(ImmigCase, cf.id)
    if ic is not None:
        info["stage"] = CLIENT_STAGE.get(ic.stage)
        info["procedure"] = db.get(ImmigProcedure, ic.procedure_id).name
    return info


def _visible(q):
    return q.where(CommMessage.visibility == "cliente", CommMessage.hidden_at.is_(None))


def _thread_for(db: Session, u: PortalUser, thread_id: uuid.UUID, request: Request) -> tuple[CommThread, CaseFile | None]:
    t = db.get(CommThread, thread_id)
    if t is None or t.contact_id != u.contact.id or t.organization_id != u.org:
        _audit(db, u, "portal.thread.denied", request, "comm_thread", thread_id, u.org, outcome="denied")
        db.commit()
        raise api_error(404, "no_encontrado", "No encontramos esa conversación.")
    return t, (db.get(CaseFile, t.case_id) if t.case_id else None)


@router.get("/threads")
def my_threads(u: PortalUser = Depends(require_terms), db: Session = Depends(get_db)) -> dict:
    threads = [core.general_thread(db, u.contact)]
    cases = db.execute(select(CaseFile).where(CaseFile.contact_id == u.contact.id, CaseFile.organization_id == u.org)
                       .order_by(CaseFile.created_at.desc())).scalars()
    threads += [core.case_thread(db, cf) for cf in cases]
    db.commit()
    out = []
    for t in threads:
        mark = core.read_mark(db, t.id, "portal", u.id)
        msgs = list(db.execute(_visible(select(CommMessage).where(CommMessage.thread_id == t.id,
                                                                  CommMessage.author_portal_id.is_(None)))).scalars())
        unread = sum(1 for m in msgs if mark is None or m.created_at > mark)
        confirmed = set(db.execute(select(CommConfirmation.message_id).where(
            CommConfirmation.portal_account_id == u.id)).scalars())
        urgent = sum(1 for m in msgs if m.requires_confirmation and m.id not in confirmed)
        cf = db.get(CaseFile, t.case_id) if t.case_id else None
        out.append({"id": str(t.id), "kind": t.kind, "case": _case_info(db, cf), "unread": unread,
                    "urgent_pending": urgent,
                    "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
                    "missing_documents": len(_missing_requirements(db, cf))})
    return {"threads": out}


def _thread_view(db: Session, u: PortalUser, t: CommThread, cf: CaseFile | None) -> dict:
    msgs = list(db.execute(_visible(select(CommMessage).where(CommMessage.thread_id == t.id))
                           .order_by(CommMessage.created_at)).scalars())
    cache: dict = {}
    missing = [{"index": m["index"], "label": m["label"], "required": m["kind"] == "obligatorio",
                "state": DOC_STATE.get(m["state"], m["state"])} for m in _missing_requirements(db, cf)]
    return {"id": str(t.id), "kind": t.kind, "case": _case_info(db, cf),
            "messages": [core.message_out(db, m, viewer="portal", cache=cache, viewer_portal_id=u.id) for m in msgs],
            "missing_documents": missing}


@router.get("/threads/{thread_id}")
def thread(thread_id: uuid.UUID, request: Request, u: PortalUser = Depends(require_terms),
           db: Session = Depends(get_db)) -> dict:
    t, cf = _thread_for(db, u, thread_id, request)
    core.mark_read(db, t.id, "portal", u.id)
    _audit(db, u, "portal.thread.read", request, "comm_thread", t.id, u.org)
    db.commit()
    return _thread_view(db, u, t, cf)


@router.post("/threads/{thread_id}/messages", status_code=201)
async def write(thread_id: uuid.UUID, request: Request, text: str = Form(""),
                requirement_index: int | None = Form(None), files: list[UploadFile] | None = File(None),
                u: PortalUser = Depends(require_terms), db: Session = Depends(get_db)) -> dict:
    t, cf = _thread_for(db, u, thread_id, request)
    body = core.clean_text(text)
    atts = []
    for f in files or []:
        if not f.filename:
            continue
        data = await f.read(vault.MAX_BYTES + 1)
        try:
            mime = vault.sniff(data)
        except vault.VaultError as exc:
            raise api_error(422, "archivo_no_valido", f"{f.filename}: {exc.message}") from exc
        atts.append(((f.filename or "archivo")[:200], data, mime))
    if len(atts) > MAX_FILES:
        raise api_error(422, "validacion", f"Puede enviar como máximo {MAX_FILES} archivos a la vez.")
    if not body and not atts:
        raise api_error(422, "validacion", "Escriba un mensaje o adjunte un archivo.")
    label = None
    if requirement_index is not None:
        req = {m["index"]: m for m in _missing_requirements(db, cf)}.get(requirement_index)
        if req is None or not atts:
            raise api_error(422, "validacion", "Ese documento ya no está pendiente o falta el archivo.")
        label = req["label"]
        if not body:
            body = f"Le envío: {label}."
    m = CommMessage(organization_id=t.organization_id, thread_id=t.id, author_portal_id=u.id,
                    visibility="cliente", level="normal", body_enc=textcrypt.enc(body))
    db.add(m)
    db.flush()
    store_attachments(db, m, atts, requirement_index)
    t.last_message_at = t.last_client_message_at = core.now()
    if cf is not None:
        cf.last_activity_at = core.now()
    core.mark_read(db, t.id, "portal", u.id)
    _audit(db, u, "portal.message.send", request, "comm_thread", t.id, u.org,
           {"mensaje": str(m.id), "adjuntos": [a[0] for a in atts], **({"documento_pedido": label} if label else {})})
    db.commit()
    return _thread_view(db, u, t, cf)


class EditIn(BaseModel):
    text: str = Field(min_length=1, max_length=core.MAX_TEXT)


@router.patch("/messages/{message_id}")
def edit(message_id: uuid.UUID, body: EditIn, request: Request, u: PortalUser = Depends(require_terms),
         db: Session = Depends(get_db)) -> dict:
    m = db.get(CommMessage, message_id)
    if m is None or m.author_portal_id != u.id:
        raise api_error(404, "no_encontrado", "No encontramos ese mensaje.")
    t, cf = _thread_for(db, u, m.thread_id, request)
    if m.created_at <= core.now() - core.EDIT_WINDOW:
        raise api_error(409, "fuera_de_plazo", "Los mensajes solo se pueden corregir durante 15 minutos.")
    db.add(CommMessageVersion(organization_id=m.organization_id, message_id=m.id, version=m.version,
                              body_enc=m.body_enc, edited_by_portal=u.id))
    m.body_enc, m.edited_at, m.version = textcrypt.enc(core.clean_text(body.text)), core.now(), m.version + 1
    _audit(db, u, "portal.message.edit", request, "comm_thread", t.id, u.org, {"mensaje": str(m.id), "version": m.version})
    db.commit()
    return _thread_view(db, u, t, cf)


@router.post("/messages/{message_id}/confirm")
def confirm(message_id: uuid.UUID, request: Request, u: PortalUser = Depends(require_terms),
            db: Session = Depends(get_db)) -> dict:
    m = db.get(CommMessage, message_id)
    if m is None or m.hidden_at or m.visibility != "cliente":
        raise api_error(404, "no_encontrado", "No encontramos ese aviso.")
    t, cf = _thread_for(db, u, m.thread_id, request)
    if not m.requires_confirmation:
        raise api_error(409, "conflicto", "Este mensaje no necesita confirmación.")
    exists = db.execute(select(CommConfirmation.id).where(CommConfirmation.message_id == m.id,
                                                          CommConfirmation.portal_account_id == u.id)).first()
    if not exists:
        db.add(CommConfirmation(organization_id=m.organization_id, message_id=m.id, portal_account_id=u.id,
                                ip=req_ctx(request).ip))
        core.mark_read(db, t.id, "portal", u.id)
        _audit(db, u, "portal.notice.confirm", request, "comm_thread", t.id, u.org, {"mensaje": str(m.id)})
        db.commit()
    return _thread_view(db, u, t, cf)


@router.get("/attachments/{att_id}/file")
def attachment(att_id: uuid.UUID, request: Request, u: PortalUser = Depends(require_terms),
               db: Session = Depends(get_db)) -> Response:
    a = db.get(CommAttachment, att_id)
    m = db.get(CommMessage, a.message_id) if a else None
    if a is None or m is None or m.visibility != "cliente" or m.hidden_at:
        raise api_error(404, "no_encontrado", "No encontramos ese archivo.")
    t, _cf = _thread_for(db, u, m.thread_id, request)
    _audit(db, u, "portal.attachment.download", request, "comm_thread", t.id, u.org, {"adjunto": str(a.id)})
    db.commit()
    return Response(vault.load(a.file_path), media_type=a.mime,
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(a.original_name)}"})
