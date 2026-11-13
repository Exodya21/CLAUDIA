# Decisiones: aprobadas frente a abiertas

Fecha de corte: 02/11/2026 (actualizado con F0.2). Regla: **lo que no figura en la sección 1 no está aprobado**. Una propuesta técnica
razonable sigue siendo una propuesta hasta que el responsable la valida por escrito.

## 1. Realmente aprobado

### 1.1 Directrices del encargo (PROMPT 00, CLAUDE.md y Plan Maestro)
Fijadas por la Dirección del despacho como condiciones de trabajo. Se aplican desde F0.1.

| # | Directriz | Aplicación en el sistema |
|---|---|---|
| A-01 | Sistema propio sin dependencia obligatoria de MNProgram ni de Odoo | Arquitectura propia (ADR-0001) |
| A-02 | Desarrollo solo con datos sintéticos | Semilla ficticia; la semilla se niega a correr fuera de desarrollo |
| A-03 | Permisos reales en backend, denegar por defecto | Motor de política + tests AT-01/AT-02 |
| A-04 | Auditoría de ediciones, accesos y descargas | `audit_event` inmutable |
| A-05 | Una persona = un contacto maestro con N expedientes; nunca fusión automática por teléfono | Modelo + AT-04 |
| A-06 | La IA prepara borradores; no decide viabilidad, plazos, firmas ni presentaciones | Sin IA en F0.1; regla para F6 (D-24) |
| A-07 | Tratamiento de "usted" en comunicaciones al cliente | Regla para M12 (U-15) |
| A-08 | No ofrecer automatizaciones de reserva de actuaciones biométricas | Excluido del backlog (U-17) |
| A-09 | ATC registra, investiga y escala; no decide viabilidad ni aprueba devoluciones; Contabilidad valida devoluciones | Máquinas de estado (estados.md §3 y §7) |
| A-10 | Tres fichas laborales con preguntas comprensibles y OCR solo con confirmación humana | Diseño M04 (F2) |
| A-11 | Sin envío/descarga automática en portales oficiales sin interfaz autorizada y autorización profesional | M10 bloqueado por D-09 |
| A-12 | Stack sugerido (Next.js + FastAPI + PostgreSQL, monolito modular) | Adoptado (ADR-0001, ADR-0002) |

### 1.2 Decisiones de la matriz ya resueltas
| ID | Decisión | Situación |
|---|---|---|
| D-14 | Q-6.20 duplicado → se conserva como Q-6.20 y Q-6.20B | Resuelta documentalmente |

### 1.3 Acuerdos U-01…U-18
Constan como "Para validación final" en la matriz. **Se diseñan conforme a ellos, pero no están aprobados.**
Deben validarse antes de construir M04 (F2).

## 2. Abiertas — de la matriz (D-01…D-25)

Lista completa con riesgo, propuesta e IDs afectados: [`registro_decisiones_matriz.md`](registro_decisiones_matriz.md)
(generado desde la matriz). Resumen por lo que bloquean:

| Bloquea | Decisiones | Efecto en el plan |
|---|---|---|
| Reglas de plazos (M09) | D-02 FOGASA, D-03 pruebas vs margen, D-04 caducidad, D-21 ejecución | F2.2 construye tareas y plazos **sin** reglas automáticas: el letrado introduce y valida la fecha legal |
| Nacionalidad/extranjería (M11) | D-01 plazo no universal | Recordatorios solo con regla versionada aprobada por Legal Extranjería |
| Firma (M07) | D-08 evidencias, D-22 firma por página | F2.3 almacena documentos; la firma espera proveedor y validación |
| Comunicaciones (M12) | D-10 mensaje de apertura, D-20 bloqueo WhatsApp | Plantillas sin afirmaciones procesales |
| Economía (M14) | D-05 honorarios, D-06 Intrastat, D-07 SIF/VeriFactu, D-16 factura global, D-18 suplidos, D-25 proveedor | F5.0 construye control económico **no fiscal** (cobros, devoluciones, cajas, gastos). Las facturas se emitirán con un programa homologado conectado (comparativa D-25 en preparación) |
| Citas (M03) | D-11 videollamada, D-19 elección de asesor | Modalidad y selector configurables |
| Acceso (M00) | D-13 recepción, D-17 Colombia | Implementado de forma restrictiva; ampliar solo con aprobación |
| Datos/migración | D-15 corte con MNP, D-23 volumen real | F1.1 ensayo de importación con datos ficticios |
| Portales (M10) | D-09 | F6, solo con interfaz autorizada |
| Formularios | D-12 una encuesta por rama | Motor de plantillas versionadas |
| IA | D-24 | F6 |

## 3. Abiertas — técnicas y de producto surgidas en el diseño (T-01…T-50)

| ID | Pregunta | Propuesta | Valida | Bloquea |
|---|---|---|---|---|
| T-01 | Proveedor de identidad OIDC con MFA (Microsoft Entra ID, Google Workspace, Keycloak propio…) | Si el despacho usa Microsoft 365 (I-114), Entra ID evita otra cuenta. **F0.2 ya incluye el cliente OIDC genérico** (PKCE, MFA exigido): solo falta registrar la aplicación y rellenar 3 variables. Mientras tanto funciona el acceso local con contraseña + código del móvil | Dirección / TI | Acceso corporativo único (no bloquea: existe acceso local con MFA) |
| T-02 | Alojamiento y región de datos | Proveedor en la UE con contrato de encargo; producción, pruebas y desarrollo separados | Dirección / DPO | Producción |
| T-03 | Almacenamiento de documentos | S3 compatible en la UE, cifrado en servidor, versiones, antivirus | TI / DPO | F2.3 |
| T-04 | Catálogo de finalidades y bases jurídicas de consentimiento; minimización en auditoría | Borrador en `ConsentIn.purpose`; DPO lo sustituye | DPO | Datos reales |
| T-05 | Política de conservación y archivo de expedientes y contactos | Archivo lógico; plazos por tipo de expediente definidos por DPO y Dirección | DPO / Dirección jurídica | F2.1 (archivo) |
| T-06 | Formato del código visible de expediente | `LAB-AAAA-NNNN` por entidad, consecutivo sin reutilización (implementado como propuesta) | Dirección | F2.1 |
| T-07 | ¿Recepción de una sede localiza clientes de las otras sedes? | Sí (implementado), porque los clientes llaman a cualquier sede | Dirección / DPO | — |
| T-08 | Roles reales y su correspondencia con puestos actuales | Sustituir los roles de demostración por el organigrama vigente (D-23) | Dirección / RRHH | Datos reales |
| T-09 | ¿Cifrar a nivel de columna los números de documento? | Evaluar con DPO frente a coste en búsquedas exactas | DPO / TI | F0.2 |
| T-10 | Inventario de exportaciones de MNP y Bookitit (campos, derechos de exportación) | Solicitar exportación de prueba anonimizada | Dirección / TI | F1.1 |
| T-11 | Umbral del indicador de expediente inactivo (Q-6.4) | 30 días sin actividad registrada; configurable | Dirección | — (implementado como propuesta) |
| T-12 | ¿Quién valida plazos legales? | Permiso `deadline.validate`, hoy en Líder Laboral y Dirección; crear rol Letrado por rama | Dirección jurídica | Uso real de plazos |
| T-13 | Separación entre quien propone y quien valida un plazo | Obligatoria (implementada). ¿Excepción para despachos unipersonales o urgencias? | Dirección jurídica | — |
| T-15 | Recuperación del segundo factor si se pierde el móvil | Dirección restablece credenciales (auditado, cierra sesiones). Sin códigos de recuperación de momento | Dirección / DPO | — (implementado como propuesta) |
| T-16 | Política de contraseñas y de sesión | ≥12 caracteres; bloqueo 15 min tras 5 fallos; sesión máx. 8 h y 60 min de inactividad (configurables) | Dirección / TI | — (implementado como propuesta) |
| T-17 | Dónde se guardan las copias fuera del ordenador y con qué cifrado; frecuencia | Diaria, conservando 14; copia externa cifrada en la UE | Dirección / TI / DPO | Uso con datos reales |
| T-18 | Control de gastos: ¿dentro de SISTEMA PROPIO o con Microsoft 365 / Power Automate (nota de Dirección, programador ISJ)? | Dentro del sistema (F5.0, ya operativo): une gastos, caja, permisos y auditoría. Si se mantiene SharePoint para la captura, se importa desde allí | Dirección / Contabilidad | — |
| T-19 | Formato real del extracto de las tarjetas de empresa | Pedir un extracto de ejemplo anonimizado a Contabilidad; hoy CSV genérico `fecha;concepto;importe;tarjeta` | Contabilidad | Conciliación automática con el banco real |
| T-20 | ¿Lectura de tickets con un servicio de IA externo (p. ej. Azure Document Intelligence, el motor de AI Builder)? | Hoy lectura local sin enviar datos fuera. Un servicio externo exige contrato de encargo y región UE | Dirección / DPO | Mejor precisión en fotos de baja calidad |
| T-21 | Tipos de gasto (catálogo de conceptos) y quién puede pagar con la caja | 9 conceptos iniciales; cualquier empleado puede imputar gasto a la caja de su sede | Contabilidad | — |
| T-22 | Aviso de pasaporte próximo a caducar | 90 días antes (`PASSPORT_WARN_DAYS`); configurable | Legal Extranjería | — (implementado como propuesta) |
| T-23 | Validación del catálogo de 14 trámites de extranjería (listas de documentos copiadas de las hojas informativas oficiales con su fecha) | Cada trámite queda «pendiente de validar» hasta que Legal Extranjería lo apruebe; los expedientes muestran el aviso | Legal Extranjería | Uso real de las listas |
| T-31 | Canal con el cliente: ¿WhatsApp o portal propio? | **APROBADA por Dirección el 06/11/2026: portal propio, sin depender de WhatsApp.** Construido en F2.3 (ADR-0009). Los requisitos de WhatsApp de la matriz (I-093, I-115, Q-3.3, Q-3.4, Q-6.3) se conservan y quedan «sustituidos por el portal» a falta del acta de cierre (T-36) | Dirección | — |
| T-32 | Textos al cliente: bienvenida, condiciones del portal y plantillas (solicitud de documentos, citación de conciliación, señalamiento, requerimiento) | Redactados de usted, sin afirmaciones sobre plazos (D-10) ni promesas; en `app/comm/templates.py` y `routers/portal.py` | Dirección / Dirección jurídica / DPO | Uso con clientes reales |
| T-33 | Proveedor de correo saliente (códigos de acceso y avisos) | Servicio SMTP con contrato de encargo y servidores en la UE; se configura con variables `SMTP_*`. Sin él no sale ningún correo | Dirección / TI / DPO | Uso real del portal |
| T-34 | Quién puede enviar avisos urgentes | Propuesta implementada: Líderes y Dirección (`comm.notice.urgent`); asesores y gestores envían avisos importantes | Dirección | — (implementado como propuesta) |
| T-35 | SMS y notificaciones push para avisos urgentes (fase 2) | Proveedor de SMS con contrato en la UE; push cuando haya app instalable. Hoy: correo sin contenido + escalado a llamada a las 24 h | Dirección / TI | Fase 2 de comunicaciones |
| T-36 | Acta sobre los requisitos de WhatsApp de la matriz | Cerrarlos por sustitución (portal propio) o mantener WhatsApp solo como aviso «tiene un mensaje en su portal» | Dirección | Cierre de I-093, I-115, Q-3.3, Q-3.4, Q-6.3 |
| T-37 | Plazo de conservación de conversaciones y adjuntos | Mismo plazo que el expediente (T-05); nada se borra mientras tanto | DPO / Dirección | Uso con datos reales |
| T-38 | Estructura bancaria A (Laboral) / B (Extranjería) / C (Tesorería) | Implementada como propuesta en F5.1 (cuentas ficticias 1111/2222/3333). Viable si una sola sociedad opera las tres oficinas; con titulares distintos o fondos de clientes segregados, revisión profesional antes de mezclar | Dirección / gestoría | Uso con cuentas reales |
| T-39 | Formato de extracto de cada banco | El sistema lee **Excel (.xlsx, .xls y el «.xls» en HTML de la banca electrónica)**, Norma 43, CAMT.053 y CSV; busca la cabecera aunque haya filas de título y admite Importe o Cargo/Abono. Si un banco usa otros nombres de columna, el error dice cuáles hacen falta: enviar solo la **fila de cabecera** (sin movimientos) para añadirlos. Para probar un extracto real sin dejarlo en la base: botón **«Comprobar sin importar»**, que no guarda nada | Contabilidad | Importación real |
| T-40 | Plan de cuentas para proponer asientos | Hasta tenerlo, solo exportación CSV para la gestoría (implementado, también del cierre del mes F5.4). En Contabilidad → Cierre del mes figura «Propuesta de asientos: no disponible aún» | Gestoría | Propuestas de asientos (DR-CON-6) |
| T-41 | Sistema de control horario actual | Conectar por exportación o API si existe; si no, registro propio | RRHH / Dirección | F5.3 RRHH |
| T-44 | Justificante de cobro no fiscal | Implementado como propuesta en F5.2: «Justificante de pago — documento interno, NO ES UNA FACTURA», numerado REC-SEDE-AÑO-000001, inmutable; falta validar el texto con la gestoría | Contabilidad / gestoría | Uso con clientes reales |
| T-45 | Frecuencia del seguimiento al cliente | Implementada como propuesta: cada 75 días, expedientes abiertos o en trámite sin mensajes del despacho en ese tiempo | Dirección | — (ajustable) |
| T-46 | Hora de los recordatorios del día anterior | Implementada como propuesta: 10:00 hora de Madrid | Dirección | — (ajustable) |
| T-47 | Envío automático sin revisión | Implementado: por defecto el agente **propone** y una persona aprueba; Dirección puede activar «automático» solo para bienvenida, avisos/recordatorios de fecha y seguimiento, tras el piloto. Novedades, presentación, cierre y resoluciones: siempre una persona | Dirección | Activar tras el piloto |
| T-49 | Festivos de cada sede (nacionales, autonómicos y locales) para contar días de vacaciones y plazos internos | Hoy se cuentan lunes a viernes; los festivos se cargarán por sede y año cuando RRHH facilite el calendario | RRHH / Dirección | Saldo exacto de vacaciones |
| T-50 | Días de vacaciones al año por convenio y categoría | Se informan en cada ficha (demo: 22 laborables en España y 15 en Colombia, **pendiente de validar**); el sistema no los calcula | RRHH / gestoría | Uso real de vacaciones |
| T-51 | Quién valida el cierre diario de caja | Implementado como propuesta: Contabilidad y Dirección (`cash.close.validate`), nunca quien contó la caja | Dirección | — (implementado como propuesta) |
| T-52 | Rol de Recursos Humanos y quién decide vacaciones | Rol «RRHH» con plantilla, nóminas y avisos; los líderes deciden las ausencias de su departamento; nadie aprueba las suyas | Dirección / RRHH | Uso real |
| T-48 | Buzón para recibir facturas de proveedores | Buzón dedicado de solo lectura (IMAP) o reenvío a la bandeja. Mientras tanto (F5.4) las facturas se suben a mano y se leen igual | Contabilidad / TI | Entrada automática por correo |
| T-53 | Coste de personal en el cuadro de mando | Implementado como propuesta en F5.4: quien no tiene `hr.salary` ve el coste de personal y el resultado **agrupados** cuando el grupo (actividad u oficina) tiene menos de 3 personas, para no revelar salarios individuales | Dirección / RRHH / DPO | Uso con nóminas reales |
| T-54 | Quién firma las remesas de pago | Implementado como propuesta en F5.4: Contabilidad propone; **dos personas distintas de Dirección** (`treasury.approve`) firman; nunca quien propone (también en la base de datos). En demo: «Dirección» y «Socio Director». El sistema genera el fichero SEPA y una persona lo sube a la banca; nunca ordena transferencias | Dirección | Uso con cuentas reales |
| T-55 | IBAN completos para el fichero SEPA | Implementado: el IBAN de cada cuenta del despacho y de cada proveedor se guarda **cifrado** (se muestra enmascarado); hace falta el formato SEPA que acepta cada banco (pain.001.001.03 por defecto) | Contabilidad / banco | Primera remesa real |
| T-57 | Calendario de la rutina de Contabilidad | Implementado como propuesta (F5.4b, manual de Dirección): diario extractos y conciliación; lunes facturas, martes pagos, cajas e informe semanal; días 1 y 16 informe quincenal (1–15 y 16–fin); días 2, 3, 4 y 5 extractos, conciliación, nóminas/facturas y cierre; día 7 aprobación del cierre e informe mensual. Fin de semana → lunes; sin festivos (T-49). Responsables demo: Contabilidad y Dirección | Dirección / Contabilidad | — (ajustable) |
| T-58 | Destinatarios de los informes y aviso por correo | Implementado como propuesta: correo **sin cifras** a quien tiene permiso de leer Contabilidad (Contabilidad y Dirección); Dirección los marca como revisados. Necesita el proveedor de correo (T-33) | Dirección / DPO | Envío real de correos |
| T-59 | CIF del despacho para la lectura de facturas recibidas | Implementado: variable `OWN_TAX_IDS` en el `.env` de cada instalación (nunca en el código); además se descartan los CIF que aparecen junto al nombre de la entidad o tras «a la mercantil», «cliente»… Si la factura trae varios CIF y no se sabe cuál es el del proveedor, la pantalla los ofrece para elegir. Propuesta: pasar el CIF a la ficha de la entidad en Administración | Dirección / TI | — |
| T-60 | Usar los datos reales en una instalación local antes del servidor definitivo (T-02) | Pedido por la usuaria el 09/11/2026 para empezar las pruebas reales. Implementado: instalación REAL separada (`INICIAR_REAL.bat`, base y documentos propios, sin datos ficticios, acceso con contraseña + código, cifrado con `.env.real`, copias propias). Condiciones: disco cifrado, copia diaria y `.env.real` guardado fuera del equipo. Es de un solo ordenador: para el equipo y las sedes, servidor en la UE (T-02) | Dirección / DPO | Uso por todo el equipo |
| T-56 | Límites y calendario de pagos | Sin límites automáticos: cada remesa la deciden dos personas. Propuesta para validar: importe máximo por remesa y día fijo de pagos | Dirección | Uso real |
| T-24 | Extensión de navegador para **rellenar** Mercurio (fase 2) | **APROBADA por Dirección el 05/11/2026**: rellena pero no presenta. Construida en F4.2 (ADR-0008) | Dirección / Legal Extranjería | — |
| T-27 | Validar la extensión sobre Mercurio real (las etiquetas y la estructura pueden diferir de la página de prueba) | Expediente con datos inventados, rellenar sin presentar y enviar el diagnóstico (sin datos) de cada pestaña | Legal Extranjería / TI | Uso con clientes reales |
| T-29 | Pestaña del empleador en Mercurio real: identificadores de cuenta de cotización, centro de trabajo, puesto, retribución | Enviar el diagnóstico «Copiar estructura de esta página (sin datos)» de esa pestaña; hasta entonces se rellena por etiqueta | Legal Extranjería / TI | Relleno completo del empleador |
| T-30 | Formatos de contrato, padrón y vida laboral que se leen | Modelos públicos (SEPE, padrón genérico, 790-052, TIE); para otros formatos, ejemplos anonimizados | Legal Extranjería | Mejora de la lectura |
| T-28 | Distribución de la extensión en los equipos | Hoy carga manual («Cargar descomprimida»). En producción: Chrome Web Store privada o política de Google Workspace / Intune | Dirección / TI | Despliegue |
| T-25 | Notificaciones de DEHú (fase 3): ¿alta como gran destinatario en LEMA (servicios web) o descarga manual + lectura automática del PDF? | Primero lectura del PDF descargado por una persona (sin credenciales en el sistema); LEMA cuando Dirección tramite la declaración responsable y la representación esté registrada | Dirección / TI | Fase 3 |
| T-26 | Calendario de días hábiles e inhábiles (nacional, autonómico, local) para proponer plazos de requerimientos | Sin calendario: el letrado propone el plazo con su fuente y otro lo valida (D-01, D-03) | Legal Extranjería | Cálculo asistido de plazos (fase 3) |
| T-14 | Catálogo de orígenes de leads y cuáles exigen campaña | 9 orígenes iniciales; TikTok Live y Google Ads exigen campaña | Marketing / Dirección | — |

