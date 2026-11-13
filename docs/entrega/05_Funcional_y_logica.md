# 05 · Documentación funcional y lógica

Sistema Propio · versión F5.6 · 12/11/2026

Para cada módulo se describen tres cosas:
- qué hace;
- las reglas de negocio (todas comprobadas en el servidor, y las críticas también en la base de datos);
- lo que el sistema **no hace nunca**.

Los estados que se citan son los del código (`routers/*.py`, `FLOW`).

Reglas comunes a todos los módulos:
- Cada cambio de estado es un evento con actor, fecha, estado anterior y nuevo, y motivo cuando se exige.
- Nada se borra: los estados finales son «anulado», «archivado», «sustituido» o «descartado», con motivo.
- La interfaz solo muestra los botones permitidos (`allowed`), pero quien decide es la API.

## 1. Contactos (persona maestra)
**Qué hace.** Una ficha única por persona, con identificadores (DNI, NIE, pasaporte, CIF), teléfonos y correos, y el
vínculo con sus expedientes.

**Reglas**
- Los identificadores se validan con su dígito de control (`validation.py`). Si no es válido, no se guarda.
- Al crear un contacto, el sistema avisa de posibles duplicados (mismo identificador, mismo nombre y fecha, mismo
  teléfono). **Nunca fusiona** automáticamente; un teléfono compartido (familia) no basta.
- **Ficha mínima** (Recepción, Atención al cliente): datos enmascarados, sin documentación. La **ficha completa**
  requiere `contact.read.all` o ser el titular de un expediente asignado.

**Nunca:** borrar un contacto (trigger) ni copiar sus datos en otros módulos.

## 2. CRM (leads)
**Qué hace.** Registra el interés de una persona con su origen (canal y campaña) y su avance por el embudo.

**Estados:** `nuevo` → `contactado` ↔ `en_seguimiento` → `cita_solicitada` → `convertido` / `no_convertido`.
`descartado` se puede reabrir a `contactado`.

**Reglas**
- El origen es obligatorio.
- Descartar o «no convertido» exigen motivo.
- «Convertido» lo pone el sistema al abrir un expediente vinculado.
- La entidad Colombia tiene su propio embudo, separado.

## 3. Expedientes
**Qué hace.** Asunto de un cliente con código consecutivo por área y año (`LAB-2026-0001`, `EXT-2026-0001`),
personas asignadas, resumen confidencial y estado.

**Estados y permisos:**

| Desde | Hacia | Permiso |
|---|---|---|
| preapertura | abierto | `case.transition` |
| preapertura, abierto | desistido | `case.transition.legal` |
| abierto | en_tramite, suspendido | `case.transition` |
| en_tramite | suspendido | `case.transition` |
| en_tramite | resuelto | `case.transition.legal` |
| suspendido | en_tramite | `case.transition` |
| resuelto | en_ejecucion, archivado | `case.transition.legal` |
| en_ejecucion | resuelto | `case.transition.legal` |

**Reglas**
- Lectura según el nivel: todo, departamento o asignado. Las autorizaciones puntuales (`access_grant`) tienen
  caducidad.
- Una asignación tiene inicio y fin: no se borra, se cierra.

**Nunca:** borrar un expediente (trigger) ni decidir el resultado jurídico (solo personas con `case.transition.legal`).

## 4. Agenda, tareas y plazos
**Estados:** `pendiente` → `en_curso` → `completada`. También `pospuesta` y `anulada`. «Completada» y «anulada» son
finales.

**Reglas**
- Aplazar exige motivo y queda en el historial.
- Los señalamientos y las conciliaciones exigen hora de inicio y fin; el sistema avisa de solapes de la misma persona.
- **Plazo legal**: una tarea puede llevar `legal_deadline`.
  - Queda en `pendiente_validacion` hasta que un letrado con `deadline.validate` lo valida.
  - El objetivo interno es una fecha distinta de la fecha legal.
  - El sistema **no calcula** plazos legales ni festivos (T-25, T-26, T-49).

## 5. Extranjería
**Qué hace.**
- Expediente de extranjería con el trámite elegido del catálogo (cada trámite con su fuente oficial y la versión
  vigente al abrir).
- Documentos requeridos.
- Lectura automática de documentos.
- Ficha del modelo EX.
- Preparación para Mercurio.

**Fases:** consulta → documentación → preparación → lista para presentar → presentado → requerimiento →
requerimiento respondido → resolución favorable o desfavorable → TIE → recurso → cerrado.
Las fases jurídicas (resoluciones, recurso, cierre) solo las registra quien tiene `case.transition.legal`.

**Reglas**
- Los cambios en el catálogo de trámites crean una versión **pendiente de validar** por Legal Extranjería.
- **Lectura de documentos.**
  - Tipos que se leen: pasaporte (MRZ, en todas las páginas y con giros), contrato, padrón, TIE y tasa.
  - El resultado se **propone**. Solo llega a la ficha desde documentos marcados como válidos, con su origen.
  - Nunca sobrescribe un valor guardado; si hay diferencia, avisa.
  - Un identificador sin control válido se descarta: mejor vacío que equivocado.
- Mismo archivo (sha256) en el mismo expediente: no se guarda dos veces.
- Un requerimiento crea una tarea `plazo` **sin** fecha legal, que propone un letrado con fuente.
- **Extensión Mercurio:**
  - el sistema genera un código de 15 minutos y 10 lecturas;
  - la extensión rellena los campos de la página oficial;
  - **nunca** pulsa botones, envía, marca «NO CONSIENTO» ni elige el supuesto. Lo vigila una prueba automática.

**Nunca:** presentar en Mercurio, descargar de DEHú ni ofrecer citas biométricas.

## 6. Portal del cliente y comunicaciones
**Qué hace.**
- El cliente entra con un código que recibe por correo.
- Ve sus expedientes, sube documentos y conversa con el despacho, con **trato de usted**.
- El equipo responde desde el expediente.

**Reglas**
- Los textos se guardan cifrados.
- Un mensaje se puede corregir durante 15 minutos (queda la versión anterior) y ocultar con motivo. Nada se borra.
- **Avisos urgentes:** solo con plantilla y con la fecha de una tarea del expediente; plazo legal solo si está validado.
- Los correos llevan un aviso («tiene un mensaje nuevo»), **nunca el contenido**.
- **Mensajes automáticos** (agente `mensajes`):
  - plantillas versionadas para apertura, cierre, citas y documentación;
  - la fecha y el lugar salen solo de la tarea;
  - el modo automático solo funciona si Dirección lo activa (T-47); si no, son propuestas.

**Pendiente:** WhatsApp/Callbell (T-31) y SMS (T-35).

## 7. Economía (control no fiscal) y Recepción
**Qué hace.** Registro de cargos y cobros por expediente o por consulta, justificante no fiscal, caja por sede,
devoluciones e informe de recepción.

> **En Odoo 20 (13/11/2026):** implementado en parte en el módulo `sp_recepcion` (`odoo/addons/sp_recepcion/`,
> versión 20.0.1.1.0): sedes, cobros con justificante, aviso de repetidos, confirmación y anulación por Contabilidad,
> cierre de caja validado por otra persona (también con check y trigger en la base de datos), cada persona de
> Recepción limitada a sus sedes y **devoluciones** (`sp.devolucion`) con la misma tabla de estados de abajo:
> Atención al cliente revisa, el letrado informa si se escala y Contabilidad aprueba o rechaza y paga (rectificativa y
> pago, o pago de salida sin factura). Faltan el informe por sede y el vínculo con expedientes. Detalle en 19 §3.1,
> permisos en 08 §10, manual en 15 §8b; cambios en 11 · DOC-8 y DOC-10. Quién aprueba la devolución: Contabilidad (18 · AL-14, decidido 13/11/2026).

**Reglas**
- Importes en céntimos enteros.
- Un cobro sin expediente solo es posible si es una consulta (check en la base de datos).
- **Cobros repetidos:** antes de guardar, el sistema busca posibles duplicados. Para seguir, hay que explicar el motivo
  y Contabilidad recibe el aviso.
- **Justificante:** uno por cobro, cifrado e inmutable. **No es una factura.**
- **Cierre de caja:** uno por sede y día, contado por una persona y validado por **otra** (check y trigger). La caja
  solo cambia con movimientos de solo inserción.
- **Devoluciones:**

  | Desde | Hacia | Permiso |
  |---|---|---|
  | registrada | en_revision | `refund.review` |
  | registrada, en_revision | aprobada, rechazada | `refund.decide` (nunca quien la solicitó) |
  | en_revision | escalada_legal | `refund.review` |
  | escalada_legal | en_revision | `refund.legal_opinion` |
  | aprobada | pagada | `refund.decide` |
  | rechazada | en_revision | `refund.decide` (reapertura con motivo) |

**Nunca:** emitir facturas ni calcular honorarios, IVA o suplidos.

## 8. Gastos de empresa
**Qué hace.** La persona sube el ticket, el OCR local propone importe, fecha y comercio, y la persona confirma.
Los gastos en efectivo mueven la caja de su sede.

**Estados:** el gasto es editable en `borrador` y `devuelto`. Después lo revisa quien tiene permiso.

## 9. Banco y conciliación
**Qué hace.** Cuentas bancarias (IBAN completo cifrado) e importación de extractos en Norma 43, CAMT.053, CSV, Excel
`.xlsx` y `.xls`, y el «.xls» en HTML.

**Reglas**
- **Varios extractos a la vez:** cada uno va a la cuenta cuyo IBAN termina igual. Si el archivo no indica la cuenta o
  hay dos que coinciden, **no adivina**.
- **Comprobar sin importar:** lee y muestra el resultado sin guardar nada.
- Una línea ilegible da error; no se inventa.
- El original se guarda cifrado. Reimportar el mismo extracto no duplica movimientos.
- **Estados del movimiento:**
  - abiertos: `pendiente`, `propuesto`, `parcial`, `sin_justificar`;
  - cerrados: `conciliado`, `traspaso`, `ignorado`.
- **Conciliación:**
  - el agente propone con reglas deterministas y explica por qué;
  - Contabilidad valida, y validar confirma el cobro;
  - un traspaso entre cuentas propias nunca cuenta como ingreso.

**Nunca:** conciliar sin una persona ni conectarse al banco (la conexión directa PSD2 está pendiente de decidir).

## 10. Contabilidad
### 10.1 Facturas de proveedores
- Se suben varias a la vez y se leen solas (lectura v2):
  - etiquetas, fechas escritas en letra, NIF/CIF e IBAN;
  - cuadre base + IVA − retención = total;
  - OCR a 300 ppp si el PDF escaneado tiene una capa de texto mala;
  - el CIF del despacho (`OWN_TAX_IDS`) se descarta.
- La lectura **propone**; la persona comprueba, da de alta el proveedor si es nuevo y registra.
- El total debe cuadrar con base + IVA − retención (check en la base de datos). **El IVA es el que figura en la
  factura**: el sistema no lo calcula.
- Duplicados: mismo archivo o mismo proveedor, importe y fecha. Solo se puede seguir explicando el motivo.
- **Estados:** `recibida` → `validada` → `programada` (en remesa) → `pagada` (cuando el cargo se concilia).

### 10.2 Tesorería y remesas
1. Contabilidad propone una remesa con facturas validadas.
2. Dirección firma dos veces: **dos personas distintas**, ninguna la que propuso (trigger).
3. El sistema genera el fichero **SEPA pain.001** y una persona lo sube al banco.
4. El sistema nunca envía órdenes al banco.

### 10.3 Cierre del mes
- Cálculo por actividad (laboral, extranjería, compartida) y por sede: ingresos devengados, cobros, gastos de
  proveedores y de personal, coste de personal y pagos.
- Revisión y aprobación por Dirección.
- Recalcular crea una revisión nueva y la anterior pasa a `sustituido`.
- Un cierre aprobado es inmutable, con huella.
- El coste de personal se agrupa si hay menos de 3 personas y quien mira no tiene `hr.salary`.
- Los asientos contables están pendientes (T-40).

### 10.4 Rutina de trabajo e informes
| Cuándo | Pasos |
|---|---|
| Cada día | Extractos del día anterior; conciliaciones pendientes |
| Cada lunes | Facturas por validar; pagos de la semana; cierres de caja; informe semanal |
| Días 1 y 16 | Informe quincenal |
| Días 2 a 5 | Extractos de fin de mes; conciliar el mes; nóminas y facturas; cierre provisional |
| Día 7 | Aprobación del cierre; informe mensual |

- Cada paso tiene responsable (lo asigna Dirección) y fecha objetivo.
- Un paso se da por **hecho solo cuando el sistema lo comprueba** en los datos.
- «No aplica» exige un motivo de al menos 10 caracteres.
- Los pasos no diarios crean su tarea en la Agenda, que se cierra sola.
- **Informes** semanal, quincenal y mensual:
  - contenido: cifras por actividad y sede, comparación con el periodo anterior, tesorería, previsión de pagos,
    pendientes y cumplimiento de la rutina;
  - foto inmutable, en pantalla, PDF y CSV;
  - aviso por correo **sin cifras**;
  - Dirección los marca como revisados.

## 11. Recursos humanos
**Qué hace.** Ficha única del personal, carpeta de documentos (contrato, nóminas, certificados), ausencias y avisos.

**Reglas**
- El salario lo ven solo `hr.salary` y la propia persona; en la auditoría aparece como «•••».
- Bajas y partes médicos: solo RRHH y la propia persona.
- **Nóminas:** se leen y RRHH las confirma solo si devengado − deducciones = líquido. El sistema **no calcula
  nóminas** ni días por convenio (T-50).
- Aprobar una ausencia crea una tarea en la Agenda.

**Pendiente:** control horario (T-41), formación y cuadro de mando.

## 12. Agentes y «Pendientes de decidir»
- Los agentes revisan los datos cuando ocurre un hecho, y también de forma periódica cada 5 minutos o cada día.
- Crean **propuestas** dentro del departamento correspondiente.
- Cada propuesta lleva explicación, permiso necesario y una clave que evita repetirla.
- Las que afectan al cliente exigen además acceso completo al expediente.
- La configuración de los agentes está en Administración: activar, desactivar y modo automático solo donde Dirección
  lo permite.

## 13. Lo que el sistema no decide nunca
| Tema | Quién decide |
|---|---|
| Plazos legales, festivos, días por convenio | Letrado o RRHH con fuente; el sistema solo guarda la fecha validada |
| Resultado de un expediente | Persona con `case.transition.legal` |
| Presentación en Mercurio, LexNET, DEHú | La persona habilitada, manualmente |
| IVA, honorarios, facturación | Programa de facturación certificado (D-07, D-25). En Odoo: el estándar de Odoo 20 con Verifactu emite las facturas de venta y calcula su IVA; los honorarios los fija una persona; el IVA de las facturas recibidas es el que figura en ellas (18 · AL-03, 19 §1.3) |
| Conciliación, pagos | Contabilidad y Dirección (doble firma) |
| Fusión de contactos | Una persona, revisando el aviso |
