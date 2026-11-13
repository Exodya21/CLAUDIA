"""RRHH (F5.3): reglas comunes. Acceso por función, lectura de nóminas, días laborables y saldo de vacaciones.

- Acceso: `hr.read`/`hr.manage`/`hr.salary` a nivel de entidad (RRHH, Dirección); `hr.leave.decide` de un líder
  solo para su departamento; `hr.self` solo para su propia ficha (vinculada a su usuario).
- La nómina se LEE para proponer periodo, devengado, deducciones y líquido; una persona lo confirma. No se calcula.
- Días laborables: lunes a viernes. Los festivos de cada sede no se descuentan todavía (T-49) y los días de
  vacaciones por año los fija el convenio de cada persona (T-50): el sistema no los inventa.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models_hr import Employee, LeaveRequest
from ..security.auth import Principal

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
DOC_KINDS = {"contrato": "Contrato", "anexo": "Anexo al contrato", "nomina": "Nómina", "certificado": "Certificado",
             "solicitud": "Solicitud", "baja": "Parte de baja", "otro": "Otro"}
LEAVE_KINDS = {"vacaciones": "Vacaciones", "asuntos_propios": "Asuntos propios", "permiso": "Permiso",
               "baja": "Baja médica", "otro": "Otro"}
RESTRICTED_DOCS = ("baja",)  # datos de salud: solo RRHH
SALARY_DOCS = ("nomina",)


def access(p: Principal, e: Employee) -> set[str]:
    """Qué puede hacer esta persona con esta ficha."""
    org = e.organization_id
    if org not in p.org_ids():
        return set()
    out: set[str] = set()
    if e.user_id and e.user_id == p.id and p.has(org, "hr.self"):
        out.add("self")
    for perm, key in (("hr.read", "read"), ("hr.manage", "manage"), ("hr.salary", "salary")):
        if p.has(org, perm):
            out.add(key)
    if p.has(org, "hr.manage") and p.has(org, "hr.leave.decide"):
        out.add("leave")
    elif any(m.department_id is not None and m.department_id == e.department_id
             for m in p.memberships_with(org, "hr.leave.decide")):
        out |= {"leave", "team"}
    if "manage" in out:
        out.add("read")
    return out


def working_days(start: date, end: date) -> int:
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def vacation_balance(db: Session, e: Employee, year: int | None = None) -> dict:
    year = year or date.today().year
    q = select(LeaveRequest.status, func.coalesce(func.sum(LeaveRequest.working_days), 0)).where(
        LeaveRequest.employee_id == e.id, LeaveRequest.kind == "vacaciones",
        func.extract("year", LeaveRequest.start_date) == year,
        LeaveRequest.status.in_(("aprobada", "solicitada"))).group_by(LeaveRequest.status)
    rows = {k: int(v) for k, v in db.execute(q).all()}
    total = e.vacation_days_year
    used, pending = rows.get("aprobada", 0), rows.get("solicitada", 0)
    return {"year": year, "total": total, "used": used, "pending": pending,
            "remaining": None if total is None else total - used - pending}


def overlaps(db: Session, e: Employee, start: date, end: date, exclude_id=None) -> list[LeaveRequest]:
    """Ausencias que coinciden en el mismo departamento y sede (para avisar, no para impedir)."""
    q = (select(LeaveRequest).join(Employee, Employee.id == LeaveRequest.employee_id)
         .where(Employee.organization_id == e.organization_id, Employee.branch_id == e.branch_id,
                Employee.department_id == e.department_id, Employee.id != e.id,
                LeaveRequest.status.in_(("aprobada", "solicitada")),
                LeaveRequest.start_date <= end, LeaveRequest.end_date >= start))
    if exclude_id:
        q = q.where(LeaveRequest.id != exclude_id)
    return list(db.execute(q).scalars())


# ------------------------------------------------------------------ lectura de nóminas (propone; no calcula)
def _num(s: str) -> int:
    return int(round(float(s.replace(".", "").replace(",", ".")) * 100))


def _fold(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


AMOUNT = r"(\d{1,3}(?:\.\d{3})*,\d{2})"


def read_payslip(text: str, e: Employee) -> dict:
    t = _fold(text)
    out: dict = {}
    m = re.search(r"PERIODO\W+(\d{2})/(\d{2})/(\d{4})\s*(?:-|A|AL)\s*(\d{2})/(\d{2})/(\d{4})", t)
    if m:
        out["periodo"] = f"{m.group(6)}-{m.group(5)}"
    else:
        m = re.search(r"\b(" + "|".join(x.upper() for x in MONTHS) + r")\s+(?:DE\s+)?(20\d{2})\b", t)
        if m:
            out["periodo"] = f"{m.group(2)}-{MONTHS.index(m.group(1).lower()) + 1:02d}"
    for key, rx in (("devengado_cents", r"TOTAL\s+DEVENGADO\W+" + AMOUNT),
                    ("deducciones_cents", r"TOTAL\s+A\s+DEDUCIR\W+" + AMOUNT),
                    ("liquido_cents", r"LIQUIDO\s+(?:TOTAL\s+)?A\s+PERCIBIR\W+" + AMOUNT)):
        m = re.search(rx, t)
        if m:
            out[key] = _num(m.group(1))
    if {"devengado_cents", "deducciones_cents", "liquido_cents"} <= out.keys():
        out["cuadra"] = out["devengado_cents"] - out["deducciones_cents"] == out["liquido_cents"]
    surname = _fold(e.family_names).split()[0] if e.family_names else ""
    out["titular_coincide"] = bool(surname) and surname in t
    found = sum(1 for k in ("periodo", "devengado_cents", "deducciones_cents", "liquido_cents") if k in out)
    out["confianza"] = "alta" if found == 4 and out.get("cuadra") and out["titular_coincide"] else (
        "media" if found >= 3 else "baja")
    return out


def mask_id(last4: str | None) -> str | None:
    return f"•••••{last4}" if last4 else None
