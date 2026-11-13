"""Comunicaciones con el cliente — lado del equipo (F2.3 + M12 fase 1; T-31: portal propio, sin WhatsApp).

Permisos: `comm.*` (catálogo) y SIEMPRE el acceso completo al expediente (o a la ficha del contacto para el
hilo general) mediante el motor de política. Entidad ajena → 404; misma entidad sin acceso → 403 (auditados).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..comm import core, templates
from ..config import get_settings
from ..db import get_db
from ..errors import api_error
from ..immigration.catalog import DOC_TYPES
from ..models import CaseFile, Contact
from ..models_agents import AgentProposal
from ..models_comm import (
    CommAttachment,
    CommConfirmation,
    CommMessage,
    CommMessageVersion,
    CommOutbox,
    CommThread,
    PortalAccount,
)
from ..models_immigration import ImmigCase, ImmigDocument, ImmigProcedure
from ..models_work import Task
from ..security.auth import Principal, get_principal
from ..security.policy import (
    case_level,
    case_visibility_filter,
    contact_level,
    contacts_with_full_case,
    load_case_scope,
)
from ..security.portal_auth import norm_email, revoke_all
from ..services import notify, pdfwrite, textcrypt, vault
from .common import req_ctx

router = APIRouter(prefix="/comm", tags=["comunicaciones"])
MAX_FILES = 10


def _deny(p: Principal, request: Request, action: str, rid, org, reason: str) -> None:
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action=action, resource_type="comm_thread", resource_id=rid,
                             organization_id=org, outcome="denied", reason=reason, ip=ctx.ip, request_id=ctx.request_id)


def _not_found() -> Exception:
    return api_error(404, "no_encontrado", "Conversación no encontrada.")


# ------------------------------------------------------------------ acceso
def _thread_access(db: Session, p: Principal, t: CommThread, request: Request, action: str, perm: str) -> CaseFile | None:
    org = t.organization_id
    if org not in p.org_ids():
        _deny(p, request, action, t.id, None, "entidad ajena")
        raise _not_found()
    if not p.has(org, "comm.read") or not p.has(org, perm):
        _deny(p, request, action, t.id, org, f"sin permiso {perm}")
        raise api_error(403, "sin_permiso", "No tiene permiso para esta acción en las conversaciones.")
    scope = load_case_scope(db, p)
    if t.case_id:
        cf = db.get(CaseFile, t.case_id)
        if case_level(p, cf, scope) != "full":
            _deny(p, request, action, t.id, org, "sin acceso completo al expediente")
            raise api_error(403, "sin_permiso", "No tiene acceso a este expediente.")
        return cf
    c = db.get(Contact, t.contact_id)
    if contact_level(p, c, contacts_with_full_case(db, p, scope)) != "full":
        _deny(p, request, action, t.id, org, "sin acceso completo al contacto")
        raise api_error(403, "sin_permiso", "No tiene acceso a la ficha de este cliente.")
    return None


def _thread(db: Session, p: Principal, thread_id: uuid.UUID, request: Request, action: str,
            perm: str = "comm.read") -> tuple[CommThread, CaseFile | None]:
    t = db.get(CommThread, thread_id)
    if t is None:
        raise _not_found()
    return t, _thread_access(db, p, t, request, action, perm)


def _case_for_thread(db: Session, p: Principal, case_id: uuid.UUID, request: Request) -> CommThread:
    cf = db.get(CaseFile, case_id)
    if cf is None or cf.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Expediente no encontrado.")
    t = core.case_thread(db, cf)
    _thread_access(db, p, t, request, "comm.thread.open", "comm.read")
    return t


# ------------------------------------------------------------------ vistas
def _missing_requirements(db: Session, cf: CaseFile | None) -> list[dict]:
    """Documentos de la lista del trámite que faltan (solo extranjería; los demás módulos aún no tienen lista)."""
    if cf is None:
        return []
    ic = db.get(ImmigCase, cf.id)
    if ic is None:
        return []
    from .immigration import _checklist

    proc = db.get(ImmigProcedure, ic.procedure_id)
    docs = list(db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id,
                                                      ImmigDocument.status != "retirado")).scalars())
    return [{"index": c["index"], "label": c["label"], "kind": c["kind"], "state": c["state"]}
            for c in _checklist(proc, docs, core.today()) if c["state"] != "cumplido"]


def _portal_info(db: Session, contact_id: uuid.UUID) -> dict:
    acc = core.portal_account_for(db, contact_id)
    if acc is None:
        return {"status": "sin_acceso"}
    return {"status": acc.status, "email": acc.email, "invited_at": acc.invited_at.isoformat(),
            "terms_accepted_at": acc.terms_accepted_at.isoformat() if acc.terms_accepted_at else None,
            "last_login_at": acc.last_login_at.isoformat() if acc.last_login_at else None,
            "blocked_reason": acc.blocked_reason}


def _thread_out(db: Session, p: Principal, t: CommThread, cf: CaseFile | None, q: str | None = None) -> dict:
    org = t.organization_id
    c = db.get(Contact, t.contact_id)
    client_read = core.client_read_at(db, t)
    cache: dict = {}
    msgs = list(db.execute(select(CommMessage).where(CommMessage.thread_id == t.id)
                           .order_by(CommMessage.created_at)).scalars())
    out_msgs = [core.message_out(db, m, viewer="staff", client_read=client_read, cache=cache) for m in msgs]
    if q:
        needle = q.strip().lower()
        out_msgs = [m for m in out_msgs if needle in m["text"].lower()
                    or any(needle in a["name"].lower() for a in m["attachments"])]
    tasks = []
    if cf is not None:
        for tk in db.execute(select(Task).where(Task.case_id == cf.id, Task.status != "anulada",
                                                Task.kind.in_(("conciliacion", "senalamiento", "plazo")))
                             .order_by(Task.due_at)).scalars():
            tasks.append({"id": str(tk.id), "title": tk.title, "kind": tk.kind,
                          "start_at": tk.start_at.isoformat() if tk.start_at else None,
                          "legal_deadline": tk.legal_deadline.isoformat() if tk.legal_deadline else None,
                          "legal_status": tk.legal_status})
    return {
        "id": str(t.id), "kind": t.kind, "status": t.status,
        "case": ({"id": str(cf.id), "code": cf.code, "title": cf.title, "materia": cf.materia} if cf else None),
        "contact": {"id": str(c.id), "name": f"{c.given_name} {c.family_names}"},
        "portal": _portal_info(db, c.id),
        "messages": out_msgs, "search": q or None,
        "missing_documents": _missing_requirements(db, cf),
        "templates": templates.catalog(), "tasks": tasks,
        "can": {
            "send": p.has(org, "comm.send"), "note": p.has(org, "comm.note"),
            "important": p.has(org, "comm.notice.important"), "urgent": p.has(org, "comm.notice.urgent"),
            "invite": p.has(org, "comm.portal.invite"), "export": p.has(org, "comm.export"),
            "incorporate": bool(cf is not None and db.get(ImmigCase, cf.id) is not None
                                and p.has(org, "immig.document.upload")),
        },
    }


def _open(db: Session, p: Principal, t: CommThread, cf: CaseFile | None, request: Request, q: str | None) -> dict:
    core.mark_read(db, t.id, "user", p.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.thread.read", resource_type="comm_thread", resource_id=t.id,
                 organization_id=t.organization_id, ip=ctx.ip, request_id=ctx.request_id,
                 after={"expediente": cf.code if cf else None, **({"busqueda": True} if q else {})})
    out = _thread_out(db, p, t, cf, q)
    db.commit()
    return out


@router.get("/inbox")
def inbox(filter: str = "todos", p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Bandeja del equipo: conversaciones que puede ver, con lo pendiente de leer y los urgentes sin confirmar."""
    orgs = p.orgs_with("comm.read")
    if not orgs:
        raise api_error(403, "sin_permiso", "No tiene acceso a las conversaciones con clientes.")
    core.sweep_urgent(db, orgs)
    db.commit()
    scope = load_case_scope(db, p)
    case_ids = select(CaseFile.id).where(case_visibility_filter(p, scope, full_only=True), CaseFile.organization_id.in_(orgs))
    full_contacts = contacts_with_full_case(db, p, scope)
    general_ok = [CommThread.contact_id.in_(full_contacts or {uuid.uuid4()})]
    for org in orgs:
        if p.has(org, "contact.read.all"):
            general_ok.append(CommThread.organization_id == org)
        elif p.has(org, "contact.read.own"):
            general_ok.append(and_(CommThread.organization_id == org,
                                   CommThread.contact_id.in_(select(Contact.id).where(Contact.created_by == p.id))))
    q = select(CommThread).where(CommThread.organization_id.in_(orgs), CommThread.last_message_at.is_not(None),
                                 or_(CommThread.case_id.in_(case_ids), and_(CommThread.kind == "general", or_(*general_ok))))
    threads = list(db.execute(q.order_by(CommThread.last_message_at.desc()).limit(300)).scalars())
    unread = core.unread_for_user(db, [t.id for t in threads], p.id)
    ids = [t.id for t in threads] or [uuid.uuid4()]
    pending_urgent = dict(db.execute(select(CommMessage.thread_id, func.count()).where(
        CommMessage.thread_id.in_(ids), CommMessage.requires_confirmation.is_(True), CommMessage.hidden_at.is_(None),
        ~select(CommConfirmation.id).where(CommConfirmation.message_id == CommMessage.id).exists())
        .group_by(CommMessage.thread_id)).all())
    items = []
    for t in threads:
        cf = db.get(CaseFile, t.case_id) if t.case_id else None
        c = db.get(Contact, t.contact_id)
        last = db.execute(select(CommMessage).where(CommMessage.thread_id == t.id).order_by(CommMessage.created_at.desc())
                          .limit(1)).scalar_one()
        item = {"id": str(t.id), "kind": t.kind, "case_code": cf.code if cf else None, "case_title": cf.title if cf else None,
                "contact": f"{c.given_name} {c.family_names}", "last_message_at": t.last_message_at.isoformat(),
                "last_from": "cliente" if last.author_portal_id else ("nota" if last.visibility == "interna" else "equipo"),
                "unread": unread.get(t.id, 0), "urgent_unconfirmed": pending_urgent.get(t.id, 0)}
        items.append(item)
    if filter == "sin_leer":
        items = [i for i in items if i["unread"]]
    elif filter == "urgentes":
        items = [i for i in items if i["urgent_unconfirmed"]]
    return {"threads": items, "totals": {"unread": sum(i["unread"] for i in items),
                                         "urgent_unconfirmed": sum(i["urgent_unconfirmed"] for i in items)}}


@router.get("/cases/{case_id}/thread")
def case_thread(case_id: uuid.UUID, request: Request, q: str | None = None, p: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    t = _case_for_thread(db, p, case_id, request)
    return _open(db, p, t, db.get(CaseFile, case_id), request, q)


@router.get("/contacts/{contact_id}/thread")
def contact_thread(contact_id: uuid.UUID, request: Request, q: str | None = None, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    c = db.get(Contact, contact_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Contacto no encontrado.")
    t = core.general_thread(db, c)
    _thread_access(db, p, t, request, "comm.thread.open", "comm.read")
    return _open(db, p, t, None, request, q)


@router.get("/threads/{thread_id}")
def get_thread(thread_id: uuid.UUID, request: Request, q: str | None = None, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    t, cf = _thread(db, p, thread_id, request, "comm.thread.read")
    return _open(db, p, t, cf, request, q)


# ------------------------------------------------------------------ escribir
async def _read_files(files: list[UploadFile] | None) -> list[tuple[str, bytes, str]]:
    out = []
    for f in files or []:
        if not f.filename:
            continue
        data = await f.read(vault.MAX_BYTES + 1)
        try:
            mime = vault.sniff(data)
        except vault.VaultError as exc:
            raise api_error(422, "archivo_no_valido", f"{f.filename}: {exc.message}") from exc
        out.append(((f.filename or "archivo")[:200], data, mime))
    if len(out) > MAX_FILES:
        raise api_error(422, "validacion", f"Máximo {MAX_FILES} archivos por mensaje.")
    return out


def store_attachments(db: Session, m: CommMessage, files: list[tuple[str, bytes, str]], requirement_index: int | None) -> None:
    for name, data, mime in files:
        path, sha = vault.store(data)
        db.add(CommAttachment(organization_id=m.organization_id, message_id=m.id, original_name=name, mime=mime,
                              size_bytes=len(data), sha256=sha, file_path=path, requirement_index=requirement_index))


@router.post("/threads/{thread_id}/messages", status_code=201)
async def send_message(thread_id: uuid.UUID, request: Request, background: BackgroundTasks,
                       text: str = Form(""), visibility: str = Form("cliente"), level: str = Form("normal"),
                       template: str | None = Form(None), task_id: uuid.UUID | None = Form(None),
                       reply_to: uuid.UUID | None = Form(None), files: list[UploadFile] | None = File(None),
                       p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    if visibility not in ("cliente", "interna") or level not in ("normal", "importante", "urgente"):
        raise api_error(422, "validacion", "Visibilidad o nivel no válidos.")
    perm = "comm.note" if visibility == "interna" else "comm.send"
    t, cf = _thread(db, p, thread_id, request, "comm.message.send", perm)
    org = t.organization_id
    body = core.clean_text(text)
    task = None
    if template:
        if visibility == "interna":
            raise api_error(422, "validacion", "Las plantillas son para mensajes al cliente.")
        if task_id:
            task = db.get(Task, task_id)
            if task is None or cf is None or task.case_id != cf.id:
                raise api_error(422, "validacion", "La tarea no es de este expediente.")
        try:
            body, level = templates.render(template, case_code=cf.code if cf else "", task=task,
                                           missing=[m["label"] for m in _missing_requirements(db, cf)])
        except templates.TemplateError as exc:
            raise api_error(409, "plantilla", exc.message) from exc
    if visibility == "interna" and level != "normal":
        raise api_error(422, "validacion", "Una nota interna no es un aviso al cliente.")
    if level == "importante" and not p.has(org, "comm.notice.important"):
        _deny(p, request, "comm.notice.important", t.id, org, "sin permiso")
        raise api_error(403, "sin_permiso", "No tiene permiso para enviar avisos importantes.")
    if level == "urgente" and not p.has(org, "comm.notice.urgent"):
        _deny(p, request, "comm.notice.urgent", t.id, org, "sin permiso")
        raise api_error(403, "sin_permiso", "No tiene permiso para enviar avisos urgentes.")
    if level == "urgente" and not template:
        raise api_error(422, "validacion", "Los avisos urgentes se envían con una plantilla: la fecha sale de la tarea del expediente.")
    attachments = await _read_files(files)
    if not body and not attachments:
        raise api_error(422, "validacion", "Escriba un mensaje o adjunte un archivo.")
    if reply_to:
        r = db.get(CommMessage, reply_to)
        if r is None or r.thread_id != t.id:
            raise api_error(422, "validacion", "El mensaje citado no es de esta conversación.")
    m = CommMessage(organization_id=org, thread_id=t.id, author_user_id=p.id, visibility=visibility, level=level,
                    body_enc=textcrypt.enc(body), reply_to_id=reply_to, template=template,
                    task_id=task.id if task else None, requires_confirmation=level == "urgente")
    db.add(m)
    db.flush()
    store_attachments(db, m, attachments, None)
    t.last_message_at = core.now()
    if cf is not None:
        cf.last_activity_at = core.now()
    core.notify_client(db, t, m, cf.code if cf else None)
    core.mark_read(db, t.id, "user", p.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.message.send", resource_type="comm_thread", resource_id=t.id,
                 organization_id=org, ip=ctx.ip, request_id=ctx.request_id,
                 after={"mensaje": str(m.id), "visibilidad": visibility, "nivel": level, "plantilla": template,
                        "adjuntos": [a[0] for a in attachments]})
    db.commit()
    background.add_task(notify.dispatch_pending)
    return _thread_out(db, p, t, cf)


class EditIn(BaseModel):
    text: str = Field(min_length=1, max_length=core.MAX_TEXT)


@router.patch("/messages/{message_id}")
def edit_message(message_id: uuid.UUID, body: EditIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    m = db.get(CommMessage, message_id)
    if m is None:
        raise _not_found()
    t, cf = _thread(db, p, m.thread_id, request, "comm.message.edit", "comm.read")
    if m.author_user_id != p.id:
        raise api_error(403, "sin_permiso", "Solo quien lo escribió puede corregir un mensaje.")
    if m.created_at <= core.now() - core.EDIT_WINDOW:
        raise api_error(409, "fuera_de_plazo", "Los mensajes solo se pueden corregir durante 15 minutos.")
    if m.template:
        raise api_error(409, "plantilla", "Un aviso hecho con plantilla no se corrige: envíe otro y oculte este.")
    db.add(CommMessageVersion(organization_id=m.organization_id, message_id=m.id, version=m.version,
                              body_enc=m.body_enc, edited_by_user=p.id))
    m.body_enc, m.edited_at, m.version = textcrypt.enc(core.clean_text(body.text)), core.now(), m.version + 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.message.edit", resource_type="comm_thread", resource_id=t.id,
                 organization_id=t.organization_id, after={"mensaje": str(m.id), "version": m.version},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _thread_out(db, p, t, cf)


@router.get("/messages/{message_id}/versions")
def message_versions(message_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                     db: Session = Depends(get_db)) -> dict:
    m = db.get(CommMessage, message_id)
    if m is None:
        raise _not_found()
    _thread(db, p, m.thread_id, request, "comm.message.versions", "comm.read")
    rows = db.execute(select(CommMessageVersion).where(CommMessageVersion.message_id == m.id)
                      .order_by(CommMessageVersion.version)).scalars()
    return {"versions": [{"version": v.version, "text": textcrypt.dec(v.body_enc), "replaced_at": v.edited_at.isoformat()}
                         for v in rows]}


class HideIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/messages/{message_id}/hide")
def hide_message(message_id: uuid.UUID, body: HideIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    """Ocultar al cliente (nunca borrar): el mensaje sigue en el historial del despacho con el motivo."""
    m = db.get(CommMessage, message_id)
    if m is None:
        raise _not_found()
    t, cf = _thread(db, p, m.thread_id, request, "comm.message.hide", "comm.send")
    if m.hidden_at:
        raise api_error(409, "conflicto", "El mensaje ya está oculto.")
    m.hidden_at, m.hidden_by, m.hidden_reason = core.now(), p.id, body.reason.strip()
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.message.hide", resource_type="comm_thread", resource_id=t.id,
                 organization_id=t.organization_id, reason=body.reason, after={"mensaje": str(m.id)},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _thread_out(db, p, t, cf)


# ------------------------------------------------------------------ adjuntos
def _attachment(db: Session, p: Principal, att_id: uuid.UUID, request: Request, action: str, perm: str = "comm.read"):
    a = db.get(CommAttachment, att_id)
    if a is None:
        raise api_error(404, "no_encontrado", "Archivo no encontrado.")
    m = db.get(CommMessage, a.message_id)
    t, cf = _thread(db, p, m.thread_id, request, action, perm)
    return a, m, t, cf


@router.get("/attachments/{att_id}/file")
def attachment_file(att_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> Response:
    a, _m, t, _cf = _attachment(db, p, att_id, request, "comm.attachment.download")
    data = vault.load(a.file_path)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.attachment.download", resource_type="comm_thread", resource_id=t.id,
                 organization_id=t.organization_id, after={"adjunto": str(a.id), "archivo": a.original_name},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return Response(data, media_type=a.mime, headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(a.original_name)}"})


@router.post("/attachments/{att_id}/incorporate")
def incorporate(att_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Pasa un archivo del chat a los documentos del expediente de extranjería (con su lectura automática)."""
    a, _m, t, cf = _attachment(db, p, att_id, request, "comm.attachment.incorporate")
    if cf is None or db.get(ImmigCase, cf.id) is None:
        raise api_error(409, "no_disponible", "Incorporar archivos solo está disponible aún en expedientes de extranjería.")
    if not p.has(t.organization_id, "immig.document.upload"):
        _deny(p, request, "comm.attachment.incorporate", t.id, t.organization_id, "sin immig.document.upload")
        raise api_error(403, "sin_permiso", "No tiene permiso para subir documentos al expediente.")
    if a.incorporated_doc_id:
        raise api_error(409, "conflicto", "Este archivo ya está en el expediente.")
    from .immigration import ingest_document

    d, err, _r = ingest_document(db, cf, vault.load(a.file_path), a.mime, a.original_name, p.id, req_ctx(request),
                                 source=f"portal: adjunto {a.id}")
    if err:
        raise api_error(409, "conflicto", err)
    a.incorporated_doc_id, a.incorporated_by, a.incorporated_at = d.id, p.id, core.now()
    db.commit()
    return {"document_id": str(d.id), "suggested_type": d.suggested_type,
            "suggested_label": DOC_TYPES.get(d.suggested_type or "", None), **_thread_out(db, p, t, cf)}


# ------------------------------------------------------------------ exportación con huella
@router.get("/threads/{thread_id}/export.pdf")
def export_pdf(thread_id: uuid.UUID, request: Request, scope: str = "cliente", p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> Response:
    """PDF de la conversación con fecha y huella SHA-256 del contenido. `cliente`: lo que ve el cliente;
    `completo`: también notas internas, mensajes ocultos y versiones (uso interno)."""
    if scope not in ("cliente", "completo"):
        raise api_error(422, "validacion", "Alcance no válido.")
    t, cf = _thread(db, p, thread_id, request, "comm.export", "comm.export")
    c = db.get(Contact, t.contact_id)
    msgs = list(db.execute(select(CommMessage).where(CommMessage.thread_id == t.id).order_by(CommMessage.created_at)).scalars())
    if scope == "cliente":
        msgs = [m for m in msgs if m.visibility == "cliente" and m.hidden_at is None]
    cache: dict = {}
    rows = [core.message_out(db, m, viewer="staff", client_read=core.client_read_at(db, t), cache=cache) for m in msgs]
    canonical = json.dumps([{k: r[k] for k in ("id", "created_at", "author", "visibility", "level", "text", "version",
                                               "confirmed_at", "hidden")} | {"attachments": [x["name"] for x in r["attachments"]]}
                            for r in rows], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    made = datetime.now(UTC).astimezone(templates.MADRID)
    title = f"Conversación {cf.code if cf else 'general'} · {c.given_name} {c.family_names}"
    lines: list[tuple[str, str]] = [("h", title),
                                    ("s", f"Exportado el {made:%d/%m/%Y %H:%M} (hora de Madrid) por {p.user.full_name}. "
                                          f"Alcance: {'lo que ve el cliente' if scope == 'cliente' else 'completo, uso interno'}."),
                                    ("s", f"Huella SHA-256 del contenido: {digest}"), ("n", "")]
    for r in rows:
        when = datetime.fromisoformat(r["created_at"]).astimezone(templates.MADRID)
        tags = []
        if r["visibility"] == "interna":
            tags.append("NOTA INTERNA")
        if r["level"] != "normal":
            tags.append(r["level"].upper())
        if r.get("hidden"):
            tags.append("OCULTO AL CLIENTE")
        if r["version"] > 1:
            tags.append(f"editado (versión {r['version']})")
        if r["confirmed_at"]:
            tags.append(f"confirmado {datetime.fromisoformat(r['confirmed_at']).astimezone(templates.MADRID):%d/%m/%Y %H:%M}")
        lines.append(("b", f"{when:%d/%m/%Y %H:%M} · {r['author']['name']}" + (f" · {' · '.join(tags)}" if tags else "")))
        for para in (r["text"] or "").split("\n"):
            lines.append(("n", para))
        for x in r["attachments"]:
            lines.append(("s", f"Adjunto: {x['name']}"))
        lines.append(("n", ""))
    pdf = pdfwrite.text_pdf(lines, footer=f"SHA-256 {digest[:16]}…")
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.export", resource_type="comm_thread", resource_id=t.id,
                 organization_id=t.organization_id, after={"alcance": scope, "sha256": digest, "mensajes": len(rows)},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    name = f"conversacion_{cf.code if cf else 'general'}_{made:%Y%m%d}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Content-SHA256": digest})


# ------------------------------------------------------------------ acceso del cliente al portal
def _contact_for_portal(db: Session, p: Principal, contact_id: uuid.UUID, request: Request, perm: str) -> Contact:
    c = db.get(Contact, contact_id)
    if c is None or c.organization_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Contacto no encontrado.")
    level = contact_level(p, c, contacts_with_full_case(db, p, load_case_scope(db, p)))
    if level != "full" or not p.has(c.organization_id, perm):
        _deny(p, request, f"{perm}", None, c.organization_id, "sin permiso o sin acceso a la ficha")
        raise api_error(403, "sin_permiso", "No tiene permiso para gestionar el acceso al portal de este cliente.")
    return c


@router.get("/contacts/{contact_id}/portal")
def portal_status(contact_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    c = _contact_for_portal(db, p, contact_id, request, "comm.read")
    emails = [cp.value_normalized for cp in c.points if cp.kind == "email"]
    outbox = []
    acc = core.portal_account_for(db, c.id)
    if acc:
        for o in db.execute(select(CommOutbox).where(CommOutbox.portal_account_id == acc.id)
                            .order_by(CommOutbox.created_at.desc()).limit(10)).scalars():
            outbox.append({"at": o.created_at.isoformat(), "subject": o.subject, "status": o.status, "purpose": o.purpose})
    return {**_portal_info(db, c.id), "emails": emails, "outbox": outbox,
            "can_invite": p.has(c.organization_id, "comm.portal.invite")}


class InviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)


@router.post("/contacts/{contact_id}/portal/invite")
def portal_invite(contact_id: uuid.UUID, body: InviteIn, request: Request, background: BackgroundTasks,
                  p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    c = _contact_for_portal(db, p, contact_id, request, "comm.portal.invite")
    email = norm_email(body.email)
    if email not in {cp.value_normalized for cp in c.points if cp.kind == "email"}:
        raise api_error(422, "validacion", "Ese correo no está en la ficha del cliente: añádalo antes en sus datos de contacto.")
    other = db.execute(select(PortalAccount).where(PortalAccount.organization_id == c.organization_id,
                                                   PortalAccount.email == email, PortalAccount.contact_id != c.id)).scalar_one_or_none()
    if other:
        raise api_error(409, "conflicto", "Ese correo ya da acceso al portal a otra persona. Cada persona necesita su propio correo.")
    acc = core.portal_account_for(db, c.id)
    if acc and acc.status == "bloqueada":
        raise api_error(409, "conflicto", "El acceso está bloqueado: reactívelo antes.")
    if acc is None:
        acc = PortalAccount(organization_id=c.organization_id, contact_id=c.id, email=email, invited_by=p.id)
        db.add(acc)
        db.flush()
        t = core.general_thread(db, c)
        db.add(CommMessage(organization_id=c.organization_id, thread_id=t.id, kind="sistema", visibility="cliente",
                           body_enc=textcrypt.enc(templates.WELCOME)))
        t.last_message_at = core.now()
    elif acc.email != email:
        acc.email = email
        acc.version += 1
    portal = get_settings().web_origin.rstrip("/") + "/portal"
    notify.enqueue(db, organization_id=c.organization_id, purpose="invitacion", to=email,
                   subject="Su acceso al portal del despacho",
                   body=(f"Estimado/a {c.given_name}:\n\nEl despacho le ha dado acceso a su portal de cliente, donde podrá "
                         f"escribirnos, enviarnos documentos y recibir avisos sobre su asunto.\n\nEntre aquí con este "
                         f"correo electrónico: {portal}\n\nLe enviaremos un código de un solo uso cada vez que entre. "
                         "Si no esperaba este mensaje, ignórelo."),
                   idem_key=f"invitacion:{acc.id}:{acc.version}", portal_account_id=acc.id)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.portal.invite", resource_type="contact", resource_id=c.id,
                 organization_id=c.organization_id, after={"cuenta": str(acc.id), "estado": acc.status},
                 ip=ctx.ip, request_id=ctx.request_id)
    # La propuesta del agente de mensajes («dar acceso al portal») queda resuelta.
    for prop in db.execute(select(AgentProposal).where(AgentProposal.dedupe_key == f"invitar:{c.id}",
                                                       AgentProposal.status == "pendiente")).scalars():
        prop.status, prop.decided_by, prop.decided_at = "aprobada", p.id, core.now()
        prop.decision_note = "Invitación enviada desde la ficha del cliente."
    db.commit()
    background.add_task(notify.dispatch_pending)
    return portal_status(contact_id, request, p, db)


class BlockIn(BaseModel):
    block: bool
    reason: str = Field(default="", max_length=300)


@router.post("/contacts/{contact_id}/portal/block")
def portal_block(contact_id: uuid.UUID, body: BlockIn, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    c = _contact_for_portal(db, p, contact_id, request, "comm.portal.invite")
    acc = core.portal_account_for(db, c.id)
    if acc is None:
        raise api_error(404, "no_encontrado", "Este cliente no tiene acceso al portal.")
    if body.block:
        if len(body.reason.strip()) < 3:
            raise api_error(422, "validacion", "Indique el motivo del bloqueo.")
        acc.status, acc.blocked_reason = "bloqueada", body.reason.strip()
        revoke_all(db, acc.id)
    else:
        acc.status = "activa" if acc.terms_accepted_at else "invitada"
        acc.blocked_reason = None
    acc.version += 1
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="comm.portal.block" if body.block else "comm.portal.unblock",
                 resource_type="contact", resource_id=c.id, organization_id=c.organization_id,
                 reason=body.reason or None, after={"cuenta": str(acc.id), "estado": acc.status},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return portal_status(contact_id, request, p, db)


__all__ = ["router", "store_attachments"]
