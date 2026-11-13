"""Agente de mensajes al cliente por el portal propio (DR-MSG-1, 4, 5, 8, 9; DR-PLT-1…5; T-45, T-46, T-47).

Qué hace:
- Expediente abierto → bienvenida (DR-PLT-1).
- Conciliación o juicio en la agenda del expediente (con fecha, hora y LUGAR) → aviso de fecha (DR-PLT-2/4) y
  recordatorio a las 10:00 (Madrid) del día anterior (DR-PLT-3/5, T-46). Si la tarea cambia, se anula lo programado
  y se programa de nuevo con la fecha nueva; si se anula o se completa, se cancela.
- Seguimiento cada 75 días (T-45) de expedientes en trámite sin mensajes del despacho en ese tiempo.
- Expediente archivado o desistido → cancela todo lo pendiente (DR-MSG-8).
Cómo envía: en modo «propone» (por defecto) deja la propuesta con el texto en la bandeja y una persona con acceso al
expediente la aprueba; en modo «automático» (solo si Dirección lo activa tras el piloto, T-47) lo publica como
mensaje del despacho. Nunca envía novedades, resoluciones ni cierres (DR-MSG-6, 7, 9): eso lo escribe una persona.
Cada envío queda en `comm_dispatch` (plantilla y versión, evento, fecha prevista y real, resultado, responsable).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import exists, select

from .. import audit
from ..comm import auto_templates as auto
from ..comm import core
from ..comm.templates import MADRID, TemplateError
from ..models import CaseFile, Contact
from ..models_agents import AgentProposal, CommDispatch
from ..models_comm import CommMessage, CommThread
from ..models_work import Task
from ..security.policy import case_level, load_case_scope
from ..services import textcrypt
from .base import Agent, ApplyError, RunContext, now, propose

FOLLOW_UP_DAYS = 75  # T-45
REMINDER_HOUR = time(10, 0)  # T-46, hora de Madrid
ACTIVE = ("abierto", "en_tramite", "suspendido", "resuelto", "en_ejecucion")
FOLLOW_UP_STATUSES = ("abierto", "en_tramite")
CLOSED = ("archivado", "desistido")


class MensajesAgent(Agent):
    code = "mensajes"
    name = "Mensajes al cliente"
    area = "Comunicaciones"
    description = ("Prepara la bienvenida, los avisos y recordatorios de conciliaciones y juicios y el seguimiento "
                   "periódico, por el portal del cliente. Sin duplicados y con registro de cada envío.")
    covers = ("DR-MSG-1", "DR-MSG-4", "DR-MSG-5", "DR-MSG-8", "DR-MSG-9", "DR-PLT-1", "DR-PLT-2", "DR-PLT-3",
              "DR-PLT-4", "DR-PLT-5")
    requirements = ("I-031", "I-032", "U-15")
    events = ("case.opened", "case.closed", "task.created", "task.changed")
    scheduled_every_min = 15
    can_be_automatic = True
    limits = ("Solo usa las plantillas aprobadas, de usted y sin datos sensibles.",
              "Fechas, horas y lugares salen de la agenda del expediente; sin lugar no se avisa.",
              "Nunca envía novedades, resoluciones, presentaciones ni cierres: eso lo revisa y escribe una persona.",
              "No usa WhatsApp ni servicios externos: todo va por el portal propio (T-31).")

    # ------------------------------------------------------------ eventos
    def handle(self, ctx: RunContext, event) -> None:
        db = ctx.db
        if event.kind == "case.opened":
            cf = db.get(CaseFile, event.ref_id)
            if cf is not None and cf.status not in CLOSED:
                self._schedule(ctx, cf, "bienvenida_expediente", "case.opened", now(), key=f"bienvenida:{cf.id}")
        elif event.kind == "case.closed":
            self._cancel_case(ctx, event.ref_id, f"expediente {((event.payload or {}).get('fase') or 'cerrado')}")
        elif event.kind in ("task.created", "task.changed"):
            t = db.get(Task, event.ref_id)
            if t is not None:
                self._task(ctx, t, event.kind)

    def _task(self, ctx: RunContext, t: Task, trigger: str) -> None:
        db = ctx.db
        if t.kind not in auto.BY_TASK_KIND or t.case_id is None:
            return
        live = t.status in ("pendiente", "en_curso", "pospuesta") and t.start_at is not None
        start = t.start_at.isoformat() if t.start_at else None
        # Lo programado con otra fecha (o con la tarea anulada/completada) deja de valer.
        for d in db.execute(select(CommDispatch).where(CommDispatch.task_id == t.id,
                                                       CommDispatch.status == "propuesto")).scalars():
            if not live or (d.snapshot or {}).get("start_at") != start:
                self._cancel(ctx, d, "la fecha de la agenda cambió" if live else f"tarea {t.status}")
        if not live or t.start_at <= now():
            return
        cf = db.get(CaseFile, t.case_id)
        if cf is None or cf.status in CLOSED:
            return
        aviso, recordatorio = auto.BY_TASK_KIND[t.kind]
        self._schedule(ctx, cf, aviso, trigger, now(), task=t, key=f"aviso:{t.id}:{start}")
        day_before = t.start_at.astimezone(MADRID).date() - timedelta(days=1)
        when = datetime.combine(day_before, REMINDER_HOUR, tzinfo=MADRID).astimezone(UTC)
        if when > now():
            self._schedule(ctx, cf, recordatorio, trigger, when, task=t, key=f"recordatorio:{t.id}:{start}")
        # Lo que ya vencía y esperaba un dato (p. ej. el lugar) se vuelve a preparar.
        for d in list(db.execute(select(CommDispatch).where(CommDispatch.task_id == t.id,
                                                            CommDispatch.status == "propuesto",
                                                            CommDispatch.proposal_id.is_(None),
                                                            CommDispatch.scheduled_for <= now())).scalars()):
            self._process(ctx, d)

    def _schedule(self, ctx: RunContext, cf: CaseFile, template: str, trigger: str, when: datetime, *, key: str,
                  task: Task | None = None) -> CommDispatch | None:
        db = ctx.db
        if db.execute(select(CommDispatch.id).where(CommDispatch.dedupe_key == key)).first():
            ctx.count("duplicados_evitados")
            return None
        snap = {"start_at": task.start_at.isoformat() if task and task.start_at else None,
                "lugar": task.location if task else None}
        d = CommDispatch(organization_id=cf.organization_id, case_id=cf.id, contact_id=cf.contact_id,
                         template=template, template_version=auto.VERSION, trigger_event=trigger,
                         task_id=task.id if task else None, scheduled_for=when, snapshot=snap,
                         responsible_id=core._responsible(db, cf, cf.created_by), dedupe_key=key)
        db.add(d)
        db.flush()
        ctx.count("programados")
        if when <= now():
            self._process(ctx, d)  # lo que vence ya (bienvenida, aviso de fecha) va directo a la bandeja
        return d

    def _cancel(self, ctx: RunContext, d: CommDispatch, reason: str) -> None:
        d.status, d.cancel_reason = "cancelado", reason[:300]
        if d.proposal_id:
            p = ctx.db.get(AgentProposal, d.proposal_id)
            if p is not None and p.status == "pendiente":
                p.status, p.decided_at, p.decision_note = "caducada", now(), f"Cancelado: {reason}"[:500]
        ctx.count("cancelados")

    def _cancel_case(self, ctx: RunContext, case_id, reason: str) -> None:
        for d in ctx.db.execute(select(CommDispatch).where(CommDispatch.case_id == case_id,
                                                           CommDispatch.status == "propuesto")).scalars():
            self._cancel(ctx, d, reason)

    # ------------------------------------------------------------ calendario
    def scheduled(self, ctx: RunContext) -> None:
        db = ctx.db
        self._follow_ups(ctx)
        due = list(db.execute(select(CommDispatch).where(CommDispatch.organization_id == ctx.org_id,
                                                         CommDispatch.status == "propuesto",
                                                         CommDispatch.scheduled_for <= now())
                              .order_by(CommDispatch.scheduled_for)).scalars())
        for d in due:
            self._process(ctx, d)

    def _follow_ups(self, ctx: RunContext) -> None:
        db = ctx.db
        limit = now() - timedelta(days=FOLLOW_UP_DAYS)
        staff_msg = exists().where(CommThread.case_id == CaseFile.id, CommMessage.thread_id == CommThread.id,
                                   CommMessage.visibility == "cliente", CommMessage.author_portal_id.is_(None),
                                   CommMessage.created_at > limit)
        recent = exists().where(CommDispatch.case_id == CaseFile.id, CommDispatch.template == "seguimiento_expediente",
                                CommDispatch.created_at > limit)
        rows = db.execute(select(CaseFile).where(CaseFile.organization_id == ctx.org_id,
                                                 CaseFile.status.in_(FOLLOW_UP_STATUSES),
                                                 CaseFile.engagement_confirmed_at.is_not(None),
                                                 CaseFile.engagement_confirmed_at < limit,
                                                 ~staff_msg, ~recent).limit(500)).scalars()
        for cf in list(rows):
            self._schedule(ctx, cf, "seguimiento_expediente", "calendario:75_dias", now(),
                           key=f"seguimiento:{cf.id}:{now():%Y-%m-%d}")

    def _process(self, ctx: RunContext, d: CommDispatch) -> None:
        db = ctx.db
        cf = db.get(CaseFile, d.case_id)
        if cf is None or cf.status in CLOSED:
            self._cancel(ctx, d, "expediente cerrado")
            return
        task = db.get(Task, d.task_id) if d.task_id else None
        if task is not None and (task.status not in ("pendiente", "en_curso", "pospuesta") or task.start_at is None
                                 or task.start_at.isoformat() != (d.snapshot or {}).get("start_at")
                                 or task.start_at <= now()):
            self._cancel(ctx, d, "la fecha de la agenda ya no es la programada o ya pasó")
            return
        try:
            text = self.render(db, d)
        except TemplateError as exc:
            propose(ctx, self, kind="dato_falta", title=f"Completar datos para avisar al cliente · {cf.code}",
                    permission="comm.send", dedupe_key=f"falta:{d.id}", priority="alta",
                    detail=f"{auto.AUTO[d.template][0]}: {exc.message}", case_id=cf.id, assignee_id=d.responsible_id,
                    ref_type="comm_dispatch", ref_id=d.id)
            return
        for fp in db.execute(select(AgentProposal).where(AgentProposal.dedupe_key == f"falta:{d.id}",
                                                          AgentProposal.status == "pendiente")).scalars():
            fp.status, fp.decided_at, fp.decision_note = "caducada", now(), "Dato completado en la agenda."
        if ctx.mode == "automatico" and d.template in auto.AUTOMATIC_ALLOWED:
            self.send(db, d, text, None)
            ctx.count("enviados")
            return
        if d.proposal_id is None:
            p = propose(ctx, self, kind="mensaje", title=f"{auto.AUTO[d.template][0]} · {cf.code}",
                        permission="comm.send", dedupe_key=f"msg:{d.id}", priority="alta" if task else "media",
                        detail=text, case_id=cf.id, branch_id=cf.branch_id, assignee_id=d.responsible_id,
                        ref_type="comm_dispatch", ref_id=d.id,
                        payload={"plantilla": d.template, "version": d.template_version,
                                 "programado": d.scheduled_for.isoformat()})
            if p is not None:
                d.proposal_id = p.id

    def render(self, db, d: CommDispatch) -> str:
        cf = db.get(CaseFile, d.case_id)
        c = db.get(Contact, d.contact_id)
        task = db.get(Task, d.task_id) if d.task_id else None
        return auto.render(d.template, nombre=f"{c.given_name} {c.family_names}".strip(), expediente=cf.code, task=task)

    def send(self, db, d: CommDispatch, text: str, user) -> CommMessage:
        """Publica el mensaje en el hilo del expediente y avisa por correo (sin contenido) si tiene portal."""
        cf = db.get(CaseFile, d.case_id)
        t = core.case_thread(db, cf)
        m = CommMessage(organization_id=cf.organization_id, thread_id=t.id,
                        author_user_id=user.id if user else None, kind="texto" if user else "sistema",
                        visibility="cliente", level="normal", body_enc=textcrypt.enc(text), template=d.template,
                        task_id=d.task_id)
        db.add(m)
        db.flush()
        t.last_message_at = core.now()
        core.notify_client(db, t, m, cf.code)
        acc = core.portal_account_for(db, cf.contact_id)
        d.status, d.message_id, d.sent_at = "enviado", m.id, now()
        d.snapshot = {**(d.snapshot or {}), "portal": acc.status if acc else "sin_acceso"}
        audit.record(db, actor_id=user.id if user else None, action="comm.auto.send", resource_type="comm_thread",
                     resource_id=t.id, organization_id=cf.organization_id,
                     after={"mensaje": str(m.id), "plantilla": d.template, "version": d.template_version,
                            "envio": str(d.id), "modo": "aprobado" if user else "automatico"})
        if acc is None:
            # El mensaje queda en su portal; para que lo lea necesita acceso (DR-MSG-1).
            existing = db.execute(select(AgentProposal.id).where(AgentProposal.dedupe_key == f"invitar:{cf.contact_id}")).first()
            if not existing:
                db.add(AgentProposal(organization_id=cf.organization_id, agent_code=self.code, kind="invitar_portal",
                                     title=f"Dar acceso al portal al cliente de {cf.code}",
                                     detail="El despacho le ha escrito por el portal, pero el cliente aún no tiene acceso. "
                                            "Invítelo desde su ficha («Portal y mensajes»).",
                                     priority="media", permission="comm.portal.invite", case_id=cf.id,
                                     assignee_id=d.responsible_id, ref_type="contact", ref_id=cf.contact_id,
                                     dedupe_key=f"invitar:{cf.contact_id}"))
        return m

    # ------------------------------------------------------------ decisiones de la bandeja
    def _check_case(self, db, proposal: AgentProposal, user) -> CaseFile:
        cf = db.get(CaseFile, proposal.case_id)
        if cf is None or case_level(user, cf, load_case_scope(db, user)) != "full":
            raise ApplyError("Necesita acceso completo al expediente para enviar este mensaje.", 403)
        return cf

    def apply(self, db, proposal: AgentProposal, user, request_ctx) -> dict:
        if proposal.kind == "invitar_portal":
            raise ApplyError("Invite al cliente desde su ficha («Portal y mensajes»); la propuesta se cierra sola.", 422)
        d = db.get(CommDispatch, proposal.ref_id)
        if d is None:
            raise ApplyError("Envío no encontrado.", 404)
        self._check_case(db, proposal, user)
        if proposal.kind == "dato_falta":
            raise ApplyError("Complete el dato que falta en la agenda; el mensaje se preparará solo.", 422)
        if d.status != "propuesto":
            raise ApplyError(f"El envío está {d.status}.")
        task = db.get(Task, d.task_id) if d.task_id else None
        if task is not None and (task.start_at is None or task.start_at.isoformat() != (d.snapshot or {}).get("start_at")):
            raise ApplyError("La fecha de la agenda ha cambiado desde que se preparó el mensaje.")
        try:
            text = self.render(db, d)
        except TemplateError as exc:
            raise ApplyError(exc.message, 422) from exc
        m = self.send(db, d, text, user)
        return {"mensaje": str(m.id), "envio": str(d.id)}

    def reject(self, db, proposal: AgentProposal, user) -> None:
        if proposal.kind != "mensaje":
            return
        d = db.get(CommDispatch, proposal.ref_id)
        if d is not None and d.status == "propuesto":
            d.status, d.cancel_reason = "cancelado", f"rechazado por {user.user.full_name}"[:300]
