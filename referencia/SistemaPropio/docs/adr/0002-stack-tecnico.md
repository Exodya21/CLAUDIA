# ADR-0002 · Stack técnico

- Estado: **Propuesto** · Fecha: 02/11/2026

## Decisión
- Web: Next.js 15 (App Router) + TypeScript, sin librerías de UI externas; CSS propio accesible.
- API: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Datos: PostgreSQL 16 (JSONB para auditoría, triggers para invariantes críticas).
- Pruebas: pytest contra PostgreSQL real (no SQLite: los triggers y tipos deben probarse de verdad), vitest en web, recorrido en navegador.

## Motivo
Coincide con la propuesta del encargo; Python facilita el trabajo posterior de OCR, cálculos y documentos DOCX.
La web reenvía `/api/v1/*` a la API para compartir origen: cookie `httpOnly` + `SameSite=Strict` sin CORS.
