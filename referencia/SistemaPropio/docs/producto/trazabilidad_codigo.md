# Trazabilidad requisito → código → prueba (F0.1)

Solo se listan los IDs con implementación real. El resto de los 208 sigue en [`mapa_cobertura.md`](mapa_cobertura.md)
con su fase.

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| Q-1.1 | Multicompañía | `models.Organization`, `Membership`; `policy.py` (frontera por entidad) | `test_multiempresa_y_ataques.py` | Separación de datos entre entidades. Facturación intercompany: F5 |
| Q-1.2 | Control de accesos y seguridad de contactos | `security/catalog.py`, `security/policy.py`, `routers/contacts.py`, `routers/cases.py` | AT-01, AT-02 | Completo para contactos y expedientes F0.1 |
| U-18 | Multisede y soporte Colombia | Semilla: 3 sedes + entidad Colombia; `membership.branch_id` | `test_soporte_colombia_sin_acceso…` | Estructura; acceso internacional bloqueado por D-17 |
| Q-6.17 | Historial y autoría inalterable | `audit.py`, migración `0001` (triggers), `routers/audit_log.py` | AT-03 | Completo para F0.1 |
| Q-6.23 | No editar/eliminar lo ajeno | Sin DELETE; triggers anti‑borrado; `contact.update` solo con nivel `full` | `test_no_existe_borrado…`, `test_control_de_version…` | Base. Agendas/tareas: F2.2 |
| I-003 | Detección de duplicados | `/contacts/duplicate-check`, 409 `posible_duplicado`, `duplicate_review` | AT-04 | Por documento; fuzzy por nombre: F1.1 |
| I-120 | Control de accesos, registro de errores | Motor de política, `errors.py` (request_id), auditoría de denegaciones | AT-01, AT-03 | Orquestación/colas: F1.3 |
| Q-6.2 | Estructura del expediente, numeración | `CaseFile`, `CaseCodeCounter`, `seed.next_case_code` | AT-01 (estructura) | Mínimo; alta y fases: F2.1 |
| D-13 | Recepción sin acceso transversal | Niveles `minimal`/`metadata` | AT-02 | Propuesta implementada, pendiente de aprobación |
| D-14 | Q-6.20B | `scripts/build_coverage.py` | Recuento 208 | Resuelta |
| U-17 | Sin reservas biométricas | No existe ninguna funcionalidad ni texto que las ofrezca | Revisión de interfaz | Cumplido por exclusión |

## F1.2 CRM + F2.1 expedientes + F2.2 tareas (02/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| Q-2.1 | Captación con origen obligatorio | `models_work.Lead`, `LeadOrigin`; `routers/leads.py` (POST) | AT-05 | Completo; campaña obligatoria por origen configurable |
| Q-2.7 | Trazabilidad lead → cita → expediente | `Lead.case_file_id`, `convert_on_case_open`, `/leads/funnel` | AT-06 | Lead → expediente. Cita pagada e ingreso: F1.3/F5 |
| Q-2.8 | TikTok Live / seguimiento 24 h · 72 h · 7 d | `follow_up_level`, `/leads?follow_up=true` | `test_seguimiento_*` | Alertas visibles en bandeja e Inicio; sin envíos automáticos (M12) |
| Q-3.1 | Oportunidades estancadas y flujos reversibles | `FLOW` de leads con reapertura motivada | `test_transiciones_*` | Completo para leads |
| I-099, I-102 | Consultas atendidas, conversión | `/leads/funnel` por estado y origen | `test_marketing_*` | Base del cuadro de mando (M16) |
| Q-6.2 | Alta de expediente, secuencia, especialidad | `POST /cases`, `next_case_code` | AT-15 | Completo |
| I-007 | Apertura de expedientes | `POST /cases` desde cliente o lead | AT-06, AT-15 | Manual asistida (no automática sin encargo) |
| I-008, I-088 | Asignación de responsables / gestor | `/cases/{id}/assignments`, `eligible()` por rama | `test_responsables_por_rama` | Completo |
| I-009, I-092 | Actualización y seguimiento | `last_activity_at`, `case_phase_event` | AT-16 | Completo |
| I-010 | Clasificación por materia, fase y prioridad | Filtros de `/cases` | `test_indicador_*` | Materia y fase; prioridad vive en tareas |
| Q-6.4 | Fases e indicador de inactividad | `FLOW`, `INACTIVITY_DAYS` | AT-16, `test_indicador_*` | Umbral pendiente T-11 |
| I-067, I-068 | Señalamientos y conciliaciones | `Task.kind` + inicio/fin/lugar | `test_senalamiento_exige_horario` | Registro manual (sin portales, D-09) |
| I-069, I-076 | Calendario y agendas | `/tasks/agenda/week`, pantalla Agenda | recorrido f2_05 | Semana, mías / todas visibles |
| I-073, Q-6.20B | Control de vencimientos, orden por fecha límite | Orden por plazo legal o fecha interna; `overdue` | `test_agenda_*` | Completo |
| I-074 | Detección de solapamientos | `_overlaps` | `test_agenda_solapes_y_orden` | Por persona responsable |
| Q-6.9, Q-6.10 | Plazos procesales | Plazo legal propuesto + validación letrada; **sin cálculo** | AT-19 | Bloqueado el cálculo por D-02/D-03/D-04 |
| Q-6.15 | Tipificación por colores | `KindBadge` por tipo de tarea | Revisión de interfaz | Completo |
| Q-6.23 | No editar tareas ajenas | `_can_edit`, `task.manage.others` | `test_q623_*` | Completo |
| U-16 | Tarea completada / pospuesta con motivo y responsable | `TaskEvent` con fecha anterior y nueva | AT-20 | Completo |

## F0.2 Acceso seguro, sesiones, administración y copias (02/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| Q-1.2 | Control de accesos y seguridad | `security/credentials.py` (Argon2id + TOTP cifrado), `routers/auth.py`, `security/auth.py` (`user_session`) | `test_f02_acceso.py` | Acceso local con doble verificación completo; OIDC listo a falta de T-01 |
| Q-1.2 | Gestión de usuarios por rol/sede/departamento | `routers/admin.py`, pantalla Administración | `test_f02_admin.py`, recorrido F0.2 | Completo para roles del catálogo; organigrama real pendiente de T-08 |
| I-120 | Control de accesos, registro de errores | `security/ratelimit.py` (`auth_attempt`), auditoría de cada fallo y bloqueo | `test_bloqueo_*` | Completo para acceso |
| Q-6.23 | No modificar lo ajeno | Administración acotada por entidad; nadie se retira a sí mismo | `test_no_puede_quitarse…`, `test_usuario_compartido…` | Completo |
| Q-6.17 | Autoría inalterable | Eventos `auth.*`, `admin.*`, `session.revoke`, `backup.verify` con antes/después | Todos los tests F0.2 | Completo |
| AT-29 | Copia y restauración | `ops/backup.py`, `ops/copia.sh`, `COPIA_SEGURIDAD.bat`, `backup_run` (solo inserción) | `test_f02_copias.py` | Restauración comprobada; copia externa cifrada pendiente de T-02 |
| U-18 | Multisede | Pertenencias con sede/departamento desde Administración | `test_sede_o_departamento_de_otra_entidad_rechazado` | Completo |
| (S de la matriz) | Autorización puntual | `GET /grants/lookup` + formulario en Ajustes | `test_alta_de_autorizacion_desde_formulario`, recorrido F0.2 | Completo (antes solo por API) |

## F5.0 Control económico no fiscal y gastos de empresa (03/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| Q-3.9 | Reclamaciones y devoluciones con Contabilidad | `routers/economy.py` (`REFUND_FLOW`), `Refund`, `RefundEvent` | `test_devolucion_atc_registra_contabilidad_decide` | Completo (A-09) sin facturas de abono |
| Q-4.4 | Registro de devoluciones | Devoluciones con pago y referencia; caja si es efectivo | `test_no_se_devuelve_mas_de_lo_cobrado` | Registro; factura de abono → programa homologado (D-25) |
| Q-4.14 | Cajas chicas por sede | `CashMovement`, `CashClosing`, `/economy/cash` | `test_caja_arqueo_…` | Completo |
| Q-4.13 | Digitalización de gastos con OCR | `services/receipts.py` (Tesseract local), `routers/expenses.py` | `test_lectura_propone…`, `test_parser_de_tickets` | Completo con confirmación humana; IA externa: T-20 |
| Q-4.5 | Conciliación (tarjetas) | Importación de extracto CSV y conciliación propuesta | `test_tarjeta_de_empresa_y_extracto` | Tarjetas de empresa; conciliación bancaria general: D-25 |
| Q-2.6, Q-4.3 | Cobros | `Payment` (efectivo, TPV, transferencia, Bizum) | `test_recepcion_cobra_…` | Registro manual; pasarela y enlaces de pago: F1.3 |
| Q-4.7, Q-6.19 | Honorarios | `Charge`: importe que introduce una persona | `test_importe_pactado_…` | **Sin cálculo** (D-05) |
| Q-4.8 | Suplidos | Tipo «gasto por cuenta del cliente» sin tratamiento contable | — | Bloqueado por D-18 |
| I-101, I-110 | Expedientes contratados, cuadro por sede | `/economy/summary` | `test_resumen_…` | Base del cuadro de mando (M16) |

## F4.1 Expediente de extranjería — fase 1 (05/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| I-007…I-010, Q-6.2 | Expediente con fases hasta la resolución | `ImmigCase`, `ImmigStageEvent` (solo inserción), `STAGE_FLOW` en `immigration/catalog.py`, `/immigration/cases/{id}/stage` | `test_fases_requerimiento_crea_tarea_sin_calcular_plazo` | Completo; fases con efecto jurídico solo letrado/Dirección |
| M11 | Tipos de trámite y documentación exigida | Catálogo versionado de 14 trámites con fuente oficial (`immigration/catalog.py`, `sync.py`, `ImmigProcedure`) | `test_catalogo_…`, `test_cambio_en_el_catalogo_crea_version_nueva…` | Pendiente de validar por Legal (T-23) |
| I-078, I-079, Q-6.6 | Documentos cifrados y lectura automática | `services/vault.py` (Fernet), `immigration/reader.py` (Tesseract local), `immigration/mrz.py` (OACI 9303 TD3/TD1 con dígitos de control y reparación O/0) | `test_lectura_de_pasaporte_…`, `test_mrz_…` | Lectura propuesta + confirmación humana |
| I-083, I-087 | Avisos de documentos caducados o incoherentes | `_doc_warnings`, `_detail.alerts`, bandeja `/immigration/inbox` | `test_avisos_caducado_titular_distinto_y_duplicado`, `test_bandeja_y_semilla` | Caducidad, titular distinto, duplicado, MRZ errónea, formato y tamaño para Mercurio |
| D-09, A-11 | Presentación en Mercurio | Paquete `.zip` (orden de la hoja, PDF/JPG ≤ 6 MB, índice y ficha de datos) | `test_paquete_mercurio` | **Sin presentación automática**; extensión de relleno: T-24 |
| D-01, D-03 | Plazos de requerimientos | Tarea `plazo` para el letrado sin fecha legal | `test_fases_requerimiento_…` | Sin cálculo (T-26) |
| AT-29 | Copias con documentos | `ops/copia.sh` y `ops/backup.py` (`_documentos.tar`) | `test_at29_copia_incluye_documentos_de_expedientes` | Completo |

## F4.2 Ficha del modelo EX y extensión que rellena Mercurio (05/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| M11, I-083 | Rellenar Mercurio con los datos del expediente | `routers/immigration_forms.py` (ficha, código), `apps/extension-mercurio/` | `test_f42_formularios.py`, `recorrido_f42.mjs`, `extension_mercurio.test.ts` | Relleno asistido; **sin presentación** (A-11, D-09, T-24) |
| Q-6.2 | Datos de la solicitud una sola vez | `immig_form` (migración `0006`), `immigration/forms.py` (16 modelos EX + ficha general) | `test_ficha_propone…`, `test_ficha_general…` | Propuestas confirmadas por una persona |
| I-078 | Modelo oficial relleno | `forms.fill_pdf` (vista previa interna) | `test_dieciseis_modelos…`, `test_domicilio_compuesto…` | Vista previa; el oficial lo genera Mercurio |
| Q-1.2 | Datos del despacho como representante | `immig_office_profile`, permiso `immig.office.manage` | `test_datos_del_despacho…` | Completo |

## F4.3 Lectura de documentos → ficha del formulario (05/11/2026)

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| I-079, Q-6.6 | Leer los documentos aportados y proponer los datos | `immigration/extract.py` (contrato, padrón, TIE, tasa, vida laboral; NIE/DNI/CIF con control), `reader.py` (MRZ en PDF escaneado de varias páginas) | `test_f43_lectura_documentos.py` | Propuesta; una persona valida el documento y guarda la ficha |
| Q-6.2, I-083 | Datos del empleador y del contrato una sola vez para Mercurio | `routers/immigration_forms.py::_proposals` (origen por documento, contradicciones, titular distinto), sección «Contrato de trabajo» en modelos con empleador | `test_datos_leidos_solo_pasan…`, `recorrido_f43.mjs` | Relleno asistido sin presentación (T-24) |
| I-087 | Comprobación de la tasa | aviso de tasa sin NRC | `test_tipo_corregido…` | Aviso; no se consulta la AEAT |

## F2.3 Portal del cliente y conversaciones por expediente (06/11/2026) · ADR-0009 · T-31

| ID | Necesidad | Implementación | Prueba | Alcance cubierto |
|---|---|---|---|---|
| I-097, Q-6.18 | Registro de comunicaciones / historial unificado | `models_comm.py`, `routers/comm.py` (hilo por expediente y general, nada se borra, versiones, exportación con huella) | `test_f23_*`, `recorrido_f23.mjs` | Portal propio; correo de Outlook e historial de WhatsApp pendientes |
| I-091, Q-6.3 | Mensaje de bienvenida y solicitud inicial | `comm/templates.py` (`WELCOME`, `solicitud_documentos` con la lista del trámite) | `test_invitacion…`, recorrido paso 2 | Por el portal, no por WhatsApp (T-31); texto sin afirmaciones de plazos (D-10), pendiente T-32 |
| I-093, Q-3.3, I-115 | Mensajes por WhatsApp / Callbell | **Sustituido por el portal propio (T-31)**; se conservan hasta el acta T-36 | — | No se implementa WhatsApp |
| Q-3.4 | Lista negra de contactos | Bloqueo del acceso al portal con motivo (`/portal/block`) | `test_bloquear…` | En el portal propio (D-20 deja de depender de Meta) |
| I-090, I-096 | Avisos de apertura y de cambio de estado | Avisos importantes/urgentes y correo sin contenido (`core.notify_client`) | `test_urgente…`, `test_correos…` | Aviso manual del equipo; los automáticos por cambio de fase, pendientes |
| I-070, Q-6.10 | Avisos de juicio y recordatorios | Plantillas `senalamiento_juicio`, `citacion_conciliacion` con fecha de la agenda; confirmación y escalado a 24 h | `test_urgente_sin_confirmar…` | Sin recordatorios programados todavía |
| Q-6.13 | Portal del cliente para subir pruebas y archivos | `routers/portal.py` (lista de documentos que faltan, subida, paso al expediente con lectura) | `test_pendientes_del_tramite…` | PDF/JPG/PNG ≤ 20 MB; audio y vídeo pendientes |
| U-15 | Comunicación al cliente de usted, sin promesas | Textos del portal y plantillas | revisión de textos (T-32) | — |
| Q-4.5, I-074, I-075, DR-CON-2 | Importar extractos y conciliar cobros con el banco | `bank/parsers.py` (Norma 43, CAMT.053, CSV; ids estables), `bank/service.py` (original cifrado, cuadre de saldos y continuidad, sin duplicados), `routers/bank.py` | `test_f51_*` (lectura, cuadre, reimportación), `recorrido_f51.mjs` pasos 1–2 | Formato real de cada banco pendiente de ejemplo anonimizado (T-39) |
| DR-CON-3 | Conciliación automática con explicación y excepciones | `bank/matcher.py` (reglas referencia, Bizum, TPV con comisión, traspaso, devolución, importe y fecha), `agents/conciliacion.py` | `test_reglas_proponen_y_explican`, `test_validar_confirma_cobro…`, recorrido pasos 3–7 | Siempre valida Contabilidad |
| DR-CON-1 (en parte), T-38 | Cuentas A/B/C por actividad | `models_bank.BankAccount` (purpose, activity), aviso si el cobro entra en la cuenta de otra actividad | `test_f51_*` | Estructura pendiente de T-38 |
| «Motores» de Dirección | Agentes coordinados por eventos con bandeja única | `agents/` (base, engine, registry), `models_agents.py`, `routers/agents.py`, `ops/agents.py` | `test_panel_de_agentes…`, recorrido paso 9 | ADR-0010 |
| DR-MSG-1, DR-PLT-1, I-091 | Bienvenida al abrir el expediente | `agents/mensajes.py`, `comm/auto_templates.py` | `test_bienvenida_se_propone_sin_duplicar`, recorrido paso 8 | Textos pendientes de T-32 |
| DR-MSG-5, DR-PLT-2…5, I-070, Q-6.10 | Avisos de fecha y recordatorio del día anterior (10:00, T-46) | `agents/mensajes.py` (`_task`), `POST /tasks/{id}/location` | `test_avisos_de_fecha_y_recordatorio` | Sin lugar no se avisa |
| DR-MSG-4 | Seguimiento periódico | `agents/mensajes.py` (`_follow_ups`, 75 días, T-45) | `test_seguimiento_75_dias` | — |
| DR-MSG-8, DR-MSG-9 | Trazabilidad de cada envío, sin duplicados, cancelación al cerrar | `models_agents.CommDispatch`, métricas `GET /agents/mensajes/metrics` | `test_avisos…` (cancelación), `test_bienvenida…` (sin duplicados) | — |
| DR-REC-3, Q-4.4, T-44 | Cobros de consulta/provisión/servicio con justificante no fiscal | `routers/reception.py` (`/payments`), `reception/service.py` (`issue_receipt`, numeración por sede y año), `models_reception.py` | `test_consulta_sin_expediente…`, `test_numeracion…`, `recorrido_f52_f53` paso 1 | Texto del justificante por validar (T-44) |
| DR-REC-8 | Cada cobro una sola vez; saldos pendientes | `reception/service.possible_duplicates`, agente `recepcion` (`cobro_duplicado`), `/reception/contacts/{id}/cases` | `test_cobro_repetido…`, `test_sede_ajena…`, pasos 2 y 5 | Facturación en programa homologado (D-25) |
| DR-REC-4, Q-4.14 | Caja diaria, arqueo y cierre validado por otra persona | `reception/service.close_day/decide_closing`, trigger `sp_cash_closing_guard`, agente `recepcion` | `test_cierre_del_dia…`, `test_quien_cuenta…`, pasos 3 y 5 | — |
| DR-REC-9 | Operativa y caja separadas por sede; consolidado para Dirección | `routers/reception.operable/viewable`, propuestas por sede (`BRANCH_SCOPED`) | `test_sede_ajena_y_permisos`, paso 4 | — |
| DR-REC-10, I-101 | Informe diario y semanal por oficina | `GET /reception/report` | `test_informe_diario_por_sede`, paso 6 | Visitas y citas con F5.5 |
| DR-RH-1, Q-5.1 | Ficha única e importación con duplicados y campos ausentes | `models_hr.Employee`, `routers/hr.py` (`/employees`, `/import`) | `test_plantilla…`, `test_alta…`, `test_importacion…` | Formato real de MN Program (T-10) |
| DR-RH-2 | Carpeta documental con lectura de nóminas | `models_hr.EmployeeDocument`, `hr/service.read_payslip`, `/documents/{id}/review` | `test_nomina_se_lee…`, paso 7 | — |
| DR-RH-4, Q-5.2, Q-5.3 | Vacaciones, permisos y ausencias; bajas restringidas | `models_hr.LeaveRequest`, `/leaves`, `/calendar`, `hr/service.vacation_balance/overlaps` | `test_vacaciones…`, `test_baja_medica…`, paso 10 | Festivos por sede (T-49), días por convenio (T-50) |
| DR-RH-5 | Resumen de nóminas para la gestoría sin calcularlas | `GET /hr/payroll` | `test_resumen_de_nominas…`, paso 9 | — |
| DR-RH-6 | Contratos, periodos de prueba y documentación: avisos con responsable | agente `rrhh` (`agents/rrhh.py`) → tarea en la agenda | `test_avisos_de_vencimientos…`, paso 8 | Control horario (DR-RH-3, T-41) |
| DR-CON-1 (facturas), DR-CON-4, Q-4.12 | Facturas recibidas: lectura que propone (número, CIF, fechas, base, IVA de la factura, retención, total, IBAN), comprobación base + IVA − retención = total, duplicados por archivo y por proveedor/importe/fecha, validación con actividad, oficina y centro de coste; proveedores con CIF e IBAN comprobados | `models_accounting.py` (migración `0011`), `accounting/invoices.py`, `routers/accounting.py` (`/suppliers`, `/invoices`), `components/accounting.tsx` (InvoicesPanel) | `test_proveedores_validan_cif_e_iban`, `test_factura_se_lee…`, `test_validar_o_rechazar…`, `recorrido_f54` pasos 1–4 | Entrada por correo (T-48); el sistema nunca calcula IVA |
| DR-CON-4 (alertas) | Avisos de facturas sin validar, que vencen o vencidas y de proveedores recurrentes sin factura del mes | agente `contabilidad` (`agents/contabilidad.py`) → Contabilidad → Pendientes | `test_agente_avisa_y_propone_cierre` | — |
| DR-CON-7 | Tesorería: saldos por cuenta según extracto, cajas, previsión 7/30/60/90 días; remesas con **doble firma** (nunca quien propone), fichero SEPA pain.001 que sube una persona; el cargo en el extracto marca las facturas como pagadas | `accounting/treasury.py`, `/treasury`, `/batches`, `bank/matcher.rule_factura` (reglas `remesa` y `factura`), `bank/service.validate_matches` | `test_remesa_con_doble_autorizacion…`, `test_remesa_rechazada…`, `test_cargo_de_la_remesa…`, pasos 5–7 | T-54, T-55, T-56 |
| DR-CON-5 | Coste de personal desde las nóminas confirmadas por RRHH, por oficina y actividad, agrupado si hay menos de 3 personas | `accounting/close.compute/for_viewer` | `test_cuadro_de_mando_por_actividad_y_oficina` | Cotizaciones de empresa (dato de la gestoría); T-53 |
| DR-CON-8 | Cierre provisional del mes (agente el día 5): ingresos devengados, cobros, gastos, pagos, resultado, tesorería; comparación con el mes anterior, desviaciones ≥ 15 %, pendientes y fiabilidad; borrador → revisado → aprobado (congelado con huella), recalcular crea revisión nueva; exportación CSV | `accounting/close.py`, `/dashboard`, `/closes`, ClosePanel | `test_cierre_del_mes_preparar_revisar_aprobar`, `test_nada_se_borra`, paso 8 | Asientos (DR-CON-6) bloqueados por T-40 |
| DR-CON (calendario días 1–5 y resumen de los lunes), petición de Dirección 09/11/2026 | Rutina de trabajo de Contabilidad: pasos diarios, semanales, quincenales y mensuales con responsable; hechos SOLO cuando el sistema lo comprueba; tarea en la Agenda; «no aplica» con motivo; cumplimiento por persona | `accounting/routine.py`, `models_accounting.RoutineItem/RoutineOwner` (migración `0012`), `/accounting/routine*`, `components/accounting_routine.tsx` (RoutinePanel), agente `contabilidad` | `test_f54b_rutina_informes.py` (rutina, no aplica, responsables), `recorrido_f54b` pasos 1–3 y 6 | Festivos (T-49); calendario T-57 |
| DR-CON-8, DR-REC-10 (informes), petición de Dirección 09/11/2026 | Informes semanal (lunes), quincenal (1 y 16) y mensual (día 5): foto inmutable con huella y versiones, comparación, tesorería y previsión, remesas, pendientes, cumplimiento de la rutina; PDF y CSV; correo sin cifras; revisión de Dirección | `accounting/reports.py`, `models_accounting.AccountingReport`, `/accounting/reports*`, ReportsPanel | `test_informes_se_generan_solos_y_no_cambian`, `test_informe_mensual_protege_salarios`, pasos 4–5 | T-58, T-33 (correo) |
| Q-4.5, I-074, DR-CON-2 (formatos) | Extractos en Excel (.xlsx, .xls, .xls-HTML) con filas de título, fechas de Excel, Importe o Cargo/Abono; comprobación de cuenta por IBAN del título | `bank/parsers.py` (`parse_rows`, `parse_xlsx`, `parse_xls`, `parse_html_table`) | `test_f55_extractos_excel.py` | Nombres de columna de cada banco real (T-39) |
| DR-CON-1 (lectura v2), Q-4.12 | Lectura de facturas recibidas con formatos reales: etiquetas variadas, fechas en letra, NIF con separadores, OCR de escaneados con elección de la mejor lectura, identificación por cuadre, nombre del proveedor, CIF propio descartado | `accounting/invoices.read_invoice` (`READER_VERSION = 2`), `services/receipts.LocalExtractor.ocr_pdf`, `routers/accounting.read_upload`, `QuickSupplier` | `test_f55_lectura_facturas.py` | T-59 (CIF del despacho) |
