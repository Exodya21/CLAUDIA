"""Cierre provisional del mes y cuadro de mando (DR-CON-8, DR-CON-5, DR-CON-3).

Cifras deterministas (sumas de registros, en céntimos) separadas por actividad y oficina, con su comparación con el
mes anterior, los pendientes que impiden darlo por bueno y un indicador de fiabilidad. No es la contabilidad oficial:
no hay asientos (T-40) ni criterio fiscal; el IVA soportado es el dato de las facturas.

Reglas de asignación:
- Actividad de ingresos y cobros: materia del expediente (nacionalidad cuenta como extranjería); un cobro de consulta
  sin expediente queda «sin asignar» (se ve, no se reparte a ojo).
- Facturas de proveedores: la actividad y oficina que se les asignan al validarlas. Gastos de empleados: «compartida».
- Coste de personal: devengado de las nóminas CONFIRMADAS por RRHH, por departamento (Laboral → laboral,
  Extranjería/Nacionalidad → extranjería, resto → compartida) y sede de la ficha. Sin cotizaciones de empresa.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Branch, CaseFile, Department, Organization
from ..models_accounting import SupplierInvoice
from ..models_bank import BankAccount, BankMovement
from ..models_economy import CashClosing, Charge, Expense, Payment
from ..models_hr import Employee, EmployeeDocument
from .treasury import account_balance, cash_balances

MADRID = ZoneInfo("Europe/Madrid")
ACTIVITIES = ("laboral", "extranjeria", "compartida", "sin_asignar")
LINES = ("ingresos_devengados", "cobros", "gastos_proveedores", "gastos_empleados", "coste_personal", "pagos",
         "resultado")
MATERIA = {"laboral": "laboral", "extranjeria": "extranjeria", "nacionalidad": "extranjeria"}
DEPT = {"LAB": "laboral", "EXT": "extranjeria", "NAC": "extranjeria"}
DEVIATION_PCT = 15


def month_bounds(month: str) -> tuple[date, date, datetime, datetime]:
    y, m = int(month[:4]), int(month[5:])
    first = date(y, m, 1)
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    start = datetime.combine(first, time.min, tzinfo=MADRID).astimezone(UTC)
    end = datetime.combine(nxt, time.min, tzinfo=MADRID).astimezone(UTC)
    return first, nxt, start, end


def prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:])
    return f"{y - (m == 1)}-{(m - 2) % 12 + 1:02d}"


def _empty() -> dict:
    return {k: 0 for k in LINES}


def compute(db: Session, org_id, month: str, with_previous: bool = True) -> dict:
    first, nxt, _, _ = month_bounds(month)
    out = period_figures(db, org_id, first, nxt, payroll_months=[month])
    out["month"] = month
    if with_previous:
        prev = compute(db, org_id, prev_month(month), with_previous=False)
        out["previous"] = {"month": prev["month"], "total": prev["total"]}
        out["deviations"] = deviations(out["total"], prev["total"])
    return out


def deviations(cur: dict, prev: dict) -> dict:
    dev: dict = {}
    for line in LINES:
        a, b = cur[line], prev[line]
        if b and abs(a - b) * 100 >= DEVIATION_PCT * abs(b):
            dev[line] = round((a - b) * 100 / abs(b), 1)
        elif not b and a:
            dev[line] = None  # aparece sin base de comparación
    return dev


def period_figures(db: Session, org_id, first: date, nxt: date, payroll_months: list[str]) -> dict:
    """Cifras de [first, nxt) por actividad y oficina. Las nóminas son mensuales: solo entran los meses indicados."""
    start = datetime.combine(first, time.min, tzinfo=MADRID).astimezone(UTC)
    end = datetime.combine(nxt, time.min, tzinfo=MADRID).astimezone(UTC)
    org = db.get(Organization, org_id)
    branches = {b.id: b.name for b in db.execute(select(Branch).where(Branch.organization_id == org_id)).scalars()}
    by_act = {a: _empty() for a in ACTIVITIES}
    by_branch: dict[str, dict] = {}
    total = _empty()
    iva = 0
    heads_act: dict[str, int] = {}
    heads_branch: dict[str, int] = {}

    def add(line: str, cents: int, act: str, branch_id) -> None:
        by_act[act][line] += cents
        bname = branches.get(branch_id, "Sin oficina")
        by_branch.setdefault(bname, _empty())[line] += cents
        total[line] += cents

    case_cache: dict = {}

    def case(cid):
        if cid not in case_cache:
            case_cache[cid] = db.get(CaseFile, cid) if cid else None
        return case_cache[cid]

    # Ingresos devengados: cargos vigentes creados en el mes
    for c in db.execute(select(Charge).where(Charge.organization_id == org_id, Charge.status == "vigente",
                                             Charge.created_at >= start, Charge.created_at < end)).scalars():
        cf = case(c.case_id)
        add("ingresos_devengados", c.amount_cents, MATERIA.get(cf.materia, "compartida") if cf else "sin_asignar",
            cf.branch_id if cf else None)
    # Cobros: no anulados, recibidos en el mes (confirmados y pendientes de confirmar)
    cobros_conf = cobros_total = 0
    for x in db.execute(select(Payment).where(Payment.organization_id == org_id, Payment.status != "anulado",
                                              Payment.received_at >= start, Payment.received_at < end)).scalars():
        cf = case(x.case_id)
        add("cobros", x.amount_cents, MATERIA.get(cf.materia, "compartida") if cf else "sin_asignar",
            x.branch_id or (cf.branch_id if cf else None))
        cobros_total += 1
        cobros_conf += x.status == "confirmado"
    # Gastos de proveedores (base imponible) por fecha de factura; IVA como dato aparte
    inv_total = inv_valid = 0
    for inv in db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == org_id,
                                                        SupplierInvoice.status != "rechazada",
                                                        SupplierInvoice.issue_date >= first,
                                                        SupplierInvoice.issue_date < nxt)).scalars():
        inv_total += 1
        if inv.status == "recibida":
            continue  # sin validar no entra en cifras; cuenta como pendiente
        inv_valid += 1
        add("gastos_proveedores", inv.base_cents, inv.activity, inv.branch_id)
        iva += inv.vat_cents
    # Pagos: facturas pagadas (conciliadas con el banco) en el mes
    for inv in db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == org_id,
                                                        SupplierInvoice.status == "pagada",
                                                        SupplierInvoice.paid_at >= first,
                                                        SupplierInvoice.paid_at < nxt)).scalars():
        add("pagos", inv.total_cents, inv.activity, inv.branch_id)
    # Gastos de empleados aprobados (importe sin la cuota de IVA leída)
    for e in db.execute(select(Expense).where(Expense.organization_id == org_id,
                                              Expense.status.in_(("aprobado", "conciliado")),
                                              Expense.expense_date >= first, Expense.expense_date < nxt)).scalars():
        add("gastos_empleados", (e.amount_cents or 0) - (e.vat_cents or 0), "compartida", e.branch_id)
        iva += e.vat_cents or 0
    # Coste de personal (nóminas confirmadas por RRHH)
    slips_total = slips_ok = 0
    for d, emp in db.execute(select(EmployeeDocument, Employee).join(Employee, Employee.id == EmployeeDocument.employee_id)
                             .where(Employee.organization_id == org_id, EmployeeDocument.kind == "nomina",
                                    EmployeeDocument.period.in_(payroll_months or ["-"]), EmployeeDocument.status != "rechazado")).all():
        slips_total += 1
        if d.status != "valido" or not d.confirmed:
            continue
        slips_ok += 1
        dpt = db.get(Department, emp.department_id) if emp.department_id else None
        act = DEPT.get(dpt.code if dpt else "", "compartida")
        add("coste_personal", int(d.confirmed.get("devengado_cents") or 0), act, emp.branch_id)
        heads_act[act] = heads_act.get(act, 0) + 1
        bname = branches.get(emp.branch_id, "Sin oficina")
        heads_branch[bname] = heads_branch.get(bname, 0) + 1
    for bucket in [*by_act.values(), *by_branch.values(), total]:
        bucket["resultado"] = (bucket["ingresos_devengados"] - bucket["gastos_proveedores"] - bucket["gastos_empleados"]
                               - bucket["coste_personal"])
    # Tesorería a fin de mes
    last_day = nxt - timedelta(days=1)
    accounts = []
    for a in db.execute(select(BankAccount).where(BankAccount.organization_id == org_id).order_by(BankAccount.name)).scalars():
        b = account_balance(db, a, until=last_day)
        accounts.append({"name": a.name, "iban_last4": a.iban_last4, "balance_cents": b["balance_cents"], "as_of": b["as_of"]})
    cash = cash_balances(db, org_id, until=end)
    # Pendientes y fiabilidad
    movs = list(db.execute(select(BankMovement.status).where(BankMovement.organization_id == org_id,
                                                             BankMovement.booking_date >= first,
                                                             BankMovement.booking_date < nxt)).scalars())
    mov_done = sum(1 for s in movs if s in ("conciliado", "traspaso", "ignorado"))
    closings = list(db.execute(select(CashClosing.status).where(CashClosing.organization_id == org_id,
                                                                CashClosing.day >= first, CashClosing.day < nxt)).scalars())
    overdue = db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == org_id,
                                                       SupplierInvoice.status.in_(("validada", "programada")),
                                                       SupplierInvoice.due_date < min(nxt, date.today()))).scalars().all()
    pending = {
        "movimientos_sin_conciliar": len(movs) - mov_done,
        "facturas_sin_validar": inv_total - inv_valid,
        "cobros_sin_confirmar": cobros_total - cobros_conf,
        "cierres_caja_sin_validar": sum(1 for s in closings if s == "pendiente_validacion"),
        "nominas_sin_confirmar": slips_total - slips_ok,
        "facturas_vencidas_sin_pagar": len(overdue),
        "accounts_sin_extracto": [a["name"] for a in accounts if a["as_of"] is None or a["as_of"] < (last_day - timedelta(days=3)).isoformat()],
    }

    def pct(a: int, b: int):
        return None if b == 0 else round(a * 100 / b, 1)
    indicators = {"movimientos_conciliados_pct": pct(mov_done, len(movs)), "cobros_confirmados_pct": pct(cobros_conf, cobros_total),
                  "facturas_validadas_pct": pct(inv_valid, inv_total), "nominas_confirmadas_pct": pct(slips_ok, slips_total),
                  "cierres_caja_validados_pct": pct(sum(1 for s in closings if s == "validado"), len(closings))}
    vals = [v for v in indicators.values() if v is not None]
    level = "sin_datos" if not vals else "alta" if min(vals) >= 95 else "media" if min(vals) >= 80 else "baja"
    out = {
        "organization": org.name, "currency": org.currency, "from": first.isoformat(), "to": (nxt - timedelta(days=1)).isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "total": total, "by_activity": by_act, "by_branch": by_branch,
        "headcount": {"by_activity": heads_act, "by_branch": heads_branch, "total": sum(heads_act.values())}, "iva_soportado_dato_cents": iva,
        "treasury": {"accounts": accounts, "cash_cents": cash,
                     "bank_cents": sum(a["balance_cents"] or 0 for a in accounts)},
        "pending": pending, "reliability": {"indicators": indicators, "level": level},
        "notes": ["Resultado provisional de gestión: no sustituye la contabilidad de la gestoría ni contiene asientos (T-40).",
                  "Coste de personal: devengado de las nóminas confirmadas por RRHH; sin cotizaciones a cargo de la empresa.",
                  "Gastos sin IVA: el IVA soportado se muestra como dato leído de las facturas, sin criterio fiscal."],
    }
    if not payroll_months:
        out["notes"][1] = "Coste de personal: las nóminas son mensuales; se incluyen en el informe mensual."
    return out


def digest(figures: dict) -> str:
    stable = {k: v for k, v in figures.items() if k != "generated_at"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


MIN_GROUP = 3  # menos de 3 personas en una celda: el coste no se muestra separado a quien no ve salarios


def for_viewer(figures: dict, can_salary: bool) -> dict:
    """Quien no tiene `hr.salary` no ve el coste de personal (ni el resultado) de grupos de menos de 3 personas."""
    if can_salary:
        return figures
    f = json.loads(json.dumps(figures))
    for dim in ("by_activity", "by_branch"):
        heads = f.get("headcount", {}).get(dim, {})
        for key, bucket in f.get(dim, {}).items():
            n = heads.get(key, 0)
            if 0 < n < MIN_GROUP:
                bucket["coste_personal"] = None
                bucket["resultado"] = None
    f["personal_agrupado"] = True
    return f
