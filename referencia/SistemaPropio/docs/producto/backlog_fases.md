# Backlog por incrementos

Cada incremento se cierra solo cuando cumple la **definición de terminado** (CLAUDE.md): migración, API, interfaz,
control de permisos, tests ejecutados, documentación, decisiones marcadas e IDs de requisitos vinculados. Ningún
incremento rompe los anteriores: las migraciones solo añaden; los tests de incrementos previos siguen en verde en CI.

Los IDs de requisito remiten a [`mapa_cobertura.md`](mapa_cobertura.md). Ninguno se elimina: los que no aparecen
abajo siguen en su fase de la matriz (F3–F6) y se detallarán al acercarse.

---

## F0.1 — Núcleo de seguridad + directorio de clientes ✅ implementado

| Aspecto | Contenido |
|---|---|
| Requisitos | Q-1.1, Q-1.2, Q-6.17, Q-6.23 (base), U-18, I-003, I-120 (control de accesos), Q-6.2 (estructura mínima) |
| Entidades | organization, branch, department, user_account, role, role_permission, membership, access_grant, contact, identifier, contact_point, address, consent, duplicate_review, case_file, case_assignment, case_code_counter, audit_event |
| Endpoints | `/auth/*`, `/me`, `/organizations`, `/permissions`, `/contacts` (GET/POST/PATCH, duplicate-check, cases, history), `/cases` (GET), `/grants`, `/audit-events` (+verify), `/health` |
| Pantallas | Login demo, Inicio por rol, Clientes (búsqueda, alta, ficha con 4 pestañas, edición), Expedientes (listado, detalle/403), Ajustes (perfil, permisos, autorizaciones, auditoría), 9 módulos "Pendiente de desarrollar" |
| Tests | 49 API (pytest, PostgreSQL real) + 10 web (vitest) + recorrido de 11 pasos en Chrome |
| Salida | AT-01 ✅ AT-02 ✅ AT-03 ✅ AT-04 ✅ multiempresa ✅ — ver `docs/pruebas/evidencias_F0.1.md` |

## F0.2 — Acceso seguro, sesiones, administración y copias ✅ implementado (02/11/2026)

| Aspecto | Contenido |
|---|---|
| Requisitos | Q-1.2, I-120, AT-29, Q-6.23, U-18 |
| Entidades | `user_session` (revocable), `auth_attempt` (límite de intentos), `backup_run` (solo inserción); credenciales en `user_account` (Argon2id, TOTP cifrado) |
| Endpoints | `/auth/login`, `/auth/mfa`, `/auth/enroll/{start,confirm}`, `/auth/password`, `/auth/sessions` (+revoke), `/auth/oidc/{login,callback}` (PKCE + MFA), `/admin/users` (alta, edición, desactivar, reactivar, restablecer), `/admin/users/{id}/memberships`, `/admin/memberships/{id}/end`, `/admin/sessions/{id}/revoke`, `/admin/backups`, `/grants/lookup` |
| Pantallas | Acceso con contraseña + código, primer acceso con QR, Ajustes → Seguridad (sesiones, cambio de contraseña), Administración (usuarios, roles, sesiones, copias), alta de autorizaciones puntuales |
| Operación | `COPIA_SEGURIDAD.bat` / `ops/copia.sh` + `python -m app.ops.backup`; `python -m app.ops.primer_admin` para la primera persona administradora en una instalación limpia; `python -m app.security.catalog_sync` en cada arranque |
| Tests | 37 API nuevos (106 en total), 13 web, recorrido F0.2 de 13 pasos (35 pasos con los anteriores) — `docs/pruebas/evidencias_F0.2.md` |
| Salida | AT-29 ✅; CI con base de restauración |
| Queda fuera | Proveedor OIDC real (T-01), alojamiento y copia externa cifrada (T-02, T-17), proxy inverso que fije la IP del cliente, roles reales del organigrama (T-08) |

## F1.1 — Migración de ensayo de contactos

| Aspecto | Contenido |
|---|---|
| Requisitos | I-112, D-15, AT-30, T-10 |
| Entidades | `import_batch`, `import_row` (estado: nuevo / coincidente / dudoso / error), `external_ref` (ID de MNP/Bookitit como referencia histórica) |
| Endpoints | `POST /imports` (CSV), `GET /imports/{id}` (informe), `POST /imports/{id}/apply` |
| Pantallas | Carga, mapeo de columnas, informe de excepciones con aprobador |
| Tests | AT-30: 1.000 contactos ficticios → informe de coincidencias, errores y mapeos; sin fusión; reversible por lote |
| Depende de | Exportación de prueba (T-10) |

## F1.2 — Leads y origen comercial (CRM) ✅ implementado (02/11/2026)

| Aspecto | Contenido |
|---|---|
| Requisitos | Q-2.1, Q-2.7, Q-2.8, Q-3.1, I-099, I-102 |
| Entidades | `lead` (contact_id, origen, campaña, utm_*, asesor, estado), `lead_event`, catálogo `lead_origin` |
| Endpoints | `/leads` CRUD sin borrado, `/leads/{id}/transition`, `/leads?estado=&origen=&sede=` |
| Pantallas | Bandeja de leads, ficha de lead vinculada al contacto, alertas 24 h / 72 h / 7 d |
| Permisos | `lead.create` (Recepción, ATC, Marketing, asesores), `lead.read` por entidad/sede; Marketing sin acceso a expedientes |
| Tests | AT-05 (sin origen no se guarda), AT-06 (trazabilidad hasta expediente), transición no permitida → 403 |
| Depende de | F0.1 |

## F1.3 — Citas con cobro previo (pasarela en modo prueba)

| Aspecto | Contenido |
|---|---|
| Requisitos | Q-2.4, Q-2.5, Q-2.6, Q-3.7, U-14, I-069 |
| Entidades | `availability_rule`, `appointment`, `payment_reference`, `integration_event` (outbox) |
| Endpoints | `/availability`, `/appointments`, `/payments/webhook/{proveedor}` (firma verificada, idempotente) |
| Pantallas | Buscador de huecos (rama > sede/modalidad > asesor opcional > hora), agenda de citas |
| Tests | AT-07 (callback duplicado), AT-08 (sin pago no ocupa agenda), AT-09 (asesor opcional) |
| Depende de | D-11, D-19 (configurables), elección de pasarela, F1.2 |

## F2 — Trabajo jurídico inicial

Evidencias de F1.2, F2.1 y F2.2: `docs/pruebas/evidencias_F1.2_F2.md`.

| Incremento | Requisitos | Pruebas de salida | Depende de |
|---|---|---|---|
| ✅ F2.1 Expediente completo: alta desde ficha, fases, relaciones, inactividad | Q-6.2, Q-6.4, I-007…I-010, I-088, I-092 | AT-15, AT-16 | T-05, T-06 |
| ✅ F2.2 Tareas, agenda y plazos (sin reglas automáticas) | I-067…I-077, Q-6.9, Q-6.10, Q-6.15, Q-6.16, Q-6.20, Q-6.20B, U-16 | AT-19, AT-20 | D-02, D-03, D-04, D-21 para automatizar |
| F2.3 Documentos y portal de pruebas | I-078…I-087, Q-3.10, Q-6.13, Q-6.14, Q-6.22 | AT-17, AT-32 | T-03; firma: D-08, D-22 |
| F2.4 Fichas laborales (3 rutas) | I-004, I-006, Q-2.9, Q-6.1, U-01…U-12 | AT-10, AT-12, AT-13, AT-14 | Validación de U-01…U-12 por Laboral |
| F2.5 Extracción asistida de nóminas | I-002, I-079, U-02, Q-5.5 (patrón) | AT-11 | Proveedor OCR en la UE |

## F5.0 — Control económico no fiscal y gastos de empresa ✅ implementado (03/11/2026)

Adelantado a petición de Dirección (nota «Automatización urgente del control de gastos»). Respeta los bloqueos
fiscales: no emite facturas ni calcula honorarios, IVA o suplidos.

| Aspecto | Contenido |
|---|---|
| Requisitos | Q-3.9, Q-4.4, Q-4.13, Q-4.14, Q-4.5 (tarjetas), Q-2.6/Q-4.3 (registro de cobros), I-101, I-110 |
| Entidades | `charge`, `payment`, `refund` + `refund_event`, `cash_movement`, `cash_closing`, `expense` + `expense_event`, `company_card`, `card_transaction` (migración `0004`, triggers de no borrado, solo inserción y misma entidad) |
| Endpoints | `/economy/cases/{id}` (+charges, payments, refunds), `/economy/lookup`, `/economy/payments` (+confirm, annul), `/economy/refunds` (+transition), `/economy/cash` (+movements, closings), `/economy/summary`; `/expenses` (subida, edición, envío, revisión, conciliación, justificante), `/expenses/cards/*` (tarjetas, extracto CSV, movimientos), `/expenses/summary/month(.csv)` |
| Pantallas | Economía (buscar expediente, cobros por confirmar, devoluciones, caja, resumen); Gastos (mis gastos, revisión, tarjetas y extractos, resumen mensual); sección Economía en la ficha del expediente |
| Tests | 21 API nuevos (127 en total), 15 web, recorrido F5.0 de 12 pasos — `docs/pruebas/evidencias_F5.0.md` |
| Pendiente | Facturación con programa homologado (D-25, D-07), formato real del extracto (T-19), IA externa opcional (T-20), pasarela (F1.3) |

## F3–F6 (resumen; se detallarán al cerrar F2)

| Fase | Alcance | Pruebas | Bloqueos |
|---|---|---|---|
| F3 | Cálculos laborales deterministas sobre datos confirmados, papeletas y demandas DOCX | AT-18, AT-25 | Reglas y plantillas aprobadas por abogados |
| F4 | Extranjería, comunicaciones, ATC/devoluciones, cuadro de mando | AT-22, AT-23, AT-24, AT-27 | D-01, D-10, D-20 |
| F5 | Economía, RRHH, multientidad contable | AT-25, AT-26, AT-31 | D-05, D-06, D-07, D-16, D-18, D-25 |
| F6 | Notificaciones oficiales autorizadas, IA asistiva con fuentes, integraciones | AT-21, AT-28 | D-09, D-24 |
