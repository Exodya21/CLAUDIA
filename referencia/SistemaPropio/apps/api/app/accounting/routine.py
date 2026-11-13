"""Rutina de trabajo de Contabilidad (sistema de trabajo pedido por Dirección; calendario del manual DR-CON).

Calendario del manual: días 1–2 importar extractos y documentos; día 3 conciliar; día 4 nóminas y facturas pendientes;
día 5 cierre provisional; cada lunes, resumen semanal. Se añaden la revisión diaria del banco y el informe quincenal.

Reglas:
- Un paso se da por HECHO solo cuando el sistema lo comprueba con los datos (no basta con marcarlo). Así la rutina
  mide el trabajo real y nadie tiene que acordarse de «tachar».
- «No aplica» exige motivo y queda auditado (p. ej. una cuenta sin movimientos ese día).
- Los pasos semanales, quincenales y mensuales crean además una tarea en la Agenda de su responsable; la tarea se
  cierra sola cuando el paso queda comprobado. Los diarios solo están en la lista (para no llenar la agenda).
- Fines de semana: la fecha objetivo pasa al lunes. Los festivos de cada sede siguen pendientes (T-49).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Membership, RolePermission, UserAccount
from ..models_accounting import (
    AccountingReport,
    MonthClose,
    PaymentBatch,
    PaymentBatchItem,
    RoutineItem,
    RoutineOwner,
    SupplierInvoice,
)
from ..models_bank import BankAccount, BankImport, BankMovement
from ..models_economy import CashClosing
from ..models_hr import Employee, EmployeeDocument
from ..models_work import Task, TaskEvent

MADRID = ZoneInfo("Europe/Madrid")
DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre")
OPEN_MOV = ("pendiente", "propuesto", "parcial", "sin_justificar")


@dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: date  # primer día que cubre
    end: date  # último día que cubre
    opens: date  # día en que aparece en la rutina


@dataclass(frozen=True)
class Step:
    code: str
    cadence: str
    title: str
    how: str
    perm: str  # permiso de quien puede ser responsable
    due: Callable[[Period], date]
    check: Callable[[Session, object, Period], tuple[bool, str]]
    agenda: bool = True


def business(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def prev_business(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def month_end(first: date) -> date:
    return (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _fmt(d: date) -> str:
    return f"{d:%d/%m/%Y}"


# ---------------------------------------------------------------- periodos
def day_period(d: date) -> Period:
    return Period(d.isoformat(), f"{DAYS[d.weekday()]} {d:%d/%m}", d, d, d)


def week_period(d: date) -> Period:
    """Semana ISO de `d`: la rutina semanal se hace el lunes y mira la semana anterior."""
    monday = d - timedelta(days=d.weekday())
    y, w, _ = monday.isocalendar()
    return Period(f"{y}-W{w:02d}", f"semana del {monday:%d/%m}", monday, monday + timedelta(days=6), monday)


def quincena_period(first: date, half: int) -> Period:
    """Quincena que se informa: 1–15 (se revisa desde el 16) o 16–fin (desde el día 1 del mes siguiente)."""
    if half == 1:
        return Period(f"{first:%Y-%m}-Q1", f"1–15 {MONTHS[first.month - 1]} {first.year}", first, first.replace(day=15),
                      first.replace(day=16))
    end = month_end(first)
    return Period(f"{first:%Y-%m}-Q2", f"16–{end.day} {MONTHS[first.month - 1]} {first.year}", first.replace(day=16), end,
                  end + timedelta(days=1))


def last_quincena(today: date) -> Period:
    if today.day >= 16:
        return quincena_period(today.replace(day=1), 1)
    prev_first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    return quincena_period(prev_first, 2)


def month_period(first: date) -> Period:
    end = month_end(first)
    return Period(f"{first:%Y-%m}", f"{MONTHS[first.month - 1]} {first.year}", first, end, end + timedelta(days=1))


def prev_month_period(today: date) -> Period:
    return month_period((today.replace(day=1) - timedelta(days=1)).replace(day=1))


def nth_day(p: Period, n: int) -> date:
    """Día n del mes siguiente al periodo mensual (día 2, 3, 4, 5…), pasado a laborable."""
    return business(p.opens.replace(day=n))


# ---------------------------------------------------------------- comprobaciones (deterministas, sobre los datos)
def _accounts(db: Session, org) -> list[BankAccount]:
    return list(db.execute(select(BankAccount).where(BankAccount.organization_id == org, BankAccount.active)
                           .order_by(BankAccount.name)).scalars())


def _statements_until(db: Session, org, until: date) -> tuple[bool, str]:
    missing = []
    accs = _accounts(db, org)
    for a in accs:
        last = db.execute(select(func.max(BankImport.period_to)).where(BankImport.account_id == a.id)).scalar_one()
        if last is None or last < until:
            missing.append(f"{a.name} ({'sin extractos' if last is None else 'hasta ' + _fmt(last)})")
    if not accs:
        return False, "No hay cuentas bancarias dadas de alta."
    if missing:
        return False, f"Falta el extracto hasta el {_fmt(until)}: " + "; ".join(missing)
    return True, f"Extractos de {len(accs)} cuenta(s) importados hasta el {_fmt(until)}."


def chk_daily_statements(db, org, p: Period):
    return _statements_until(db, org, prev_business(p.start))


def chk_daily_reconcile(db, org, p: Period):
    ok, ev = _statements_until(db, org, prev_business(p.start))
    if not ok:
        return False, "Primero hay que importar los extractos. " + ev
    limit = p.start - timedelta(days=2)
    n = db.execute(select(func.count()).select_from(BankMovement).where(
        BankMovement.organization_id == org, BankMovement.status.in_(OPEN_MOV), BankMovement.booking_date <= limit)).scalar_one()
    if n:
        return False, f"{n} movimiento(s) del banco de hace más de 2 días sin conciliar ni justificar."
    return True, f"Sin movimientos del banco anteriores al {_fmt(limit + timedelta(days=1))} pendientes."


def chk_week_invoices(db, org, p: Period):
    since = datetime.combine(p.start, time.min, tzinfo=MADRID).astimezone(UTC)
    n = db.execute(select(func.count()).select_from(SupplierInvoice).where(
        SupplierInvoice.organization_id == org, SupplierInvoice.status == "recibida",
        SupplierInvoice.registered_at < since)).scalar_one()
    if n:
        return False, f"{n} factura(s) registradas antes del lunes siguen sin validar."
    return True, "Todas las facturas recibidas hasta el lunes están validadas o rechazadas."


def chk_week_payments(db, org, p: Period):
    horizon = p.start + timedelta(days=7)
    active = select(PaymentBatchItem.invoice_id).join(PaymentBatch, PaymentBatch.id == PaymentBatchItem.batch_id).where(
        PaymentBatch.status.in_(("propuesta", "autorizada", "enviada")))
    n = db.execute(select(func.count()).select_from(SupplierInvoice).where(
        SupplierInvoice.organization_id == org, SupplierInvoice.status == "validada",
        SupplierInvoice.due_date.is_not(None), SupplierInvoice.due_date <= horizon,
        SupplierInvoice.id.not_in(active))).scalar_one()
    if n:
        return False, f"{n} factura(s) vencidas o que vencen antes del {_fmt(horizon)} sin incluir en una remesa."
    return True, f"Ninguna factura que venza antes del {_fmt(horizon)} queda fuera de una remesa."


def chk_week_cash(db, org, p: Period):
    n = db.execute(select(func.count()).select_from(CashClosing).where(
        CashClosing.organization_id == org, CashClosing.status == "pendiente_validacion",
        CashClosing.day < p.start)).scalar_one()
    if n:
        return False, f"{n} cierre(s) de caja anteriores al lunes pendientes de validar."
    return True, "Todos los cierres de caja hasta el domingo están validados."


def _report_reviewed(db, org, kind: str, start: date) -> tuple[bool, str]:
    r = db.execute(select(AccountingReport).where(AccountingReport.organization_id == org, AccountingReport.kind == kind,
                                                  AccountingReport.period_from == start)
                   .order_by(AccountingReport.version.desc()).limit(1)).scalar_one_or_none()
    if r is None:
        return False, f"El informe {kind} aún no se ha generado."
    if r.reviewed_by is None:
        return False, f"Informe {kind} «{r.label}» generado, pendiente de revisar."
    who = db.get(UserAccount, r.reviewed_by).full_name
    return True, f"Informe {kind} «{r.label}» revisado por {who}."


def chk_week_report(db, org, p: Period):
    return _report_reviewed(db, org, "semanal", p.start - timedelta(days=7))


def chk_quincena_report(db, org, p: Period):
    return _report_reviewed(db, org, "quincenal", p.start)


def chk_month_statements(db, org, p: Period):
    return _statements_until(db, org, p.end)


def chk_month_reconcile(db, org, p: Period):
    ok, ev = _statements_until(db, org, p.end)
    if not ok:
        return False, "Primero hay que importar los extractos de fin de mes. " + ev
    n = db.execute(select(func.count()).select_from(BankMovement).where(
        BankMovement.organization_id == org, BankMovement.status.in_(OPEN_MOV),
        BankMovement.booking_date >= p.start, BankMovement.booking_date <= p.end)).scalar_one()
    if n:
        return False, f"{n} movimiento(s) de {p.label} sin conciliar ni justificar."
    total = db.execute(select(func.count()).select_from(BankMovement).where(
        BankMovement.organization_id == org, BankMovement.booking_date >= p.start, BankMovement.booking_date <= p.end)).scalar_one()
    return True, f"{total} movimiento(s) de {p.label}: todos conciliados, traspasos o justificados."


def chk_month_docs(db, org, p: Period):
    inv = db.execute(select(func.count()).select_from(SupplierInvoice).where(
        SupplierInvoice.organization_id == org, SupplierInvoice.status == "recibida",
        SupplierInvoice.issue_date >= p.start, SupplierInvoice.issue_date <= p.end)).scalar_one()
    slips = list(db.execute(select(EmployeeDocument).join(Employee, Employee.id == EmployeeDocument.employee_id).where(
        Employee.organization_id == org, EmployeeDocument.kind == "nomina", EmployeeDocument.period == p.key,
        EmployeeDocument.status != "rechazado")).scalars())
    unconfirmed = sum(1 for d in slips if d.status != "valido" or not d.confirmed)
    problems = []
    if inv:
        problems.append(f"{inv} factura(s) de {p.label} sin validar")
    if unconfirmed:
        problems.append(f"{unconfirmed} nómina(s) de {p.label} sin confirmar por RRHH")
    if problems:
        return False, "; ".join(problems) + "."
    return True, f"Facturas de {p.label} validadas y {len(slips)} nómina(s) confirmadas."


def _close(db, org, p: Period) -> MonthClose | None:
    return db.execute(select(MonthClose).where(MonthClose.organization_id == org, MonthClose.month == p.key,
                                               MonthClose.status != "sustituido")
                      .order_by(MonthClose.revision.desc()).limit(1)).scalar_one_or_none()


def chk_month_close(db, org, p: Period):
    c = _close(db, org, p)
    if c is None:
        return False, f"Cierre de {p.label} sin preparar."
    if c.status == "borrador":
        return False, f"Cierre de {p.label} (revisión {c.revision}) preparado, pendiente de dar por revisado."
    return True, f"Cierre de {p.label} revisión {c.revision} {c.status}."


def chk_month_approve(db, org, p: Period):
    c = _close(db, org, p)
    if c is None or c.status != "aprobado":
        return False, f"Cierre de {p.label} sin aprobar por Dirección."
    return True, f"Cierre de {p.label} aprobado (huella {c.figures_sha256[:12]})."


def chk_month_report(db, org, p: Period):
    return _report_reviewed(db, org, "mensual", p.start)


STEPS: tuple[Step, ...] = (
    Step("d_extractos", "diaria", "Importar los extractos del día anterior",
         "Contabilidad → Banco y conciliación: importe el extracto de cada cuenta hasta el último día laborable.",
         "bank.import", lambda p: p.start, chk_daily_statements, agenda=False),
    Step("d_conciliar", "diaria", "Revisar las conciliaciones pendientes",
         "Contabilidad → Pendientes: valide o corrija las propuestas; que no quede nada de hace más de 2 días.",
         "bank.reconcile", lambda p: p.start, chk_daily_reconcile, agenda=False),
    Step("s_facturas", "semanal", "Validar las facturas recibidas",
         "Proveedores y facturas → «Por validar»: revise datos, actividad y oficina de cada factura.",
         "invoice.validate", lambda p: p.start, chk_week_invoices),
    Step("s_pagos", "semanal", "Programar los pagos de la semana",
         "Tesorería y remesas: incluya en una remesa las facturas vencidas o que vencen en 7 días.",
         "treasury.propose", lambda p: p.start + timedelta(days=1), chk_week_payments),
    Step("s_cajas", "semanal", "Validar los cierres de caja de la semana",
         "Economía o Recepción → cierres pendientes: valide los de la semana anterior (nunca los propios).",
         "cash.close.validate", lambda p: p.start + timedelta(days=1), chk_week_cash),
    Step("s_informe", "semanal", "Revisar el informe semanal",
         "Contabilidad → Informes: lea el informe de la semana anterior y márquelo como revisado.",
         "accounting.close.approve", lambda p: p.start + timedelta(days=1), chk_week_report),
    Step("q_informe", "quincenal", "Revisar el informe quincenal",
         "Contabilidad → Informes: lea el informe de la quincena y márquelo como revisado.",
         "accounting.close.approve", lambda p: business(p.opens + timedelta(days=1)), chk_quincena_report),
    Step("m_extractos", "mensual", "Días 1–2 · Extractos de fin de mes de todas las cuentas",
         "Importe el extracto de cada cuenta hasta el último día del mes.",
         "bank.import", lambda p: nth_day(p, 2), chk_month_statements),
    Step("m_conciliar", "mensual", "Día 3 · Conciliar el mes",
         "Que no quede ningún movimiento del mes sin conciliar, sin traspaso o sin justificar.",
         "bank.reconcile", lambda p: nth_day(p, 3), chk_month_reconcile),
    Step("m_documentos", "mensual", "Día 4 · Nóminas confirmadas y facturas del mes validadas",
         "Valide las facturas del mes; RRHH debe haber confirmado las nóminas.",
         "invoice.validate", lambda p: nth_day(p, 4), chk_month_docs),
    Step("m_cierre", "mensual", "Día 5 · Preparar y revisar el cierre provisional",
         "Cierre del mes: prepárelo y dele por revisado (explique los pendientes en la nota).",
         "accounting.close", lambda p: nth_day(p, 5), chk_month_close),
    Step("m_aprobar", "mensual", "Aprobar el cierre del mes",
         "Cierre del mes: revise las cifras y apruébelo (queda congelado).",
         "accounting.close.approve", lambda p: nth_day(p, 7), chk_month_approve),
    Step("m_informe", "mensual", "Revisar el informe mensual",
         "Contabilidad → Informes: lea el informe del mes y márquelo como revisado.",
         "accounting.close.approve", lambda p: nth_day(p, 7), chk_month_report),
)
BY_CODE = {s.code: s for s in STEPS}


def period_for(step: Step, key: str) -> Period:
    if step.cadence == "diaria":
        return day_period(date.fromisoformat(key))
    if step.cadence == "semanal":
        y, w = key.split("-W")
        return week_period(date.fromisocalendar(int(y), int(w), 1))
    if step.cadence == "quincenal":
        return quincena_period(date.fromisoformat(key[:7] + "-01"), int(key[-1]))
    return month_period(date.fromisoformat(key + "-01"))


def current_periods(step: Step, today: date) -> list[Period]:
    if step.cadence == "diaria":
        return [day_period(today)] if today.weekday() < 5 else []
    if step.cadence == "semanal":
        return [week_period(today)]
    if step.cadence == "quincenal":
        return [last_quincena(today)]
    return [prev_month_period(today)]


# ---------------------------------------------------------------- responsables
def users_with(db: Session, org, perm: str) -> list[UserAccount]:
    now = datetime.now(UTC)
    q = (select(UserAccount).join(Membership, Membership.user_id == UserAccount.id)
         .join(RolePermission, RolePermission.role_id == Membership.role_id)
         .where(Membership.organization_id == org, Membership.status == "activa",
                (Membership.valid_to.is_(None)) | (Membership.valid_to > now), RolePermission.permission == perm,
                UserAccount.status == "activo").distinct().order_by(UserAccount.full_name))
    return list(db.execute(q).scalars())


def owner_for(db: Session, org, step: Step) -> UserAccount | None:
    row = db.execute(select(RoutineOwner).where(RoutineOwner.organization_id == org, RoutineOwner.step == step.code)).scalar_one_or_none()
    if row is not None:
        u = db.get(UserAccount, row.user_id)
        if u and u.status == "activo" and u.id in {x.id for x in users_with(db, org, step.perm)}:
            return u
    cands = users_with(db, org, step.perm)
    return cands[0] if len(cands) == 1 else None


# ---------------------------------------------------------------- sincronizar
def _task_for(db: Session, item: RoutineItem, step: Step, owner: UserAccount) -> Task:
    t = Task(organization_id=item.organization_id, case_id=None, title=f"Rutina Contabilidad · {step.title} ({item.period_label})"[:200],
             description=f"{step.how}\nSe cierra sola cuando el sistema compruebe que está hecho.", kind="gestion",
             priority="alta" if step.cadence == "mensual" else "media", assignee_id=owner.id,
             due_at=datetime.combine(item.due_date, time(9, 0), tzinfo=MADRID).astimezone(UTC), created_by=owner.id)
    db.add(t)
    db.flush()
    db.add(TaskEvent(task_id=t.id, actor_user_id=owner.id, kind="creada", to_status="pendiente", new_due_at=t.due_at,
                     reason="Creada por la rutina de Contabilidad"))
    return t


def _close_task(db: Session, item: RoutineItem, status: str, reason: str) -> None:
    t = db.get(Task, item.task_id) if item.task_id else None
    if t is None or t.status in ("completada", "anulada"):
        return
    before = t.status
    t.status, t.version = status, t.version + 1
    if status == "completada":
        t.completed_at = datetime.now(UTC)
    db.add(TaskEvent(task_id=t.id, actor_user_id=t.assignee_id, kind="estado", from_status=before, to_status=status,
                     reason=reason[:500]))


def ensure(db: Session, org, today: date) -> int:
    created = 0
    for step in STEPS:
        for per in current_periods(step, today):
            if per.opens > today:
                continue
            if db.execute(select(RoutineItem.id).where(RoutineItem.organization_id == org, RoutineItem.step == step.code,
                                                       RoutineItem.period == per.key)).first():
                continue
            owner = owner_for(db, org, step)
            item = RoutineItem(organization_id=org, step=step.code, cadence=step.cadence, period=per.key,
                               period_label=per.label, due_date=step.due(per), status="pendiente",
                               owner_id=owner.id if owner else None)
            ok, evidence = step.check(db, org, per)
            item.evidence = evidence[:500]
            if ok:  # ya estaba hecho al abrir el periodo: sin tarea, y sin medir puntualidad
                item.status, item.done_at, item.on_time = "hecho", datetime.now(UTC), None
            db.add(item)
            db.flush()
            if not ok and step.agenda and owner is not None:
                item.task_id = _task_for(db, item, step, owner).id
            created += 1
    return created


def evaluate(db: Session, org, today: date) -> int:
    done = 0
    now = datetime.now(UTC)
    for item in db.execute(select(RoutineItem).where(RoutineItem.organization_id == org,
                                                     RoutineItem.status == "pendiente")).scalars():
        step = BY_CODE.get(item.step)
        if step is None:
            continue
        ok, evidence = step.check(db, org, period_for(step, item.period))
        item.evidence = evidence[:500]
        if ok:
            # Puntualidad solo si el paso existía antes de su fecha (al instalar, lo ya vencido no cuenta como tarde)
            measurable = item.created_at.astimezone(MADRID).date() <= item.due_date
            item.status, item.done_at, item.on_time = "hecho", now, (today <= item.due_date) if measurable else None
            _close_task(db, item, "completada", f"Comprobado por la rutina de Contabilidad: {evidence}")
            done += 1
    return done


def sync(db: Session, org, today: date | None = None) -> dict:
    today = today or datetime.now(MADRID).date()
    created = ensure(db, org, today)
    done = evaluate(db, org, today)
    return {"creados": created, "comprobados": done}


def mark_na(db: Session, item: RoutineItem, user_id, reason: str) -> None:
    item.status, item.na_by, item.na_reason, item.done_at = "no_aplica", user_id, reason[:500], datetime.now(UTC)
    _close_task(db, item, "anulada", f"No aplica: {reason}")


def compliance(db: Session, org, start: date, end: date) -> dict:
    """Cumplimiento de la rutina con fecha objetivo dentro del periodo (para los informes)."""
    today = datetime.now(MADRID).date()
    rows = list(db.execute(select(RoutineItem).where(RoutineItem.organization_id == org, RoutineItem.due_date >= start,
                                                     RoutineItem.due_date <= end).order_by(RoutineItem.due_date)).scalars())
    out = {"total": len(rows), "a_tiempo": 0, "tarde": 0, "pendientes": 0, "vencidos": 0, "no_aplica": 0, "sin_medir": 0, "vencidos_medibles": 0,
           "por_persona": {},
           "vencidos_detalle": []}
    for r in rows:
        who = db.get(UserAccount, r.owner_id).full_name if r.owner_id else "Sin responsable"
        per = out["por_persona"].setdefault(who, {"total": 0, "a_tiempo": 0, "tarde": 0, "pendientes": 0})
        per["total"] += 1
        if r.status == "hecho" and r.on_time is None:
            out["sin_medir"] += 1
        elif r.status == "hecho":
            key = "a_tiempo" if r.on_time else "tarde"
            out[key] += 1
            per[key] += 1
        elif r.status == "no_aplica":
            out["no_aplica"] += 1
        else:
            out["pendientes"] += 1
            per["pendientes"] += 1
            if r.due_date < today:
                out["vencidos"] += 1
                if r.created_at.astimezone(MADRID).date() <= r.due_date:
                    out["vencidos_medibles"] += 1
                step = BY_CODE.get(r.step)
                out["vencidos_detalle"].append({"paso": step.title if step else r.step, "periodo": r.period_label,
                                                "fecha": r.due_date.isoformat(), "responsable": who, "motivo": r.evidence})
    # Cumplimiento = a tiempo / (a tiempo + tarde + vencidos). Lo que aún no ha llegado a su fecha no cuenta, ni lo que
    # ya estaba vencido al instalar la rutina.
    eval_n = out["a_tiempo"] + out["tarde"] + out["vencidos_medibles"]
    out["cumplimiento_pct"] = None if eval_n == 0 else round(out["a_tiempo"] * 100 / eval_n, 1)
    return out
