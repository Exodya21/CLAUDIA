"""F5.3 — Recursos Humanos: ficha única de empleado, carpeta documental, vacaciones y ausencias (DR-RH-1, 2, 4, 5, 6).

Reglas (guion de RRHH de Dirección, 08/11/2026):
- Una ficha por persona con oficina, categoría, antigüedad, jornada, salario y situación. Los datos de personal
  están AISLADOS de los expedientes de clientes (Q-5.x): otras tablas y otros permisos.
- Salario y nóminas solo con `hr.salary`; las bajas médicas solo las ve RRHH (dato de salud): el resto ve «ausencia».
- El sistema NO calcula nóminas ni días por convenio: guarda lo que se le da y lo compara entre periodos.
- Las decisiones sobre personas (aprobar vacaciones, renovar un contrato) las toma una persona; nada se borra.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import _created, _uuid


class Employee(Base):
    __tablename__ = "employee"
    __table_args__ = (UniqueConstraint("organization_id", "code"), UniqueConstraint("organization_id", "user_id"),
                      Index("ix_employee_org_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(12), nullable=False)  # EMP-0001
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))  # su usuario del sistema
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_names: Mapped[str] = mapped_column(String(200), nullable=False)
    national_id_enc: Mapped[str | None] = mapped_column(Text)  # DNI/NIE cifrado
    national_id_last: Mapped[str | None] = mapped_column(String(4))  # para mostrarlo enmascarado
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")  # ES | CO
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("department.id"))
    category: Mapped[str] = mapped_column(String(80), nullable=False)  # categoría profesional (convenio)
    job_title: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # indefinido | temporal | practicas | fijo_discontinuo | otro
    workday: Mapped[str] = mapped_column(String(10), nullable=False)  # completa | parcial
    weekly_hours: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)  # antigüedad
    contract_end_date: Mapped[date | None] = mapped_column(Date)
    trial_end_date: Mapped[date | None] = mapped_column(Date)
    salary_annual_cents: Mapped[int | None] = mapped_column(BigInteger)  # bruto anual pactado (hr.salary)
    vacation_days_year: Mapped[int | None] = mapped_column(Integer)  # días laborables según convenio (T-50)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    # activo | baja | excedencia | finalizado
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(1000))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EmployeeDocument(Base):
    """Carpeta del empleado: contratos, anexos, nóminas, certificados y solicitudes (original cifrado)."""

    __tablename__ = "employee_document"
    __table_args__ = (UniqueConstraint("employee_id", "sha256"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employee.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # contrato | anexo | nomina | certificado | solicitud | baja | otro
    period: Mapped[str | None] = mapped_column(String(7))  # AAAA-MM (nóminas)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(200), nullable=False)
    extracted: Mapped[dict | None] = mapped_column(JSONB)  # lo que propone la lectura
    confirmed: Mapped[dict | None] = mapped_column(JSONB)  # lo que una persona ha confirmado
    status: Mapped[str] = mapped_column(String(18), nullable=False, default="pendiente_revision")
    # pendiente_revision | valido | rechazado
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    uploaded_at: Mapped[datetime] = _created()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class LeaveRequest(Base):
    __tablename__ = "leave_request"
    __table_args__ = (Index("ix_leave_employee_dates", "employee_id", "start_date"),)
    id: Mapped[uuid.UUID] = _uuid()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employee.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # vacaciones | asuntos_propios | permiso | baja | otro
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)  # lunes a viernes (festivos: T-49)
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="solicitada")
    # solicitada | aprobada | rechazada | anulada
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    requested_at: Mapped[datetime] = _created()
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
