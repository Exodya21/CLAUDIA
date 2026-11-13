# Política de permisos

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
