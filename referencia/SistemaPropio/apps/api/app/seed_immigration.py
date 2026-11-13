"""Datos FICTICIOS de extranjería (F4.1): trámites asignados a los expedientes demo y documentos inventados.

Incremental e idempotente:
- crea el usuario «lider.extranjeria» si la base demo ya existía (la semilla base no se repite);
- sincroniza el catálogo de trámites;
- solo asigna trámites y documentos si ningún expediente tiene aún trámite de extranjería.

Los pasaportes son imágenes generadas con el país ficticio «UTO» de la especificación OACI 9303, números con
prefijo ZZ y una MRZ correcta. No representan a ninguna persona real.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .immigration import mrz, reader
from .immigration.sync import current, sync_procedures
from .models import CaseFile, Contact, Department, Membership, Organization, Role, UserAccount
from .models_immigration import ImmigCase, ImmigDocument, ImmigOfficeProfile, ImmigStageEvent
from .services import vault

# (trámite, fase) para los expedientes demo de extranjería, por orden de creación
PLAN = [
    ("ARR-SOCIOLABORAL", "documentacion"), ("ARR-SOCIAL", "preparacion"), ("REN-RT-CA", "lista_presentar"),
    ("REAG-FAM", "presentado"), ("ARR-FAMILIAR", "requerimiento"), ("LD-UE", "resolucion_favorable"),
    ("MOD-ESTUDIOS", "documentacion"), ("ARR-EXTRAORDINARIO", "consulta"), ("LD-NACIONAL", "documentacion"),
    ("ARR-SEGUNDA-OP", "preparacion"), ("REN-RT-CA", "preparacion"),
]
STAGE_PATH = ["consulta", "documentacion", "preparacion", "lista_presentar", "presentado", "requerimiento",
              "requerimiento_respondido", "resolucion_favorable"]


def _font(size: int):
    from PIL import ImageFont

    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def passport_image(surname: str, given: str, number: str, birth: date, expiry: date, sex: str = "F") -> tuple[bytes, list[str]]:
    """Página de datos de un pasaporte FICTICIO (país UTO) con MRZ válida. Devuelve (PNG, líneas MRZ)."""
    from PIL import Image, ImageDraw

    lines = mrz.build_td3("P", "UTO", reader.norm(surname).upper(), reader.norm(given).upper(), number, "UTO",
                          birth, sex, expiry)
    img = Image.new("RGB", (1250, 880), (236, 240, 232))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 1250, 90), fill=(40, 70, 95))
    d.text((40, 22), "PASAPORTE FICTICIO · UTOPIA (OACI 9303) · SIN VALOR", fill=(255, 255, 255), font=_font(34))
    d.rectangle((40, 130, 330, 500), outline=(120, 120, 120), width=3)
    d.text((95, 300), "FOTO", fill=(150, 150, 150), font=_font(40))
    small, big = _font(22), _font(30)
    y = 130
    for k, v in (("Apellidos", surname.upper()), ("Nombre", given.upper()), ("Nacionalidad", "UTOPIA"),
                 ("Fecha de nacimiento", birth.strftime("%d %m %Y")), ("Sexo", sex), ("Número", number),
                 ("Fecha de expedición", (expiry - timedelta(days=3652)).strftime("%d %m %Y")),
                 ("Fecha de caducidad", expiry.strftime("%d %m %Y"))):
        d.text((380, y), k, fill=(90, 90, 90), font=small)
        d.text((380, y + 24), v, fill=(10, 10, 10), font=big)
        y += 62
    mz = _font(36)
    d.rectangle((0, 700, 1250, 880), fill=(255, 255, 255))
    d.text((30, 725), lines[0], fill=(0, 0, 0), font=mz)
    d.text((30, 795), lines[1], fill=(0, 0, 0), font=mz)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), lines


def text_pdf(title: str, body: list[str]) -> bytes:
    """PDF de una página con texto (certificados FICTICIOS)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1240, 1754), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((90, 90), "DOCUMENTO FICTICIO — SIN VALOR", fill=(170, 30, 30), font=_font(30))
    d.text((90, 170), title, fill=(0, 0, 0), font=_font(40))
    y = 280
    for line in body:
        d.text((90, y), line, fill=(20, 20, 20), font=_font(28))
        y += 50
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue()


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def _ensure_lider(db: Session, es: Organization) -> None:
    if _u(db, "lider.extranjeria"):
        return
    role = db.execute(select(Role).where(Role.code == "lider_extranjeria")).scalar_one_or_none()
    dept = db.execute(select(Department).where(Department.organization_id == es.id, Department.code == "EXT")).scalar_one_or_none()
    if role is None or dept is None:
        return
    u = UserAccount(username="lider.extranjeria", full_name="Líder Extranjería (demo)",
                    email="lider.extranjeria@demo.invalid", is_demo=True)
    db.add(u)
    db.flush()
    db.add(Membership(user_id=u.id, organization_id=es.id, department_id=dept.id, role_id=role.id))
    db.flush()


OFFICE_DEMO = {  # despacho FICTICIO como representante (el real lo introduce el despacho en «Datos del despacho»)
    "rep.nombre": "Despacho Demo Extranjería (ficticio)", "rep.doc": "12345678Z", "rep.tipo_via": "Calle",
    "rep.domicilio": "Inventada", "rep.municipio": "Madrid",
    "rep.numero": "10", "rep.piso": "2º", "rep.localidad": "Madrid", "rep.cp": "28001", "rep.provincia": "Madrid",
    "rep.telefono": "+34600000000", "rep.email": "presentaciones@demo.invalid", "sol.firma_lugar": "Madrid",
}


def _ensure_office(db: Session, es: Organization) -> None:
    if db.get(ImmigOfficeProfile, es.id):
        return
    who = _u(db, "lider.extranjeria") or _u(db, "direccion.demo")
    if who:
        db.add(ImmigOfficeProfile(organization_id=es.id, data=dict(OFFICE_DEMO), updated_by=who.id))
        db.flush()


def _doc(db: Session, cf: CaseFile, user: UserAccount, data: bytes, name: str, *, doc_type: str | None,
         status: str, extracted: dict | None = None, issued: date | None = None, expires: date | None = None,
         label: str | None = None, reviewer: UserAccount | None = None) -> None:
    mime = vault.sniff(data)
    path, sha = vault.store(data)
    db.add(ImmigDocument(organization_id=cf.organization_id, case_id=cf.id, status=status,
                         doc_type=doc_type if status != "pendiente_revision" else None, suggested_type=doc_type,
                         suggested_confidence="alta" if extracted else "media", label=label, original_name=name,
                         mime=mime, size_bytes=len(data), sha256=sha, file_path=path, extracted=extracted,
                         ocr_engine="semilla", issued_on=issued, expires_on=expires, uploaded_by=user.id,
                         reviewed_by=reviewer.id if reviewer and status != "pendiente_revision" else None,
                         reviewed_at=datetime.now(UTC) if reviewer and status != "pendiente_revision" else None))


def seed_immigration(db: Session) -> None:
    from .seed import ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None:
        return
    _ensure_lider(db, es)
    sync_procedures(db)
    _ensure_office(db, es)
    if db.execute(select(func.count()).select_from(ImmigCase)).scalar_one() > 0:
        return
    asesor = _u(db, "asesor.extranjeria.mad") or _u(db, "direccion.demo")
    lider = _u(db, "lider.extranjeria") or asesor
    today = date.today()
    now = datetime.now(UTC)
    cases = list(db.execute(select(CaseFile).where(CaseFile.organization_id == es.id, CaseFile.materia == "extranjeria")
                            .order_by(CaseFile.created_at)).scalars())
    for i, cf in enumerate(cases):
        code, stage = PLAN[i % len(PLAN)]
        pr = current(db, code)
        if pr is None:
            continue
        idx = STAGE_PATH.index(stage) if stage in STAGE_PATH else 1
        since = now - timedelta(days=3 + 4 * i)
        ic = ImmigCase(case_id=cf.id, organization_id=es.id, procedure_id=pr.id, stage=stage, stage_changed_at=since,
                       province="Madrid", created_by=asesor.id)
        if idx >= STAGE_PATH.index("presentado"):
            ic.presented_at = since - timedelta(days=20)
            ic.registry_number = f"REGAGE-FICT-{2026000 + i}"
        if stage == "resolucion_favorable":
            ic.resolution_at = (since).date()
        db.add(ic)
        prev = None
        for st in STAGE_PATH[: idx + 1]:
            if st == "consulta" and stage != "consulta":
                continue
            db.add(ImmigStageEvent(case_id=cf.id, actor_user_id=(lider if st == "resolucion_favorable" else asesor).id,
                                   from_stage=prev, to_stage=st, note="Datos ficticios de demostración"))
            prev = st
        contact = db.get(Contact, cf.contact_id)
        if stage == "consulta":
            continue
        # Pasaporte ficticio: uno caducado, uno a punto de caducar y el resto vigentes
        expiry = today + timedelta(days=(-40 if i == 1 else 60 if i == 2 else 1400 + 30 * i))
        birth = contact.birth_date or date(1990, 1, 1)
        number = f"ZZ{700000 + i:07d}"[:9]
        png, lines = passport_image(contact.family_names, contact.given_name, number, birth, expiry,
                                    "F" if i % 2 == 0 else "M")
        parsed = mrz.parse("\n".join(lines), today) or {}
        extracted = {"mrz": {k: v for k, v in parsed.items() if k != "lines"}, "mrz_lines": lines,
                     "expires_on": expiry.isoformat()}
        reviewed = idx >= STAGE_PATH.index("preparacion")
        _doc(db, cf, asesor, png, "pasaporte_ficticio.png", doc_type="pasaporte",
             status="valido" if reviewed else "pendiente_revision", extracted=extracted, expires=expiry,
             label="Pasaporte (ficticio)", reviewer=asesor)
        if idx >= STAGE_PATH.index("documentacion"):
            pdf = text_pdf("Certificado de empadronamiento", [
                f"Persona: {contact.given_name} {contact.family_names}",
                "Domicilio: Calle Inventada 1, Municipio Demo",
                f"Fecha de expedición: {(today - timedelta(days=30)).strftime('%d/%m/%Y')}",
            ])
            _doc(db, cf, asesor, pdf, "padron_ficticio.pdf", doc_type="empadronamiento",
                 status="valido" if reviewed else "pendiente_revision", issued=today - timedelta(days=30),
                 label="Empadronamiento (ficticio)", reviewer=asesor)
        if idx >= STAGE_PATH.index("lista_presentar"):
            pdf = text_pdf("Modelo de solicitud (borrador ficticio)", [pr.data.get("ex_form") or "", pr.name])
            _doc(db, cf, asesor, pdf, "solicitud_ficticia.pdf", doc_type="formulario_ex", status="valido",
                 label=f"Solicitud {pr.data.get('ex_form') or ''}".strip(), reviewer=asesor)
        if idx >= STAGE_PATH.index("presentado"):
            pdf = text_pdf("Justificante de presentación (ficticio)", [f"Registro: {ic.registry_number}"])
            _doc(db, cf, asesor, pdf, "resguardo_ficticio.pdf", doc_type="resguardo_presentacion", status="valido",
                 label="Resguardo de presentación", reviewer=asesor)
    nac = list(db.execute(select(CaseFile).where(CaseFile.organization_id == es.id, CaseFile.materia == "nacionalidad")
                          .order_by(CaseFile.created_at).limit(1)).scalars())
    pr = current(db, "NAC-RESIDENCIA")
    for cf in nac:
        if pr:
            db.add(ImmigCase(case_id=cf.id, organization_id=es.id, procedure_id=pr.id, stage="documentacion",
                             province="Barcelona", created_by=asesor.id))
            db.add(ImmigStageEvent(case_id=cf.id, actor_user_id=asesor.id, from_stage=None, to_stage="documentacion",
                                   note="Datos ficticios de demostración"))
    db.flush()
