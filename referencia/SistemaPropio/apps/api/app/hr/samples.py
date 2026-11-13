"""Documentos de RRHH FICTICIOS para desarrollo y pruebas (nóminas y contratos). Ningún dato es real."""

from __future__ import annotations

from datetime import date

from ..services import pdfwrite
from .service import MONTHS


def _eur(c: int) -> str:
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def payslip_pdf(company: str, name: str, category: str, year: int, month: int, gross_cents: int,
                deductions_cents: int) -> bytes:
    last = (date(year + (month == 12), month % 12 + 1, 1) - date.resolution).day
    lines = [
        ("h", "RECIBO INDIVIDUAL DE SALARIOS (FICTICIO)"),
        ("n", f"Empresa: {company}"),
        ("n", f"Trabajador: {name}"),
        ("n", f"Categoría: {category}"),
        ("n", f"Periodo: 01/{month:02d}/{year} - {last:02d}/{month:02d}/{year}  ({MONTHS[month - 1]} {year})"),
        ("n", ""),
        ("b", "DEVENGOS"),
        ("n", f"Salario base  {_eur(int(gross_cents * 0.85))}"),
        ("n", f"Complementos  {_eur(gross_cents - int(gross_cents * 0.85))}"),
        ("b", f"TOTAL DEVENGADO  {_eur(gross_cents)}"),
        ("n", ""),
        ("b", "DEDUCCIONES"),
        ("n", f"Cotizaciones e IRPF (ficticios)  {_eur(deductions_cents)}"),
        ("b", f"TOTAL A DEDUCIR  {_eur(deductions_cents)}"),
        ("n", ""),
        ("h", f"LÍQUIDO TOTAL A PERCIBIR  {_eur(gross_cents - deductions_cents)}"),
        ("s", "Documento de prueba generado por SISTEMA PROPIO. No corresponde a ninguna persona real."),
    ]
    return pdfwrite.text_pdf(lines, footer="Nómina ficticia")


def contract_pdf(company: str, name: str, job: str, contract_type: str, start: date, end: date | None) -> bytes:
    lines = [
        ("h", "CONTRATO DE TRABAJO (FICTICIO)"),
        ("n", f"Empresa: {company}"),
        ("n", f"Trabajador/a: {name}"),
        ("n", f"Puesto: {job}"),
        ("n", f"Modalidad: {contract_type}"),
        ("n", f"Fecha de inicio: {start:%d/%m/%Y}"),
        ("n", f"Fecha de fin: {end:%d/%m/%Y}" if end else "Duración: indefinida"),
        ("s", "Documento de prueba generado por SISTEMA PROPIO. No corresponde a ninguna persona real."),
    ]
    return pdfwrite.text_pdf(lines, footer="Contrato ficticio")
