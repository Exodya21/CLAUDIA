# 16 · Documentación de integraciones y APIs

Sistema Propio · versión F5.6 · 12/11/2026. Especificación completa y ejecutable en `openapi.json` (adjunto) y en
`/api/v1/docs` con el sistema en marcha.

## 1. Convenciones de la API
| Aspecto | Regla |
|---|---|
| Base | `/api/v1`, JSON UTF-8. La web la sirve en el mismo origen (`/api/*` → API), sin CORS abierto |
| Autenticación del equipo | Cookie de sesión HttpOnly (`POST /auth/login` → `/auth/mfa`). No hay tokens de API para terceros |
| Autenticación del cliente | Cookie `sp_portal` (`/portal/auth/request-code` → `/portal/auth/verify`). No es intercambiable con la del equipo |
| Autorización | Cada ruta pide un permiso del catálogo (ver 08). Entidad ajena → 404; sin permiso → 403 |
| Errores | `{"error": {"code", "message", "details", "request_id"}}` con 400/401/403/404/409/422/429 |
| Importes | Céntimos enteros (`*_cents`) |
| Fechas | ISO 8601 en UTC |
| Identificadores | UUID |
| Idempotencia | Extractos (sha256 + `ext_id`), documentos (sha256 por expediente), propuestas (`dedupe_key`), correo (clave de cola) |
| Archivos | `multipart/form-data`; descargas con `Content-Disposition`, auditadas |
| Límite de intentos | Acceso del equipo y del portal: 429 al superar el límite |

## 2. Integraciones existentes
| Integración | Sentido | Formato | Cómo |
|---|---|---|---|
| Extractos bancarios | Entrada (archivo) | Norma 43 (AEB), CAMT.053 (ISO 20022), CSV, Excel `.xlsx`/`.xls`, «.xls» HTML | `POST /bank/accounts/{id}/imports`, `/bank/imports/auto` (varios), `/bank/accounts/{id}/check` (sin guardar) |
| Pagos a proveedores | Salida (archivo) | SEPA **pain.001.001.03** | Descarga de la remesa firmada; una persona la sube a la banca electrónica |
| Mercurio (extranjería) | Salida (relleno) | JSON de la ficha (claves `rol.campo`) | Extensión de Chrome → `GET /immigration/fill/{código}` (única ruta sin sesión: hash, 15 min, 10 lecturas, auditada). **Nunca presenta** |
| Modelos oficiales EX | Salida (PDF) | PDF rellenado con `pypdf` | Mapas en `immigration/ex_forms/EXnn.json` |
| Correo saliente | Salida | SMTP + STARTTLS | Cola `comm_outbox`, adaptador `services/notify.py`. Sin contenido sensible |
| OIDC (identidad corporativa) | Entrada | OpenID Connect + PKCE | `/auth/oidc/login` y `/callback`. Proveedor pendiente (T-01) |
| Exportaciones | Salida | CSV, PDF | Cierre del mes, informes, justificantes |

## 3. Integraciones previstas (no construidas)
| Integración | Estado / decisión | Diseño recomendado |
|---|---|---|
| **MNProgram** (importar expedientes activos y plazos) | Pendiente de decisión. MNP no exporta todo en Excel | Importador por lotes con validación, aviso de duplicados **sin fusión** y la fecha legal como «pendiente de validar» |
| **Callbell / WhatsApp** | T-31 en revisión | Adaptador con cola: plantillas aprobadas de WhatsApp Business, webhooks de entrada con firma, conversación vinculada al expediente. En Odoo, un conector propio (el módulo WhatsApp es Enterprise) |
| SMS / push | T-35 | Adaptador con cola |
| Bancos por PSD2 (agregador) | Pendiente de elegir proveedor | El proveedor regulado (AISP) entrega los movimientos; el sistema los trata como un extracto más (misma idempotencia) |
| Facturación certificada (VeriFactu) | D-07, D-25 | Programa homologado: el sistema le pasa los datos y guarda la referencia (`invoice_ref`) |
| Firma electrónica | Pendiente | Proveedor cualificado (eIDAS) por adaptador |
| DEHú / LexNET | D-09: sin automatismo | Solo con interfaz autorizada y autorización del profesional |
| Pasarela de pago de citas | F1.3 | Pago previo con reserva caducable y retorno idempotente |

**Patrón para toda integración nueva:**
1. Adaptador aislado.
2. Cola de salida (*outbox*) con clave de idempotencia y reintentos.
3. Webhooks de entrada con firma verificada y deduplicados.
4. Secretos en variables seguras.
5. Auditoría de cada envío y cada recepción.
6. Nunca datos sensibles en URL ni en registros.

## 4. Integración con Odoo Community
Si se mantiene alguna pieza de este sistema como servicio junto a Odoo (por ejemplo, la lectura de documentos):
- Odoo llama al servicio por HTTP interno (red privada, token de servicio), nunca desde el navegador.
- El servicio devuelve **propuestas** (JSON) y Odoo las guarda como no validadas.
- Odoo expone su propia API externa por XML-RPC/JSON-RPC (`/xmlrpc/2/object`, `/jsonrpc`); en Odoo 17+, también
  JSON-2.
- Para terceros: usuario técnico con permisos mínimos y clave de API de Odoo (Preferencias → Seguridad de la cuenta).

## 5. Agentes (integración interna por eventos)
| Agente | Nombre | Requisitos que cubre | Se activa con |
|---|---|---|---|
| `conciliacion` | Conciliación bancaria | DR-CON-2, DR-CON-3 | `bank.imported` + ejecución programada |
| `mensajes` | Mensajes al cliente | DR-MSG-1, DR-MSG-4, DR-MSG-5, DR-MSG-8, DR-MSG-9, DR-PLT-1, DR-PLT-2, DR-PLT-3, DR-PLT-4, DR-PLT-5 | `case.opened`, `case.closed`, `task.created`, `task.changed` + ejecución programada |
| `recepcion` | Recepción y caja | DR-REC-3, DR-REC-4, DR-REC-8, DR-REC-9 | `cash.closed`, `payment.duplicate_override` + ejecución programada |
| `rrhh` | Avisos de plantilla | DR-RH-4, DR-RH-5, DR-RH-6 | `hr.leave.requested` + ejecución programada |
| `contabilidad` | Proveedores, tesorería y cierre | DR-CON-4, DR-CON-7, DR-CON-8 | `treasury.batch.proposed` + ejecución programada |

Eventos emitidos: `bank.imported`, `case.opened`, `case.closed`, `task.created`, `task.changed`, `cash.closed`,
`payment.duplicate_override`, `hr.leave.requested`, `treasury.batch.proposed`.

## 6. Catálogo completo de rutas
229 rutas, agrupadas por recurso. Generado desde la especificación OpenAPI.

### `/api/v1/accounting` (31)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/accounting/suppliers` | List Suppliers |
| POST | `/api/v1/accounting/suppliers` | Create Supplier |
| PATCH | `/api/v1/accounting/suppliers/{supplier_id}` | Update Supplier |
| POST | `/api/v1/accounting/accounts/{account_id}/iban` | Set Account Iban — IBAN completo de una cuenta propia (cifrado): necesario para generar el fichero de la remesa. |
| POST | `/api/v1/accounting/invoices/read` | Read Upload — Lee una factura y PROPONE sus datos (no guarda nada): proveedor por CIF, importes y posibles duplicados. |
| POST | `/api/v1/accounting/invoices` | Register Invoice |
| GET | `/api/v1/accounting/invoices` | List Invoices |
| GET | `/api/v1/accounting/invoices/{invoice_id}/file` | Invoice File |
| POST | `/api/v1/accounting/invoices/{invoice_id}/decide` | Decide Invoice |
| GET | `/api/v1/accounting/treasury` | Treasury View |
| POST | `/api/v1/accounting/batches` | Propose Batch |
| GET | `/api/v1/accounting/batches` | List Batches |
| POST | `/api/v1/accounting/batches/{batch_id}/sign` | Sign |
| GET | `/api/v1/accounting/batches/{batch_id}/sepa.xml` | Batch File |
| POST | `/api/v1/accounting/batches/{batch_id}/sent` | Mark Sent — Una persona confirma que ha subido el fichero a la banca electrónica (el sistema no lo envía). |
| POST | `/api/v1/accounting/batches/{batch_id}/cancel` | Cancel Batch |
| GET | `/api/v1/accounting/dashboard` | Dashboard |
| POST | `/api/v1/accounting/closes` | Create Close |
| GET | `/api/v1/accounting/closes` | List Closes |
| POST | `/api/v1/accounting/closes/{close_id}/review` | Review Close |
| POST | `/api/v1/accounting/closes/{close_id}/approve` | Approve Close |
| GET | `/api/v1/accounting/closes/{close_id}/export.csv` | Export Close |
| GET | `/api/v1/accounting/routine` | Get Routine — Comprueba la rutina AHORA (crea los pasos del periodo y da por hechos los que ya lo están) y la devuelve. |
| POST | `/api/v1/accounting/routine/{item_id}/na` | Routine Na |
| GET | `/api/v1/accounting/routine/owners` | Routine Owners |
| PUT | `/api/v1/accounting/routine/owners` | Set Owner |
| GET | `/api/v1/accounting/reports` | List Reports |
| POST | `/api/v1/accounting/reports` | Generate Report — Genera ahora (o vuelve a generar: versión nueva) el informe del periodo que contiene `day`. |
| GET | `/api/v1/accounting/reports/{report_id}` | Get Report |
| GET | `/api/v1/accounting/reports/{report_id}/file` | Report File |
| POST | `/api/v1/accounting/reports/{report_id}/review` | Review |

### `/api/v1/immigration` (24)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/immigration/procedures` | Procedures |
| POST | `/api/v1/immigration/procedures/{proc_id}/approve` | Approve Procedure |
| GET | `/api/v1/immigration/cases/{case_id}` | Get Case |
| POST | `/api/v1/immigration/cases/{case_id}` | Setup Case |
| PATCH | `/api/v1/immigration/cases/{case_id}` | Update Case |
| POST | `/api/v1/immigration/cases/{case_id}/stage` | Change Stage |
| POST | `/api/v1/immigration/cases/{case_id}/documents` | Upload |
| GET | `/api/v1/immigration/documents/{doc_id}/file` | Document File |
| POST | `/api/v1/immigration/documents/{doc_id}/reread` | Reread Document — Vuelve a leer un documento ya subido con la versión actual de la lectura. No cambia su estado ni su tipo |
| GET | `/api/v1/immigration/documents/{doc_id}/diagnostic` | Document Diagnostic — Estructura del texto leído SIN datos: etiquetas del formulario visibles, todo lo demás enmascarado. |
| POST | `/api/v1/immigration/documents/{doc_id}/review` | Review Document |
| POST | `/api/v1/immigration/documents/{doc_id}/retire` | Retire Document |
| GET | `/api/v1/immigration/cases/{case_id}/package/check` | Package Check |
| GET | `/api/v1/immigration/cases/{case_id}/package.zip` | Package Zip |
| GET | `/api/v1/immigration/inbox` | Inbox |
| GET | `/api/v1/immigration/forms` | List Forms |
| GET | `/api/v1/immigration/cases/{case_id}/form` | Get Form |
| PUT | `/api/v1/immigration/cases/{case_id}/form` | Save Form |
| GET | `/api/v1/immigration/cases/{case_id}/form.pdf` | Form Pdf |
| GET | `/api/v1/immigration/office` | Get Office |
| PUT | `/api/v1/immigration/office/{org_id}` | Put Office |
| POST | `/api/v1/immigration/cases/{case_id}/fill-token` | Create Token |
| GET | `/api/v1/immigration/fill/{code}` | Read With Token — Lo llama la extensión (sin sesión). Devuelve SOLO la ficha confirmada de un expediente. |
| GET | `/api/v1/immigration/cases/{case_id}/reading-review` | Reading Review — Revisión automática de la lectura de todos los documentos del expediente y de la ficha. Solo nombres de |

### `/api/v1/bank` (19)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/bank/accounts` | List Accounts |
| POST | `/api/v1/bank/accounts` | Create Account |
| POST | `/api/v1/bank/accounts/{account_id}/active` | Set Active |
| POST | `/api/v1/bank/accounts/{account_id}/imports` | Import Statement |
| GET | `/api/v1/bank/accounts/{account_id}/imports` | List Imports |
| POST | `/api/v1/bank/accounts/{account_id}/check` | Check Statement — Comprueba si el sistema sabe leer un extracto SIN GUARDAR NADA: ni el archivo ni los movimientos. |
| POST | `/api/v1/bank/imports/auto` | Import Many — Varios extractos a la vez (Caixa, BBVA…): cada archivo va a la cuenta cuyo IBAN termina como el del extracto. |
| GET | `/api/v1/bank/imports/{import_id}/original` | Download Original |
| GET | `/api/v1/bank/accounts/{account_id}/demo-statement` | Demo Statement — Extracto Norma 43 FICTICIO para probar la conciliación. Solo existe en desarrollo y pruebas. |
| GET | `/api/v1/bank/accounts/{account_id}/movements` | List Movements |
| GET | `/api/v1/bank/accounts/{account_id}/errors` | List Errors |
| GET | `/api/v1/bank/movements/{movement_id}` | Get Movement |
| GET | `/api/v1/bank/movements/{movement_id}/candidates` | Candidates — Opciones para conciliar a mano: cobros registrados (ingresos), devoluciones pagadas (cargos) y movimientos |
| POST | `/api/v1/bank/movements/{movement_id}/validate` | Validate |
| POST | `/api/v1/bank/movements/{movement_id}/reject` | Reject |
| POST | `/api/v1/bank/movements/{movement_id}/manual` | Manual |
| POST | `/api/v1/bank/movements/{movement_id}/justify` | Justify |
| GET | `/api/v1/bank/accounts/{account_id}/export.csv` | Export Csv — Exportación para la gestoría (T-40: hasta tener plan de cuentas no se proponen asientos). |
| POST | `/api/v1/bank/reconcile/run` | Run Now |

### `/api/v1/economy` (16)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/economy/cases/{case_id}` | Case Economy |
| GET | `/api/v1/economy/lookup` | Lookup — Localiza expedientes por código para registrar un cobro o una devolución (Recepción, ATC). |
| POST | `/api/v1/economy/cases/{case_id}/charges` | Add Charge |
| POST | `/api/v1/economy/charges/{charge_id}/cancel` | Cancel Charge |
| POST | `/api/v1/economy/cases/{case_id}/payments` | Add Payment |
| GET | `/api/v1/economy/payments` | List Payments |
| POST | `/api/v1/economy/payments/{payment_id}/confirm` | Confirm Payment |
| POST | `/api/v1/economy/payments/{payment_id}/annul` | Annul Payment |
| POST | `/api/v1/economy/cases/{case_id}/refunds` | Add Refund |
| GET | `/api/v1/economy/refunds` | List Refunds |
| GET | `/api/v1/economy/refunds/{refund_id}` | Get Refund |
| POST | `/api/v1/economy/refunds/{refund_id}/transition` | Transition Refund |
| GET | `/api/v1/economy/cash` | Cash Overview |
| POST | `/api/v1/economy/cash/{branch_id}/movements` | Cash Movement |
| POST | `/api/v1/economy/cash/{branch_id}/closings` | Cash Closing — Cierre del día (mismo circuito que Recepción: queda pendiente de validar por otra persona). |
| GET | `/api/v1/economy/summary` | Summary |

### `/api/v1/expenses` (16)

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/api/v1/expenses` | Upload |
| GET | `/api/v1/expenses` | List Expenses |
| GET | `/api/v1/expenses/catalog` | Catalog |
| GET | `/api/v1/expenses/{expense_id}` | Get Expense |
| PATCH | `/api/v1/expenses/{expense_id}` | Update |
| GET | `/api/v1/expenses/{expense_id}/receipt` | Receipt |
| POST | `/api/v1/expenses/{expense_id}/submit` | Submit |
| POST | `/api/v1/expenses/{expense_id}/review` | Review |
| POST | `/api/v1/expenses/{expense_id}/reconcile` | Reconcile |
| GET | `/api/v1/expenses/cards/all` | List Cards |
| POST | `/api/v1/expenses/cards` | Add Card |
| GET | `/api/v1/expenses/cards/holders` | Holders |
| POST | `/api/v1/expenses/cards/import` | Import Statement — Extracto en CSV con columnas: fecha;concepto;importe;tarjeta (4 últimos dígitos). Cargos en positivo. |
| GET | `/api/v1/expenses/cards/transactions` | Card Transactions |
| GET | `/api/v1/expenses/summary/month` | Monthly |
| GET | `/api/v1/expenses/summary/month.csv` | Monthly Csv |

### `/api/v1/hr` (15)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/hr/employees` | List Employees |
| POST | `/api/v1/hr/employees` | Add Employee |
| GET | `/api/v1/hr/me` | Me |
| GET | `/api/v1/hr/employees/{employee_id}` | Get Employee |
| PATCH | `/api/v1/hr/employees/{employee_id}` | Update Employee |
| POST | `/api/v1/hr/employees/{employee_id}/documents` | Upload Document |
| GET | `/api/v1/hr/documents/{doc_id}/file` | Document File |
| POST | `/api/v1/hr/documents/{doc_id}/review` | Review Document |
| POST | `/api/v1/hr/employees/{employee_id}/leaves` | Request Leave |
| GET | `/api/v1/hr/leaves` | List Leaves |
| POST | `/api/v1/hr/leaves/{leave_id}/decide` | Decide |
| POST | `/api/v1/hr/leaves/{leave_id}/cancel` | Cancel Leave |
| GET | `/api/v1/hr/calendar` | Calendar |
| GET | `/api/v1/hr/payroll` | Payroll |
| POST | `/api/v1/hr/import` | Import Employees — Importación desde una hoja (CSV exportado de MN Program u otra). Primero se previsualiza: nuevas, duplicadas y |

### `/api/v1/comm` (14)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/comm/inbox` | Inbox — Bandeja del equipo: conversaciones que puede ver, con lo pendiente de leer y los urgentes sin confirmar. |
| GET | `/api/v1/comm/cases/{case_id}/thread` | Case Thread |
| GET | `/api/v1/comm/contacts/{contact_id}/thread` | Contact Thread |
| GET | `/api/v1/comm/threads/{thread_id}` | Get Thread |
| POST | `/api/v1/comm/threads/{thread_id}/messages` | Send Message |
| PATCH | `/api/v1/comm/messages/{message_id}` | Edit Message |
| GET | `/api/v1/comm/messages/{message_id}/versions` | Message Versions |
| POST | `/api/v1/comm/messages/{message_id}/hide` | Hide Message — Ocultar al cliente (nunca borrar): el mensaje sigue en el historial del despacho con el motivo. |
| GET | `/api/v1/comm/attachments/{att_id}/file` | Attachment File |
| POST | `/api/v1/comm/attachments/{att_id}/incorporate` | Incorporate — Pasa un archivo del chat a los documentos del expediente de extranjería (con su lectura automática). |
| GET | `/api/v1/comm/threads/{thread_id}/export.pdf` | Export Pdf — PDF de la conversación con fecha y huella SHA-256 del contenido. `cliente`: lo que ve el cliente; |
| GET | `/api/v1/comm/contacts/{contact_id}/portal` | Portal Status |
| POST | `/api/v1/comm/contacts/{contact_id}/portal/invite` | Portal Invite |
| POST | `/api/v1/comm/contacts/{contact_id}/portal/block` | Portal Block |

### `/api/v1/auth` (13)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/auth/mode` | Auth Mode |
| GET | `/api/v1/auth/demo/users` | Demo Users |
| POST | `/api/v1/auth/demo/login` | Demo Login |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/mfa` | Mfa |
| POST | `/api/v1/auth/enroll/start` | Enroll Start |
| POST | `/api/v1/auth/enroll/confirm` | Enroll Confirm |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/auth/sessions` | My Sessions |
| POST | `/api/v1/auth/sessions/{session_id}/revoke` | Revoke My Session |
| POST | `/api/v1/auth/password` | Change Password |
| GET | `/api/v1/auth/oidc/login` | Oidc Login |
| GET | `/api/v1/auth/oidc/callback` | Oidc Callback |

### `/api/v1/admin` (13)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/admin/catalog` | Catalog |
| GET | `/api/v1/admin/users` | List Users |
| POST | `/api/v1/admin/users` | Create User |
| GET | `/api/v1/admin/users/{user_id}` | Get User |
| PATCH | `/api/v1/admin/users/{user_id}` | Update User |
| POST | `/api/v1/admin/users/{user_id}/deactivate` | Deactivate |
| POST | `/api/v1/admin/users/{user_id}/reactivate` | Reactivate |
| POST | `/api/v1/admin/users/{user_id}/reset-credentials` | Reset Credentials — Contraseña provisional nueva + doble verificación a configurar de nuevo; cierra todas sus sesiones. |
| POST | `/api/v1/admin/users/{user_id}/memberships` | Add Membership |
| POST | `/api/v1/admin/memberships/{membership_id}/end` | End Membership |
| POST | `/api/v1/admin/sessions/{session_id}/revoke` | Revoke Session |
| POST | `/api/v1/admin/users/{user_id}/revoke-sessions` | Revoke All |
| GET | `/api/v1/admin/backups` | Backups |

### `/api/v1/portal` (11)

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/api/v1/portal/auth/request-code` | Request Code |
| POST | `/api/v1/portal/auth/verify` | Verify |
| POST | `/api/v1/portal/auth/logout` | Logout |
| GET | `/api/v1/portal/me` | Me |
| POST | `/api/v1/portal/terms` | Accept Terms |
| GET | `/api/v1/portal/threads` | My Threads |
| GET | `/api/v1/portal/threads/{thread_id}` | Thread |
| POST | `/api/v1/portal/threads/{thread_id}/messages` | Write |
| PATCH | `/api/v1/portal/messages/{message_id}` | Edit |
| POST | `/api/v1/portal/messages/{message_id}/confirm` | Confirm |
| GET | `/api/v1/portal/attachments/{att_id}/file` | Attachment |

### `/api/v1/reception` (9)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/reception/branches` | Branches |
| GET | `/api/v1/reception/contacts/{contact_id}/cases` | Contact Cases — Expedientes de un cliente para elegir a qué se cobra: código, materia, fase y, con `reception.balance`, |
| POST | `/api/v1/reception/payments` | Charge |
| GET | `/api/v1/reception/payments/{payment_id}/receipt.pdf` | Receipt Pdf |
| GET | `/api/v1/reception/day` | Day View |
| POST | `/api/v1/reception/cash/{branch_id}/close` | Close |
| GET | `/api/v1/reception/closings` | List Closings |
| POST | `/api/v1/reception/closings/{closing_id}/decide` | Decide |
| GET | `/api/v1/reception/report` | Report |

### `/api/v1/cases` (8)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/cases` | List Cases |
| POST | `/api/v1/cases` | Create Case |
| GET | `/api/v1/cases/eligible-users` | Eligible Users — Personas que pueden ser responsables de un expediente de esa materia (para formularios). |
| GET | `/api/v1/cases/{case_id}` | Get Case |
| POST | `/api/v1/cases/{case_id}/transition` | Transition |
| POST | `/api/v1/cases/{case_id}/assignments` | Assign |
| POST | `/api/v1/cases/{case_id}/assignments/{assignment_id}/end` | End Assignment |
| POST | `/api/v1/cases/{case_id}/relations` | Relate |

### `/api/v1/tasks` (8)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/tasks` | List Tasks |
| POST | `/api/v1/tasks` | Create Task |
| GET | `/api/v1/tasks/{task_id}` | Get Task |
| POST | `/api/v1/tasks/{task_id}/location` | Set Location — Completar o corregir el lugar de una cita, conciliación o juicio (los avisos al cliente lo necesitan). |
| POST | `/api/v1/tasks/{task_id}/transition` | Transition |
| POST | `/api/v1/tasks/{task_id}/legal-deadline` | Propose Legal |
| POST | `/api/v1/tasks/{task_id}/legal-deadline/decision` | Decide Legal |
| GET | `/api/v1/tasks/agenda/week` | Week — Agenda semanal (I-069, I-076): lunes a domingo, con tareas vencidas arrastradas al principio. |

### `/api/v1/contacts` (7)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/contacts` | Search Contacts |
| POST | `/api/v1/contacts` | Create Contact |
| POST | `/api/v1/contacts/duplicate-check` | Duplicate Check |
| GET | `/api/v1/contacts/{contact_id}` | Get Contact |
| PATCH | `/api/v1/contacts/{contact_id}` | Update Contact |
| GET | `/api/v1/contacts/{contact_id}/cases` | Contact Cases |
| GET | `/api/v1/contacts/{contact_id}/history` | Contact History |

### `/api/v1/leads` (7)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/leads/origins` | Origins |
| GET | `/api/v1/leads` | List Leads |
| POST | `/api/v1/leads` | Create Lead |
| GET | `/api/v1/leads/funnel` | Funnel — Embudo (I-102, base de AT-27): mismos registros que la bandeja, sin tablas paralelas. |
| GET | `/api/v1/leads/{lead_id}` | Get Lead |
| PATCH | `/api/v1/leads/{lead_id}` | Assign |
| POST | `/api/v1/leads/{lead_id}/transition` | Transition |

### `/api/v1/agents` (6)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/agents` | List Agents |
| POST | `/api/v1/agents/{code}/settings` | Update Setting |
| GET | `/api/v1/agents/{code}/runs` | List Runs |
| POST | `/api/v1/agents/{code}/run` | Run Agent |
| GET | `/api/v1/agents/mensajes/templates` | Message Templates |
| GET | `/api/v1/agents/mensajes/metrics` | Message Metrics — Medición semanal del piloto (DR-MSG): programados, enviados, cancelados, fallidos, respuestas, derivados. |

### `/api/v1/grants` (4)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/grants` | List Grants |
| POST | `/api/v1/grants` | Create Grant |
| GET | `/api/v1/grants/lookup` | Lookup — Para el formulario de alta: localiza un expediente por código y lista a quién puede concederse. |
| POST | `/api/v1/grants/{grant_id}/revoke` | Revoke Grant |

### `/api/v1/audit-events` (2)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/audit-events` | List Events |
| GET | `/api/v1/audit-events/verify` | Verify |

### `/api/v1/proposals` (2)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/proposals` | List Proposals — Pendientes que la persona puede decidir. Cada pantalla los pide filtrados por su función: Contabilidad |
| POST | `/api/v1/proposals/{proposal_id}/decide` | Decide |

### `/api/v1/me` (1)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/me` | Me |

### `/api/v1/organizations` (1)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/organizations` | Organizations — Solo las entidades donde el usuario tiene pertenencia vigente. |

### `/api/v1/permissions` (1)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/permissions` | Permission Catalog — Descripción legible de cada permiso (para la pantalla de permisos efectivos). |

### `/api/v1/health` (1)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/health` | Health |
