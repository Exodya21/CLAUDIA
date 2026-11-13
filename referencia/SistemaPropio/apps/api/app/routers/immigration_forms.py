"""F4.2 — Ficha de datos del modelo EX, borrador del PDF oficial y código temporal para la extensión de Mercurio.

Límites (T-24 aprobada el 05/11/2026): la extensión solo RELLENA campos en el navegador del profesional; no firma,
no pulsa «Concluir», «Presentación electrónica» ni «Firmar y registrar». Solo lee valores que una persona ha
confirmado en la ficha, mediante un código de un solo expediente que caduca a los 15 minutos.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..errors import api_error
from ..immigration import extract, forms, reader
from ..immigration.catalog import DOC_TYPES
from ..models import Address, CaseFile, Contact, ContactPoint, Identifier, UserAccount
from ..models_immigration import ImmigCase, ImmigDocument, ImmigFillToken, ImmigForm, ImmigOfficeProfile, ImmigProcedure
from ..security.auth import Principal, get_principal
from .common import req_ctx
from .immigration import _case, _deny, _immig

router = APIRouter(prefix="/immigration", tags=["extranjería · formularios"])
TOKEN_MINUTES = 15
TOKEN_USES = 10
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I
OFFICE_KEYS = {f"rep.{k}" for k in forms.FIELDS["rep"]} | {f"notif.{k}" for k in forms.FIELDS["notif"]} | {
    "sol.firma_lugar", "sol.dirigida_a", "sol.dir3"}


def _now() -> datetime:
    return datetime.now(UTC)


class FormIn(BaseModel):
    model: str = Field(pattern=r"^(EX\d{2}|GENERAL)$")
    values: dict[str, str] = Field(default_factory=dict)
    options: list[str] = Field(default_factory=list, max_length=80)
    extra: dict[str, str] = Field(default_factory=dict)
    version: int | None = None


class OfficeIn(BaseModel):
    data: dict[str, str]
    version: int | None = None


def _clean(values: dict[str, str], allowed: set[str]) -> tuple[dict[str, str], list[dict]]:
    out, errors = {}, []
    for k, v in values.items():
        if k not in allowed:
            errors.append({"field": k, "message": "Campo desconocido"})
            continue
        v = re.sub(r"\s+", " ", str(v)).strip()
        if len(v) > 200:
            errors.append({"field": k, "message": "Máximo 200 caracteres"})
            continue
        if not v:
            continue
        if k.endswith(".fecha_nacimiento"):
            try:
                d = date.fromisoformat(v)
                if d > date.today():
                    raise ValueError
            except ValueError:
                errors.append({"field": k, "message": "Fecha no válida (AAAA-MM-DD, no futura)"})
                continue
        if k.endswith(".nie") and not re.fullmatch(r"[XYZ]\W?\d{7}\W?[A-Z]", v.upper()):
            errors.append({"field": k, "message": "Formato de NIE: X-1234567-L"})
            continue
        if k.endswith(".email") and "@" not in v:
            errors.append({"field": k, "message": "Correo no válido"})
            continue
        choices = forms.CHOICES.get(k.split(".", 1)[1])
        if choices and v not in choices:
            errors.append({"field": k, "message": "Opción no válida"})
            continue
        out[k] = v.upper() if k.endswith(".nie") else v
    return out, errors


def _office(db: Session, org_id) -> ImmigOfficeProfile | None:
    return db.get(ImmigOfficeProfile, org_id)


def _mrz(db: Session, case_id) -> dict | None:
    docs = db.execute(select(ImmigDocument).where(ImmigDocument.case_id == case_id, ImmigDocument.status == "valido",
                                                  ImmigDocument.doc_type == "pasaporte")
                      .order_by(ImmigDocument.reviewed_at.desc())).scalars()
    for d in docs:
        m = (d.extracted or {}).get("mrz")
        if m and m.get("valid"):
            return m
    return None


def _proposals(db: Session, cf: CaseFile, ic: ImmigCase) -> dict:
    c = db.get(Contact, cf.contact_id)
    ids = list(db.execute(select(Identifier).where(Identifier.contact_id == c.id)).scalars())
    addrs = list(db.execute(select(Address).where(Address.contact_id == c.id)).scalars())
    pts = list(db.execute(select(ContactPoint).where(ContactPoint.contact_id == c.id)).scalars())
    office = _office(db, cf.organization_id)
    props = forms.proposals(c, ids, addrs, pts, _mrz(db, cf.id), office.data if office else {}, ic.province)
    # Datos leídos de documentos YA CONFIRMADOS por una persona (contrato, padrón, TIE, pasaporte…)
    docs = db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id, ImmigDocument.status == "valido")
                      .order_by(ImmigDocument.reviewed_at)).scalars()
    for d in docs:
        mrz_data = (d.extracted or {}).get("mrz")
        other_holder = bool(mrz_data) and reader.name_matches(c.given_name, c.family_names, mrz_data) is False
        for k, v in extract.sanitize((d.extracted or {}).get("ficha") or {}).items():
            if not v or (other_holder and k.startswith("ext.")):
                continue  # el titular del documento no es el cliente: sus datos personales no se proponen
            # los nombres con tildes de la ficha del cliente valen más que la MRZ (sin tildes)
            if k in ("ext.nombre", "ext.apellido1", "ext.apellido2") and k in props and props[k]["source"] == "cliente":
                continue
            src = f"documento: {DOC_TYPES.get(d.doc_type, d.doc_type)}"
            prev = props.get(k)
            if prev and _norm(prev["value"]) != _norm(str(v)):
                # dos fuentes dicen cosas distintas: gana la última revisada, pero la otra queda a la vista
                others = [o for o in prev.get("others", []) if _norm(o["value"]) != _norm(str(v))]
                others.append({"value": prev["value"], "source": prev["source"]})
                props[k] = {"value": str(v), "source": src, "others": others}
            elif not prev:
                props[k] = {"value": str(v), "source": src}
    return props


def _norm(v: str) -> str:
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().upper()
    return "".join(ch for ch in v if ch.isalnum())


def _form_out(db: Session, p: Principal, cf: CaseFile, ic: ImmigCase, model: str | None) -> dict:
    saved = db.get(ImmigForm, cf.id)
    proc = db.get(ImmigProcedure, ic.procedure_id)
    default = forms.model_code(proc.data.get("ex_form"))
    code = model or (saved.model if saved else None) or default
    avail = forms.available()
    if code not in avail and code != forms.GENERAL:
        code = forms.GENERAL  # Mercurio pide los mismos datos comunes aunque no tengamos el PDF del modelo
    sp = forms.spec(code)
    props = _proposals(db, cf, ic)
    keys = {f["key"] for r in sp["roles"] for f in r["fields"]}
    values = dict(saved.values) if saved and saved.model == code else {}
    pending = {k: v for k, v in props.items() if k in keys and k not in values}
    # Valores ya guardados que un documento confirmado contradice: se avisa, no se cambia nada
    differs = {k: {"value": v["value"], "source": v["source"]} for k, v in props.items()
               if k in values and v["source"].startswith("documento:") and _norm(str(values[k])) != _norm(v["value"])}
    office = _office(db, cf.organization_id)
    org = cf.organization_id
    return {"available": True, "model": code, "default_model": default, "spec": sp, "values": values,
            "options": saved.options if saved and saved.model == code else [],
            "extra": saved.extra if saved and saved.model == code else {},
            "proposals": pending, "differs": differs, "version": saved.version if saved else None,
            "confirmed_by": db.get(UserAccount, saved.confirmed_by).full_name if saved else None,
            "confirmed_at": saved.confirmed_at.isoformat() if saved else None,
            "office_configured": bool(office and office.data),
            "procedure_model": proc.data.get("ex_form"),
            "models": [{"code": forms.GENERAL, "model": "General", "title": "Datos comunes de Mercurio (sin PDF)"}]
            + [{"code": k, "model": v["model"], "title": v.get("title", "")} for k, v in avail.items()],
            "can": {"edit": p.has(org, "immig.document.review"), "pdf": p.has(org, "immig.package"),
                    "token": p.has(org, "immig.package")}}


@router.get("/forms")
def list_forms(p: Principal = Depends(get_principal)) -> dict:
    return {"models": [{"code": k, "model": v["model"], "title": v.get("title", ""), "fields": len(v["fields"]),
                        "options": len(v.get("options", []))} for k, v in forms.available().items()]}


@router.get("/cases/{case_id}/form")
def get_form(case_id: uuid.UUID, request: Request, model: str | None = None, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.form.read")
    return _form_out(db, p, cf, _immig(db, cf), model)


@router.put("/cases/{case_id}/form")
def save_form(case_id: uuid.UUID, body: FormIn, request: Request, p: Principal = Depends(get_principal),
              db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.form.save", perm="immig.document.review")
    ic = _immig(db, cf)
    if body.model not in forms.available() and body.model != forms.GENERAL:
        raise api_error(422, "validacion", "Modelo no disponible.", [{"field": "model", "message": "No disponible"}])
    sp = forms.spec(body.model)
    keys = {f["key"] for r in sp["roles"] for f in r["fields"]}
    values, errors = _clean(body.values, keys)
    opt_fields = {o["field"] for o in sp["options"]}
    extra_fields = {e["field"] for e in sp["extra_text"]}
    errors += [{"field": o, "message": "Casilla no válida"} for o in body.options if o not in opt_fields]
    extra, e2 = _clean({k: v for k, v in body.extra.items() if k in extra_fields}, extra_fields)
    errors += e2 + [{"field": k, "message": "Campo desconocido"} for k in body.extra if k not in extra_fields]
    if errors:
        raise api_error(422, "validacion", "Revise los datos marcados.", errors)
    saved = db.get(ImmigForm, cf.id)
    if saved and body.version is not None and body.version != saved.version:
        raise api_error(409, "conflicto_version", "Otra persona ha cambiado la ficha. Recargue la página.")
    before = set(saved.values) if saved else set()
    changed = sorted(k for k in set(values) | before if (saved.values.get(k) if saved else None) != values.get(k))
    if saved is None:
        saved = ImmigForm(case_id=cf.id, organization_id=cf.organization_id, model=body.model, values=values,
                          options=sorted(set(body.options)), extra=extra, confirmed_by=p.id)
        db.add(saved)
    else:
        saved.model, saved.values, saved.options, saved.extra = body.model, values, sorted(set(body.options)), extra
        saved.version += 1
        saved.confirmed_by, saved.confirmed_at = p.id, _now()
    cf.last_activity_at = _now()
    ctx = req_ctx(request)
    # En la auditoría van las CLAVES cambiadas, no los valores (datos personales y números de documento).
    audit.record(db, actor_id=p.id, action="immig.form.save", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id,
                 after={"modelo": body.model, "campos_cambiados": changed, "casillas": len(body.options)},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _form_out(db, p, cf, ic, body.model)


@router.get("/cases/{case_id}/form.pdf")
def form_pdf(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)) -> Response:
    cf = _case(db, p, case_id, request, "immig.form.pdf", perm="immig.package")
    _immig(db, cf)
    saved = db.get(ImmigForm, cf.id)
    if saved is None:
        raise api_error(409, "sin_ficha", "Guarde primero la ficha de datos del formulario.")
    if saved.model == forms.GENERAL:
        raise api_error(409, "sin_modelo", "La ficha general no tiene modelo PDF: el formulario lo genera Mercurio.")
    pdf = forms.fill_pdf(saved.model, saved.values, saved.options, saved.extra)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.form.pdf", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after={"modelo": saved.model, "version_ficha": saved.version},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    name = f"VISTA_PREVIA_{forms.available()[saved.model]['model']}_{cf.code}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ datos del despacho
def _office_out(prof: ImmigOfficeProfile | None, p: Principal, org) -> dict:
    labels = {}
    for k in sorted(OFFICE_KEYS):
        r, f = k.split(".", 1)
        labels[k] = f"{forms.ROLES[r].split(' (')[0]} · {forms.FIELDS[r][f]}"
    return {"organization_id": str(org), "data": prof.data if prof else {}, "version": prof.version if prof else None,
            "updated_at": prof.updated_at.isoformat() if prof else None, "labels": labels,
            "can_edit": p.has(org, "immig.office.manage")}


@router.get("/office")
def get_office(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    orgs = p.orgs_with("immig.office.manage") | p.orgs_with("immig.package")
    if not orgs:
        raise api_error(403, "prohibido", "Su rol no gestiona presentaciones de extranjería.")
    return {"offices": [_office_out(db.get(ImmigOfficeProfile, o), p, o) for o in sorted(orgs, key=str)]}


@router.put("/office/{org_id}")
def put_office(org_id: uuid.UUID, body: OfficeIn, request: Request, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)) -> dict:
    ctx = req_ctx(request)
    if org_id not in p.org_ids():
        raise api_error(404, "no_encontrado", "Entidad no encontrada.")
    if not p.has(org_id, "immig.office.manage"):
        _deny(p, ctx, "immig.office.update", org_id, org_id, "sin immig.office.manage")
        raise api_error(403, "prohibido", "Solo Dirección o Líder Extranjería cambian los datos del despacho.")
    data, errors = _clean(body.data, OFFICE_KEYS)
    if errors:
        raise api_error(422, "validacion", "Revise los datos marcados.", errors)
    prof = db.get(ImmigOfficeProfile, org_id)
    if prof and body.version is not None and body.version != prof.version:
        raise api_error(409, "conflicto_version", "Otra persona ha cambiado estos datos. Recargue la página.")
    changed = sorted(data)
    if prof is None:
        prof = ImmigOfficeProfile(organization_id=org_id, data=data, updated_by=p.id)
        db.add(prof)
    else:
        changed = sorted(k for k in set(data) | set(prof.data) if prof.data.get(k) != data.get(k))
        prof.data, prof.version, prof.updated_by, prof.updated_at = data, prof.version + 1, p.id, _now()
    audit.record(db, actor_id=p.id, action="immig.office.update", resource_type="organization", resource_id=org_id,
                 organization_id=org_id, after={"campos_cambiados": changed}, ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return _office_out(prof, p, org_id)


# ------------------------------------------------------------------ código para la extensión
def _hash(code: str) -> str:
    return hashlib.sha256(re.sub(r"[^A-Z0-9]", "", code.upper()).encode()).hexdigest()


@router.post("/cases/{case_id}/fill-token", status_code=201)
def create_token(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)) -> dict:
    cf = _case(db, p, case_id, request, "immig.fill.token", perm="immig.package")
    _immig(db, cf)
    saved = db.get(ImmigForm, cf.id)
    if saved is None or not saved.values:
        raise api_error(409, "sin_ficha", "Guarde primero la ficha de datos: la extensión solo usa datos confirmados.")
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    code = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
    t = ImmigFillToken(organization_id=cf.organization_id, case_id=cf.id, token_hash=_hash(code), created_by=p.id,
                       expires_at=_now() + timedelta(minutes=TOKEN_MINUTES), max_uses=TOKEN_USES)
    db.add(t)
    ctx = req_ctx(request)
    audit.record(db, actor_id=p.id, action="immig.fill.token", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after={"caduca": t.expires_at.isoformat(), "modelo": saved.model},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    return {"code": code, "expires_at": t.expires_at.isoformat(), "max_uses": TOKEN_USES, "model": saved.model}


@router.get("/fill/{code}")
def read_with_token(code: str, request: Request, db: Session = Depends(get_db)) -> dict:
    """Lo llama la extensión (sin sesión). Devuelve SOLO la ficha confirmada de un expediente."""
    ctx = req_ctx(request)
    t = db.execute(select(ImmigFillToken).where(ImmigFillToken.token_hash == _hash(code))
                   .with_for_update()).scalar_one_or_none()
    if t is None or t.revoked_at or t.expires_at < _now() or t.uses >= t.max_uses:
        audit.record_independent(actor_id=t.created_by if t else None, action="immig.fill.read",
                                 resource_type="case_file", resource_id=t.case_id if t else None,
                                 organization_id=t.organization_id if t else None, outcome="denied",
                                 reason="código inexistente, caducado o agotado", ip=ctx.ip, request_id=ctx.request_id)
        raise api_error(404, "codigo_no_valido", "El código no existe, ha caducado o ya se ha usado demasiadas veces. "
                                                 "Genere otro en SISTEMA PROPIO.")
    saved = db.get(ImmigForm, t.case_id)
    cf = db.get(CaseFile, t.case_id)
    creator = db.get(UserAccount, t.created_by)
    if saved is None or creator is None or creator.status != "activo":
        raise api_error(404, "codigo_no_valido", "La ficha ya no está disponible. Genere otro código.")
    t.uses += 1
    spec = forms.spec(saved.model)
    opt_labels = [o["label"] for o in spec.get("options", []) if o["field"] in saved.options]
    labels = {}
    for k in saved.values:
        r, f = k.split(".", 1)
        labels[k] = forms.FIELDS.get(r, {}).get(f, f)
    audit.record(db, actor_id=t.created_by, action="immig.fill.read", resource_type="case_file", resource_id=cf.id,
                 organization_id=cf.organization_id, after={"lectura": t.uses, "agente": (request.headers.get("user-agent") or "")[:120]},
                 ip=ctx.ip, request_id=ctx.request_id)
    db.commit()
    contact = db.get(Contact, cf.contact_id)
    return {"case_code": cf.code, "client": f"{contact.given_name} {contact.family_names}", "model": spec["model"],
            "model_title": spec.get("title", ""), "values": saved.values, "labels": labels,
            "choices": {k: forms.CHOICES[k.split('.', 1)[1]] for k in saved.values if k.split('.', 1)[1] in forms.CHOICES},
            "options": opt_labels,
            "expires_at": t.expires_at.isoformat(), "uses_left": t.max_uses - t.uses,
            "confirmed_at": saved.confirmed_at.isoformat(),
            "notice": "Rellene, revise cada pestaña y firme usted. La extensión no presenta nada."}



# ------------------------------------------------------------------ revisión automática de la lectura (F4.3)
def _label(key: str) -> str:
    role, _, field = key.partition(".")
    return forms.FIELDS.get(role, {}).get(field) or {"nrc": "NRC del pago", "importe": "importe",
                                                      "dias_cotizados": "días cotizados"}.get(key, key)


def _pages(d: ImmigDocument) -> int | None:
    if d.mime != "application/pdf":
        return 1
    try:
        import io

        import pypdf

        from ..services import vault

        return len(pypdf.PdfReader(io.BytesIO(vault.load(d.file_path))).pages)
    except Exception:  # noqa: BLE001
        return None


def _doc_review(d: ImmigDocument) -> dict:
    ext = d.extracted or {}
    dtype = d.doc_type or d.suggested_type
    rv = extract.review(dtype, d.ocr_text or "", ext.get("mrz"))
    pages = _pages(d)
    problems: list[dict] = []

    def add(level: str, text: str) -> None:
        problems.append({"level": level, "text": text})

    seeded = d.ocr_engine == "semilla"  # documentos ficticios de la semilla: no pasan por la lectura
    old = not seeded and ext.get("lector") != reader.READER_VERSION
    if old:
        add("accion", "Leído con una versión anterior de la lectura: pulse «Volver a leer».")
    if not dtype:
        add("error", "No se reconoce qué documento es: elija el tipo al revisarlo.")
    if not seeded and rv["caracteres_texto"] < 40 and (dtype in extract.EXPECTED or dtype in extract.EXPECTED_INFO) \
            and dtype not in ("pasaporte", "tie_nie"):
        add("error", "Casi no se ha podido leer texto: escaneo poco nítido, torcido o foto. Escanéelo a 300 ppp.")
    if dtype in ("pasaporte", "tie_nie"):
        mz = ext.get("mrz")
        where = f" en {pages} página(s)" if pages else ""
        if not mz:
            add("error", f"No se ha encontrado la zona de lectura mecánica (las líneas con «<<<»){where}. "
                         "Compruebe que la hoja de datos está incluida y se ve entera y nítida.")
        elif not mz.get("valid"):
            bad = [k for k, ok in (mz.get("checks") or {}).items() if not ok]
            add("aviso", f"La zona de lectura mecánica se ha leído con errores en: {', '.join(bad)}. Revise esos datos a mano.")
    if rv["faltan"] and not seeded:
        add("aviso", "No se ha encontrado: " + ", ".join(_label(k) for k in rv["faltan"]) + ".")
    if rv["descartados"]:
        add("aviso", "Descartado por no parecer un dato válido: " + ", ".join(_label(k) for k in rv["descartados"])
            + ". Escríbalo a mano en la ficha.")
    if d.status == "pendiente_revision" and rv["leidos"]:
        add("info", "Pendiente de revisar: sus datos pasan a la ficha cuando lo marque «válido».")
    if d.status == "rechazado":
        add("info", "Marcado como no válido: sus datos no se usan.")
    return {"id": str(d.id), "nombre": extract.mask_text(d.original_name), "tipo": DOC_TYPES.get(dtype or "", "sin tipo"),
            "tipo_codigo": dtype, "estado": d.status, "paginas": pages, "motor": d.ocr_engine,
            "mrz": ({"formato": ext["mrz"].get("format"), "controles": ext["mrz"].get("checks")} if ext.get("mrz") else None),
            "leidos": [_label(k) for k in rv["leidos"]], "faltan": [_label(k) for k in rv["faltan"]],
            "descartados": [_label(k) for k in rv["descartados"]], "problemas": problems,
            "antiguo": old}


@router.get("/cases/{case_id}/reading-review")
def reading_review(case_id: uuid.UUID, request: Request, p: Principal = Depends(get_principal),
                   db: Session = Depends(get_db)) -> dict:
    """Revisión automática de la lectura de todos los documentos del expediente y de la ficha. Solo nombres de
    campos y avisos: ningún valor. «informe» es el mismo resultado como texto, con el texto leído enmascarado,
    para enviarlo a soporte sin datos personales."""
    cf = _case(db, p, case_id, request, "immig.reading.review", perm="immig.document.review")
    ic = _immig(db, cf)
    docs = list(db.execute(select(ImmigDocument).where(ImmigDocument.case_id == cf.id, ImmigDocument.status != "retirado")
                           .order_by(ImmigDocument.uploaded_at)).scalars())
    items = [_doc_review(d) for d in docs]
    form = _form_out(db, p, cf, ic, None)
    empty = []
    if form.get("available"):
        filled = set(form["values"]) | set(form["proposals"])
        for r in form["spec"]["roles"]:
            if r["role"] in ("ext", "emp", "con"):
                miss = [f["label"] for f in r["fields"] if f["key"] not in filled
                        and f["key"].split(".", 1)[1] in ("pasaporte", "nie", "apellido1", "nombre", "sexo", "fecha_nacimiento",
                                                          "nacionalidad", "domicilio", "numero", "cp", "municipio",
                                                          "provincia", "doc", "ccc", "puesto")]
                if miss:
                    empty.append({"apartado": r["label"], "campos": miss})
    conflicts = sorted({k for k, v in form.get("proposals", {}).items() if v.get("others")} | set(form.get("differs", {})))
    lines = [f"INFORME DE LECTURA (sin datos) · lector {reader.READER_VERSION} · modelo {form.get('model')}"]
    for it, d in zip(items, docs, strict=True):
        lines.append(f"\n## {it['tipo']} · {it['estado']} · {it['paginas']} pág. · motor {it['motor']} · archivo {it['nombre']}")
        if it["mrz"]:
            lines.append(f"MRZ {it['mrz']['formato']} controles {it['mrz']['controles']}")
        lines.append("Leídos: " + (", ".join(it["leidos"]) or "—"))
        lines.append("Faltan: " + (", ".join(it["faltan"]) or "—") + " · Descartados: " + (", ".join(it["descartados"]) or "—"))
        lines += [f"- {x['text']}" for x in it["problemas"]]
        lines.append("Texto leído (enmascarado):\n" + extract.mask_text(d.ocr_text or "")[:2500])
    if empty:
        lines.append("\n## Ficha: datos importantes sin valor ni propuesta")
        lines += [f"- {e['apartado']}: {', '.join(e['campos'])}" for e in empty]
    if conflicts:
        lines.append("Contradicciones en: " + ", ".join(_label(k) for k in conflicts))
    ctx = req_ctx(request)
    audit.record_independent(actor_id=p.id, action="immig.reading.review", resource_type="case_file", resource_id=cf.id,
                             organization_id=cf.organization_id, after={"documentos": len(docs)}, ip=ctx.ip,
                             request_id=ctx.request_id)
    return {"documentos": items, "ficha_vacia": empty, "contradicciones": [_label(k) for k in conflicts],
            "antiguos": [it["id"] for it in items if it["antiguo"]], "informe": "\n".join(lines)}
