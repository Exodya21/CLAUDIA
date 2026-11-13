# 06 · Documentación técnica y del código

Sistema Propio · versión F5.6 · 12/11/2026. Las convenciones completas de cada incremento están en `CLAUDE.md`, en
la raíz del repositorio.

## 1. Estructura del repositorio
```
sistema-propio/
├── apps/
│   ├── api/                      FastAPI (Python 3.12)
│   │   ├── app/
│   │   │   ├── main.py           creación de la app, routers, middleware request_id, errores
│   │   │   ├── config.py         variables de configuración (pydantic-settings)
│   │   │   ├── db.py             motor y sesiones SQLAlchemy
│   │   │   ├── errors.py         formato de error {"error": {code, message, details, request_id}}
│   │   │   ├── audit.py          auditoría encadenada (SHA-256)
│   │   │   ├── validation.py     DNI/NIE/pasaporte, teléfonos, enmascarado
│   │   │   ├── models*.py        11 archivos de modelos (78 tablas)
│   │   │   ├── security/         policy, catalog, catalog_sync, auth, credentials, oidc, portal_auth, ratelimit
│   │   │   ├── routers/          21 routers HTTP
│   │   │   ├── services/         vault (archivos cifrados), receipts (OCR), textcrypt, notify (correo), pdfwrite
│   │   │   ├── immigration/      catálogo, lectura (reader, mrz, extract), formularios EX, muestras
│   │   │   ├── bank/             parsers de extractos, matcher (conciliación), demo
│   │   │   ├── accounting/       invoices (lectura v2), treasury (remesas/SEPA), close, routine, reports
│   │   │   ├── reception/        cobros, justificantes, cierre de caja
│   │   │   ├── hr/               acceso, nóminas, ausencias, muestras
│   │   │   ├── comm/             núcleo del portal, plantillas
│   │   │   ├── agents/           base, engine, registry (5 agentes)
│   │   │   ├── ops/              agents, outbox, backup, primer_admin (órdenes de consola)
│   │   │   └── seed*.py          datos FICTICIOS de demostración
│   │   ├── alembic/versions/     0001…0012
│   │   └── tests/                25 archivos pytest
│   ├── web/                      Next.js 15
│   │   ├── app/(app)/            páginas por módulo (clientes, crm, expedientes, agenda, extranjeria, …)
│   │   ├── components/           componentes por módulo (accounting.tsx, bank.tsx, immigration.tsx, …)
│   │   ├── lib/                  modules.ts (menú y estado), format.ts (fechas Europe/Madrid), api
│   │   ├── tests/                vitest
│   │   └── e2e/                  12 recorridos playwright
│   └── extension-mercurio/       extensión de Chrome (Manifest V3)
├── docs/                         producto, seguridad, operación, pruebas, adr, entrega
├── ops/                          copia.sh, crear_env_real.ps1
├── scripts/                      cobertura de requisitos, generación de los mapas EX, muestras
├── docker-compose.yml
└── *.bat                         arranque, parada y copias en Windows (demo y real)
```

## 2. Convenciones obligatorias
### 2.1 Autorización
- Siempre con `security/policy.py` y los permisos de `security/catalog.py`. **Nunca** se comprueba un rol por su
  nombre en un router.
- Cada permiso nuevo se añade al catálogo y a `docs/seguridad/politica_permisos.md`.
- Entidad ajena → 404; sin permiso → 403. Ambos se auditan con `audit.record_independent` (transacción propia).

### 2.2 Auditoría
- `audit.record(...)` en la **misma** transacción que el cambio, con `before`/`after` y `reason` cuando aplique.
- Los documentos de identidad van enmascarados. Contraseñas, valores de la ficha EX o salarios nunca aparecen
  (se registran las claves cambiadas o «•••»).

### 2.3 Datos
- Toda tabla de negocio lleva `organization_id`.
- Importes en céntimos (`int`). Fechas en UTC.
- Sin DELETE físico de lo que tiene valor de prueba (triggers `*_no_delete`).
- Migraciones **solo aditivas y reversibles**; las pruebas hacen subida → bajada → subida.

### 2.4 Errores
Formato único:
```json
{"error": {"code": "acceso_denegado", "message": "texto para la persona", "details": {}, "request_id": "…"}}
```

### 2.5 Interfaz
- Un módulo no construido se marca en `lib/modules.ts` con `status: "pendiente"` y se muestra «No disponible aún».
  **Nunca** se ponen datos de ejemplo en la interfaz.
- Las fechas se muestran en Europe/Madrid con `lib/format.ts`.
- `PendingList.onCount` va en una ref, para no recargar la lista en bucle.

### 2.6 Agentes
- Los hechos se emiten **solo** con `agents.emit(...)` dentro de la transacción, y
  `background.add_task(agents.dispatch_events)` tras el commit.
- Nunca se llama a un agente directamente desde un router.
- Toda propuesta pasa por `agents.base.propose`, con `dedupe_key` estable y el permiso con el que se decide.

### 2.7 Archivos
- Los documentos se guardan con `services/vault.py` (cifrado, sha256) y los justificantes con
  `services/receipts.py`. Nunca en la base de datos y nunca sin cifrar.
- Los correos salen **solo** por `services/notify.enqueue` (cola idempotente) y sin contenido sensible.

### 2.8 Lectores de documentos
- Leen y **proponen**; una persona confirma.
- Al mejorar un lector se sube su versión (`READER_VERSION`), para ofrecer «Volver a leer».
- Los formatos nuevos se prueban con **textos o archivos ficticios con la misma forma**, nunca con documentos reales.

## 3. Cómo añadir una funcionalidad (definición de terminado)
1. **Migración** Alembic nueva (`00NN_...py`), con tablas, `organization_id`, checks y triggers. Reversible.
2. **Modelo** en `models_<módulo>.py`.
3. **Permisos** en `catalog.py` (y en el rol que corresponda) y en la política documentada.
4. **Servicio** con la lógica en `app/<módulo>/`, con auditoría y eventos.
5. **Router** con esquemas Pydantic y `policy`; registrarlo en `main.py`.
6. **Interfaz**: página en `app/(app)/<módulo>`, componente y estado en `lib/modules.ts`.
7. **Pruebas**:
   - pytest (permitido, denegado, entidad ajena, reglas, no borrado);
   - vitest si hay lógica de interfaz;
   - recorrido e2e.
8. **Documentación**:
   - evidencias en `docs/pruebas/`;
   - decisiones en `decisiones.md`;
   - requisitos vinculados en `trazabilidad_codigo.md`;
   - README y `CLAUDE.md`.

En Odoo, el equivalente es un módulo `sp_*` con:
- `__manifest__.py`;
- `models/`;
- `security/ir.model.access.csv` y `security/rules.xml`;
- `views/`;
- `data/`;
- `tests/`;
- `migrations/`.

## 4. Piezas reutilizables en Odoo
| Pieza | Archivo | Depende de FastAPI |
|---|---|---|
| Validación DNI/NIE, teléfonos y enmascarado | `app/validation.py` | No |
| Validación de IBAN y CIF | `app/accounting/invoices.py` (`valid_iban`), `immigration/extract.py` (`valid_cif`) | No |
| Parsers de extractos (N43, CAMT, CSV, Excel, HTML) | `app/bank/parsers.py` | No |
| Reglas de conciliación | `app/bank/matcher.py` | Usa modelos (adaptar) |
| Lectura de facturas v2 | `app/accounting/invoices.py` (`read_invoice`) | No |
| Generación SEPA pain.001 | `app/accounting/treasury.py` | Usa modelos (adaptar) o sustituir por OCA |
| OCR de tickets y PDF | `app/services/receipts.py` | No |
| MRZ y lectura de documentos de extranjería | `app/immigration/mrz.py`, `reader.py`, `extract.py` | No |
| Mapas de los formularios EX | `app/immigration/ex_forms/*.json` | No |
| Lectura de nóminas | `app/hr/service.py` (`read_payslip`) | No |
| Cadena de auditoría | `app/audit.py` (`compute_hash`) | No |
| Extensión de Mercurio | `apps/extension-mercurio/` | No (cambiar la URL de la API) |

## 5. Calidad
- `ruff check` sin errores; `tsc --noEmit` sin errores; `next build` correcto.
- Las pruebas de API se ejecutan contra **PostgreSQL real** (`TEST_DATABASE_URL`, con un nombre de base que termine
  en `_test`).
- Ningún secreto en el código. `.env`, `.env.real` y `copias_real/` están en `.gitignore`.
