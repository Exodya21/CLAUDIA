"""Datos FICTICIOS de RRHH (F5.3): 5 fichas y sus nóminas, como pide el guion de Dirección para empezar.

Personas inventadas (apellidos «Demo», «Ficticio», «Prueba»), sin documentos reales. Las fechas se calculan desde
hoy para que haya avisos que probar: un contrato temporal que vence, un periodo de prueba que termina, una ficha
sin contrato y una diferencia de nómina. Idempotente: solo se carga si no hay ninguna ficha.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .hr import samples
from .hr.service import read_payslip, working_days
from .models import Branch, Department, Organization, UserAccount
from .models_hr import Employee, EmployeeDocument, LeaveRequest
from .services import receipts, vault


def _u(db: Session, username: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def _months_back(n: int) -> tuple[int, int]:
    d = date.today().replace(day=1)
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.year, d.month


def seed_hr(db: Session) -> None:
    from .seed import ORG_CO, ORG_ES

    es = db.execute(select(Organization).where(Organization.name == ORG_ES)).scalar_one_or_none()
    co = db.execute(select(Organization).where(Organization.name == ORG_CO)).scalar_one_or_none()
    if es is None or db.execute(select(func.count()).select_from(Employee)).scalar_one() > 0:
        return
    hr_user = _u(db, "rrhh.demo") or _u(db, "direccion.demo")
    today = date.today()

    def br(org, name):
        return db.execute(select(Branch).where(Branch.organization_id == org.id, Branch.name == name)).scalar_one()

    def dp(org, code):
        return db.execute(select(Department).where(Department.organization_id == org.id, Department.code == code)).scalar_one_or_none()

    people = [
        # org, sede, dpto, usuario, nombre, apellidos, categoría, puesto, contrato, jornada, horas, alta, fin, prueba, salario
        (es, "Barcelona", "LAB", "asesor.laboral.bcn", "Marcos", "Vidal Ficticio", "Titulado superior", "Asesor laboral",
         "indefinido", "completa", 40, date(2021, 3, 1), None, None, 2_800_000),
        (es, "Barcelona", "REC", "recepcion.bcn", "Laura", "Gómez Demo", "Auxiliar administrativo", "Recepcionista",
         "temporal", "completa", 40, today - timedelta(days=150), today + timedelta(days=20), None, 2_100_000),
        (es, "Madrid", "EXT", "asesor.extranjeria.mad", "Daniel", "Ortiz Prueba", "Titulado superior",
         "Asesor de extranjería", "indefinido", "completa", 40, today - timedelta(days=170), None,
         today + timedelta(days=10), 2_600_000),
        (es, "Valencia", "LAB", "gestor.laboral.vlc", "Sara", "Molina Ficticia", "Oficial administrativo",
         "Gestora laboral", "indefinido", "parcial", 30, date(2019, 9, 16), None, None, 1_950_000),
    ]
    if co is not None:
        people.append((co, "Bogotá (soporte)", "ATC", "soporte.colombia", "Andrés", "Ruiz Demo", "Analista",
                       "Soporte de atención (Colombia)", "indefinido", "completa", 47, date(2024, 2, 5), None, None,
                       3_600_000_000))
    ex = receipts.extractor()
    for i, (org, bname, dcode, uname, given, family, cat, job, ctype, wday, hours, start, end, trial, salary) in enumerate(people, 1):
        u = _u(db, uname)
        e = Employee(organization_id=org.id, code=f"EMP-{i:04d}", user_id=u.id if u else None, given_name=given,
                     family_names=family, email=f"{given.lower()}.{family.split()[0].lower()}@demo.invalid",
                     country="CO" if org is co else "ES", branch_id=br(org, bname).id,
                     department_id=dp(org, dcode).id if dp(org, dcode) else None, category=cat, job_title=job,
                     contract_type=ctype, workday=wday, weekly_hours=Decimal(hours), start_date=start,
                     contract_end_date=end, trial_end_date=trial, salary_annual_cents=salary,
                     vacation_days_year=22 if org is es else 15, is_synthetic=True, created_by=hr_user.id,
                     notes="Ficha FICTICIA de pruebas. Días de vacaciones pendientes de validar según convenio (T-50).")
        db.add(e)
        db.flush()
        if i != 5:  # la ficha de Colombia queda sin contrato para probar el aviso
            data = samples.contract_pdf(org.name, f"{given} {family}", job, ctype, start, end)
            path, sha = vault.store(data)
            db.add(EmployeeDocument(organization_id=org.id, employee_id=e.id, kind="contrato",
                                    original_name=f"contrato_{e.code}.pdf", mime="application/pdf", size_bytes=len(data),
                                    sha256=sha, file_path=path, status="valido", uploaded_by=hr_user.id,
                                    reviewed_by=hr_user.id, reviewed_at=datetime.now(UTC)))
        monthly = salary // 14 if org is es else salary // 12
        for back in (2, 1):
            y, m = _months_back(back)
            gross = monthly if not (i == 2 and back == 1) else int(monthly * 1.18)  # diferencia para el aviso
            deductions = int(gross * 0.18)
            data = samples.payslip_pdf(org.name, f"{given} {family}", cat, y, m, gross, deductions)
            extracted = read_payslip(ex.text(data, "application/pdf"), e) if ex else None
            confirmed = i != 5 or back == 2
            path, sha = vault.store(data)
            db.add(EmployeeDocument(
                organization_id=org.id, employee_id=e.id, kind="nomina", period=f"{y}-{m:02d}",
                original_name=f"nomina_{e.code}_{y}{m:02d}.pdf", mime="application/pdf", size_bytes=len(data),
                sha256=sha, file_path=path, extracted=extracted, status="valido" if confirmed else "pendiente_revision",
                confirmed={"periodo": f"{y}-{m:02d}", "devengado_cents": gross, "deducciones_cents": deductions,
                           "liquido_cents": gross - deductions} if confirmed else None,
                uploaded_by=hr_user.id, reviewed_by=hr_user.id if confirmed else None,
                reviewed_at=datetime.now(UTC) if confirmed else None))
        if i == 1:
            s, f = date(today.year, 8, 3), date(today.year, 8, 14)
            db.add(LeaveRequest(organization_id=org.id, employee_id=e.id, kind="vacaciones", start_date=s, end_date=f,
                                working_days=working_days(s, f), status="aprobada", requested_by=u.id if u else hr_user.id,
                                decided_by=hr_user.id, decided_at=datetime.now(UTC) - timedelta(days=90)))
        if i == 3 and u is not None:
            s = today + timedelta(days=21 - today.weekday())
            f = s + timedelta(days=4)
            db.add(LeaveRequest(organization_id=org.id, employee_id=e.id, kind="vacaciones", start_date=s, end_date=f,
                                working_days=working_days(s, f), status="solicitada", requested_by=u.id,
                                note="Vacaciones (ficticio)"))
        if i == 4:
            s, f = today - timedelta(days=40), today - timedelta(days=33)
            db.add(LeaveRequest(organization_id=org.id, employee_id=e.id, kind="baja", start_date=s, end_date=f,
                                working_days=working_days(s, f), status="aprobada", requested_by=hr_user.id,
                                note="Parte de baja recibido (ficticio)"))
    db.flush()
