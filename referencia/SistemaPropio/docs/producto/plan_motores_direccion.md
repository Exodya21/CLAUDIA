# Documentos de Dirección (08/11/2026): motores de Recepción, Contabilidad, RRHH y mensajes automáticos

Fuente: cinco documentos que Dirección entregó el 08/11/2026 (fotografiados; las marcas a mano ✓ y F no se tienen
en cuenta por indicación expresa). Se transcriben aquí sus requisitos con un identificador propio (**DR-…**) para
mantener la trazabilidad, igual que I-xxx/Q-x.x/U-xx, y se cruzan con lo que ya existe.

| Documento | Identificadores |
|---|---|
| Plan de automatización de Recepción (10 motores, Barcelona, Madrid y Valencia) | DR-REC-1 … DR-REC-10 |
| Manual de instrucciones para automatizar Contabilidad (8 motores, cierre del día 5) | DR-CON-1 … DR-CON-8 |
| Guion de automatización de Recursos Humanos (8 motores) | DR-RH-1 … DR-RH-8 |
| Plan de automatización de WhatsApp → **se aplica al portal propio** (T-31) | DR-MSG-1 … DR-MSG-9 |
| Cinco plantillas para Meta → **plantillas del portal** | DR-PLT-1 … DR-PLT-5 (+ seguimiento) |

## 1. Cómo se traducen los «motores» a este sistema

Dirección habla de *motores*; en SISTEMA PROPIO son **agentes**: piezas del propio sistema, con un nombre, unos
permisos limitados y un registro de todo lo que hacen. Reaccionan a hechos (un cliente sube un documento, se abre un
expediente, se importa un extracto) y **proponen**; una persona aprueba lo que tiene efecto jurídico o económico.

- No se usa n8n ni Callbell: la coordinación entre agentes va dentro del sistema (mismos permisos, misma auditoría,
  sin que los datos de clientes pasen por otra herramienta). n8n quedaría, si acaso, como puente con algún programa
  externo sin conexión propia.
- Una **bandeja única de excepciones** con prioridad y responsable (lo pide Contabilidad, sirve para todos).
- Los cálculos de caja y conciliación son **reglas deterministas y verificables**; la IA, cuando se contrate (D-24),
  solo clasifica y redacta borradores.

## 2. Recepción (DR-REC)

Objetivo del documento: módulo único de recepción; la atención presencial sigue siendo humana; se automatizan
registros, avisos, controles y tareas repetitivas. Orden propuesto: (1) cobros, caja y facturación; (2) bienvenida,
citas y documentación; (3) comunicaciones y tareas; (4) coordinación e informes.

| ID | Motor | Qué pide | Situación hoy | Qué falta |
|---|---|---|---|---|
| DR-REC-1 | Bienvenida y registro | Identificar al cliente, comprobar su cita, registrar llegada, avisar al responsable | Búsqueda de clientes con aviso de duplicados (F0.1), CRM (F1.2) | Registro de llegada y aviso al responsable; depende de citas (DR-REC-2) |
| DR-REC-2 | Citas y agenda | Citas de laboral y extranjería, confirmaciones, recordatorios, retrasos, cancelaciones, ausencias | Agenda interna (F2.2) | Citas de clientes propias (Q-2.4, Q-2.5; D-11, D-19) |
| DR-REC-3 | Cobros y justificantes | Consultas, provisiones y servicios; efectivo, tarjeta, Bizum y transferencia; justificante; datos a Contabilidad | Cobros por expediente con forma de pago y confirmación de Contabilidad (F5.0) | Tipo de cobro (consulta/provisión/servicio), cobro de consulta sin expediente, **justificante no fiscal** (T-44) |
| DR-REC-4 | Caja diaria y arqueo | Libro de caja digital: saldo inicial, movimientos, recuento, diferencias y **cierre diario firmado por responsable** | Caja por sede con movimientos y arqueo (F5.0) | Cierre del día validado por un responsable distinto de quien cuenta |
| DR-REC-5 | Identificación y documentación | Verificar contacto, registrar documentos recibidos y pendientes, asociarlos al expediente | Extranjería completa (F4.1–F4.3) y portal (F2.3) | Laboral (F2.4, U-01…U-12) |
| DR-REC-6 | Llamadas y mensajes | Identificar el asunto, proponer respuestas habituales, derivar al gestor, controlar pendientes | Portal con bandeja y plantillas (F2.3) | **Agente de recepción** que clasifica y deriva; llamadas (centralita, T-35) |
| DR-REC-7 | Tareas y distribución interna | Convertir solicitudes en tareas con responsable, plazo y seguimiento | Tareas (F2.2) | Que el agente proponga la tarea desde el mensaje |
| DR-REC-8 | Facturación e impagados | Comprobar pagos, solicitar o generar facturas según el sistema autorizado, duplicidades, saldos pendientes | Importes pactados y cobros; sin facturas (D-07, D-25) | Detección de cobros duplicados y saldos pendientes por expediente |
| DR-REC-9 | Coordinación entre oficinas | Operativa y caja separadas por sede; Dirección ve lo consolidado | Permisos por sede y resumen consolidado (F5.0) | — |
| DR-REC-10 | Supervisión e informes | Informes diarios y semanales de visitas, consultas, ingresos, caja, incidencias y productividad por oficina | Resumen económico (F5.0) | Informe diario/semanal (M16, I-099…I-110) |

Condiciones técnicas del documento (todas se cumplen o se exigen): una interfaz sencilla en móvil y ordenador; cajas
independientes por sede y permisos por empleado; **cada cobro se registra una sola vez**, correcciones y devoluciones
con historial y autorización; integración con contabilidad sin duplicar ingresos y exportación/importación con MN
Program según sus capacidades reales; protección de datos, copias y supervisión humana de cobros y arqueos; **la IA
clasifica y propone, los cálculos de caja son deterministas**. Primer desarrollo recomendado: pantalla de cobros y
caja (elegir oficina, identificar cliente, concepto e importe, medio de pago, justificante, libro de caja; al
cierre, efectivo contado y diferencia).

## 3. Contabilidad (DR-CON)

Objetivo: disponer el **día 5 de cada mes** de un resultado económico provisional, fiable y separado por actividad
y oficina. No sustituye la contabilidad oficial de la gestoría. **Toda cifra rastreable hasta su justificante.**
Dimensiones obligatorias de cada registro: fecha del documento, de la operación y del cobro/pago; importe;
impuestos cuando proceda; proveedor o cliente; cuenta bancaria; oficina; actividad (laboral/extranjería/compartida);
estado de conciliación; enlace al documento original.

| ID | Motor | Qué pide | Situación hoy | Qué falta |
|---|---|---|---|---|
| DR-CON-1 | Lectura, clasificación y distribución documental | Correo autorizado y carpeta de gastos, facturas, tickets, nóminas y justificantes; tipo, duplicados y confianza; dudosos a revisión; no borrar originales | Lectura de tickets (F5.0) y documentos de expedientes (F4.3), originales cifrados sin borrado | Facturas recibidas y nóminas; entrada por correo (buzón autorizado, T-48) |
| DR-CON-2 | Conciliación bancaria | Extractos de todas las cuentas en formato normalizado; emparejar por importe, fecha, referencia, beneficiario y factura; comisiones TPV, devoluciones, traspasos, pagos parciales; pendientes y diferencias | Extracto de tarjetas de empresa (F5.0) | **Construido en F5.1** (este bloque) |
| DR-CON-3 | Control de ingresos y cobros | Relacionar recibos con transferencias, Bizum y TPV; actividad y oficina por referencia de expediente, terminal, canal o regla; facturado/cobrado/pendiente; traspasos internos no son ingresos | Cobros registrados y confirmados (F5.0) | Enlace con el banco (F5.1) y reglas de terminal/canal |
| DR-CON-4 | Gastos, proveedores y facturas pendientes | Facturas recibidas, vencimientos, centros de coste, IVA y pagos; duplicados, gastos sin factura, recurrentes; alertas, no pagos | Gastos de empleados con tarjeta (F5.0) | Registro de facturas de proveedores |
| DR-CON-5 | Nóminas y coste de personal | Resumen mensual validado de nóminas, SS e indemnizaciones; reparto por oficina y actividad; acceso restringido | — | Depende de RRHH (DR-RH-5) |
| DR-CON-6 | Propuesta de asientos | Propuestas según el plan de cuentas aprobado; IVA, periodificaciones, anticipos, provisiones, amortizaciones; sin contabilizar lo dudoso | — | **Bloqueado** hasta tener el plan de cuentas de la gestoría (T-40); solo exportación |
| DR-CON-7 | Tesorería y programación de pagos | Saldos por banco, previsión, vencimientos; propuestas y remesas con **doble autorización**; el agente nunca ordena transferencias | — | Tras DR-CON-2 y DR-CON-4 |
| DR-CON-8 | Cierre provisional y cuadro de mando | Día 5: ingresos devengados, cobros, gastos, pagos, resultado y tesorería por actividad, oficina y total; comparación mensual, desviaciones, pendientes y fiabilidad | Resumen económico (F5.0) | Tras DR-CON-2…5 |

Trazabilidad de principio a fin (9 pasos): recibir con origen, fecha e identificador único → guardar el original sin
modificar → extraer y clasificar con incertidumbres y duplicados → asignar actividad, oficina, proveedor/cliente y
expediente → cruzar factura, justificante y movimiento (conciliado/parcial/pendiente) → propuesta de registro y
excepciones a revisión → nóminas, devengos y ajustes → cierre provisional con versión bloqueada → exportación a la
gestoría y reconciliación con el cierre oficial.

Estructura bancaria propuesta (sección 7): de 13–14 cuentas a tres — **A** cobros de laboral, **B** cobros de
extranjería y nacionalidad, **C** pagos y tesorería central; traspasos A/B→C documentados que **no son ingresos**.
Exigir al banco exportación (CSV, Excel, CAMT.053/OFX), extractos y saldos diarios, referencias de cobro y detalle de
comisiones. Migración segura: inventariar, elegir, mantener temporalmente las antiguas, no cerrar todas de golpe.
**Si hay titulares jurídicos distintos o fondos de clientes que deban segregarse, no mezclar sin revisión
profesional** → decisión T-38.

Calendario: días 1–2 importar movimientos y documentos; día 3 conciliación y partidas sin pareja; día 4 nóminas,
facturas pendientes, periodificaciones y ajustes; día 5 informe provisional con pendientes y fecha de corte. Cada
lunes, resumen semanal. **No confundir tesorería (cobrado/pagado) con resultado (devengado).**

Criterios de aceptación del documento: el total importado coincide con extractos y saldos; cada operación conserva
documento fuente, estado, responsable y fecha de revisión; no se duplican traspasos, TPV, Bizum, devoluciones ni
facturas; la suma por oficina y actividad coincide con el total (incluidos gastos compartidos); excepciones en una
bandeja única con prioridad y responsable; pagos con autorización humana y nóminas restringidas; el cierre del día 5
indica qué cifras son provisionales y qué falta por conciliar.

**Instrucción final de Dirección:** empezar por una prueba real de lectura de documentos y **conciliación de una
cuenta**, con una pantalla de movimientos importados, conciliados, pendientes y errores; después conectar los ocho
motores y preparar un informe provisional de un mes conocido; todo revisable en móvil y ordenador con permisos
diferenciados. Prototipo: un mes cerrado, 30–50 documentos y 50–100 movimientos de una cuenta.

## 4. Recursos Humanos (DR-RH)

Un módulo con ocho motores y **una ficha única de empleado**. Antes de cada motor, comprobar qué ya resuelve MN
Program o el control horario actual.

| ID | Motor | Qué pide | Situación hoy | Qué falta |
|---|---|---|---|---|
| DR-RH-1 | Importación y ficha única | Excel de MN Program y nóminas PDF → ficha: oficina, categoría, antigüedad, jornada, salario, situación; duplicados y campos ausentes | Usuarios del sistema (F0.2), sin ficha laboral | Nuevo; formato de exportación de MN (T-10) |
| DR-RH-2 | Lectura y archivo documental | Contratos, anexos, nóminas, certificados, solicitudes; carpeta del empleado con acceso restringido | Lector de documentos (F4.3) | Nuevo, reutilizando el lector |
| DR-RH-3 | Control horario e incidencias | Conectarse al control horario existente; faltas de fichaje, excesos y diferencias, sin duplicar el registro | — | Saber qué sistema se usa (T-41) |
| DR-RH-4 | Vacaciones, permisos y ausencias | Saldos, calendario, solicitudes, coincidencias, avisos; bajas con acceso restringido | — | Nuevo (Q-5.2, Q-5.3) |
| DR-RH-5 | Nóminas y gestoría | Datos de nóminas, cambios de jornada, variables, altas, bajas; resumen para la gestoría y diferencias entre periodos; **no calcula la nómina** | — | Nuevo |
| DR-RH-6 | Contratos, vencimientos y alertas | Vencimientos, periodos de prueba, documentación; borradores para revisión de RRHH | — | Nuevo |
| DR-RH-7 | Formación y seguimiento | Manuales, lectura semanal de 30 min, examen mensual de 10 preguntas por capítulo, informes | — | Nuevo; exámenes con IA (D-24) |
| DR-RH-8 | Cuadro de mando de plantilla | Barcelona, Madrid, Valencia y Colombia: plantilla, categorías, costes, movimientos, ausencias; reglas por país | — | Nuevo; reglas de Colombia por validar |

Criterios del documento: empezar con **5 fichas y 5 nóminas ficticias**; nombre, categoría, salario, centro,
fechas y documentos bien vinculados; cada alerta con empleado, motivo, fecha y responsable; **decisiones sobre
personas con validación humana**; registro de errores, accesos y cambios, permisos por función, cifrado y copias;
**no migrar ni eliminar datos de MN Program hasta validar integridad, funcionamiento y recuperación**.

## 5. Mensajes automáticos al cliente (DR-MSG) — por el portal, no por WhatsApp

El plan de WhatsApp se aplica al **portal propio** (T-31): no hay Callbell, ni plantillas de Meta, ni ventana de
24 horas (notas de la persona responsable: «No serán necesarios», «No habrá ventana de 24 h porque se usará una
plataforma personal»).

| ID | Mensaje | Cuándo | Condición |
|---|---|---|---|
| DR-MSG-1 | Bienvenida | Al abrir el expediente | Cliente con acceso al portal |
| DR-MSG-2 | Documentación pendiente | Solicitud y recordatorio | Lista del trámite con faltas |
| DR-MSG-3 | Presentación | Solo cuando esté **verificada** | Fase «presentado» confirmada por una persona |
| DR-MSG-4 | Seguimiento | Cada 2–3 meses | Comprobando que el expediente sigue en trámite |
| DR-MSG-5 | Recordatorios | Citas, conciliaciones y juicios | Fecha y lugar **verificados** (tarea de la agenda) |
| DR-MSG-6 | Novedades | Para revisión y envío por el gestor | Nunca automático |
| DR-MSG-7 | Cierre | Comunicación final cuando proceda | Revisión humana |
| DR-MSG-8 | Trazabilidad | Expediente, cliente, tipo, versión de plantilla, evento, fecha programada y real, entrega, respuestas, incidencias, gestor | Sin duplicados; se detiene al cerrar el expediente |
| DR-MSG-9 | Seguridad | Sin datos sensibles; resoluciones, denegaciones y situaciones delicadas con revisión humana | RGPD, conservación, baja |

Piloto: primero bienvenida y recordatorios de juicio o cita; después seguimientos y documentación; grupo reducido
de expedientes con supervisión diaria. Medir cada semana: mensajes programados, entregados y fallidos, respuestas,
errores, duplicados y casos derivados al personal.

Plantillas (texto de Dirección, adaptado al portal; `{n}` = dato del expediente):
- **DR-PLT-1 bienvenida_expediente**: «Buenos días, {nombre}. Le confirmamos que hemos abierto su expediente con
  referencia {expediente} en Abogado Rafael Serrano. Para consultas relacionadas con su expediente, puede responder a
  este mensaje.»
- **DR-PLT-2 aviso_fecha_conciliacion**: «Buenos días, {nombre}. Le informamos de que la conciliación
  correspondiente a su expediente {expediente} está señalada para el día {fecha}, a las {hora}, en {lugar}. Si se
  produce algún cambio, se lo comunicaremos.»
- **DR-PLT-3 recordatorio_conciliacion_24h**: «Buenos días, {nombre}. Le recordamos que la conciliación de su
  expediente {expediente} está prevista para mañana, día {fecha}, a las {hora}, en {lugar}. Si tiene alguna
  incidencia para asistir, comuníquenoslo cuanto antes.»
- **DR-PLT-4 aviso_fecha_juicio**: «Buenos días, {nombre}. Le informamos de que el juicio correspondiente a su
  expediente {expediente} está señalado para el día {fecha}, a las {hora}, en {lugar}. Le avisaremos si se produce
  alguna modificación.»
- **DR-PLT-5 recordatorio_juicio_24h**: «Buenos días, {nombre}. Le recordamos que el juicio de su expediente
  {expediente} está previsto para mañana, día {fecha}, a las {hora}, en {lugar}. Si tiene alguna incidencia para
  asistir, comuníquenoslo cuanto antes.»
- **Seguimiento (ejemplo)**: «Buenos días. Le contactamos desde el despacho Abogado Rafael Serrano. Hemos comprobado
  que su expediente continúa en trámite. Seguimos pendientes de novedades y le informaremos cuando se produzca alguna
  actuación relevante. Gracias por su confianza.»

## 6. Orden de construcción acordado

| Bloque | Contenido | Por qué primero |
|---|---|---|
| **F5.1 ✔ (08/11/2026)** | Motor de agentes (eventos, agentes, bandeja única de propuestas) + **conciliación bancaria** (DR-CON-2, DR-CON-3 en parte) con pantalla de importados/conciliados/pendientes/errores + **agente de mensajes** (DR-MSG-1, 4, 5; DR-PLT-1…5) | Instrucción final de Dirección; el piloto de mensajes pide bienvenida y recordatorios primero |
| **F5.2 ✔ (08/11/2026)** | Recepción: cobros de consulta/provisión/servicio, justificante no fiscal, cierre diario validado, duplicados y saldos (DR-REC-3, 4, 8) + informe diario (DR-REC-10) | Fase 1 del plan de Recepción |
| **F5.3 ✔ (08/11/2026)** | RRHH: ficha única con 5 empleados y 5 nóminas ficticias, archivo documental, vacaciones y ausencias, vencimientos (DR-RH-1, 2, 4, 6) | Fases 1–3 del guion de RRHH |
| **F5.4 ✔ (09/11/2026)** | Facturas de proveedores con lectura y duplicados (DR-CON-1 en parte, DR-CON-4), tesorería con previsión y **remesas de doble firma** con fichero SEPA (DR-CON-7), coste de personal desde RRHH (DR-CON-5), **cierre provisional del día 5** con cuadro de mando por actividad y oficina (DR-CON-8). Asientos bloqueados (DR-CON-6, T-40); entrada por correo pendiente (T-48) | Necesita banco y gastos |
| **F5.4b ✔ (09/11/2026)** | Petición de Dirección: **sistema de trabajo de Contabilidad** (rutina con el calendario de este manual, comprobada por el sistema, con tareas en la Agenda y responsables) e **informes semanales, quincenales y mensuales** (PDF/CSV, correo sin cifras, revisión de Dirección). Extractos en **Excel** | Mejora el trabajo diario y la supervisión |
| F5.5 | Citas propias y llegada a recepción (DR-REC-1, 2), agente de recepción que clasifica y deriva (DR-REC-6, 7) | Decisiones D-11, D-19 |

## 7. Decisiones nuevas que salen de estos documentos

| ID | Pregunta | Propuesta | Valida |
|---|---|---|---|
| T-38 | Estructura bancaria A/B/C | Viable si una sola sociedad opera las tres oficinas; con titulares distintos o fondos de clientes segregados, revisión profesional antes de mezclar | Dirección / gestoría |
| T-39 | Formato de extracto de cada banco | CSV del banco, Norma 43 (AEB) o CAMT.053; el sistema lee los tres | Contabilidad |
| T-40 | Plan de cuentas para propuestas de asientos | Lo facilita la gestoría; hasta entonces solo exportación | Gestoría |
| T-41 | Sistema de control horario actual | Conectar por exportación o API si existe; si no, registro propio | RRHH / Dirección |
| T-44 | Justificante de cobro no fiscal | Documento interno que no es factura; la factura sale del programa homologado | Contabilidad / gestoría |
| T-45 | Frecuencia del seguimiento | Cada 75 días (entre 2 y 3 meses), solo expedientes en trámite y sin mensajes del despacho en ese tiempo | Dirección |
| T-46 | Hora de los recordatorios de 24 h | 10:00 del día anterior, hora de Madrid | Dirección |
| T-47 | Envío automático de mensajes sin revisión | Bienvenida, recordatorios y seguimiento: automáticos tras el piloto aprobado; novedades, presentación, cierre y resoluciones: siempre revisión | Dirección |
| T-48 | Buzón de correo para recibir facturas | Buzón dedicado con acceso de solo lectura (IMAP) o reenvío a la bandeja | Contabilidad / TI |
