"""Informes de Contabilidad semanales (lunes), quincenales (días 1 y 16) y mensuales (día 5).

Cada informe es una FOTO inmutable con su huella: cifras del periodo por actividad y oficina (las mismas reglas que el
cierre), comparación con el periodo anterior, tesorería y previsión de pagos en el momento de generarlo, remesas,
pendientes y el cumplimiento de la rutina de trabajo. Volver a generarlo crea una versión nueva; la anterior se conserva.
El correo de aviso no lleva cifras: solo dice que hay un informe y dónde verlo.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..models import Organization
from ..models_accounting import AccountingReport, MonthClose, PaymentBatch
from ..services import notify, pdfwrite
from . import close as closing
from . import routine, treasury

KINDS = ("semanal", "quincenal", "mensual")
KIND_LABEL = {"semanal": "Informe semanal", "quincenal": "Informe quincenal", "mensual": "Informe mensual"}
LINE_LABELS = {"ingresos_devengados": "Ingresos devengados", "cobros": "Cobros", "gastos_proveedores": "Gastos de proveedores (base)",
               "gastos_empleados": "Gastos de empleados (sin IVA)", "coste_personal": "Coste de personal (devengado)",
               "pagos": "Pagos a proveedores", "resultado": "Resultado provisional"}
PEND_LABELS = {"movimientos_sin_conciliar": "Movimientos del banco sin conciliar", "facturas_sin_validar": "Facturas sin validar",
               "cobros_sin_confirmar": "Cobros sin confirmar", "cierres_caja_sin_validar": "Cierres de caja sin validar",
               "nominas_sin_confirmar": "Nóminas sin confirmar", "facturas_vencidas_sin_pagar": "Facturas vencidas sin pagar"}


def period_of(kind: str, any_day: date) -> tuple[date, date, str]:
    """Periodo que CONTIENE `any_day`: semana lunes–domingo, quincena 1–15 / 16–fin, o mes."""
    if kind == "semanal":
        start = any_day - timedelta(days=any_day.weekday())
        end = start + timedelta(days=6)
        return start, end, f"semana del {start:%d/%m} al {end:%d/%m/%Y}"
    if kind == "quincenal":
        p = routine.quincena_period(any_day.replace(day=1), 1 if any_day.day <= 15 else 2)
        return p.start, p.end, p.label
    p = routine.month_period(any_day.replace(day=1))
    return p.start, p.end, p.label


def previous(kind: str, start: date) -> tuple[date, date, str]:
    return period_of(kind, start - timedelta(days=1))


def due(today: date) -> list[tuple[str, date, date, str]]:
    """Informes que ya deberían existir: semana anterior (desde el lunes), última quincena cerrada y mes anterior
    (desde el día 5, cuando el manual pide el cierre provisional)."""
    out = [("semanal", *previous("semanal", today - timedelta(days=today.weekday())))]
    q = routine.last_quincena(today)
    out.append(("quincenal", q.start, q.end, q.label))
    if today.day >= 5:
        out.append(("mensual", *previous("mensual", today.replace(day=1))))
    return out


def _batches(db: Session, org, start: date, end: date) -> dict:
    rows = list(db.execute(select(PaymentBatch).where(PaymentBatch.organization_id == org,
                                                      PaymentBatch.execution_date >= start,
                                                      PaymentBatch.execution_date <= end)).scalars())
    out = {"num": len(rows), "por_estado": {}}
    for b in rows:
        e = out["por_estado"].setdefault(b.status, {"num": 0, "total_cents": 0})
        e["num"] += 1
        e["total_cents"] += b.total_cents
    return out


def build(db: Session, org, kind: str, start: date, end: date, label: str) -> dict:
    nxt = end + timedelta(days=1)
    payroll = [f"{start:%Y-%m}"] if kind == "mensual" else []
    f = closing.period_figures(db, org, start, nxt, payroll_months=payroll)
    pstart, pend, plabel = previous(kind, start)
    prev = closing.period_figures(db, org, pstart, pend + timedelta(days=1),
                                  payroll_months=[f"{pstart:%Y-%m}"] if kind == "mensual" else [])
    f.update({
        "kind": kind, "label": label,
        "previous": {"label": plabel, "total": prev["total"]},
        "deviations": closing.deviations(f["total"], prev["total"]),
        "forecast": {k: v for k, v in treasury.forecast(db, org).items() if k in ("payables", "payables_total_cents", "note")},
        "batches": _batches(db, org, start, end),
        "routine": routine.compliance(db, org, start, end),
    })
    if kind == "mensual":
        c = db.execute(select(MonthClose).where(MonthClose.organization_id == org, MonthClose.month == f"{start:%Y-%m}",
                                                MonthClose.status != "sustituido").order_by(MonthClose.revision.desc())
                       .limit(1)).scalar_one_or_none()
        f["close"] = None if c is None else {"status": c.status, "revision": c.revision, "huella": c.figures_sha256[:12]}
        f["notes"].append("Si el cierre del mes aún no está aprobado, las cifras de este informe son provisionales.")
    return f


def create(db: Session, org, kind: str, start: date, end: date, label: str, user_id=None, ctx=None) -> AccountingReport:
    last = db.execute(select(AccountingReport).where(AccountingReport.organization_id == org, AccountingReport.kind == kind,
                                                     AccountingReport.period_from == start)
                      .order_by(AccountingReport.version.desc()).limit(1)).scalar_one_or_none()
    figures = build(db, org, kind, start, end, label)
    r = AccountingReport(organization_id=org, kind=kind, period_from=start, period_to=end, label=label,
                         version=(last.version + 1) if last else 1, figures=figures, figures_sha256=closing.digest(figures),
                         generated_by=user_id)
    db.add(r)
    db.flush()
    audit.record(db, actor_id=user_id, action="accounting.report.generate", resource_type="accounting_report",
                 resource_id=r.id, organization_id=org,
                 after={"tipo": kind, "periodo": label, "version": r.version, "huella": r.figures_sha256,
                        "origen": "persona" if user_id else "rutina automática"},
                 ip=getattr(ctx, "ip", None), request_id=getattr(ctx, "request_id", None))
    notify_people(db, r)
    return r


def notify_people(db: Session, r: AccountingReport) -> int:
    """Correo SIN cifras a quien puede leer Contabilidad en la entidad (sale solo si hay proveedor de correo, T-33)."""
    org = db.get(Organization, r.organization_id)
    url = f"{get_settings().web_origin.rstrip('/')}/contabilidad?tab=informes"
    n = 0
    for u in routine.users_with(db, r.organization_id, "accounting.read"):
        if not u.email:
            continue
        body = (f"Buenos días.\n\nYa está disponible el {KIND_LABEL[r.kind].lower()} de Contabilidad de {org.name} "
                f"({r.label}).\nPuede consultarlo, descargarlo y marcarlo como revisado en SISTEMA PROPIO:\n{url}\n\n"
                "Este correo no incluye cifras. Por seguridad, acceda con su usuario.")
        if notify.enqueue(db, organization_id=r.organization_id, purpose="informe_contabilidad", to=u.email,
                          subject=f"{KIND_LABEL[r.kind]} de Contabilidad · {r.label}", body=body,
                          idem_key=f"acc-report:{r.id}:{u.id}"):
            n += 1
    return n


def ensure_due(db: Session, org, today: date) -> list[AccountingReport]:
    made = []
    for kind, start, end, label in due(today):
        exists = db.execute(select(AccountingReport.id).where(AccountingReport.organization_id == org,
                                                               AccountingReport.kind == kind,
                                                               AccountingReport.period_from == start)).first()
        if not exists:
            made.append(create(db, org, kind, start, end, label))
    return made


# ---------------------------------------------------------------- salida
def _eur(v) -> str:
    if v is None:
        return "agrupado"
    return f"{v / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def pdf(r: AccountingReport, f: dict, org_name: str) -> bytes:
    lines: list[tuple[str, str]] = [("h", f"{KIND_LABEL[r.kind]} de Contabilidad · {r.label}"),
                                    ("s", f"{org_name} · versión {r.version} · generado el "
                                          f"{r.generated_at.astimezone(routine.MADRID):%d/%m/%Y %H:%M} · huella {r.figures_sha256[:16]}"),
                                    ("n", ""), ("b", f"Resultado del periodo (comparado con {f['previous']['label']})")]
    for k, lab in LINE_LABELS.items():
        dev = f.get("deviations", {}).get(k, "-")
        extra = "" if dev == "-" else (" · nuevo" if dev is None else f" · {dev:+} %")
        lines.append(("n", f"{lab}: {_eur(f['total'][k])}  (antes {_eur(f['previous']['total'][k])}){extra}"))
    lines += [("n", ""), ("b", "Por actividad")]
    for a, vals in f["by_activity"].items():
        lines.append(("n", f"{a.replace('_', ' ').capitalize()}: ingresos {_eur(vals['ingresos_devengados'])} · cobros "
                           f"{_eur(vals['cobros'])} · gastos {_eur(vals['gastos_proveedores'] + vals['gastos_empleados'])} · "
                           f"resultado {_eur(vals['resultado'])}"))
    lines += [("n", ""), ("b", "Por oficina")]
    for b, vals in f["by_branch"].items():
        lines.append(("n", f"{b}: ingresos {_eur(vals['ingresos_devengados'])} · cobros {_eur(vals['cobros'])} · "
                           f"resultado {_eur(vals['resultado'])}"))
    t = f["treasury"]
    lines += [("n", ""), ("b", "Tesorería y pagos"),
              ("n", (f"Bancos al {f['to']}: {_eur(t['bank_cents'])}" if any(a["balance_cents"] is not None for a in t["accounts"])
                     else "Bancos: sin extractos importados hasta esa fecha") + f" · cajas {_eur(t['cash_cents'])}")]
    pay = f["forecast"]["payables"]
    lines.append(("n", f"Pagos previstos al generar: vencido {_eur(pay['vencido'])} · 7 días {_eur(pay['7'])} · 8–30 días "
                       f"{_eur(pay['30'])} · 31–60 {_eur(pay['60'])} · 61–90 {_eur(pay['90'])}"))
    for st, v in f["batches"]["por_estado"].items():
        lines.append(("n", f"Remesas {st}: {v['num']} por {_eur(v['total_cents'])}"))
    lines += [("n", ""), ("b", "Pendientes")]
    for k, lab in PEND_LABELS.items():
        lines.append(("n", f"{lab}: {f['pending'].get(k, 0)}"))
    lines.append(("n", f"Fiabilidad de las cifras: {f['reliability']['level'].replace('_', ' ')}"))
    rt = f["routine"]
    lines += [("n", ""), ("b", "Rutina de trabajo"),
              ("n", f"{rt['total']} pasos con fecha en el periodo: {rt['a_tiempo']} a tiempo, {rt['tarde']} tarde, "
                    f"{rt['pendientes']} pendientes ({rt['vencidos']} vencidos), {rt['no_aplica']} no aplican. "
                    f"Cumplimiento: {'-' if rt['cumplimiento_pct'] is None else str(rt['cumplimiento_pct']) + ' %'}")]
    for who, v in rt["por_persona"].items():
        lines.append(("n", f"{who}: {v['a_tiempo']} a tiempo, {v['tarde']} tarde, {v['pendientes']} pendientes de {v['total']}"))
    for x in rt["vencidos_detalle"][:20]:
        lines.append(("s", f"Vencido · {x['paso']} ({x['periodo']}) · {x['responsable']} · {x['motivo'] or ''}"))
    if f.get("close") is not None or r.kind == "mensual":
        c = f.get("close")
        lines += [("n", ""), ("b", "Cierre del mes"),
                  ("n", "Sin preparar" if not c else f"Revisión {c['revision']} · {c['status']} · huella {c['huella']}")]
    lines += [("n", "")] + [("s", n) for n in f["notes"]]
    return pdfwrite.text_pdf(lines, footer=f"{KIND_LABEL[r.kind]} · {r.label} · documento interno, no es contabilidad oficial")


def to_csv(r: AccountingReport, f: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    acts = ["laboral", "extranjeria", "compartida", "sin_asignar"]

    def eur(v):
        return "" if v is None else f"{v / 100:.2f}".replace(".", ",")
    w.writerow([f"{KIND_LABEL[r.kind]} · {r.label} · versión {r.version} · huella {r.figures_sha256[:16]}"])
    w.writerow(["Concepto", "Laboral", "Extranjería", "Compartida", "Sin asignar", "Total", f["previous"]["label"]])
    for line, label in LINE_LABELS.items():
        w.writerow([label, *[eur(f["by_activity"][a][line]) for a in acts], eur(f["total"][line]),
                    eur(f["previous"]["total"][line])])
    w.writerow([])
    w.writerow(["Oficina", *LINE_LABELS.values()])
    for b, vals in f["by_branch"].items():
        w.writerow([b, *[eur(vals[k]) for k in LINE_LABELS]])
    w.writerow([])
    w.writerow(["Pendiente", "Número"])
    for k, lab in PEND_LABELS.items():
        w.writerow([lab, f["pending"].get(k, 0)])
    w.writerow([])
    rt = f["routine"]
    w.writerow(["Rutina", "Total", "A tiempo", "Tarde", "Pendientes", "Vencidos", "No aplica", "Cumplimiento %"])
    w.writerow(["Todas", rt["total"], rt["a_tiempo"], rt["tarde"], rt["pendientes"], rt["vencidos"], rt["no_aplica"],
                "" if rt["cumplimiento_pct"] is None else str(rt["cumplimiento_pct"]).replace(".", ",")])
    return ("﻿" + buf.getvalue()).encode()


def now() -> datetime:
    return datetime.now(UTC)
