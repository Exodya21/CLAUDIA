# Necesidades del Project Charter (08/09/2026), por bloques

Cada necesidad tiene tres partes: **problema**, **solución acordada** y, cuando el charter lo indica, **fase** y **desarrollo a medida**. Las anotaciones en mayúsculas del original están marcadas como «Punto abierto».

---

## Bloque 1 · Estructura, multicompañía y seguridad

**1.1 Multicompañía e intercompañía (FASE 1)**
- Odoo multicompañía con 3 entidades: la S.L. principal, la filial de Colombia y el autónomo del titular.
- Se puede consolidar la información o filtrarla por empresa.
- Cuando Colombia o el autónomo facturan a la S.L., se crea automáticamente la factura de proveedor enlazada en la S.L.

**1.2 Roles y permisos por fases (FASE 1)**
- Se usan grupos de permisos y reglas de acceso por registro (*record rules*).
- **Fase 1:**
  - Dirección: acceso total, incluidos los paneles y Power BI.
  - Administrador de Atención al Cliente: CRM, embudo, agenda, WhatsApp/VoIP y supervisión de recepción.
  - Colaborador de Atención al Cliente: leads, citas y consultas; solo los registros que tiene asignados.
  - RRHH: empleados, fichajes, ausencias, contratos, nóminas, reclutamiento y evaluaciones.
  - Marketing: CRM, campañas (Brevo/WhatsApp), formularios y sitio web.
  - Contabilidad: facturación, diarios, bancos, impuestos y analítica.
- **Fase 2:**
  - Administrador de Extranjería y Laboral: acceso total a los expedientes, agendas, documentos, facturación de honorarios y tickets de su departamento.
  - Colaborador de Extranjería y Laboral: solo los expedientes asignados (tareas, historial, notificaciones y carga de pruebas).
- Motivo: el RGPD y que la base de más de 100.000 contactos está expuesta.

**1.3 Partes de horas (Timesheets)**
- Cada tarea de Proyectos tiene un temporizador Play/Pause, también en la cabecera de Odoo 20.
- Informes de tiempo estimado frente a tiempo real por expediente o cliente, para medir la carga de trabajo y la rentabilidad.

**1.4 Alojamiento en la nube (FASE 1)**
- QUBIQ Cloud, Odoo.sh o un servidor dedicado, con SSL, monitorización, mantenimiento y copias de seguridad automáticas.
- Punto abierto: QUBIQ presentará un presupuesto y el cliente decide.

---

## Bloque 2 · Captación de clientes

**2.1 Captación multicanal con Origen obligatorio (FASE 1)**
- Odoo CRM es el núcleo de todas las iniciativas.
- **Meta Ads → WhatsApp:** el lead se crea a mano desde el chat.
- **Formularios web:** crean el lead automáticamente. Se formará al equipo para crear formularios.
- **TikTok, llamadas y recepción:** el lead se crea a mano o mediante un alias de correo.
- **Bookitic:** se sustituye por Citas (ver 2.4).
- El campo **Origen/Canal es obligatorio**. Si el lead viene de una automatización, se rellena solo; si no, no se puede guardar sin él.

**2.2 Email marketing masivo con Brevo y campañas por WhatsApp (FASE 1)**
- Odoo Email Marketing, con segmentación por etiquetas de contacto (Laboral, Extranjería, TikTok, Sorteo…).
- **Correo:** se envía por el SMTP de Brevo, para no caer en spam ni en los bloqueos de Outlook. El historial se ve en un botón de la ficha del contacto.
- **WhatsApp:** se usan plantillas aprobadas por Meta y una acción de servidor que se lanza sobre los contactos filtrados.

**2.3 Redes sociales (FASE 1)**
- Odoo Marketing Social con Facebook, Instagram y TikTok.
- Se ven los comentarios públicos y se crea un lead con un clic; el origen se categoriza solo.
- Los chats privados **no** se atienden desde Odoo en esta fase: siguen en Meta Business o Metricool.

**2.4 Citas de Odoo en lugar de Bookitic (FASE 1)**
- Odoo Citas publicado en el sitio web de Odoo.
- Cada reserva entra como oportunidad.

**2.5 Filtrado jerárquico de las citas (FASE 1)**
1. **Rama** (Laboral, Extranjería, Cálculo de finiquito…). *Desarrollo:* modelo nuevo y campo obligatorio en la cita, que sirve de filtro en la web.
2. **Modalidad y ubicación** (Presencial Barcelona, Madrid o Valencia, Llamada, Videollamada). *Desarrollo:* campo nuevo que también sirve de filtro.
3. **Por día o por asesor** (estándar): calendario conjunto de todos los asesores que cumplen el filtro, o un asesor concreto con su nombre y foto.
4. **Franjas fijas** por tipo de cita (estándar).
- Formulario de preguntas nativo. Una vez pagada la cita, se crea la oportunidad y el evento en el calendario.
- El despacho podrá crear sus propios tipos de cita, cuestionarios y franjas.
- Problema que resuelve: citas presenciales en Barcelona reservadas con asesores que están en Madrid o Colombia.

**2.6 Pago previo obligatorio, promociones y trazabilidad (FASE 1)**
- Redsys y pago por adelantado nativo, con los productos «Consulta Extranjería 40 €» y «Consulta Laboral 50 €».
- La cita solo se confirma, y la oportunidad solo se crea o actualiza, cuando Redsys confirma el pago.
- **Promociones (desarrollo):**
  - Códigos de descuento de UGC o influencers, para medir el retorno.
  - Descuentos por **nacionalidad**: la respuesta del formulario se vincula a un país y hay un tipo de promoción limitado a ciertos países.
  - Descuentos por fechas o días de poca demanda.
- **Desarrollo:** el primer presupuesto o factura de la cita queda vinculado y visible en la ficha de la oportunidad.

**2.7 Embudo Lead → Cita pagada → Expediente, con analítica heredada (FASE 1)**
- **Lead:** captación y cualificación, sin dinero de por medio.
- **Oportunidad:** cita cobrada y etapas. Si el cliente contrata, la oportunidad se marca como Ganada y se hace el presupuesto del expediente con un producto de tipo servicio. Al confirmarlo, se crea el proyecto o expediente desde la plantilla de su rama.
- **Desarrollo:**
  - Al confirmar el presupuesto de la cita web, se crea una cuenta analítica ligada a la oportunidad.
  - El segundo presupuesto (el del expediente) **hereda la misma cuenta analítica**, para ver el margen de toda la operación.
- Se formará al equipo en informes y filtros, por ejemplo: citas en un rango de fechas que acabaron en Ganado.

**2.8 Leads de TikTok Live «Teléfono Rojo» (FASE 1)**
- Etiqueta de origen «TikTok Live / Teléfono Rojo».
- Los números se cargan de forma masiva desde Excel o a mano. Hay formación sobre importar y exportar.
- Las acciones automatizadas crean actividades de seguimiento (a las 72 h, a la semana…).

**2.9 Encuestas antes de la cita, según la rama (FASE 1)**
- Al pasar a la etapa «Cita Confirmada», una acción automatizada envía por correo **y** WhatsApp el enlace a una encuesta de la rama de la oportunidad.
  - La rama es un campo nuevo obligatorio, presente también en la encuesta.
  - Hay **una encuesta por rama**.
- También se podrá enviar a mano con una acción de servidor.
- **Desarrollo:**
  - Un token en el enlace y un botón en la oportunidad con las encuestas respondidas.
  - Al responder, la oportunidad pasa sola a la siguiente etapa.
- **Acción planificada:** recordatorios cada X días por correo o WhatsApp hasta la cita.
- **Módulo de terceros** `bi_survey_files_upload`, para que el cliente adjunte documentos (DNI, contrato, vida laboral, nóminas).

**2.10 Sitio web en Odoo (FASE 1)**
- La web pasa a Odoo Website, propiedad del despacho, con los contenidos actuales replicados.
- Se formará a Marketing en el editor visual.
- Citas va integrada en la web.

---

## Bloque 3 · Atención al cliente

**3.1 Oportunidades estancadas, SLA y flujo reversible (FASE 1)**
- Tiempo máximo por etapa (p. ej. 10 días), con avisos y colores.
- Las oportunidades pueden avanzar y retroceder. Si al cliente aún le falta tiempo (p. ej. un año de empadronamiento), la oportunidad vuelve a «En espera / Cultivo» con una actividad programada para más adelante.

**3.2 Recordatorios de renovación y nacionalidad**
- La ficha de contacto tiene dos campos: **Fecha de residencia inicial** y **Fecha de renovación de residencia**.
- Una revisión diaria automática se encarga de:
  - **Renovación:** 2 o 3 meses antes del vencimiento crea una oportunidad y envía una plantilla de WhatsApp o correo.
  - **Nacionalidad:** a los 2 años de la residencia inicial crea una oportunidad para ofrecer el trámite.

**3.3 WhatsApp API (FASE 1)**
- Integración de WhatsApp con Odoo para gestionar los chats y los envíos automáticos.
- Contexto: el número del despacho llegó a recibir 6.000 mensajes en un día y quedó bloqueado. Hoy se usa Callbell.

**3.4 Lista negra de WhatsApp**
- **No se puede hacer en Odoo** (según el charter).

**3.5 Centralita VoIP con grabación y transcripción (FASE 1)**
- Se mantiene Telefónica y se pasa a **Fusión Digital 365**.
- **Desarrollo de QUBIQ por API**, porque no hay integración estándar.
- Las llamadas se hacen y reciben desde Odoo.
- La grabación y la transcripción por IA se enlazan en el historial del contacto, de la oportunidad o del expediente.

**3.6 Secretaría virtual mediante alias de correo (FASE 1)**
- La secretaría externa escribe a un alias (p. ej. `secretaria@…` o `leads@…`) y se crea una iniciativa en el CRM con aviso al asignado.
- Se formará al equipo para configurar los alias.

**3.7 Videollamadas (FASE 1)**
- Si se elige la modalidad «Videollamada», Odoo Discuss genera una URL única que va en los correos de aviso.

**3.8 Helpdesk con SLA (FASE 1)**
- Los tickets llegan por correo, por la web o se crean a mano.
- Tienen prioridad (estrellas), clasificación (Consulta, Queja, Cliente molesto…) y políticas de SLA.
- Sustituye a los Excel actuales.

**3.9 Reclamaciones y devoluciones con Contabilidad (FASE 1)**
1. Atención al Cliente investiga y lo deja escrito en el historial.
2. Pasa el ticket a la etapa «Aprobado para Devolución» y menciona a @contabilidad.
3. Contabilidad hace el abono o la transferencia, adjunta el justificante y cierra el ticket.

**3.10 Recepción sin papel y firma en tableta (FASE 1)**
- Odoo Sign con tabletas de firma en las recepciones de Barcelona, Madrid y Valencia.
- **Pagos:** se genera el recibo o la factura y el cliente lo firma en el pad.
- **Autorizaciones:** se envía el PDF a la tableta o al móvil del cliente y, una vez firmado, se adjunta al expediente.
- Algunos documentos seguirán imprimiéndose; se escanean y se adjuntan.

**3.11 Sincronización con el calendario de Outlook en los dos sentidos (FASE 1)**
- Las citas web, los señalamientos y las reuniones de Odoo aparecen en Outlook.
- Los bloqueos que se ponen en Outlook actualizan la disponibilidad en Odoo.

---

## Bloque 4 · Facturación y contabilidad

**4.1 Facturación unificada y series (FASE 1)**
- **Problema:** hoy se factura en Bookitic (citas) y en MN Program (expedientes). Contabilidad junta dos Excel al mes y renumera a mano para la gestoría.
- **Solución:**
  - **Citas:** con el pago por Redsys se confirma la cita, se crea la oportunidad y se emite la factura con el cobro ya registrado.
  - **Expedientes:** facturas con la cuenta analítica del expediente.
  - **Diario de ventas:** el charter dice «solo un diario de ventas» y, a la vez, dos series independientes: **CIT/2026/00001** (citas web) y **EXP/2026/00001** (expedientes). Están pensadas para la correlatividad que exige Verifactu.
- **Punto abierto:** ¿la cuenta analítica va con el expediente o con el contacto? ¿Cómo se controla qué está pagado y en qué estado?
- **Punto abierto** (pendiente de que lo evalúe Dirección): una factura por el coste total del producto y cobros a medida que avanza el proceso.

**4.2 Verifactu en la S.L. y el autónomo (FASE 1)**
- Huella (hash) y encadenamiento al registrar cada factura, y envío a la AEAT según el calendario legal.
- En Community 20 existe el módulo `l10n_es_edi_verifactu`.

**4.3 Cobro por varias vías y enlaces de pago (FASE 1)**
- **Redsys:** enlace de pago con un clic, enviado por correo o WhatsApp. Al pagar, la factura o el presupuesto queda como pagado.
- **Cobros presenciales:** se registran en el diario de caja.

**4.4 Devoluciones y abonos (FASE 1)**
- Cuando se aprueba el ticket de Helpdesk, Contabilidad recibe el aviso y pulsa «Crear factura rectificativa / nota de abono», que revierte el asiento.
- La devolución por Redsys la hace Contabilidad **fuera de Odoo**.

**4.5 Conciliación bancaria automática (FASE 1)**
- Sincronización con los 3 bancos y sus varias cuentas.
- Reglas de conciliación; solo se revisan a mano las excepciones.

**4.6 Activos fijos**
- De 3 a 4 activos, dados de alta a mano con su valor, vida útil y método.
- La tabla de amortización y los asientos periódicos son automáticos.

**4.7 Honorarios del 20 % en Laboral**
- Campo **obligatorio** «Total del acuerdo ganado» en el expediente laboral.
- Cuando entra el 100 % en el banco:
  1. Se hace a mano la factura de honorarios del 20 % + IVA al cliente.
  2. La salida del 80 % al cliente se registra con un asiento en una **cuenta de mediación**, de forma que se concilia sin buscar el expediente en papel.

**4.8 Suplidos y pagos parciales en Extranjería**
- Las tasas oficiales van en líneas de suplido, con cuentas del grupo 554/555, y no afectan a la cuenta de resultados.
- Los pagos parciales (100 €, 50 €, 20 €…) van reduciendo el saldo hasta liquidarlo.

**4.9 Ficheros SEPA para nóminas y colaboradores**
- Pagos masivos ISO 20022: se genera el fichero y se sube al banco.
- Incluye las liquidaciones semanales a los abogados colaboradores.

**4.10 Gestoría externa con usuario propio e Intrastat de servicios**
- Usuario con rol de auditor o contable para la gestoría: revisa facturas, la contabilidad europea y el Intrastat de servicios, y saca los datos de los modelos de la AEAT.
- Se dejan de enviar Excel.

**4.11 Analítica por sede y departamento**
- Planes analíticos jerárquicos:
  - **Sede:** Barcelona, Madrid, Valencia, Colombia.
  - **Departamento:** Laboral, Extranjería, Marketing, RRHH, Administración.
- Cada gasto se imputa a su cuenta, lo que da una cuenta de resultados por segmento.

**4.12 Migración y catálogo**
- **QUBIQ migra:**
  - Contactos sin duplicados.
  - Asiento de apertura a la fecha de corte.
  - Efectos pendientes de cobro y de pago.
  - Mandatos SEPA.
- **El despacho da de alta a mano** los productos y servicios (consultas, trámites, cuotas laborales) con sus precios, cuentas e impuestos, después de la formación.

**4.13 Gastos con OCR**
- Foto del ticket desde la app móvil, indicando si lo pagó el empleado o la empresa.

**4.14 Cajas por sede**
- Tres diarios de efectivo: Caja Barcelona, Caja Madrid y Caja Valencia.
- Se puede auditar el saldo de cada una en cualquier momento.

**4.15 Multimoneda y plan contable de Colombia**
- Tipo de cambio COP/EUR diario del Banco Central Europeo.
- Plan contable colombiano para la filial.
- Facturación intercompañía de Colombia a la S.L.

**4.16 Intercompañía y reparto de costes**
- Cuando Colombia factura a la S.L., se crea automáticamente la factura de proveedor en la S.L., con los saldos intergrupo conciliados.

**4.17 Compras simplificadas**
- Sin pedidos de compra: las facturas de proveedor se registran directamente y se imputan a la analítica de sede o departamento.

**4.18 Plantillas PDF propias (QWeb)**
- **Facturas y abonos:** imagen corporativa, datos fiscales de la S.L. o del autónomo, impuestos, datos de Verifactu, IBAN y SWIFT.
- **Justificantes de cobro y de presentación:** recibos de caja o TPV y justificantes de presentación ante la Administración o el juzgado.
- **Hojas de encargo y contratos:** se formará al despacho para actualizarlas en la app de firma.

---

## Bloque 5 · Recursos humanos y control

**5.1 Fichajes y horarios por temporada**
- Odoo Asistencias, desde el móvil o la web.
- RRHH configura los calendarios de verano e invierno sin intermediarios. La jornada intensiva va del 15 de julio al 15 de septiembre.
- Se registran la IP y la geolocalización (opcional) y se calculan las horas trabajadas, extra o que faltan.

**5.2 Vacaciones con doble aprobación**
- Aprueban primero el responsable del departamento y después RRHH.
- Se asignan los días anuales (p. ej. 23 laborables).
- Se descuentan solos los fines de semana y festivos, y el saldo se ve en tiempo real.

**5.3 Calendario de ausencias y permisos según convenio**
- Convenio de Oficinas y Despachos.
- Tipos: Horas de médico (la más frecuente), Permiso retribuido, Licencia sin sueldo y Baja médica.
- Vista de calendario con filtros para detectar solapamientos antes de aprobar.

**5.4 Exportar la plantilla a Excel**
- Exportación estándar de los campos que se elijan, con plantillas que se pueden reutilizar.

**5.5 Carga masiva de nóminas en PDF**
- *Desarrollo:* un importador lee el NIF o DNI del PDF y lo archiva en la carpeta privada de cada empleado, en Documentos.

**5.6 Firma de documentos de personal**
- Odoo Sign para contratos, entregas de equipos, RGPD y confidencialidad, con certificado de auditoría.

**5.7 Reclutamiento**
- Puestos con un alias de correo propio (p. ej. `empleo@…`).
- Kanban de candidaturas: Solicitud recibida → Primera entrevista → Entrevista técnica → Oferta enviada → Contratado.
- Guarda los CV y las notas.

**5.8 Evaluaciones de desempeño**
- Anuales, semestrales o al acabar el periodo de prueba.
- Autoevaluación y valoración del responsable, de forma confidencial y con historial.

**5.9 Helpdesk interno**
- Alias de correo (p. ej. `rrhh@…`).
- Tickets por tipo: Suministros, Informática y Consultas contractuales.

---

## Bloque 6 · Laboral y Extranjería

**6.1 Viabilidad previa y ficha de preguntas**
- Hay una etapa de **Evaluación de viabilidad** en el CRM, con campos dinámicos en una pestaña nueva que cambia según la rama.
- **Favorable:** se hace un presupuesto con el producto del expediente; al confirmarlo se crea el borrador del expediente.
- **No viable:** la oportunidad se marca como perdida, con el motivo.
- **Desarrollo:** una acción de servidor exporta los datos a una **plantilla Word (.docx) editable** que el letrado puede retocar.
- En este repositorio, el prototipo es la Super Ficha Laboral.

**6.2 Alta y estructura del expediente**
- Se usa Odoo Proyectos.
- **Secuencia consecutiva sin saltos:** `EXP-LAB-2026-001` / `EXP-EXT-2026-001`.
- **Campos obligatorios:**
  - Tipo o Especialidad: campo nuevo que se toma del proyecto plantilla del producto.
  - Cliente: viene del presupuesto.
  - Parte contraria o Demandado.
  - Usuario creador.
  - Letrado asignado: es el gerente del proyecto.
  - Fecha de alta: automática.
  - Estado mediante etapas: Abierto, Pausado, Cerrado.
  - Relación entre expedientes.
  - El ID del proyecto como identificador.

**6.3 Bienvenida por WhatsApp y petición de pruebas**
- Al llegar a la etapa marcada como «Expediente Abierto» (solo una etapa puede tener esa marca), se envía una plantilla de WhatsApp. El mensaje:
  - confirma la apertura;
  - informa de que el despacho asume los plazos;
  - incluye un enlace único para subir las pruebas.

**6.4 Fases del expediente y alerta de inactividad**
- Vistas Kanban y de lista con las etapas Abierto, En tramitación, Pausado y Cerrado.
- Se cuentan los días desde la última modificación de las tareas. A partir de **15 días sin cambios**, la tarjeta se pone en rojo y se avisa al responsable.

**6.5 Preapertura en Extranjería, con requisitos por trámite**
- Estado «Preapertura / Borrador de expediente».
- Se crean automáticamente las carpetas que tocan según la tipología; las carpetas plantilla se definen en los ajustes.
- El cliente recibe un enlace con los requisitos de su trámite (arraigo, nacionalidad, menor nacido en España…) y sube ahí los documentos.
- El gestor valida o pide corrección de cada documento. Con todo validado, el expediente pasa a «Abierto».
- Problema que resuelve: hoy llegan fotos por WhatsApp que hay que pasar a PDF y comprimir a mano.

**6.6 Firma de varios documentos con un solo enlace**
- Hoy se envían de 8 a 9 enlaces y el cliente solo firma el primero.
- Con Odoo Sign: un enlace (por WhatsApp o correo) para firmar todo seguido: hoja de encargo, RGPD y autorizaciones de representación. Al terminar, se desbloquea la apertura.
- **Desarrollo:** el PDF que se descarga lleva adjunto el certificado de firma.

**6.7 Validez de la firma ante los juzgados**
- Hay Juzgados de lo Social (p. ej. en Asturias o Cataluña) que rechazan firmas ordinarias, y al fusionar PDF se cortan las firmas en los márgenes.
- Solución:
  - Formato **PDF/A con OCR**.
  - **Desarrollo:** certificado adjunto al PDF firmado.
- El título del charter menciona un sello en el margen inferior derecho.

**6.8 Plantillas de papeleta y demanda**
- Con un clic, los campos del expediente se pasan al documento editable: cliente, NIF, salario diario, convenio, fecha de despido, demandado… Son unas 100 variables.
- Se anexa la autorización ya firmada, **sin volver a firmar**.
- Se formará al despacho para unir y dividir PDF en Odoo.

**6.9 Plazos antes del juicio**
- Pestaña **Plazos procesales** en el expediente.
- A partir de la **Fecha fin laboral** se calculan los límites de la papeleta (CMAC) a **15 y 20 días hábiles**, descontando fines de semana y festivos.
- Otros campos de fecha: Conciliación, Inicio laboral, Burofax y Demanda de despido.
- Las acciones automatizadas crean tareas **5 y 2 días** antes de cada vencimiento.
- Sustituye al Excel de plazos.

**6.10 Juicio, pruebas y recordatorios**
- Al introducir la **Fecha del juicio** (día y hora):
  - se crea la actividad «Aportación de pruebas» **12 días hábiles antes** (la ley exige 10; el margen interno es de 12 a 13);
  - se envía un WhatsApp al cliente **30 días y 24 h antes**;
  - se envía un mensaje después de la vista;
  - se programa la revisión de la sentencia a los **60 días**.

**6.11 Sentencia y ejecución**
- Resultado «Sentencia estimatoria» más la Fecha de sentencia. Se crean alertas para el letrado:
  - a los **2 meses**, para la demanda de ejecución;
  - a los **9 meses**, para la averiguación patrimonial o la insolvencia.

**6.12 Insolvencia y FOGASA**
- Campo nuevo: **Fecha del decreto de insolvencia**, en la pestaña de plazos.
- El plazo es de 1 año. Se crean 4 actividades encadenadas a los **90, 180, 270 y 330 días**; la de 330 días va en prioridad alta (roja).

**6.13 Portal de pruebas y archivos pesados**
- El cliente sube fotos, audios y vídeos por el portal o por un enlace de una carpeta compartida de Documentos.
- **Desarrollo:** al crear el expediente se crean sus carpetas en Documentos, enlazadas con él.

**6.14 Repositorio y envío seguro a letrados sustitutos (RGPD)**
- Carpetas: `01. Pruebas Cliente`, `02. Selección Juicio`, `03. Notificaciones`.
- **Desarrollo:**
  - Botón en el proyecto que abre su carpeta.
  - Estructura de carpetas por tipología, definida en los ajustes. Se crea por código y es de solo lectura.
- Se comparte la carpeta con el sustituto mediante un enlace que solo pueden abrir las personas autorizadas. Sustituye a WeTransfer.

**6.15 Tipos de actuación, colores y nombres de las tareas**
- **Campos nuevos en las tareas:**
  - **Tipología**, con nombre y color en un menú propio.
  - **Subtipología**, por ejemplo Señalamiento, Requerimiento o Vista.
  - **Nombre predeterminado**: nombre, descripción, subtipología y tipología.
- El color de la tipología se ve en las vistas de lista, Kanban, Gantt y calendario.
- Casilla **«nombre manual»**: si está marcada, se usa `name_manually`; si no, el nombre predeterminado, que rellena la descripción. Una automatización copia el valor que toca en `name`.

**6.16 Preparación de juicios: Pendiente o Preparado**
- Las tareas de tipo Juicio usan la bolita de estado: Pendiente (rojo) o Preparado (verde).
- «Preparado» se marca a mano y solo cuando la carpeta de pruebas está validada.
- Cuando se completa, sale de la vista de pendientes pero queda en el historial.

**6.17 Historial y autoría de los cambios**
- No se pueden modificar las tareas de otros.
- El historial (chatter) registra quién crea, cambia una fecha o descripción, o cambia el estado, con la fecha y la hora.

**6.18 Plugin de Outlook y historial unificado**
- Plugin oficial de Odoo para Outlook: con un clic, el correo y sus adjuntos se asocian al expediente.
- Las conversaciones de WhatsApp quedan en la conversación del cliente.

**6.19 Aviso a Contabilidad tras una resolución favorable**
- Propuesta: al marcar «Sentencia estimatoria» o «Trámite concluido» e introducir el importe, se crea **a mano** un borrador de factura y se menciona a @contabilidad.
- **Punto abierto:** revisarlo con Contabilidad. En Laboral, el cobro del 20 % no es un aviso manual: el dinero llega al despacho y se devuelve el 80 %.

**6.20 Colores de la agenda de Extranjería**
- Rojo: lo urgente y lo que vence hoy.
- Verde: revisión de documentación y presentación telemática.
- Azul: aperturas en seguimiento inicial.
- Los colores van por tipología, con filtro en el calendario.

**6.21 Pagos escalonados en Extranjería**
- El pago inicial se pide con el pedido de venta, que es lo que crea el expediente. Se paga por transferencia o en efectivo en recepción.
- Tras el pago final se emiten la factura y el justificante de presentación.
- **Punto abierto:** cómo se avisa del pago final.
- Preferencia anotada: **una factura global** del trámite y cobros sobre ella, por transferencia nacional o internacional y en efectivo.

**6.22 Documentación por trámite**
- Al elegir el trámite en la preapertura, se genera su paquete de documentos (hoja de encargo, autorizaciones y cláusulas) para firmar o descargar desde el enlace personal.

**6.23 Restricción de edición en agendas ajenas**
- Con el grupo Project User, cada usuario solo puede modificar o desagendar sus propias tareas. Los cambios quedan en el historial.

**6.24 Orden por fecha límite**
- Se usa el campo `deadline`. La vista de lista de tareas se ordena por defecto por ese campo, ascendente.

**6.25 Migración de expedientes desde MN Program («corte limpio»)**
- **Fase 1:** contactos, asiento de apertura y efectos pendientes. Los expedientes antiguos siguen en MN Program.
- **Fase 2:** se importan los expedientes **activos** con plantillas CSV o Excel: número, cliente, letrado, estado procesal y documentos clave.
- Desde la puesta en marcha (Go-Live), todo lo nuevo se abre solo en Odoo.

---

## Contexto adicional

- **Integración con la Administración:** hoy no hay ninguna integración ni API con LexNET, Justíciacat ni la Subdelegación del Gobierno. Las presentaciones y las descargas se hacen a mano y los justificantes en PDF se suben después al expediente. El charter **no** incluye esa integración.
- **Integración con MN Program:** el traspaso de la Super Ficha también menciona como pendiente la integración con MN Program (identificador de cliente y de expediente).
