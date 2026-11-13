# CLAUDE.md - SISTEMA PROPIO

## Objetivo
Plataforma propia modular del despacho del abogado Rafael Serrano. Sustitucion gradual de MNP y otras herramientas, empezando por seguridad, datos maestros y circuito comercial/jurídico. Fuente canonica: `03_Backlog_Maestro_208.json` + PDFs originales; `docs/fuentes/02_Matriz_Maestra_208_Requisitos.xlsx` para control de cobertura (`scripts/build_coverage.py` genera `docs/producto/mapa_cobertura.md`).

## Reglas que no puedes romper
1. Conservar trazabilidad individual de I-001..I-120, Q-1.1..Q-6.23, Q-6.20B, U-01..U-18. Los solapes se relacionan; nunca se eliminan sin acta.
2. Qubiq propone Odoo, pero esta plataforma NO depende obligatoriamente de Odoo ni de MNProgram.
3. Datos de clientes solo en infraestructura aprobada. Desarrollo con datos sinteticos. Nunca pegar pruebas reales en prompts, logs o commits.
4. Permisos REALES en backend por empresa/sede/departamento/rol/asignacion; no seguridad solo visual. Denegar por defecto.
5. Registro auditable de ediciones, accesos y descargas con usuario y fecha.
6. No implementar fechas legales fijas, reglas de nacionalidad universales, reglas FOGASA, firma, facturación fiscal o portales oficiales sin fuente legal vigente y revisor profesional.
7. La IA prepara borradores y sugerencias, no determina derechos, plazos, resultados ni hace presentaciones autonomas.
8. Una persona = contacto maestro; puede tener N expedientes. Nunca fusion automática por telefono, ni borrar trazas al unificar datos.
9. Superficha laboral: TRES rutas con preguntas simples. Con papeles: OCR nómina/contrato/vida laboral con confirmacion; sin papeles: períodos diferenciados; hogar sin papeles: tareas individualizadas, personas cuidadas y centros multiples.
10. Cualquier aplicación para clientes usa tratamiento formal de usted. No habilitar ofertas de reservas de actuaciones biométricas.
11. Contratos de integración con terceros via adaptador, colas e idempotencia; secretos en gestor de secretos o variables seguras.
12. Cada tarea implementada debe tener migration, API, interfaz, control de permiso, tests y documentación; no afirmar que esta completa si solo existe maqueta.
13. Las decisiones D-01..D-25 del backlog pueden bloquear reglas automatizadas. Escalar en vez de inventar.

## Convenciones técnicas ya establecidas (F0.1)
- Autorización: SIEMPRE mediante `apps/api/app/security/policy.py` y permisos de `catalog.py`. Nunca comprobar roles por nombre en un router. Cada nuevo permiso se añade al catálogo y a `docs/seguridad/politica_permisos.md`.
- Entidad ajena → 404; misma entidad sin permiso → 403. Ambos se auditan con `audit.record_independent`.
- Cambios auditados con `audit.record` en la MISMA transacción, con `before`/`after` y `reason` cuando aplique. Documentos de identidad enmascarados en la bitácora.
- Toda tabla de negocio lleva `organization_id`. Sin DELETE físico de expedientes ni contactos (triggers).
- Migraciones Alembic solo aditivas y reversibles; los tests hacen upgrade→downgrade→upgrade.
- Tiempos en UTC (BD y API); la interfaz muestra Europe/Madrid (`apps/web/lib/format.ts`).
- Errores: `{"error": {code, message, details, request_id}}` (`app/errors.py`).
- Módulos no construidos: `lib/modules.ts` con `status: "pendiente"`; nunca datos de ejemplo en la interfaz.
- Tests de API contra PostgreSQL real (`TEST_DATABASE_URL`, nombre terminado en `_test`).

## Estado
- Implementado: F0.1 (núcleo y clientes), F0.2 (acceso seguro, sesiones, administración, copias AT-29), F1.2 (CRM), F2.1 (expedientes), F2.2 (tareas y agenda), F5.0 (control económico NO fiscal y gastos con OCR local), F4.1 (expediente de extranjería, fase 1), F4.2 (ficha EX + extensión que rellena Mercurio), F4.3 (lectura de contrato/padrón/TIE/tasa → ficha), F2.3 (portal del cliente y conversaciones; portal propio sin WhatsApp, T-31), F5.1 (agentes, banco y conciliación, mensajes automáticos por el portal), F5.2 (Recepción: cobros, justificante no fiscal, cierre de caja validado, informe), F5.3 (RRHH: ficha única, carpeta, nóminas sin calcular, vacaciones, avisos), F5.4 (Contabilidad: facturas de proveedores, tesorería con remesas de doble firma y SEPA, cierre del mes), F5.4b (rutina de trabajo de Contabilidad comprobada por el sistema, informes semanales/quincenales/mensuales, extractos en Excel). Evidencias en `docs/pruebas/`.
- Siguiente recomendado (plan de Dirección, `docs/producto/plan_motores_direccion.md`): F5.5 citas, llegada y agente de recepción, RRHH fase 2 (control horario T-41, formación, cuadro de mando). Después comunicaciones fase 2 (T-35) y F2.4.
- Tablas de F1.2/F2 en `app/models_work.py` (migración `0002`); de F0.2 en `app/models_security.py` + columnas de credenciales en `user_account` (migración `0003`). Datos ficticios incrementales en `app/seed_work.py`.

## Convenciones añadidas en F0.2
- Toda sesión es una fila de `user_session`; nunca emitir cookies sin `start_session`. Revocar con `revoke_sessions`.
- `AUTH_MODE` es una lista (`demo,local,oidc`); usar `settings.auth_methods`. Nada de `demo` fuera de development/test.
- Secretos de usuario cifrados con `security/credentials.encrypt`; contraseñas solo como hash Argon2id; nunca en auditoría.
- Roles: el catálogo en código manda; `app.security.catalog_sync` se ejecuta en cada arranque en cualquier entorno.
- Tests F0.2 usan los fixtures `new_user` / `enrolled` y `totp_now` de `tests/conftest.py`.

## Convenciones añadidas en F5.0
- Economía en `app/models_economy.py` (migración `0004`). Importes SIEMPRE en céntimos enteros; los totales se convierten a `int`.
- NUNCA emitir facturas ni calcular honorarios, IVA o suplidos (D-05, D-07, D-16, D-18, D-25): solo se guarda `invoice_ref` del programa homologado.
- Devoluciones: `REFUND_FLOW` en `routers/economy.py`; solo `refund.decide` aprueba/paga y nunca quien la solicitó.
- Justificantes: `services/receipts.py` (cifrado + OCR local + `Extractor` para un proveedor futuro). La lectura propone; la persona confirma.
- La caja se mueve solo con `CashMovement` (solo inserción); los gastos en efectivo se sincronizan con `_sync_cash`.

## Convenciones añadidas en F4.1
- Extranjería en `app/models_immigration.py` (migración `0005`) y `app/immigration/`. El catálogo de trámites vive en código (`catalog.py`), se sincroniza al arrancar y cada cambio crea una versión **pendiente de validar** por Legal Extranjería; los expedientes guardan la versión con la que se abrieron.
- Cada trámite lleva su fuente oficial (`source_url`, `source_updated`). No añadir requisitos sin hoja oficial.
- Documentos de expedientes: `services/vault.py` (cifrado, `DOCUMENTS_DIR`), nunca borrado físico. La lectura (`immigration/reader.py`, `mrz.py`) propone; una persona confirma.
- Nada se presenta en Mercurio ni se descarga de DEHú automáticamente (A-11, D-09). Fase 3 (notificaciones, LEMA, festivos) pendiente: T-25, T-26.
- Un requerimiento crea una tarea `plazo` sin `legal_deadline`: la fecha la propone un letrado con fuente.
- Pasaportes de prueba: país «UTO» (OACI) y números ZZ; generador `seed_immigration.passport_image`.

## Convenciones añadidas en F4.2
- Ficha del formulario: `app/immigration/forms.py` (claves `rol.campo`), `routers/immigration_forms.py`, migración `0006`. Mapas de los PDF oficiales en `immigration/ex_forms/EXnn.json`, generados con `scripts/ex_forms_build.py` (EX-10 a mano en `scripts/ex10_manual.py`); no editar los JSON a mano.
- Solo se usan valores que una persona ha guardado; la auditoría lleva las claves cambiadas, nunca los valores.
- Extensión `apps/extension-mercurio`: NUNCA `.click()`, `submit()` ni marcar «NO CONSIENTO» o el supuesto (lo vigila `apps/web/tests/extension_mercurio.test.ts`). Cambios de reconocimiento solo a partir del diagnóstico de Mercurio real (sin datos).
- La única ruta sin sesión es `GET /immigration/fill/{código}` (hash, 15 min, 10 lecturas, auditada).

## Convenciones añadidas en F4.3
- Lectura por tipo en `immigration/extract.py::for_document` → `extracted.ficha` (claves `rol.campo`) e `extracted.info` (NRC, días cotizados). Identificadores solo con control válido (`valid_nie/dni/cif`).
- Lo leído llega a la ficha **solo** desde documentos `valido`, con origen `documento: <tipo>`; nunca se sobrescribe un valor guardado (se avisa en `differs`). Documento con titular MRZ distinto del cliente: no propone `ext.*`.
- Muestras ficticias: `immigration/samples.py` (sin dependencias nuevas) y `docs/pruebas/muestras/`. Persona demo de las muestras: Carla Ferrer Demo (cliente de EXT-2026-0001).
- Toda propuesta pasa por `extract.sanitize` (también lo guardado con versiones anteriores): mejor vacío que equivocado.
- MRZ: todas las páginas del PDF y giros (`reader._mrz_in_pages`). Mismo archivo (sha256) no se guarda dos veces por expediente.
- Revisión automática por expediente: `GET /cases/{id}/reading-review` (`extract.review`, `EXPECTED`); subir `reader.READER_VERSION` cada vez que mejore la lectura para que se ofrezca «Volver a leer».
- Para mejorar formatos reales: el despacho envía el informe de la revisión o `GET /documents/{id}/diagnostic` (texto enmascarado con `extract.mask_text`), nunca el documento.
- Nunca usar documentos reales del despacho como fixtures; para mejorar formatos, pedir ejemplos anonimizados.

## Convenciones añadidas en F2.3 (portal y comunicaciones)
- Tablas en `app/models_comm.py` (migración `0007`); reglas en `app/comm/core.py`; plantillas de usted en `app/comm/templates.py`; equipo en `routers/comm.py`, cliente en `routers/portal.py`.
- El cliente NO es `user_account`: `portal_account` + `portal_session` (cookie `sp_portal`, `security/portal_auth.py`). Ninguna ruta del equipo acepta esa cookie ni al revés.
- Acceso a un hilo del equipo: `comm.*` + `case_level == "full"` (hilo de expediente) o ficha completa (hilo general). 404/403 auditados.
- Textos cifrados (`services/textcrypt.py`); nada se borra (ocultar con motivo, versiones de 15 min, triggers).
- Correos SOLO por `services/notify.enqueue` (cola idempotente + adaptador SMTP) y nunca con el contenido del mensaje.
- Urgentes solo con plantilla y fecha de una `Task` del expediente; plazo legal solo `legal_status == "validado"`. Escalado: `core.sweep_urgent` (bandeja y `python -m app.ops.outbox`).
- Adjuntos del cliente al expediente de extranjería con `routers/immigration.ingest_document` (misma lectura).

## Stack
Next.js 15 + TypeScript (web); FastAPI + SQLAlchemy 2 + Alembic (API); PostgreSQL 16; almacenamiento cifrado S3 compatible (F2); workers asíncronos (F1.3); OpenAPI en `/api/v1/docs`; pytest; vitest; recorrido e2e con playwright-core.

## Definicion de terminado
Pruebas ejecutadas, datos demo ficticios, revisión de seguridad, README actualizado, decisiones marcadas, IDs de requisitos vinculados a código (`docs/producto/trazabilidad_codigo.md`) y criterio de aceptacion. No tocar producción sin control.

## Convenciones añadidas en F5.1 (agentes y banco)
- Agentes en `app/agents/` (`base.py`, `engine.py`, `registry.py`); tablas en `app/models_agents.py` y `app/models_bank.py` (migración `0008`). Un agente nuevo = clase en `registry.py` con `covers`, `requirements`, `events`, `limits`.
- Hechos para agentes SOLO con `agents.emit(...)` dentro de la transacción del cambio y `background.add_task(agents.dispatch_events)` tras el commit. Nunca llamar a un agente directamente desde un router.
- Toda propuesta por `agents.base.propose` con `dedupe_key` estable (no se repite ni tras rechazarla) y el `permission` con el que se decide. Las que afectan al cliente (`mensaje`, `dato_falta`, `invitar_portal`) exigen además acceso completo al expediente (`routers/agents.can_decide`).
- La conciliación nunca es automática: `bank/matcher.py` solo PROPONE con reglas deterministas y explicación; validar confirma el cobro (exige `payment.confirm`). Importes en céntimos con signo; un traspaso nunca es ingreso.
- Extractos: `bank/parsers.py` (no adivina: línea ilegible = error); original cifrado con `services/vault`; reimportar no duplica (`ext_id` estable, sha256 por cuenta). Extracto ficticio de prueba solo en development/test (`bank/demo.py`).
- Mensajes automáticos: plantillas versionadas en `comm/auto_templates.py`; fechas y lugar SOLO de la tarea de la agenda; cada envío en `comm_dispatch`; modo automático solo si Dirección lo activa (T-47).
- e2e que suben archivos necesitan fixtures FICTICIOS por variable: `PASAPORTE` (`seed_immigration.passport_image("PRUEBA","RECORRIDO",…)`), `TICKET` y `EXTRACTO` (ver `docs/pruebas/evidencias_F5.1.md`).
- Los pendientes de los agentes se muestran DENTRO de cada departamento con `components/proposals.tsx` (`PendingList` filtrado por `agent`, `case_id` o `kind`); no hay bandeja ni módulo «Agentes» en el menú. La configuración de agentes está en Administración (`components/agents_admin.tsx`). Avisos de una sede: tipos en `routers/agents.BRANCH_SCOPED`.

## Convenciones añadidas en F5.2 (Recepción)
- Lógica en `app/reception/service.py`, API en `routers/reception.py`, justificantes en `models_reception.py` (migración `0009`). El cierre de caja de Economía usa el MISMO `close_day` (uno por sede y día, pendiente de validar).
- `payment.case_id` admite vacío SOLO para `kind == "consulta"` (check en BD). Todo código que lea cobros debe tolerar `case_id` nulo.
- Justificante: `issue_receipt` una vez por cobro, cifrado e inmutable (trigger); nunca «factura» (D-07, D-25).
- Duplicados: `possible_duplicates` antes de guardar; con explicación → evento `payment.duplicate_override` → Contabilidad. Anular siempre con `routers/economy.annul`.
- `cash_closing` solo admite UPDATE de validación mientras está pendiente (`sp_cash_closing_guard`); validador ≠ quien contó (check).

## Convenciones añadidas en F5.3 (RRHH)
- Tablas en `app/models_hr.py` (migración `0010`), reglas y acceso en `app/hr/service.py` (`access(p, e)` devuelve self/read/manage/salary/leave/team), API en `routers/hr.py`. Datos de personal NUNCA en tablas de clientes.
- Salario solo con `hr.salary` o la propia persona; en auditoría como «•••». Bajas (`kind == "baja"`) y partes: solo RRHH y la propia persona.
- La nómina se lee (`read_payslip`) y RRHH la confirma solo si devengado − deducciones = líquido; el sistema NO calcula nóminas ni días por convenio (T-50) ni festivos (T-49).
- Avisos: agente `rrhh` (dedupe por persona, motivo y fecha); aprobar crea una `Task` personal. Documentos de prueba con `app/hr/samples.py`.

## Convenciones añadidas en F5.4 (Contabilidad)
- Tablas en `app/models_accounting.py` (migración `0011`), lógica en `app/accounting/` (`invoices.py`, `treasury.py`, `close.py`), API en `routers/accounting.py`, pantallas en `components/accounting.tsx`.
- Factura recibida: la lectura (`read_invoice`) solo PROPONE; el total debe ser base + IVA − retención (check en BD). NUNCA calcular IVA ni emitir facturas. Duplicados: mismo archivo (sha256) o mismo proveedor/importe/fecha → solo con explicación.
- Remesas: `sign_batch`; dos firmas `treasury.approve` de personas distintas y ninguna de quien propone (trigger `sp_batch_approval_check`). El sistema genera el SEPA y nunca envía órdenes al banco; pagada = cargo conciliado (`matcher.rule_factura`).
- IBAN completos solo cifrados (`iban_enc`); en pantalla y auditoría, enmascarados.
- Cierre del mes: `close.compute` → `prepare_close`; recalcular crea revisión nueva y la anterior pasa a `sustituido`; aprobado es inmutable (`sp_month_close_guard`). Coste de personal agrupado < 3 personas sin `hr.salary` (`for_viewer`).
- `PendingList.onCount` va en una ref: no pasar callbacks que recarguen la lista en bucle.
- e2e: `FACTURA` = factura ficticia de `accounting.invoices.invoice_pdf` (CIF e IBAN de prueba válidos).

## Convenciones añadidas en F5.4b (rutina e informes de Contabilidad)
- Rutina: catálogo `STEPS` en `app/accounting/routine.py` (código, cadencia, fecha objetivo, permiso del responsable y comprobación determinista). Un paso nuevo = una entrada en `STEPS` con su `check`; NUNCA un botón de «hecho» manual. «No aplica» exige motivo (check en BD) y un paso cerrado no vuelve atrás (`sp_routine_item_guard`).
- `routine.sync` se ejecuta desde el agente `contabilidad` y al abrir la pestaña; los pasos no diarios crean su `Task` en la Agenda y la cierran al comprobarse (evento con el motivo).
- Informes: `app/accounting/reports.py`; cifras con `close.period_figures` (las mismas reglas que el cierre; nóminas solo en el mensual), foto inmutable con huella (`sp_report_guard`), versión nueva al regenerar, `for_viewer` siempre al mostrar/descargar. Correo solo con `notify.enqueue` y SIN cifras.
- Extractos: `bank/parsers.parse_rows` es común a CSV, Excel y tabla HTML; nuevos nombres de columna solo en `CSV_COLS` (normalizados sin tildes ni puntos). Pruebas con Excel ficticios generados en el test, nunca extractos reales.
- Lectura de facturas recibidas (v2): `accounting/invoices.read_invoice` por líneas con etiquetas + cuadre (`_reconcile`, tipos habituales SOLO para reconocer cifras impresas). Subir `READER_VERSION` al mejorarla. El CIF propio llega por `OWN_TAX_IDS` (.env) y el nombre de la entidad. Para nuevos formatos: textos FICTICIOS con la misma forma en `tests/test_f55_lectura_facturas.py`; nunca guardar facturas reales en el repositorio.

## Convenciones añadidas en F5.6 (puesta en marcha real)
- Dos instalaciones con el mismo `docker-compose.yml`: demostración (proyecto `sistemapropio`, `.env`) y real (`-p sistemapropio_real --env-file .env.real`, `COPIAS_DIR=./copias_real`). La semilla SOLO corre con `APP_ENV=development` (orden del contenedor `api`). Nunca mezclar volúmenes.
- `primer_admin --crear-entidad --sedes` crea la entidad, sus sedes y los departamentos del catálogo; el resto se da de alta desde la aplicación.
- Cuentas bancarias desde la pantalla con IBAN completo (cifrado); `/bank/imports/auto` reparte varios extractos por los 4 últimos dígitos del IBAN del archivo y NO adivina si falta o hay dos cuentas iguales.
- Estado y orden de los módulos pendientes: `docs/producto/plan_cierre_modulos.md`.
