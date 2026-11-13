# 04 · Documentación del stack tecnológico

Sistema Propio · versión F5.6 · 12/11/2026 (ADR-0002)

## 1. Stack actual
| Capa | Tecnología | Versión | Uso |
|---|---|---|---|
| Base de datos | PostgreSQL | 16 | Datos, reglas con triggers y CHECK, bloqueos consultivos para la cadena de auditoría |
| Migraciones | Alembic | 1.13+ | 12 migraciones (0001–0012), solo aditivas y reversibles |
| ORM | SQLAlchemy | 2.x | Modelos en `app/models_*.py` |
| API | FastAPI + Pydantic v2 + Uvicorn | FastAPI ≥ 0.115 | `/api/v1`, OpenAPI en `/api/v1/docs` |
| Lenguaje servidor | Python | 3.12 | — |
| Contraseñas | Argon2id (`argon2-cffi`) | — | Hash de contraseñas |
| MFA | TOTP (RFC 6238) con `pyotp`; QR generado en el servidor con `segno` | — | `security/credentials.py` |
| Cifrado | `cryptography` (Fernet) | — | Columnas y archivos |
| OCR | Tesseract (español) + Poppler (`pdftoppm`, `pdftotext`) | Paquetes del sistema | Tickets, documentos de extranjería, facturas escaneadas (300 ppp) |
| PDF e imágenes | `pypdf`, `pillow` + generador propio (`services/pdfwrite.py`) | — | Informes, justificantes, relleno de los modelos EX |
| Otros | `phonenumbers`, `email-validator`, `pyjwt` (OIDC), `psycopg` 3 | — | Validación de teléfonos y correos, tokens OIDC, conexión a PostgreSQL |
| Hojas de cálculo | `openpyxl` (xlsx), `xlrd` (xls) | — | Extractos de Excel |
| Web | Next.js (App Router) + React + TypeScript | 15.5.6 / 19.1.1 / 5.9.2 | Interfaz del equipo y del portal |
| Pruebas API | pytest + httpx | pytest ≥ 8 | 254 pruebas contra PostgreSQL real |
| Pruebas web | vitest | 3.2.4 | 19 pruebas (incluida la vigilancia de la extensión) |
| Pruebas e2e | playwright-core | 1.55.0 | 12 recorridos, 128 pasos |
| Calidad | ruff, tsc | — | Estilo y tipos |
| Contenedores | Docker + Docker Compose | — | 4 servicios |
| Extensión | Chrome Manifest V3 | 0.2 | Rellena Mercurio sin presentar |
| Correo | SMTP con STARTTLS (cola propia) | — | Avisos sin contenido sensible |

Lo que **no** se usa, de forma deliberada:
- ningún servicio de IA ni OCR en la nube (todo es local, para no sacar datos de clientes);
- ninguna base de datos ni cola adicional (la cola es una tabla de PostgreSQL);
- ningún CDN para la interfaz.

## 2. Stack destino (Odoo Community)
| Capa | Tecnología | Nota |
|---|---|---|
| Plataforma | Odoo **20.0** Community (LGPL-3). Decidido el 13/11/2026 (18 · AL-02); antes se barajaban 17.0 o 18.0 | No mezclar ramas. Sin Enterprise (18 · AL-01) |
| Lenguaje | Python 3.10–3.12 (según la versión de Odoo) | Los módulos propios `sp_*` en Python + XML |
| Interfaz | OWL (framework web de Odoo), vistas XML, QWeb para informes PDF | Sustituye a Next.js |
| Base de datos | PostgreSQL 14–16 | La misma familia de reglas: triggers propios en `init()` |
| Módulos de la comunidad | OCA (GitHub `OCA/*`), en la **misma rama** que Odoo | Ver la lista en 02 · Arquitectura, 8.1 |
| Tareas programadas | `ir.cron`, `base_automation`; `queue_job` (OCA) si hace falta | Sustituye al contenedor `avisos` |
| Informes | QWeb PDF; `mis_builder` (OCA) | — |
| OCR | Tesseract + Poppler en el servidor | Llamados desde `sp_lectura` |
| Proxy | Nginx o Caddy | TLS, *websocket* o *longpolling* |
| Despliegue | Docker (imagen oficial `odoo:17`/`odoo:18`) o paquete nativo | Con `addons_path` que incluya OCA y `sp_*` |
| Pruebas | `odoo-bin --test-enable` (`TransactionCase`, `HttpCase`) | Reescribir los casos de `apps/api/tests` |

## 3. Equivalencias técnicas
| Sistema Propio | Odoo |
|---|---|
| Modelo SQLAlchemy | `models.Model` con `_name = "sp.xxx"` |
| Migración Alembic | `__manifest__.py` `version` + scripts `migrations/<versión>/pre|post-*.py` |
| Router FastAPI | Métodos del modelo + `@http.route` (controladores) para el portal y la extensión |
| Esquema Pydantic | Definición de campos + `@api.constrains` |
| `policy.require(permiso)` | `ir.model.access.csv` + `ir.rule` + `groups=` en vistas y campos |
| `audit.record` | `auditlog` + modelo propio `sp.audit.event` de solo inserción |
| `agents.emit` + propuestas | `base_automation` (al crear o escribir) + modelo `sp.proposal` |
| `notify.enqueue` | `mail.mail` / `mail.template` |
| Componentes React | Vistas XML (form, list, kanban) + componentes OWL cuando haga falta |
| Pruebas pytest | `TransactionCase` |
| Recorridos e2e | `HttpCase` con *tours* de Odoo |

## 4. Herramientas de desarrollo recomendadas
- Git con ramas por módulo y revisión obligatoria (pull request) antes de fusionar.
- `pre-commit` con `ruff`/`flake8`, `pylint-odoo` (OCA) y `prettier` para XML/JS.
- Integración continua: pruebas de Odoo en cada cambio, contra una base vacía con datos ficticios.
- Gestor de secretos o variables de entorno protegidas para `admin_passwd`, la base de datos y SMTP.
