"""Agente de RRHH (DR-RH-6, DR-RH-4, DR-RH-5): vencimientos y avisos de plantilla.

Cada aviso lleva empleado, motivo, fecha y responsable (criterio de Dirección). Aprobarlo crea una tarea en la
agenda de quien lo aprueba para esa fecha; rechazarlo exige motivo. El agente no renueva, no despide, no aprueba
vacaciones ni toca nóminas: solo avisa a tiempo.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from ..models_agents import AgentProposal
from ..models_hr import Employee, EmployeeDocument, LeaveRequest
from ..models_work import Task
from .base import Agent, ApplyError, RunContext, propose

CONTRACT_DAYS = 30
TRIAL_DAYS = 15
LEAVE_UNANSWERED_DAYS = 3
PAYSLIP_DAY = 10  # a partir de este día del mes se avisa si falta la nómina del mes anterior


def _prev_month(d: date) -> str:
    return f"{d.year - (d.month == 1)}-{(d.month - 2) % 12 + 1:02d}"


class RrhhAgent(Agent):
    code = "rrhh"
    name = "Avisos de plantilla"
    area = "Recursos Humanos"
    description = ("Avisa de contratos temporales que vencen, periodos de prueba que terminan, contratos o nóminas "
                   "que faltan en la carpeta, diferencias grandes de nómina y solicitudes de vacaciones sin responder.")
    covers = ("DR-RH-4", "DR-RH-5", "DR-RH-6")
    requirements = ("Q-5.1", "Q-5.2", "Q-5.3")
    events = ("hr.leave.requested",)
    scheduled_every_min = 60
    can_be_automatic = False
    limits = ("No renueva ni extingue contratos, no aprueba vacaciones y no calcula nóminas: avisa y prepara la tarea.",
              "No usa fechas legales fijas: las fechas salen de la ficha y de los documentos que RRHH ha confirmado.",
              "Los datos de salud (bajas) no aparecen en los avisos.")

    def handle(self, ctx: RunContext, event) -> None:
        pass  # la solicitud aparece en la cola de quien decide; el aviso llega si nadie responde en 3 días

    def _alert(self, ctx: RunContext, e: Employee, reason: str, title: str, detail: str, when: date,
               priority: str, permission: str = "hr.manage", ref_type: str = "employee", ref_id=None) -> None:
        propose(ctx, self, kind="aviso_rrhh", title=f"{title} · {e.given_name} {e.family_names}",
                permission=permission, dedupe_key=f"rrhh:{reason}:{ref_id or e.id}:{when.isoformat()}",
                priority=priority, detail=detail, branch_id=e.branch_id, ref_type=ref_type, ref_id=ref_id or e.id,
                payload={"motivo": reason, "fecha": when.isoformat(), "empleado": e.code})

    def scheduled(self, ctx: RunContext) -> None:
        db = ctx.db
        today = date.today()
        for e in db.execute(select(Employee).where(Employee.organization_id == ctx.org_id,
                                                   Employee.status.in_(("activo", "baja", "excedencia")))).scalars():
            if e.contract_end_date and today <= e.contract_end_date <= today + timedelta(days=CONTRACT_DAYS):
                left = (e.contract_end_date - today).days
                self._alert(ctx, e, "fin_contrato", "Vence el contrato",
                            f"El contrato {e.contract_type} termina el {e.contract_end_date:%d/%m/%Y} (dentro de {left} "
                            "días). Decida a tiempo si se prorroga, se convierte o finaliza, y prepare la documentación.",
                            e.contract_end_date, "alta" if left <= 15 else "media")
            if e.trial_end_date and today <= e.trial_end_date <= today + timedelta(days=TRIAL_DAYS):
                self._alert(ctx, e, "fin_prueba", "Termina el periodo de prueba",
                            f"El periodo de prueba termina el {e.trial_end_date:%d/%m/%Y}. Recoja la valoración del "
                            "responsable antes de esa fecha.", e.trial_end_date, "alta")
            has_contract = db.execute(select(EmployeeDocument.id).where(
                EmployeeDocument.employee_id == e.id, EmployeeDocument.kind == "contrato",
                EmployeeDocument.status != "rechazado")).first()
            if not has_contract:
                self._alert(ctx, e, "falta_contrato", "Falta el contrato en la carpeta",
                            "La ficha no tiene ningún contrato subido. Súbalo a su carpeta (Documentos).",
                            date(today.year, today.month, 1), "media")
            if today.day >= PAYSLIP_DAY and e.start_date < date(today.year, today.month, 1) - timedelta(days=1):
                prev = _prev_month(today)
                has_slip = db.execute(select(EmployeeDocument.id).where(
                    EmployeeDocument.employee_id == e.id, EmployeeDocument.kind == "nomina",
                    EmployeeDocument.period == prev, EmployeeDocument.status != "rechazado")).first()
                if not has_slip:
                    self._alert(ctx, e, "falta_nomina", f"Falta la nómina de {prev}",
                                f"No está la nómina del periodo {prev} en la carpeta. Pídala a la gestoría y súbala.",
                                date(today.year, today.month, PAYSLIP_DAY), "media", permission="hr.salary")
            self._payroll_jump(ctx, e)
        limit = datetime.now(UTC) - timedelta(days=LEAVE_UNANSWERED_DAYS)
        for x in db.execute(select(LeaveRequest).where(LeaveRequest.organization_id == ctx.org_id,
                                                       LeaveRequest.status == "solicitada",
                                                       LeaveRequest.requested_at < limit)).scalars():
            e = db.get(Employee, x.employee_id)
            self._alert(ctx, e, "ausencia_sin_responder", "Solicitud sin responder",
                        f"Pidió {x.working_days} día(s) del {x.start_date:%d/%m/%Y} al {x.end_date:%d/%m/%Y} hace más "
                        f"de {LEAVE_UNANSWERED_DAYS} días y nadie la ha decidido. Decídala en RRHH → Ausencias.",
                        x.start_date, "media", ref_type="leave_request", ref_id=x.id)

    def _payroll_jump(self, ctx: RunContext, e: Employee) -> None:
        slips = list(ctx.db.execute(select(EmployeeDocument).where(
            EmployeeDocument.employee_id == e.id, EmployeeDocument.kind == "nomina",
            EmployeeDocument.status == "valido").order_by(EmployeeDocument.period.desc()).limit(2)).scalars())
        if len(slips) < 2:
            return
        cur, prev = (s.confirmed or {} for s in slips)
        a, b = cur.get("devengado_cents"), prev.get("devengado_cents")
        if a and b and abs(a - b) * 100 >= 10 * b:
            pct = round((a - b) * 100 / b, 1)
            y, m = map(int, slips[0].period.split("-"))
            self._alert(ctx, e, "diferencia_nomina", f"Diferencia de nómina {slips[0].period}",
                        f"El devengado de {slips[0].period} varía un {pct:+} % respecto a {slips[1].period}. Compruebe "
                        "si hay un cambio de jornada, variables o un error antes de enviarlo a la gestoría.",
                        date(y, m, 1), "media", permission="hr.salary", ref_type="employee_document", ref_id=slips[0].id)

    def apply(self, db, proposal: AgentProposal, user, request_ctx) -> dict:
        when = date.fromisoformat((proposal.payload or {}).get("fecha") or date.today().isoformat())
        due = max(when, date.today())
        t = Task(organization_id=proposal.organization_id, case_id=None, title=proposal.title[:200],
                 description=(proposal.detail or "")[:2000], kind="gestion", priority=proposal.priority,
                 assignee_id=user.id, due_at=datetime.combine(due, time(9, 0), tzinfo=UTC), created_by=user.id)
        db.add(t)
        db.flush()
        return {"tarea": str(t.id)}

    def reject(self, db, proposal: AgentProposal, user) -> None:
        if not proposal.decision_note:
            raise ApplyError("Indique el motivo.", 422)
