# Resumen de interpretación (PROMPT 00 · apartado A)

## Recuento confirmado
| Fuente | Referencias | IDs |
|---|---|---|
| Informe de 120 operaciones (27/10/2026) | 120 | I-001 … I-120 (11 bloques B01–B11) |
| Project Charter Qubiq/Odoo (08/09/2026) | 70 | Q-1.1 … Q-6.23 (69 números distintos) + **Q-6.20B** (el 6.20 aparece dos veces, D-14) |
| Acuerdos operativos (octubre 2026) | 18 | U-01 … U-18 |
| **Total** | **208 referencias** | No 208 funciones distintas: 41 son equivalentes entre fuentes |

Clasificación (generada por `scripts/build_coverage.py`, a validar): **41 equivalentes · 61 complementarias ·
44 nuevas · 19 contradictorias · 43 sin definición**. Ningún ID eliminado.

## Fuentes usadas en esta entrega
- `02_Matriz_Maestra_208_Requisitos.xlsx` (las 208 filas, 25 decisiones, roles, 32 pruebas, roadmap).
- `01_Plan_Maestro_Sistema_Propio.docx`, `CLAUDE.md`, `04_PROMPT_00`, `05_PROMPT_01`.
- **No disponibles en la sesión**: los dos PDF originales y `03_Backlog_Maestro_208.json`. La matriz transcribe sus
  208 puntos con página de origen, pero conviene cotejar los títulos contra los PDF antes de cerrar la cobertura.

## Lectura de fondo
1. Lo que Qubiq llama "solución Odoo" se ha reducido a la **necesidad**; la propuesta técnica es propia.
2. Las 19 referencias contradictorias contienen afirmaciones jurídicas, fiscales u operativas que no se programarán como regla (nacionalidad 2 años, FOGASA, 12/13 días, 15/20 días, 80 % neto, Intrastat para servicios, mensaje de apertura, videollamada estándar, acceso amplio de recepción…).
3. Las 43 "sin definición" dependen sobre todo de interfaces oficiales autorizadas (D-09, 29 IDs de M10/M17), de la integración con MNP mientras se sustituye (D-15) y de proveedores fiscales (D-25).
