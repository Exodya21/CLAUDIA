# 08 · Documentación de seguridad y permisos

Sistema Propio · versión F5.6 · 12/11/2026. Las tablas de roles y permisos se generan desde el catálogo del código
(`apps/api/app/security/catalog.py`), que es la fuente de verdad: se sincroniza con la base de datos en cada arranque.

## 1. Principios
1. **Denegar por defecto.** Todo endpoint pide un permiso concreto mediante `security/policy.py`. Ningún router comprueba
   roles por nombre. Lo que no está concedido, no se puede hacer.
2. **La seguridad está en el servidor.** Ocultar un botón en la interfaz no es seguridad: la API vuelve a comprobarlo todo.
3. **Ámbito en cinco niveles:** entidad (empresa) → sede → departamento → rol → asignación al expediente.
   - Entidad ajena → **404** (no se revela que existe).
   - Misma entidad sin permiso → **403**.
   - Ambos se registran en la auditoría con `audit.record_independent`, aunque la operación se deshaga.
4. **Separación de funciones**, impuesta también por la base de datos:
   - quien pide una devolución no la aprueba;
   - quien cuenta la caja no la valida;
   - quien propone una remesa no la firma, y las dos firmas son de personas distintas;
   - Dirección autoriza, pero no registra facturas ni importa extractos.
5. **Mínimo dato.** Recepción y Atención al cliente ven fichas mínimas, con documentos de identidad enmascarados. El
   salario solo lo ve quien tiene `hr.salary` o la propia persona. En los informes, el coste de personal se agrupa si hay
   menos de 3 personas.
6. **La IA y los agentes no deciden.** Proponen en una bandeja, y una persona con el permiso correspondiente acepta o
   rechaza. Las propuestas que afectan al cliente exigen además acceso completo al expediente.

## 2. Autenticación
| Método | Entornos | Detalle |
|---|---|---|
| `local` | todos | Usuario y contraseña (hash **Argon2id**) + **TOTP obligatorio** (RFC 6238, 30 s, 6 dígitos). Primer acceso: cambio de contraseña y alta del TOTP (QR o clave manual). |
| `oidc` | todos | Proveedor corporativo (T-01, pendiente de elegir) con PKCE. Exige MFA (`OIDC_REQUIRE_MFA`), comprobada en el claim `amr`. |
| `demo` | **solo** development y test | Lista de usuarios ficticios. La configuración rechaza arrancar con `demo` en staging o producción. |

- **Sesiones** en la tabla `user_session`, con cookie HttpOnly, SameSite y `Secure` obligatoria en producción.
  - Duración máxima `SESSION_TTL_MINUTES` (480) e inactividad `SESSION_IDLE_MINUTES` (60).
  - Se revocan al cambiar la contraseña, al restablecer el TOTP o desde Administración.
- **Límite de intentos:** 5 fallos por usuario y 30 por IP en 15 minutos.
- **Clientes:** el portal usa cuentas distintas (`portal_account`), con código de un solo uso enviado por correo y una
  cookie propia (`sp_portal`). Ninguna ruta del equipo acepta la cookie del portal, ni al revés.
- **Secretos de usuario** (TOTP) cifrados con `FIELD_ENCRYPTION_KEY`. Las contraseñas nunca aparecen en la auditoría.

## 3. Cifrado y protección de datos
| Qué | Cómo |
|---|---|
| Secretos TOTP, textos de mensajes, IBAN completos, números de documento del personal | Cifrado de columna Fernet (AES-128-CBC + HMAC-SHA256), clave `FIELD_ENCRYPTION_KEY` |
| Justificantes, documentos de expedientes, extractos originales, carpeta de RRHH | Archivos cifrados en volumen (`services/vault.py`, `services/receipts.py`), nunca en la base de datos |
| En tránsito | HTTPS obligatorio en producción, terminado en el proxy inverso (ver 03 · Infraestructura) |
| En reposo | Disco cifrado del servidor (LUKS / BitLocker), además del cifrado de columna y de archivos |
| Copias | `pg_dump` + archivos. Sin `.env.real` (las claves) las copias no se pueden leer: guárdelas por separado |
| Registros (logs) | Sin datos personales: identificadores enmascarados y `request_id` para correlacionar |

## 4. Roles
| Código | Rol | Abreviatura | Nº permisos | Descripción |
|---|---|---|---|---|
| `direccion` | Dirección | DIR | 61 | Visión global de la entidad; autoriza excepciones. Sus accesos también se auditan. |
| `lider_laboral` | Líder Laboral | LLab | 33 | Todos los expedientes Laborales de su ámbito; nunca Extranjería. Valida fechas legales de su rama. |
| `lider_extranjeria` | Líder Extranjería | LExt | 39 | Todos los expedientes de Extranjería de su ámbito; nunca Laboral. Valida plazos y el catálogo de trámites. |
| `recepcion` | Recepción | Rec | 13 | Localiza identidades, crea contactos y leads; ve metadatos de expedientes, nunca su contenido (D-13). |
| `atc` | Atención al cliente | ATC | 9 | Registra y escala; no decide viabilidad ni aprueba devoluciones (U-13). |
| `asesor_laboral` | Asesor Laboral | ALab | 23 | Contactos, leads y expedientes Laborales asignados. |
| `asesor_extranjeria` | Asesor Extranjería | AExt | 26 | Contactos, leads y expedientes de Extranjería asignados. |
| `gestor_laboral` | Gestor Laboral | GLab | 14 | Tramitación de expedientes Laborales asignados; gestiona documentos de identidad. |
| `contabilidad` | Contabilidad | CON | 29 | Economía de todos los expedientes (sin contenido jurídico), cobros, devoluciones, cajas y gastos. Decide devoluciones (A-09). |
| `marketing` | Marketing | MKT | 6 | Leads, orígenes y embudo. Sin acceso a expedientes, pruebas ni documentos. |
| `rrhh` | Recursos Humanos | RRHH | 8 | Plantilla, carpetas, nóminas (sin calcularlas), ausencias y vencimientos. Sin acceso a expedientes de clientes. |
| `soporte_colombia` | Soporte Colombia | SCol | 5 | Solo su alcance asignado. Acceso a datos de entidades españolas pendiente de D-17. |

## 5. Matriz rol × permiso
Abreviaturas de la tabla anterior. Generada desde el catálogo; 77 permisos, 12 roles.

| Permiso | DIR | LLab | LExt | Rec | ATC | ALab | AExt | GLab | CON | MKT | RRHH | SCol |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **contact** | | | | | | | | | | | | |
| `contact.search` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |  | ✔ |
| `contact.read.all` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| `contact.read.own` |  | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  | ✔ |
| `contact.create` | ✔ | ✔ | ✔ | ✔ |  | ✔ | ✔ |  |  |  |  |  |
| `contact.update` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `contact.identifier.manage` | ✔ |  | ✔ |  |  |  |  | ✔ |  |  |  |  |
| **case** | | | | | | | | | | | | |
| `case.metadata.read` | ✔ |  |  | ✔ | ✔ |  |  |  | ✔ |  |  |  |
| `case.read.all` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| `case.read.department` |  | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| `case.read.assigned` |  |  |  |  |  | ✔ | ✔ | ✔ |  |  |  | ✔ |
| `case.create` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ |  |  |  |  |  |
| `case.transition` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `case.transition.legal` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| `case.assign` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| **grant** | | | | | | | | | | | | |
| `grant.manage` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| **audit** | | | | | | | | | | | | |
| `audit.read` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| **lead** | | | | | | | | | | | | |
| `lead.create` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |  |  | ✔ |  |  |
| `lead.read.all` | ✔ | ✔ | ✔ | ✔ | ✔ |  |  |  |  | ✔ |  |  |
| `lead.read.own` |  |  |  |  |  | ✔ | ✔ |  |  |  |  |  |
| `lead.transition` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |  |  |  |  |  |
| `lead.funnel` | ✔ | ✔ | ✔ |  |  |  |  |  |  | ✔ |  |  |
| **task** | | | | | | | | | | | | |
| `task.create` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  | ✔ |  |
| `task.manage.others` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| `task.cancel` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| **deadline** | | | | | | | | | | | | |
| `deadline.validate` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| **admin** | | | | | | | | | | | | |
| `admin.users.manage` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| `admin.backups.read` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| **economy** | | | | | | | | | | | | |
| `economy.read.all` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| `economy.read.case` |  | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `economy.report` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **charge** | | | | | | | | | | | | |
| `charge.create` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ |  | ✔ |  |  |  |
| `charge.cancel` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **payment** | | | | | | | | | | | | |
| `payment.register` | ✔ | ✔ | ✔ | ✔ |  | ✔ | ✔ |  | ✔ |  |  |  |
| `payment.confirm` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| **refund** | | | | | | | | | | | | |
| `refund.request` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |  |  |  |  |  |
| `refund.review` |  |  |  |  | ✔ |  |  |  | ✔ |  |  |  |
| `refund.legal_opinion` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| `refund.decide` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| **cash** | | | | | | | | | | | | |
| `cash.operate` |  |  |  | ✔ |  |  |  |  | ✔ |  |  |  |
| `cash.read.all` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| `cash.close.validate` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **expense** | | | | | | | | | | | | |
| `expense.submit` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `expense.review` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `expense.read.all` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **immig** | | | | | | | | | | | | |
| `immig.document.upload` | ✔ |  | ✔ | ✔ |  |  | ✔ |  |  |  |  |  |
| `immig.document.review` | ✔ |  | ✔ |  |  |  | ✔ |  |  |  |  |  |
| `immig.package` | ✔ |  | ✔ |  |  |  | ✔ |  |  |  |  |  |
| `immig.catalog.approve` | ✔ |  | ✔ |  |  |  |  |  |  |  |  |  |
| `immig.office.manage` | ✔ |  | ✔ |  |  |  |  |  |  |  |  |  |
| **comm** | | | | | | | | | | | | |
| `comm.read` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `comm.send` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `comm.note` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `comm.notice.important` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ | ✔ |  |  |  |  |
| `comm.notice.urgent` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  |  |  |
| `comm.portal.invite` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ |  |  |  |  |  |
| `comm.export` | ✔ | ✔ | ✔ |  |  | ✔ | ✔ |  |  |  |  |  |
| **agents** | | | | | | | | | | | | |
| `agents.view` | ✔ | ✔ | ✔ |  |  |  |  |  | ✔ |  | ✔ |  |
| `agents.manage` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| **bank** | | | | | | | | | | | | |
| `bank.read` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| `bank.import` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `bank.reconcile` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `bank.accounts.manage` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **reception** | | | | | | | | | | | | |
| `reception.balance` |  |  |  | ✔ |  |  |  |  |  |  |  |  |
| **hr** | | | | | | | | | | | | |
| `hr.self` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `hr.read` | ✔ |  |  |  |  |  |  |  |  |  | ✔ |  |
| `hr.manage` | ✔ |  |  |  |  |  |  |  |  |  | ✔ |  |
| `hr.salary` | ✔ |  |  |  |  |  |  |  |  |  | ✔ |  |
| `hr.leave.decide` | ✔ | ✔ | ✔ |  |  |  |  |  |  |  | ✔ |  |
| **supplier** | | | | | | | | | | | | |
| `supplier.manage` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **invoice** | | | | | | | | | | | | |
| `invoice.register` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `invoice.validate` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| **treasury** | | | | | | | | | | | | |
| `treasury.read` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| `treasury.propose` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `treasury.approve` | ✔ |  |  |  |  |  |  |  |  |  |  |  |
| **accounting** | | | | | | | | | | | | |
| `accounting.read` | ✔ |  |  |  |  |  |  |  | ✔ |  |  |  |
| `accounting.close` |  |  |  |  |  |  |  |  | ✔ |  |  |  |
| `accounting.close.approve` | ✔ |  |  |  |  |  |  |  |  |  |  |  |

## 6. Catálogo de permisos
Sufijo **[M]** = acceso mínimo (datos enmascarados); **[A]** = acceso ampliado.

**contact**

- `contact.search`: Buscar identidades y ver ficha mínima (datos enmascarados) [M]
- `contact.read.all`: Ver ficha completa de cualquier contacto de la entidad [A]
- `contact.read.own`: Ver ficha completa de contactos propios o con expediente accesible [P]
- `contact.create`: Dar de alta contactos
- `contact.update`: Modificar datos de contacto no identificativos
- `contact.identifier.manage`: Añadir o modificar documentos de identidad (dato sensible)

**case**

- `case.metadata.read`: Ver metadatos de expedientes (código, materia, estado) sin contenido [M]
- `case.read.all`: Leer cualquier expediente de la entidad [A]
- `case.read.department`: Leer expedientes de su departamento (y sede si está acotado) [A en su rama]
- `case.read.assigned`: Leer expedientes asignados o con autorización puntual vigente [P/S]
- `case.create`: Abrir expedientes de su departamento (y sede si está acotado)
- `case.transition`: Cambiar fases operativas de expedientes accesibles (apertura, trámite, suspensión)
- `case.transition.legal`: Fases con efecto jurídico: resuelto, en ejecución, desistido, archivado
- `case.assign`: Asignar y retirar responsables de expedientes accesibles

**grant**

- `grant.manage`: Conceder y revocar autorizaciones puntuales con motivo y caducidad

**audit**

- `audit.read`: Consultar la bitácora de auditoría

**lead**

- `lead.create`: Registrar leads (origen obligatorio)
- `lead.read.all`: Ver todos los leads de la entidad
- `lead.read.own`: Ver los leads asignados o creados por uno mismo
- `lead.transition`: Cambiar el estado de un lead visible
- `lead.funnel`: Ver el embudo comercial agregado

**task**

- `task.create`: Crear tareas en expedientes accesibles o propias
- `task.manage.others`: Modificar o reasignar tareas de otras personas en su ámbito (Q-6.23)
- `task.cancel`: Anular tareas (con motivo)

**deadline**

- `deadline.validate`: Validar fechas legales propuestas (función de letrado)

**admin**

- `admin.users.manage`: Dar de alta, desactivar y asignar roles a usuarios de su entidad; cerrar sus sesiones
- `admin.backups.read`: Consultar el registro de copias de seguridad y sus comprobaciones de restauración

**economy**

- `economy.read.all`: Ver la situación económica de todos los expedientes de la entidad (sin contenido jurídico)
- `economy.read.case`: Ver la situación económica de los expedientes con acceso completo
- `economy.report`: Ver el resumen económico por sede y periodo

**charge**

- `charge.create`: Registrar importes pactados pendientes de cobro (los introduce una persona; no se calculan)
- `charge.cancel`: Anular importes pendientes de cobro (con motivo)

**payment**

- `payment.register`: Registrar cobros recibidos en expedientes visibles
- `payment.confirm`: Confirmar o anular cobros (conciliación) y anotar el nº de factura del programa homologado

**refund**

- `refund.request`: Registrar solicitudes de devolución de clientes
- `refund.review`: Investigar y escalar devoluciones (no las aprueba)
- `refund.legal_opinion`: Emitir informe jurídico sobre una devolución escalada (no la aprueba)
- `refund.decide`: Aprobar o rechazar devoluciones y registrar su pago (Contabilidad, A-09)

**cash**

- `cash.operate`: Registrar movimientos y arqueos de la caja de su sede
- `cash.read.all`: Ver las cajas de todas las sedes de la entidad
- `cash.close.validate`: Validar o rechazar el cierre diario de caja de una sede (nunca el propio)

**expense**

- `expense.submit`: Subir sus propios gastos con justificante
- `expense.review`: Revisar, aprobar, devolver y conciliar gastos; gestionar tarjetas e importar extractos
- `expense.read.all`: Ver todos los gastos de la entidad y su resumen mensual

**immig**

- `immig.document.upload`: Subir documentación a expedientes de extranjería visibles (Recepción: sin poder verla después)
- `immig.document.review`: Confirmar tipo, fechas y validez de los documentos de extranjería
- `immig.package`: Preparar y descargar el paquete de documentos para Mercurio
- `immig.catalog.approve`: Validar el catálogo de trámites y sus listas de documentos (Legal Extranjería)
- `immig.office.manage`: Datos del despacho como representante en las solicitudes de extranjería (modelos EX y Mercurio)

**comm**

- `comm.read`: Leer las conversaciones de los expedientes con acceso completo (y el hilo general de sus clientes)
- `comm.send`: Escribir al cliente en esas conversaciones, adjuntar archivos y ocultar mensajes (sin borrarlos)
- `comm.note`: Escribir notas internas que el cliente no ve
- `comm.notice.important`: Enviar avisos importantes (aviso por correo, sin contenido)
- `comm.notice.urgent`: Enviar avisos urgentes con confirmación de lectura (citaciones, plazos validados)
- `comm.portal.invite`: Dar acceso al portal a un cliente, y bloquearlo o reactivarlo
- `comm.export`: Exportar una conversación con su huella digital

**agents**

- `agents.view`: Ver los agentes, su actividad y sus límites
- `agents.manage`: Activar o pausar agentes y elegir su modo (propone / automático donde se permite, T-47)

**bank**

- `bank.read`: Ver cuentas bancarias, extractos, movimientos y su conciliación
- `bank.import`: Importar extractos bancarios (Norma 43, CAMT.053, CSV)
- `bank.reconcile`: Validar o rechazar emparejamientos, conciliar a mano y justificar movimientos
- `bank.accounts.manage`: Dar de alta y desactivar cuentas bancarias (A laboral, B extranjería, C tesorería)

**reception**

- `reception.balance`: Ver lo que queda por cobrar de un expediente (solo importes, sin contenido) para cobrarlo

**hr**

- `hr.self`: Ver su propia ficha, sus nóminas y documentos, y pedir vacaciones o permisos
- `hr.read`: Ver la plantilla (ficha laboral sin salario ni datos de salud)
- `hr.manage`: Alta y cambios de fichas, carpeta documental, ausencias de cualquiera, avisos e importación
- `hr.salary`: Ver y revisar salarios y nóminas; resumen mensual para la gestoría
- `hr.leave.decide`: Aprobar o rechazar vacaciones y permisos (su departamento, o toda la plantilla con hr.manage)

**supplier**

- `supplier.manage`: Dar de alta y modificar proveedores (CIF e IBAN comprobados)

**invoice**

- `invoice.register`: Registrar facturas recibidas con su original
- `invoice.validate`: Validar o rechazar facturas recibidas (datos, actividad, oficina y centro de coste)

**treasury**

- `treasury.read`: Ver saldos, previsión de pagos y remesas
- `treasury.propose`: Proponer remesas de pago a proveedores
- `treasury.approve`: Autorizar remesas (hacen falta dos personas distintas de quien la propone)

**accounting**

- `accounting.read`: Ver el cuadro de mando económico y los cierres del mes
- `accounting.close`: Preparar y revisar el cierre provisional del mes
- `accounting.close.approve`: Aprobar el cierre provisional del mes (persona distinta de quien lo preparó)

## 7. Restricciones por departamento (resumen)
| Departamento | Puede | No puede |
|---|---|---|
| Dirección | Ver todo lo de su entidad, autorizar excepciones, aprobar cierres y firmar remesas, administrar usuarios y agentes | Registrar facturas, importar extractos o firmar su propia propuesta. Sus accesos también se auditan |
| Laboral | Clientes, CRM y expedientes **asignados** de su área; tareas y agenda | Extranjería ajena, contabilidad, salarios |
| Extranjería | Expedientes de extranjería, ficha EX, lectura de documentos, paquete para Mercurio | Presentar en Mercurio (lo hace una persona) y descargar de DEHú |
| Recepción | Ficha mínima, alta de contactos y leads, cobros, justificante no fiscal, cierre de caja de su sede, subir documentos de extranjería | Ver expedientes completos, validar su propia caja, contabilidad |
| Atención al cliente | Ficha mínima, datos básicos del expediente, leads, solicitar y revisar devoluciones | Documentación completa, conversaciones (pendiente de asignar permiso, D-13), cobros |
| Contabilidad | Banco, conciliación, facturas recibidas, tesorería, cierre, rutina e informes | Aprobar el cierre o firmar remesas (Dirección) |
| RRHH | Ficha del personal, carpeta, nóminas (sin calcular), ausencias | Datos de clientes |
| Marketing | CRM y leads | Expedientes, economía |
| Soporte Colombia | Solo su entidad (Colombia) y lo asignado | Cualquier dato de la entidad España |

## 8. Política de permisos (documento de referencia del proyecto)

Estado: **implementada en F0.1 como propuesta técnica**. La matriz de la hoja ROLES_PERMISOS requiere aprobación
de Dirección y del DPO (D-13, D-17). Fuente de verdad en código: `apps/api/app/security/catalog.py` (permisos y roles)
y `apps/api/app/security/policy.py` (motor de decisión).

## 1. Cinco dimensiones, una sola decisión en backend

| Dimensión | Cómo se aplica | Dónde |
|---|---|---|
| **Entidad legal** | Frontera dura. Sin pertenencia vigente a la entidad, el recurso no existe para el usuario (404, sin confirmar existencia). | `Principal.org_ids()`, filtros SQL |
| **Rol** | Conjunto de permisos atómicos (`contact.search`, `case.read.assigned`…). Denegar por defecto. | `role_permission` |
| **Departamento (rama)** | `case.read.department` solo abre expedientes de su departamento. Laboral ≠ Extranjería ≠ Nacionalidad. | `membership.department_id` |
| **Sede** | Una pertenencia con `branch_id` limita el alcance departamental a esa sede; `NULL` = todas las sedes de la entidad. | `membership.branch_id` |
| **Asignación** | `case.read.assigned` solo abre expedientes con asignación vigente o autorización puntual vigente. | `case_assignment`, `access_grant` |

Respuesta ante acceso no permitido **dentro** de la entidad: `403 acceso_denegado` + evento `denied` en auditoría
(registrado en transacción propia para que persista). **Fuera** de la entidad: `404` + evento `denied`.

## 2. Niveles de visibilidad

| Recurso | Nivel | Qué se ve |
|---|---|---|
| Contacto | `full` | Ficha completa: documentos, teléfonos, correos, domicilios, consentimientos |
| Contacto | `minimal` | Nombre, sede, teléfonos y documentos **enmascarados** (`+34 ••• ••• 999`, `•••••567L`) |
| Expediente | `full` | Contenido, resumen confidencial, responsables (se audita cada lectura) |
| Expediente | `metadata` | Código, materia, estado, sede. Nunca título, resumen ni pruebas |

## 3. Matriz por rol (F0.1)

Leyenda de la matriz original: A total en su ámbito · P propio/asignado · M metadatos minimizados · S autorización puntual · N denegado.

| Rol | Contactos | Laboral | Extranjería | Nacionalidad | Alta contacto | Editar | Documentos identidad | Autorizaciones | Auditoría |
|---|---|---|---|---|---|---|---|---|---|
| Dirección | A (`full`) | A | A | A | Sí | Sí | Sí | Sí | Sí |
| Líder Laboral | P + búsqueda mínima | A (su ámbito/sede) | N | N | Sí | Sí | No | No | No |
| Recepción | M (búsqueda ≥3 caracteres) | M | M | M | Sí | No | No | No | No |
| Atención al cliente | M | M | M | M | No | No | No | No | No |
| Asesor Laboral | P + búsqueda mínima | P (asignados) | N | N | Sí | Sí (sus contactos) | No | No | No |
| Asesor Extranjería | P + búsqueda mínima | N | P (asignados) | N | Sí | Sí (sus contactos) | No | No | No |
| Gestor Laboral | P + búsqueda mínima | P (asignados) | N | N | No | Sí | Sí | No | No |
| Contabilidad | M | M | M | M | No | No | No | No | No (F5: economía) |
| Soporte Colombia | P en su entidad | P | P | P | No | No | No | No | No |
| Cualquier rol | — | S si Dirección concede autorización puntual con motivo y caducidad ≤ 30 días | | | | | | | |

"P" para contactos significa: ficha completa de los contactos que creó o que tienen un expediente que puede leer;
del resto, solo ficha mínima al buscar.

### Permisos añadidos en F1.2 y F2 (02/11/2026)

| Rol | Leads | Embudo | Abrir expediente | Fases operativas | Fases jurídicas | Responsables | Tareas | Validar plazo legal |
|---|---|---|---|---|---|---|---|---|
| Dirección | Todos | Sí | Cualquier rama | Sí | Sí | Sí | Crear, gestionar ajenas, anular | Sí |
| Líder Laboral | Todos | Sí | Laboral (su ámbito) | Sí | Sí | Sí | Crear, gestionar ajenas, anular | Sí (rama Laboral) |
| Recepción / ATC | Todos, cambian estado | No | No | No | No | No | No | No |
| Asesor Laboral / Extranjería | Asignados o creados | No | Su rama y sede | Sí | No | No | Crear y gestionar las suyas | No |
| Gestor Laboral | — | No | No | Sí | No | No | Crear y gestionar las suyas | No |
| Marketing (nuevo) | Todos, sin cambiar estado | Sí | No | No | No | No | No | No |
| Contabilidad / Soporte Colombia | — | No | No | No | No | No | No | No |

Reglas añadidas: quien propone un plazo legal no puede validarlo (doble control); el responsable de un expediente
debe pertenecer a su rama (las excepciones van por autorización puntual); una relación entre expedientes nunca
muestra un expediente que el usuario no puede ver; Marketing no tiene ningún permiso sobre expedientes.

Roles de la matriz original aún no creados (no hay funcionalidad que proteger todavía): Letrado
Laboral, Gestor Extranjería, RRHH, Auditor externo, Cliente portal, Letrado sustituto. Mientras no exista el rol
Letrado, la validación de plazos la hace Líder Laboral o Dirección (decisión T-12). Se añadirán en el
incremento que construya su funcionalidad; el motor ya admite cualquier combinación.

### Permisos añadidos en F0.2 (02/11/2026)

| Permiso | Quién | Qué permite |
|---|---|---|
| `admin.users.manage` | Dirección | Alta de usuarios, roles por entidad/sede/departamento, desactivar/reactivar, restablecer credenciales, cerrar sesiones de otros |
| `admin.backups.read` | Dirección | Ver el registro de copias de seguridad y su comprobación (AT-29) |

Reglas de administración (`routers/admin.py`):
- Solo se ve y gestiona a quien tiene alguna pertenencia en una entidad que el actor administra; el resto → 404.
- Desactivar, editar o restablecer credenciales exige que **todas** las pertenencias vigentes de la persona estén en
  entidades del actor (no se actúa sobre alguien de otra sociedad) → 403 auditado.
- Nadie se desactiva ni se retira a sí mismo la administración; ninguna entidad puede quedarse sin una persona
  administradora activa (422 `ultimo_administrador`, auditado).
- Sede y departamento deben ser de la misma entidad que la pertenencia.
- Un cambio de rol = nueva pertenencia + fin de la anterior: el historial no se reescribe. El efecto es inmediato en
  las sesiones abiertas (los permisos se recalculan en cada petición).
- La contraseña provisional se muestra una vez y nunca se guarda en claro ni en la auditoría.
- El catálogo de roles se sincroniza con el código en cada arranque (`python -m app.security.catalog_sync`), en
  cualquier entorno: un permiso retirado del catálogo desaparece de la base.

### Permisos añadidos en F5.0 — economía y gastos (03/11/2026)

| Rol | Ver economía | Importes pactados | Cobros | Confirmar cobros | Devoluciones | Caja | Gastos |
|---|---|---|---|---|---|---|---|
| Dirección | Toda la entidad | Crear y anular | Registrar | No | Solicitar, informar | Ver todas | Propios + ver todos |
| Contabilidad | Toda la entidad (sin contenido jurídico) | Crear y anular | Registrar | **Sí** | Revisar, **aprobar/rechazar y pagar** | Operar y ver todas | Propios + **revisar, conciliar, tarjetas, extractos** |
| Líder Laboral | Expedientes con acceso completo | Crear | Registrar | No | Solicitar, informar (su rama) | No | Propios |
| Asesores | Expedientes con acceso completo | Crear | Registrar | No | Solicitar | No | Propios |
| Gestor Laboral | Expedientes con acceso completo | No | No | No | No | No | Propios |
| Recepción | No | No | Registrar (con metadatos) | No | Solicitar | Operar **su sede** | Propios |
| ATC | No | No | No | No | Solicitar, **revisar y escalar** | No | Propios |
| Marketing / Soporte Colombia | No | No | No | No | No | No | Propios |

Reglas: nadie decide una devolución que ha solicitado ni revisa sus propios gastos; el informe jurídico de una
devolución lo da quien tiene acceso completo al expediente y no decide; no se aprueba más de lo cobrado y confirmado;
los gastos ajenos solo los ven Contabilidad y Dirección; ver un justificante queda auditado.

### Permisos añadidos en F4.1 — extranjería (05/11/2026)

| Permiso | Quién | Qué permite |
|---|---|---|
| `immig.document.upload` | Dirección, Líder Extranjería, Asesor Extranjería, **Recepción** | Subir documentos a un expediente de extranjería visible. Recepción sube con acceso de metadatos y **no** ve después el detalle ni los archivos |
| `immig.document.review` | Dirección, Líder Extranjería, Asesor Extranjería | Confirmar tipo, fechas y validez; rechazar con motivo; retirar (sin borrado físico). F4.3: «Volver a leer» y diagnóstico de la lectura **sin datos** (ambos auditados) |
| `immig.package` | Dirección, Líder Extranjería, Asesor Extranjería | Comprobar y descargar el paquete para Mercurio (descarga auditada; forzarlo con problemas queda registrado) |
| `immig.catalog.approve` | Dirección, **Líder Extranjería** (rol nuevo) | Validar la lista de documentos de cada versión del trámite |

| `immig.office.manage` | Dirección, Líder Extranjería | Datos del despacho como representante a efectos de presentación (F4.2) |
| `comm.read` | Dirección, Líderes, Asesores, Gestor Laboral | Leer conversaciones de expedientes con **acceso completo** (y el hilo general de clientes con ficha completa). Recepción, ATC, Contabilidad y Marketing no (F2.3) |
| `comm.send` | Dirección, Líderes, Asesores, Gestor Laboral | Escribir al cliente, adjuntar y **ocultar** mensajes (nunca borrar) |
| `comm.note` | Dirección, Líderes, Asesores, Gestor Laboral | Notas internas que el cliente no ve |
| `comm.notice.important` | Dirección, Líderes, Asesores, Gestor Laboral | Avisos importantes (correo sin contenido) |
| `comm.notice.urgent` | Dirección, Líderes | Avisos urgentes con plantilla, fecha de una tarea (plazo legal solo validado) y confirmación obligatoria (T-34) |
| `comm.portal.invite` | Dirección, Líderes, Asesores | Dar, reenviar, bloquear y reactivar el acceso de un cliente al portal |
| `comm.export` | Dirección, Líderes, Asesores | Exportar la conversación en PDF con huella SHA-256 (también la versión completa interna) |

F4.2: la ficha del formulario la confirma quien tiene `immig.document.review`; la vista previa del EX y el código para
la extensión exigen `immig.package`. El código (`GET /immigration/fill/{código}`) es la única ruta sin sesión: solo
devuelve la ficha confirmada de UN expediente, caduca a los 15 minutos, admite 10 lecturas, se guarda como hash y
cada lectura (o intento fallido) queda auditada a nombre de quien lo generó.

Reglas: además del permiso, el expediente debe ser accesible con el motor de siempre (entidad, sede, rama,
asignación): un asesor laboral recibe 403 auditado y otra entidad 404. Las fases «resolución favorable/desfavorable»,
«recurso» y «cerrado» exigen `case.transition.legal`. Ver o descargar un documento queda auditado. Los documentos se
guardan cifrados (Fernet) y nunca se borran: se retiran con motivo.

## 4. Casos borde

### Recepción (D-13)
- **Puede**: localizar a cualquier persona de su entidad (todas las sedes) por nombre, teléfono o documento exacto; dar de alta; ver qué expedientes tiene (metadatos) para derivar la llamada.
- **No puede**: listar el directorio sin criterio, buscar con menos de 3 caracteres, ver documentos/teléfonos completos, abrir el contenido de un expediente, ver el historial de auditoría ni modificar datos.
- Búsqueda por documento: **coincidencia exacta**, no por prefijo, para impedir enumerar documentos.
- Pendiente de decisión: si Recepción de Barcelona debe poder localizar clientes de Madrid y Valencia (hoy sí, porque el teléfono es común). Registrado como T-07.

### Soporte Colombia (D-17)
- Es **otra entidad legal**. Por defecto no tiene pertenencia a las entidades españolas: no ve ni enumera sus contactos ni expedientes (test `test_soporte_colombia_sin_acceso_a_datos_de_espana`).
- Darle acceso a datos de España requiere: decisión D-17 (base de legitimación, contrato de encargo/transferencia internacional, evaluación), y después una pertenencia explícita y limitada (rol `soporte_colombia`, solo `case.read.assigned`).
- Las autorizaciones puntuales **no** pueden concederse a usuarios sin pertenencia a la entidad del expediente (422), para evitar que una autorización puntual se convierta en transferencia internacional encubierta.

### Una persona con expedientes en dos ramas
- Lucía (dato ficticio) tiene un expediente Laboral y otro de Extranjería. El asesor laboral ve su ficha completa (tiene un expediente suyo) pero en "Expedientes autorizados" solo aparece el laboral; el de Extranjería ni siquiera figura. Recepción ve ambos como metadatos.

### Usuarios con varias entidades
- Dirección pertenece a dos entidades españolas: ve ambas, nunca la colombiana. Los permisos se calculan **por entidad**: tener `case.read.all` en una no lo concede en otra.

### Sustituciones
- Autorización puntual (`access_grant`): motivo ≥10 caracteres, caducidad obligatoria ≤30 días, revocable, auditada al conceder, revocar y en cada lectura del expediente.

## 5. Otras medidas (F0.1 + F0.2)
- Acceso (F0.2): contraseña Argon2id (mínimo 12 caracteres, sin el usuario, lista de contraseñas comunes) **y** código
  TOTP obligatorio; o proveedor OIDC con MFA exigido en `amr`. El secreto TOTP se guarda cifrado (Fernet,
  `FIELD_ENCRYPTION_KEY`) y un código no se acepta dos veces.
- Sesión: fila en `user_session` + JWT HS256 en cookie `httpOnly`, `SameSite=Strict`, `Secure` obligatorio en
  producción. Caduca a las 8 h o tras 60 min sin actividad; se revoca al cerrar sesión, al cambiar la contraseña
  (las demás), al desactivar o restablecer al usuario, o desde Administración. La revocación es inmediata.
- Límite de intentos: 5 fallos de contraseña o código por usuario en 15 min bloquean el acceso 15 min (también con la
  contraseña correcta); 30 fallos por IP. Persistido en `auth_attempt`.
- CSRF: toda petición que modifica exige la cabecera `X-Requested-With: sistema-propio`.
- Modo DEMO: la configuración aborta el arranque si `AUTH_MODE` incluye `demo` con `APP_ENV` distinto de `development`/`test`; también exige `FIELD_ENCRYPTION_KEY` y MFA en OIDC fuera de desarrollo. Si se retira `demo`, las sesiones demo abiertas dejan de valer.
- Inyección SQL: solo consultas parametrizadas (SQLAlchemy); comodines `%` y `_` escapados en búsquedas.
- Anti-enumeración: identificadores UUID, `page_size` ≤ 50, sin listado sin criterio para perfiles mínimos.
- Cabeceras: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` en la API.
- Errores: formato único sin trazas internas; cada respuesta lleva `request_id`.

## Portal del cliente (F2.3)
- El cliente **no es un usuario del equipo**: cuenta `portal_account` ligada a su contacto maestro, sesión propia
  (`sp_portal`) que no abre ninguna ruta del equipo, ni la del equipo abre el portal.
- Acceso con **código de un solo uso** al correo de su ficha (solo se guarda su hash; 10 min, 5 intentos, 5 códigos
  por hora). Pedir un código responde siempre lo mismo (no revela quién es cliente). Cierre a los 30 min sin uso.
- Solo ve sus expedientes y su hilo general; nunca notas internas ni mensajes ocultos; la fase se muestra sin
  resultados de resoluciones (se los comunica su abogado/a). Todo acceso y envío queda en la auditoría.
- Textos cifrados en reposo; adjuntos en el almacén cifrado; sin borrado físico (triggers).

## Agentes, bandeja de propuestas y banco (F5.1)
| Permiso | Para qué | Roles |
|---|---|---|
| `agents.view` | Ver los agentes, sus límites, su actividad y la medición | Dirección, Contabilidad, Líderes |
| `agents.manage` | Pausar/activar agentes y elegir modo (propone / automático solo donde se permite, T-47), lanzarlos a mano | Dirección |
| `bank.read` | Ver cuentas, extractos, movimientos, errores y exportar CSV | Dirección, Contabilidad |
| `bank.import` | Importar extractos | Contabilidad |
| `bank.reconcile` | Validar o rechazar emparejamientos, conciliar a mano, justificar o ignorar movimientos | Contabilidad |
| `bank.accounts.manage` | Alta y baja de cuentas | Dirección, Contabilidad |

- **Separación de funciones**: Dirección ve el banco pero no concilia; validar un emparejamiento **confirma el cobro**
  y exige también `payment.confirm` (Contabilidad).
- **Bandeja única**: cada persona ve solo las propuestas cuyo permiso tiene en esa entidad; las que hablan con el
  cliente (mensajes, datos que faltan, invitación al portal) exigen además **acceso completo al expediente**. Aprobar
  aplica la propuesta **con los permisos de quien aprueba**; rechazar exige motivo. Todo en la auditoría
  (`agent.proposal.approve/reject`, `bank.*`, `comm.auto.send`, `agent.setting`).
- Los agentes no tienen usuario propio ni permisos extra: preparan; la persona decide. Nada se borra (triggers en
  `agent_*`, `bank_*`, `comm_dispatch`). Cuenta de otra entidad → 404; sin permiso → 403, ambos auditados.

## Recepción (F5.2)
| Permiso | Para qué | Roles |
|---|---|---|
| `reception.balance` | Ver cuánto queda por cobrar de un expediente (solo importes, sin contenido) para cobrarlo | Recepción |
| `cash.close.validate` | Validar o rechazar el cierre diario de caja de una sede (nunca el propio; lo impide también la base de datos) | Contabilidad, Dirección |

- Cobrar exige `payment.register` + `cash.operate` **en esa sede**; Recepción de Madrid no opera ni ve la caja de Barcelona.
- El justificante es inmutable (trigger); el cierre de caja solo admite el paso «validar/rechazar» mientras está pendiente.
- Un cobro que parece repetido solo se guarda con explicación y lo revisa Contabilidad (`payment.confirm`); «es repetido» lo anula con motivo.

## RRHH (F5.3) — datos de personal aislados de los de clientes
| Permiso | Para qué | Roles |
|---|---|---|
| `hr.self` | Su propia ficha, sus nóminas y documentos; pedir vacaciones y permisos | Todos |
| `hr.read` | Plantilla sin salario ni datos de salud | RRHH, Dirección |
| `hr.manage` | Alta y cambios de fichas, carpeta documental, ausencias de cualquiera, avisos, importación | RRHH, Dirección |
| `hr.salary` | Salarios, nóminas y resumen para la gestoría | RRHH, Dirección |
| `hr.leave.decide` | Decidir ausencias: los líderes solo las de su departamento; RRHH y Dirección todas | Líderes, RRHH, Dirección |

- Las bajas médicas (dato de salud) solo las ven RRHH y la propia persona; los demás ven «ausencia».
- Nadie aprueba sus propias ausencias; además, la base de datos impide que quien pidió una ausencia la decida. En la auditoría, los salarios se registran como «•••».
- Ficha ajena → 403 auditado; otra entidad → 404. Nada se borra (triggers en `employee`, `employee_document`, `leave_request`).

## Contabilidad (F5.4) — proveedores, tesorería y cierre
| Permiso | Para qué | Roles |
|---|---|---|
| `supplier.manage` | Alta y cambios de proveedores (CIF/NIF e IBAN comprobados; IBAN cifrado) e IBAN de las cuentas propias | Contabilidad, Dirección |
| `invoice.register` | Subir y registrar facturas recibidas (la lectura propone; la persona confirma) | Contabilidad |
| `invoice.validate` | Validar o rechazar facturas recibidas (actividad, oficina y centro de coste) | Contabilidad, Dirección |
| `treasury.read` | Saldos, previsión de pagos, facturas y remesas | Contabilidad, Dirección |
| `treasury.propose` | Proponer remesas, descargar el fichero SEPA y marcarla como subida al banco, anular | Contabilidad |
| `treasury.approve` | Firmar (autorizar o no) remesas: hacen falta **dos personas distintas** y ninguna puede ser quien la propuso | Dirección |
| `accounting.read` | Cuadro de mando y cierres del mes | Contabilidad, Dirección |
| `accounting.close` | Preparar, recalcular y dar por revisado el cierre del mes | Contabilidad |
| `accounting.close.approve` | Aprobar el cierre (queda congelado con huella) | Dirección |

- La base de datos impide que quien propone una remesa la firme, que la misma persona firme dos veces, que el total de una factura no sea base + IVA − retención y que se cambie un cierre aprobado o sustituido. Nada se borra (triggers en las seis tablas).
- El coste de personal y el resultado se muestran agrupados para grupos de menos de 3 personas a quien no tiene `hr.salary` (T-53).
- Entidad ajena → 404; misma entidad sin permiso → 403; ambos auditados. Descargas de facturas y del fichero SEPA, auditadas.


## 9. Odoo Community: cómo trasladar este modelo
| Sistema Propio | Odoo Community |
|---|---|
| Entidad (`organization`) | `res.company` (multicompañía) con `company_ids` en el usuario |
| Sede, departamento | `hr.department` o modelo propio `sp.branch` + campo en cada registro |
| Rol → permisos | `res.groups` (un grupo por rol) + `ir.model.access.csv` (lectura/escritura por modelo) |
| Ámbito por entidad, sede y asignación | `ir.rule` con dominios (`[('company_id','in',company_ids)]`, `[('user_ids','in',user.id)]`) |
| Ficha mínima enmascarada | Campos con `groups=` + campos calculados que enmascaran; vistas separadas por grupo |
| 404 frente a 403 | Odoo devuelve `AccessError`. Para no revelar existencia: `ir.rule` filtra (el registro «no existe» para el usuario) |
| Separación de funciones (dos firmas, validador ≠ autor) | `@api.constrains` en Python **y** restricción/trigger SQL en `init()` del modelo |
| TOTP obligatorio | Módulo `auth_totp` (Community) + política que lo exija a todos los usuarios internos (`auth_totp_mail_enforce` o desarrollo propio) |
| OIDC | `auth_oauth` (Community) o OCA `auth_oidc` |
| Portal del cliente con cuenta propia | Usuarios portal (`base.group_portal`) + `ir.rule` de portal |
| Cifrado de columna | Desarrollo propio (campo `fields.Char` con cifrado en `_compute`/`_inverse`) o cifrado a nivel de disco + `attachment` cifrado |

**Advertencia:** en Odoo, cualquier código Python que use `sudo()` se salta las reglas. Revisión obligatoria de cada
`sudo()` en el código propio; la auditoría externa de seguridad debe incluirlo.
