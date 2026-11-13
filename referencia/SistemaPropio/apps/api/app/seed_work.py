"""Datos FICTICIOS de F1.2 (CRM) y F2 (expedientes, tareas). Idempotente: solo añade lo que falta.

Los plazos legales de ejemplo son inventados y figuran como "pendiente de validación" o validados por un
perfil ficticio: no representan ningún cómputo jurídico real.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .models import CaseAssignment, CaseFile, Contact, Department, Membership, Organization, Role, UserAccount
from .models_work import CasePhaseEvent, Lead, LeadEvent, LeadOrigin, Task, TaskEvent

MAD = ZoneInfo("Europe/Madrid")

ORIGINS = [
    ("presencial", "Presencial en oficina", False), ("telefono", "Llamada telefónica", False),
    ("web", "Formulario web", False), ("whatsapp", "WhatsApp", False),
    ("tiktok_live", "TikTok Live (teléfono rojo)", True), ("instagram", "Instagram", False),
    ("facebook", "Facebook", False), ("google_ads", "Google Ads", True), ("recomendacion", "Recomendación de cliente", False),
]


def _local(day_offset: int, hh: int, mm: int = 0) -> datetime:
    d = datetime.now(MAD).date() + timedelta(days=day_offset)
    return datetime.combine(d, time(hh, mm), MAD).astimezone(UTC)


def _user(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def seed_work(db: Session) -> None:
    from .seed import ORG_ES

    for code, name, camp in ORIGINS:
        if db.get(LeadOrigin, code) is None:
            db.add(LeadOrigin(code=code, name=name, requires_campaign=camp))
    db.flush()
    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    if es is None:
        return

    # Rol Marketing (nuevo en F1.2) con su usuario ficticio.
    if _user(db, "marketing.demo") is None:
        mk = UserAccount(username="marketing.demo", full_name="Marketing (demo)", email="marketing.demo@demo.invalid", is_demo=True)
        db.add(mk)
        db.flush()
        role = db.execute(select(Role).where(Role.code == "marketing")).scalar_one()
        dept = db.execute(select(Department).where(Department.organization_id == es.id, Department.code == "MKT")).scalar_one()
        db.add(Membership(user_id=mk.id, organization_id=es.id, department_id=dept.id, role_id=role.id))
        db.flush()

    u = {n: _user(db, n) for n in ("recepcion.bcn", "atc.demo", "asesor.laboral.bcn", "asesor.extranjeria.mad",
                                   "gestor.laboral.vlc", "lider.laboral", "direccion.demo", "marketing.demo")}
    rnd = random.Random(2027)
    now = datetime.now(UTC)

    # Historial de fases para expedientes existentes (migración de la historia mínima de F0.1).
    for cf in db.execute(select(CaseFile).where(~CaseFile.id.in_(select(CasePhaseEvent.case_id)))).scalars():
        db.add(CasePhaseEvent(case_id=cf.id, actor_user_id=cf.created_by, from_status=None, to_status=cf.status,
                              note="Estado inicial (datos de demostración F0.1)"))

    if db.execute(select(func.count()).select_from(Lead)).scalar_one() == 0:
        _seed_leads(db, es, u, rnd, now)
    if db.execute(select(func.count()).select_from(Task)).scalar_one() == 0:
        _seed_tasks(db, es, u, now)
    db.flush()


def _seed_leads(db: Session, es: Organization, u: dict, rnd: random.Random, now: datetime) -> None:
    contacts = list(db.execute(select(Contact).where(Contact.organization_id == es.id, Contact.is_synthetic.is_(True))
                               .order_by(Contact.created_at, Contact.id)).scalars())
    # (estado, horas desde el último cambio, origen, materia, asignado)
    plan = [
        ("nuevo", 3, "web", "laboral", None), ("nuevo", 10, "whatsapp", "extranjeria", None),
        ("nuevo", 30, "tiktok_live", "laboral", None), ("nuevo", 50, "telefono", "nacionalidad", None),
        ("nuevo", 80, "tiktok_live", "extranjeria", None), ("nuevo", 200, "instagram", "laboral", None),
        ("contactado", 20, "telefono", "laboral", "asesor.laboral.bcn"),
        ("contactado", 75, "web", "extranjeria", "asesor.extranjeria.mad"),
        ("contactado", 30, "recomendacion", "laboral", "asesor.laboral.bcn"),
        ("en_seguimiento", 26, "google_ads", "extranjeria", "asesor.extranjeria.mad"),
        ("en_seguimiento", 180, "facebook", "laboral", "asesor.laboral.bcn"),
        ("cita_solicitada", 6, "presencial", "laboral", "asesor.laboral.bcn"),
        ("cita_solicitada", 40, "whatsapp", "extranjeria", "asesor.extranjeria.mad"),
        ("descartado", 300, "tiktok_live", "otra", None), ("no_convertido", 500, "web", "laboral", "asesor.laboral.bcn"),
    ]
    path = {"contactado": ["contactado"], "en_seguimiento": ["contactado", "en_seguimiento"],
            "cita_solicitada": ["contactado", "cita_solicitada"], "descartado": ["descartado"],
            "no_convertido": ["contactado", "cita_solicitada", "no_convertido"], "nuevo": []}
    notes = {"descartado": "No es asunto del despacho (ficticio)", "no_convertido": "Decide no contratar por ahora (ficticio)"}
    pool = contacts[25:]
    for i, (status, hours, origin, materia, who) in enumerate(plan):
        ct = pool[i % len(pool)]
        changed = now - timedelta(hours=hours)
        created = changed - timedelta(hours=rnd.randint(1, 48)) if status != "nuevo" else changed
        camp = f"Directo ficticio #{i + 1:02d}" if origin in ("tiktok_live", "google_ads") else None
        lead = Lead(organization_id=es.id, branch_id=ct.primary_branch_id, contact_id=ct.id, origin_code=origin,
                    materia=materia, summary="Consulta inicial (texto ficticio).", campaign=camp,
                    utm_source="google" if origin == "google_ads" else None, utm_medium="cpc" if origin == "google_ads" else None,
                    utm_campaign=camp if origin == "google_ads" else None,
                    assigned_user_id=u[who].id if who else None, status=status, created_by=u["recepcion.bcn"].id,
                    created_at=created, status_changed_at=changed)
        db.add(lead)
        db.flush()
        db.add(LeadEvent(lead_id=lead.id, actor_user_id=u["recepcion.bcn"].id, to_status="nuevo", note="Alta", occurred_at=created))
        prev, steps = "nuevo", path[status]
        for j, st in enumerate(steps):
            at = created + (changed - created) * (j + 1) / len(steps)
            db.add(LeadEvent(lead_id=lead.id, actor_user_id=(u[who] or u["recepcion.bcn"]).id if who else u["recepcion.bcn"].id,
                             from_status=prev, to_status=st, note=notes.get(st), occurred_at=at))
            prev = st
    # Leads ya convertidos: enlazados a expedientes existentes (trazabilidad AT-06).
    for cf in db.execute(select(CaseFile).where(CaseFile.organization_id == es.id).order_by(CaseFile.code).limit(8)).scalars():
        origin = rnd.choice(["web", "telefono", "tiktok_live", "presencial", "recomendacion"])
        lead = Lead(organization_id=es.id, branch_id=cf.branch_id, contact_id=cf.contact_id, origin_code=origin,
                    materia=cf.materia, summary="Consulta que terminó en encargo (ficticio).",
                    campaign="Directo ficticio" if origin == "tiktok_live" else None, status="convertido",
                    case_file_id=cf.id, created_by=u["recepcion.bcn"].id,
                    created_at=cf.created_at - timedelta(days=3), status_changed_at=cf.created_at)
        db.add(lead)
        db.flush()
        db.add(LeadEvent(lead_id=lead.id, actor_user_id=u["recepcion.bcn"].id, to_status="nuevo", note="Alta",
                         occurred_at=lead.created_at))
        db.add(LeadEvent(lead_id=lead.id, actor_user_id=u["direccion.demo"].id, from_status="nuevo", to_status="convertido",
                         note=f"Expediente {cf.code} abierto", occurred_at=cf.created_at))
    audit.record(db, actor_id=None, action="seed.load", resource_type="system", after={"modulo": "CRM", "leads": len(plan) + 8})


def _seed_tasks(db: Session, es: Organization, u: dict, now: datetime) -> None:
    def cases_of(username: str, materia: str) -> list[CaseFile]:
        return list(db.execute(select(CaseFile).join(CaseAssignment, CaseAssignment.case_id == CaseFile.id)
                               .where(CaseAssignment.user_id == u[username].id, CaseFile.materia == materia,
                                      CaseFile.organization_id == es.id).order_by(CaseFile.code)).scalars())

    lab = cases_of("asesor.laboral.bcn", "laboral")
    ext = cases_of("asesor.extranjeria.mad", "extranjeria")
    vlc = cases_of("gestor.laboral.vlc", "laboral")
    al, ae, gv = u["asesor.laboral.bcn"], u["asesor.extranjeria.mad"], u["gestor.laboral.vlc"]
    specs = [
        # (expediente, responsable, título, tipo, prioridad, fecha interna, inicio, fin, lugar, plazo legal, fuente)
        (lab[0], al, "Revisar nóminas aportadas por el cliente", "gestion", "media", _local(1, 10), None, None, None, None, None),
        (lab[1], al, "Señalamiento ficticio: acto de juicio", "senalamiento", "alta", _local(3, 10), _local(3, 10), _local(3, 11),
         "Juzgado de lo Social nº 0 de Barcelona (ficticio)", None, None),
        (lab[2], al, "Señalamiento ficticio: conciliación judicial", "senalamiento", "alta", _local(3, 10, 30), _local(3, 10, 30),
         _local(3, 11, 30), "Juzgado de lo Social nº 00 de Barcelona (ficticio)", None, None),
        (lab[3], al, "Llamar al cliente para pedir vida laboral", "llamada", "media", _local(-2, 12), None, None, None, None, None),
        (lab[0], al, "Preparar escrito de aportación de prueba", "plazo", "alta", _local(6, 9), None, None, None,
         (datetime.now(MAD) + timedelta(days=9)).date(), "Diligencia ficticia notificada el día de hoy (dato de demostración)"),
        (lab[4], al, "Conciliación administrativa (ficticia)", "conciliacion", "media", _local(8, 12), _local(8, 12), _local(8, 13),
         "Servicio de conciliación (ficticio)", None, None),
        (ext[0], ae, "Comprobar documentación del trámite", "gestion", "media", _local(0, 17), None, None, None, None, None),
        (ext[1], ae, "Requerimiento de documentación (ficticio)", "plazo", "alta", _local(4, 9), None, None, None,
         (datetime.now(MAD) + timedelta(days=7)).date(), "Requerimiento ficticio de la Oficina de Extranjería"),
        (ext[2], ae, "Cita con el cliente para firmar solicitud", "gestion", "baja", _local(2, 16), _local(2, 16), _local(2, 16, 30),
         "Oficina de Madrid", None, None),
        (vlc[0], gv, "Calcular cantidades reclamadas (borrador)", "gestion", "media", _local(1, 11), None, None, None, None, None),
        (vlc[1], gv, "Enviar recordatorio de documentación", "llamada", "baja", _local(-1, 10), None, None, None, None, None),
    ]
    for i, (cf, who, title, kind, prio, due, st, en, loc, legal, src) in enumerate(specs):
        t = Task(organization_id=es.id, case_id=cf.id, title=title, description="Tarea de demostración con datos ficticios.",
                 kind=kind, priority=prio, assignee_id=who.id, due_at=due, start_at=st, end_at=en, location=loc,
                 created_by=who.id, created_at=now - timedelta(days=2))
        if legal:
            t.legal_deadline, t.legal_source, t.legal_status, t.legal_proposed_by = legal, src, "pendiente_validacion", who.id
        db.add(t)
        db.flush()
        db.add(TaskEvent(task_id=t.id, actor_user_id=who.id, kind="creada", to_status="pendiente", new_due_at=due,
                         occurred_at=t.created_at))
        if legal:
            db.add(TaskEvent(task_id=t.id, actor_user_id=who.id, kind="plazo_legal_propuesto",
                             reason=f"{legal.isoformat()} · {src}", occurred_at=t.created_at))
        if i == 7:  # plazo de extranjería ya validado por Dirección (otra persona)
            t.legal_status, t.legal_validated_by, t.legal_validated_at = "validado", u["direccion.demo"].id, now - timedelta(days=1)
            db.add(TaskEvent(task_id=t.id, actor_user_id=u["direccion.demo"].id, kind="plazo_legal_validado",
                             reason=legal.isoformat(), occurred_at=now - timedelta(days=1)))
        if i == 9:  # aplazamiento con motivo y fecha anterior conservada (AT-20)
            old = due - timedelta(days=2)
            db.add(TaskEvent(task_id=t.id, actor_user_id=gv.id, kind="aplazada", from_status="pendiente", to_status="pospuesta",
                             old_due_at=old, new_due_at=due, reason="El cliente aún no ha enviado las nóminas (ficticio)",
                             occurred_at=now - timedelta(days=1)))
            t.status = "pospuesta"
    # Tarea personal sin expediente
    t = Task(organization_id=es.id, title="Devolver llamada a persona interesada (ficticia)", kind="llamada", priority="media",
             assignee_id=u["recepcion.bcn"].id, due_at=_local(0, 18), created_by=u["recepcion.bcn"].id)
    db.add(t)
    db.flush()
    db.add(TaskEvent(task_id=t.id, actor_user_id=t.created_by, kind="creada", to_status="pendiente", new_due_at=t.due_at))
    # Dos expedientes sin actividad desde hace más de 30 días (indicador Q-6.4)
    for cf in db.execute(select(CaseFile).where(CaseFile.organization_id == es.id, CaseFile.materia == "laboral")
                         .order_by(CaseFile.code.desc()).limit(2)).scalars():
        cf.last_activity_at = now - timedelta(days=45)
    audit.record(db, actor_id=None, action="seed.load", resource_type="system", after={"modulo": "Tareas", "tareas": len(specs) + 1})
