# Mapa de cobertura — 208 referencias

> Generado por `scripts/build_coverage.py` desde `docs/fuentes/02_Matriz_Maestra_208_Requisitos.xlsx`. No editar a mano: modificar las reglas del script y regenerar. Ningún ID se elimina; la clasificación es una propuesta de producto pendiente de validación por Dirección.

## Recuento

| Fuente | equivalente | complementario | nuevo | contradictorio | sin_definicion | Total |
|---|---|---|---|---|---|---|
| Informe 120 | 24 | 22 | 43 | 2 | 29 | 120 |
| Qubiq 70 | 17 | 24 | 0 | 15 | 14 | 70 |
| Acuerdos 18 | 0 | 15 | 1 | 2 | 0 | 18 |
| **Total** | **41** | **61** | **44** | **19** | **43** | **208** |

Significado: **equivalente** = misma necesidad en dos fuentes (se construye una vez, se enlazan los IDs); **complementario** = relacionado pero con alcance propio; **nuevo** = solo aparece en su fuente; **contradictorio** = contiene una afirmación jurídica/fiscal/operativa a corregir antes de programar; **sin definición** = depende de una decisión estructural abierta.

## Informe 120

| ID | Necesidad | Mód. | Fase | Cobertura | Relaciones | Decisiones |
|---|---|---|---|---|---|---|
| I-001 | Apertura automática de fichas | M01 | F1 | complementario | Q-2.9, Q-6.1 | — |
| I-002 | Lectura automática de DNI, NIE, pasaporte y documentos | M01 | F1 | complementario | Q-4.13, Q-5.5 | — |
| I-003 | Detección de clientes duplicados | M01 | F1 | nuevo | — | — |
| I-004 | Superficha laboral estructurada | M04 | F2 | equivalente | Q-2.9, Q-6.1 | — |
| I-005 | Dictado por voz y transcripción | M04 | F2 | complementario | Q-3.5 | — |
| I-006 | Detección de datos incompletos | M04 | F2 | equivalente | Q-2.9, Q-6.1 | — |
| I-007 | Apertura automática de expedientes | M05 | F2 | equivalente | Q-6.2 | — |
| I-008 | Asignación de responsables | M05 | F2 | equivalente | Q-1.2, Q-6.2 | — |
| I-009 | Actualización automática de expedientes | M05 | F2 | nuevo | — | — |
| I-010 | Clasificación por materia, fase y prioridad | M05 | F2 | equivalente | Q-6.2 | — |
| I-011 | Cálculo de finiquitos | M06 | F3 | nuevo | — | — |
| I-012 | Indemnización por despido improcedente | M06 | F3 | nuevo | — | — |
| I-013 | Indemnización por despido objetivo | M06 | F3 | nuevo | — | — |
| I-014 | Diferencias salariales según convenio | M06 | F3 | nuevo | — | — |
| I-015 | Cálculo de horas extraordinarias | M06 | F3 | nuevo | — | — |
| I-016 | Vacaciones pendientes | M06 | F3 | nuevo | — | — |
| I-017 | Pagas extraordinarias pendientes | M06 | F3 | nuevo | — | — |
| I-018 | Complementos salariales | M06 | F3 | nuevo | — | — |
| I-019 | Actualización de cantidades reclamadas | M06 | F3 | complementario | Q-4.7, Q-6.19 | — |
| I-020 | Informe económico laboral | M06 | F3 | complementario | Q-4.7, Q-4.8, Q-6.19, Q-6.21 | — |
| I-021 | Generación de papeletas desde la superficha | M08 | F3 | equivalente | Q-6.8 | — |
| I-022 | Redacción de hechos | M08 | F3 | nuevo | — | — |
| I-023 | Detección de conceptos reclamables | M08 | F3 | nuevo | — | — |
| I-024 | Papeletas por despido | M08 | F3 | nuevo | — | — |
| I-025 | Papeletas de reclamación de cantidad | M08 | F3 | nuevo | — | — |
| I-026 | Papeletas con despido y cantidad cuando proceda | M08 | F3 | nuevo | — | — |
| I-027 | Comprobación de plazos | M08 | F3 | contradictorio | Q-6.9 | D-04 |
| I-028 | Generación en Word y PDF | M08 | F3 | equivalente | Q-3.10, Q-6.6, Q-6.8, Q-6.22 | — |
| I-029 | Preparación de anexos | M08 | F3 | nuevo | — | — |
| I-030 | Presentación telemática por vías autorizadas | M10 | F6 | sin_definicion | — | D-09 |
| I-031 | Descarga de justificantes | M10 | F6 | nuevo | — | — |
| I-032 | Seguimiento de conciliaciones | M08 | F3 | nuevo | — | — |
| I-033 | Conversión de papeletas en demandas | M08 | F3 | equivalente | Q-6.8 | — |
| I-034 | Demandas por despido improcedente | M08 | F3 | nuevo | — | — |
| I-035 | Demandas por despido nulo | M08 | F3 | nuevo | — | — |
| I-036 | Demandas de reclamación de cantidad | M08 | F3 | nuevo | — | — |
| I-037 | Separación de demandas cuando proceda | M08 | F3 | nuevo | — | — |
| I-038 | Demandas por despido verbal | M08 | F3 | nuevo | — | — |
| I-039 | Demandas de trabajadores en situación administrativa irregular | M08 | F3 | nuevo | — | — |
| I-040 | Demandas por diferencias salariales | M08 | F3 | nuevo | — | — |
| I-041 | Demandas por vacaciones | M08 | F3 | nuevo | — | — |
| I-042 | Demandas por modificación sustancial | M08 | F3 | nuevo | — | — |
| I-043 | Demandas por extinción contractual | M08 | F3 | nuevo | — | — |
| I-044 | Búsqueda y propuesta de jurisprudencia verificable | M08 | F3 | sin_definicion | — | D-24 |
| I-045 | Revisión de omisiones, fechas y cantidades | M08 | F3 | sin_definicion | Q-6.1 | D-24 |
| I-046 | Generación de borrador definitivo para revisión letrada | M08 | F3 | sin_definicion | Q-6.8 | D-24 |
| I-047 | Preparación de presentaciones en LexNET | M10 | F6 | sin_definicion | — | D-09 |
| I-048 | Presentaciones en e-Justícia.cat | M10 | F6 | sin_definicion | — | D-09 |
| I-049 | Propuesta de órgano judicial con validación | M10 | F6 | sin_definicion | — | D-09 |
| I-050 | Incorporación de anexos | M10 | F6 | sin_definicion | — | D-09 |
| I-051 | Comprobación de documentos obligatorios | M10 | F6 | sin_definicion | — | D-09 |
| I-052 | Validación de formatos, firmas y datos | M10 | F6 | sin_definicion | Q-3.10, Q-5.6, Q-6.6, Q-6.7 | D-09 |
| I-053 | Descarga de justificantes | M10 | F6 | sin_definicion | — | D-09 |
| I-054 | Archivo de escritos presentados | M10 | F6 | sin_definicion | — | D-09 |
| I-055 | Descarga de LexNET | M10 | F6 | sin_definicion | — | D-09 |
| I-056 | Descarga de e-Justícia.cat | M10 | F6 | sin_definicion | — | D-09 |
| I-057 | Descarga de DEHú | M10 | F6 | sin_definicion | — | D-09 |
| I-058 | Descarga de resoluciones de extranjería | M10 | F6 | sin_definicion | — | D-09 |
| I-059 | Identificación del expediente | M10 | F6 | sin_definicion | — | D-09 |
| I-060 | Incorporación a MN Program | M10 | F6 | sin_definicion | — | D-09 |
| I-061 | Clasificación por tipo de notificación | M10 | F6 | sin_definicion | — | D-09 |
| I-062 | Extracción de plazos para validación | M10 | F6 | sin_definicion | — | D-09 |
| I-063 | Asignación al responsable | M10 | F6 | sin_definicion | — | D-09 |
| I-064 | Alertas urgentes | M10 | F6 | sin_definicion | — | D-09 |
| I-065 | Preparación de comunicaciones al cliente | M10 | F6 | sin_definicion | — | D-09 |
| I-066 | Control de pendientes | M10 | F6 | sin_definicion | — | D-09 |
| I-067 | Registro de señalamientos judiciales | M09 | F2 | equivalente | Q-6.15 | — |
| I-068 | Registro de conciliaciones | M09 | F2 | nuevo | — | — |
| I-069 | Calendario centralizado | M09 | F2 | complementario | Q-2.4, Q-2.5, Q-3.7 | — |
| I-070 | Avisos anticipados de juicios | M09 | F2 | equivalente | Q-6.10, Q-6.16 | — |
| I-071 | Recordatorios a clientes | M09 | F2 | equivalente | Q-3.2, Q-3.7, Q-6.10 | — |
| I-072 | Recordatorios a abogados | M09 | F2 | equivalente | Q-6.10 | — |
| I-073 | Control de vencimientos | M09 | F2 | contradictorio | Q-6.9, Q-6.10, Q-6.11, Q-6.12, Q-6.20, Q-6.20B | D-04 |
| I-074 | Detección de solapamientos | M09 | F2 | nuevo | — | — |
| I-075 | Asignación de sustituciones | M09 | F2 | nuevo | — | — |
| I-076 | Agendas diarias y semanales | M09 | F2 | equivalente | Q-2.5, Q-5.2, Q-5.3, Q-6.15, Q-6.20, Q-6.20B | — |
| I-077 | Informes de actuaciones | M09 | F2 | nuevo | — | — |
| I-078 | Clasificación documental | M07 | F2 | equivalente | Q-5.6, Q-6.6, Q-6.7, Q-6.13, Q-6.14, Q-6.22 | — |
| I-079 | Extracción de datos de documentos | M07 | F2 | complementario | Q-4.13, Q-5.5 | — |
| I-080 | Detección de documentos faltantes | M07 | F2 | complementario | Q-2.9, Q-6.5 | — |
| I-081 | Solicitud de documentos al cliente | M07 | F2 | equivalente | Q-6.3, Q-6.5, Q-6.13 | — |
| I-082 | Preparación de carpetas de prueba | M07 | F2 | equivalente | Q-6.13, Q-6.14, Q-6.16 | — |
| I-083 | Índices documentales | M07 | F2 | equivalente | Q-6.14 | — |
| I-084 | Instructas para juicios | M07 | F2 | complementario | Q-6.16 | — |
| I-085 | Resumen de hechos controvertidos | M07 | F2 | nuevo | — | — |
| I-086 | Clasificación de jurisprudencia favorable y desfavorable | M07 | F2 | nuevo | — | — |
| I-087 | Archivo de sentencias y resultados | M07 | F2 | complementario | Q-6.11, Q-6.12, Q-6.19 | — |
| I-088 | Asignación de gestor personal | M05 | F2 | nuevo | — | — |
| I-089 | Panel de tareas por gestor | M05 | F2 | equivalente | Q-3.1, Q-3.8, Q-5.9, Q-6.4, Q-6.23 | — |
| I-090 | Aviso de apertura de expediente | M05 | F2 | complementario | Q-3.10, Q-6.3 | — |
| I-091 | Mensaje de bienvenida | M12 | F4 | equivalente | Q-6.3 | — |
| I-092 | Seguimiento de expedientes | M05 | F2 | equivalente | Q-6.4 | — |
| I-093 | Mensajes mediante WhatsApp | M12 | F4 | equivalente | Q-2.3, Q-3.3, Q-3.4, Q-4.3 | — |
| I-094 | Correos electrónicos automáticos | M12 | F4 | complementario | Q-2.2, Q-3.2 | — |
| I-095 | Recordatorios documentales | M12 | F4 | equivalente | Q-6.3 | — |
| I-096 | Avisos de cambio de estado | M12 | F4 | nuevo | — | — |
| I-097 | Registro de comunicaciones | M12 | F4 | equivalente | Q-2.3, Q-3.3, Q-3.4, Q-3.5, Q-3.6, Q-3.9, Q-4.4, Q-6.17, Q-6.18 | — |
| I-098 | Detección de clientes sin seguimiento | M05 | F2 | equivalente | Q-2.8, Q-3.1, Q-3.2, Q-3.8, Q-6.4 | — |
| I-099 | Consultas atendidas | M16 | F4 | complementario | Q-2.1, Q-2.4, Q-2.6, Q-2.7, Q-2.8, Q-3.6 | — |
| I-100 | Fichas abiertas | M16 | F4 | nuevo | — | — |
| I-101 | Expedientes contratados | M16 | F4 | complementario | Q-2.6, Q-2.7, Q-4.1, Q-4.3 | — |
| I-102 | Conversión de consultas | M16 | F4 | complementario | Q-2.1, Q-2.7 | — |
| I-103 | Cálculos realizados | M16 | F4 | nuevo | — | — |
| I-104 | Papeletas preparadas | M16 | F4 | nuevo | — | — |
| I-105 | Conciliaciones presentadas | M16 | F4 | nuevo | — | — |
| I-106 | Demandas preparadas y presentadas | M16 | F4 | nuevo | — | — |
| I-107 | Notificaciones recibidas y gestionadas | M16 | F4 | nuevo | — | — |
| I-108 | Carga de expedientes por gestor | M16 | F4 | nuevo | — | — |
| I-109 | Tiempos de ejecución | M16 | F4 | complementario | Q-5.1, Q-5.8 | — |
| I-110 | Cuadro de mando por sede | M16 | F4 | complementario | Q-1.1, Q-4.1, Q-4.5, Q-4.6, Q-4.10, Q-4.11, Q-4.14 | — |
| I-111 | Superficha con MN Program | M17 | F6 | sin_definicion | — | — |
| I-112 | Importación y exportación Excel | M17 | F6 | complementario | Q-2.1, Q-4.10, Q-4.12, Q-5.4 | — |
| I-113 | Plantillas documentales MN Program | M17 | F6 | sin_definicion | — | — |
| I-114 | Microsoft 365 y Teams | M17 | F6 | complementario | Q-6.18 | — |
| I-115 | WhatsApp Business API y Callbell | M17 | F6 | complementario | Q-3.3 | — |
| I-116 | Correo electrónico | M17 | F6 | complementario | Q-2.2, Q-6.18 | — |
| I-117 | IA para redactar, clasificar y comprobar | M17 | F6 | sin_definicion | — | D-24 |
| I-118 | Plataformas judiciales por interfaces autorizadas | M17 | F6 | sin_definicion | — | D-09 |
| I-119 | DEHú, Mercurio y plataformas administrativas | M17 | F6 | sin_definicion | — | D-09 |
| I-120 | Orquestación, registro de errores y control de accesos | M17 | F6 | complementario | Q-1.1, Q-1.2, Q-3.9, Q-4.2, Q-4.4, Q-4.9, Q-4.15, Q-4.16, Q-5.7, Q-6.17, Q-6.23 | — |

## Qubiq 70

| ID | Necesidad | Mód. | Fase | Cobertura | Relaciones | Decisiones |
|---|---|---|---|---|---|---|
| Q-1.1 | Configuración Multicompañía e Integración Intercompany | M00 | F0 | complementario | I-110, I-120 | — |
| Q-1.2 | Control de accesos, reglas de registro y seguridad de contactos | M00 | F0 | contradictorio | I-008, I-120 | D-13 |
| Q-2.1 | Captación Multicanal Centralizada de Leads con Campo "Origen" Obligatorio | M02 | F1 | complementario | I-099, I-102, I-112 | — |
| Q-2.2 | Email Marketing Masivo mediante Servidor Dedicado (Brevo) y Segmentación por Etiquetas | M02 | F1 | complementario | I-094, I-116 | — |
| Q-2.3 | Centralización de Mensajería en Redes Sociales (Facebook, Instagram, TikTok) | M12 | F4 | equivalente | I-093, I-097 | — |
| Q-2.4 | Sustitucion de Bookitic por la Agenda Virtual de Odoo Integrada en Web | M03 | F1 | complementario | I-069, I-099 | — |
| Q-2.5 | Filtrado Jerárquico Estricto de Citas (Rama > Ubicación/Modalidad > Asesor > Horario) | M03 | F1 | complementario | I-069, I-076 | D-19 |
| Q-2.6 | Cobro Previo Obligatorio de Citas mediante Pasarela de Pago | M03 | F1 | complementario | I-099, I-101 | — |
| Q-2.7 | Trazabilidad Comercial del Embudo (Lead -> Cita Pagada -> Expediente Abierto) | M02 | F1 | complementario | I-099, I-101, I-102 | — |
| Q-2.8 | Trazabilidad y Control de Leads de TikTok Live ("Teléfono Rojo") | M02 | F1 | complementario | I-098, I-099 | — |
| Q-2.9 | Automatización de Recolección de Información Pre-Cita según la Rama (Planilla / Encuestas y Recordatorios) | M04 | F2 | equivalente | I-001, I-004, I-006, I-080 | D-12 |
| Q-3.1 | Alertas de Oportunidades Estancadas, SLA y Flujos Reversibles | M02 | F1 | complementario | I-089, I-098 | — |
| Q-3.10 | Recepción Presencial, Eliminación de Papel y Firma Digital en Tabletas/PDF | M07 | F2 | complementario | I-028, I-052, I-090 | — |
| Q-3.2 | Acciones Automatizadas para Recordatorios de Renovación de Residencia y Nacionalidad | M11 | F4 | contradictorio | I-071, I-094, I-098 | D-01 |
| Q-3.3 | Integración de WhatsApp API / Callbell con Botones de Enrutamiento Interactivo | M12 | F4 | equivalente | I-093, I-097, I-115 | — |
| Q-3.4 | Filtro y Bloqueo de Contactos Spam o Impertinentes en WhatsApp (Lista Negra) | M12 | F4 | sin_definicion | I-093, I-097 | D-20 |
| Q-3.5 | Integración de Centralita Telefónica VoIP, Grabación y Transcripción Automática | M12 | F4 | equivalente | I-005, I-097 | — |
| Q-3.6 | Integración con Secretaría Virtual Externa mediante Alias de Correo | M12 | F4 | equivalente | I-099, I-097 | — |
| Q-3.7 | Integración de Videollamadas en la Cita Virtual | M03 | F1 | contradictorio | I-069, I-071 | D-11 |
| Q-3.8 | Gestión de Consultas e Incidencias Mediante Servicio de Asistencia (Helpdesk) y SLA | M13 | F4 | complementario | I-089, I-098 | — |
| Q-3.9 | Flujo Integrado de Reclamaciones y Devoluciones de Dinero con Contabilidad | M13 | F4 | complementario | I-097, I-120 | — |
| Q-4.1 | Centralización de Facturación Unificada, Sustitución de Bookitic y MN Program, y Diarios Contables Diferenciados | M14 | F5 | sin_definicion | I-101, I-110 | D-16, D-25 |
| Q-4.10 | Intrastat por Servicios y Coordinación con Gestoría Externa mediante Usuario Directo | M14 | F5 | contradictorio | I-110, I-112 | D-06, D-25 |
| Q-4.11 | Contabilidad Analítica por Departamentos y Clasificación de Gastos | M14 | F5 | sin_definicion | I-110 | D-25 |
| Q-4.12 | Migración Contable mediante Asiento de Apertura y Efectos Pendientes | M14 | F5 | sin_definicion | I-112 | D-25 |
| Q-4.13 | Digitalización de Gastos de Personal y Viáticos mediante Lector OCR | M14 | F5 | sin_definicion | I-002, I-079 | D-25 |
| Q-4.14 | Control de Cajas Chicas en Efectivo por Sede (Diarios de Caja Barcelona, Madrid y Valencia) | M14 | F5 | sin_definicion | I-110 | D-25 |
| Q-4.15 | Configuración Multimoneda y Plan Contable de Colombia con Facturación Intercompany | M14 | F5 | sin_definicion | I-120 | D-25 |
| Q-4.16 | Facturación Intercompany y Asignación de Costes entre Entidades | M14 | F5 | sin_definicion | I-120 | D-25 |
| Q-4.2 | Adaptación a la Normativa Veri*factu (S.L. y Autónomo) | M14 | F5 | contradictorio | I-120 | D-07, D-25 |
| Q-4.3 | Cobro Multicanal, Pasarela de Pago y Generación de Enlaces de Pago (Links de Tarjeta) | M14 | F5 | sin_definicion | I-093, I-101 | D-25 |
| Q-4.4 | Registro y Gestión Automática de Devoluciones y Facturas de Abono | M14 | F5 | sin_definicion | I-097, I-120 | D-25 |
| Q-4.5 | Conciliación Bancaria Automatizada para Múltiples Cuentas y Bancos | M14 | F5 | sin_definicion | I-110 | D-25 |
| Q-4.6 | Registro y Amortización de Activos Fijos | M14 | F5 | sin_definicion | I-110 | D-25 |
| Q-4.7 | Campo Digital del Total del Acuerdo Ganado y Cálculo de Honorarios | M14 | F5 | contradictorio | I-019, I-020 | D-05, D-25 |
| Q-4.8 | Tratamiento Contable de Suplidos e Ingresos Parciales en Extranjería | M14 | F5 | contradictorio | I-020 | D-16, D-18, D-25 |
| Q-4.9 | Emision de Ficheros Bancarios SEPA (Nacional e Internacional) para Nóminas y Colaboradores | M14 | F5 | sin_definicion | I-120 | D-25 |
| Q-5.1 | Control de Asistencia, Fichajes y Gestión de Horarios Estacionales (Verano / Invierno) | M15 | F5 | complementario | I-109 | — |
| Q-5.2 | Gestión de Vacaciones con Doble Aprobación y Asignación Anual de Días | M15 | F5 | complementario | I-076 | — |
| Q-5.3 | Calendario Unificado de Ausencias y Gestión de Permisos (Retribuidos y No Retribuidos) | M15 | F5 | complementario | I-076 | — |
| Q-5.4 | Exportación de Datos de Plantilla e Informes de Personal a Excel | M15 | F5 | complementario | I-112 | — |
| Q-5.5 | Importación y Carga Masiva de Nóminas en PDF por Empleado | M15 | F5 | complementario | I-002, I-079 | — |
| Q-5.6 | Firma Digital de Documentación de Personal (Contratos, Acuerdos y Certificados) | M15 | F5 | complementario | I-052, I-078 | — |
| Q-5.7 | Módulo de Reclutamiento, Selección y Gestión de Candidatos | M15 | F5 | complementario | I-120 | — |
| Q-5.8 | Evaluaciones de Desempeño y Feedback Bidireccional | M15 | F5 | complementario | I-109 | — |
| Q-5.9 | Gestión de Incidencias Internas y Tickets de Empleados (Helpdesk Interno) | M15 | F5 | complementario | I-089 | — |
| Q-6.1 | Análisis de Viabilidad Previa, Ficha de Preguntas (Word / Formulario) y Filtrado de Casos | M04 | F2 | equivalente | I-001, I-004, I-006, I-045 | D-12 |
| Q-6.10 | Gestión de Fechas de Juicio, Alerta de Aportación de Pruebas (12 Días Hábiles) y Recordatorios por WhatsApp | M09 | F2 | contradictorio | I-070, I-071, I-072, I-073 | D-03 |
| Q-6.11 | Control de Sentencias, Ejecuciones Judiciales y Alertas Programadas a 2 y 9 Meses | M09 | F2 | contradictorio | I-073, I-087 | D-21 |
| Q-6.12 | Control de Decreto de Insolvencia y Alertas Escaladas a 3, 6, 9 y 11 Meses ante el FOGASA | M09 | F2 | contradictorio | I-073, I-087 | D-02 |
| Q-6.13 | Enlace / Portal del Cliente para Carga de Pruebas y Archivos Pesados (Fotos, Audios y Vídeos) | M07 | F2 | equivalente | I-078, I-081, I-082 | — |
| Q-6.14 | Repositorio Estructurado y Envío Seguro de Pruebas a Letrados Sustitutos (Cumplimiento RGPD) | M07 | F2 | equivalente | I-078, I-082, I-083 | — |
| Q-6.15 | Tipificación de Actuaciones por Código de Colores, Subgrupos y Tareas Predeterminadas/Manuales | M09 | F2 | equivalente | I-067, I-076 | — |
| Q-6.16 | Control de Preparación de Juicios con Doble Validación y Filtrado en Agenda (Pendiente vs. Preparado) | M09 | F2 | equivalente | I-070, I-082, I-084 | — |
| Q-6.17 | Historial de Descripciones, Control de Autoría (Audit Trail) y Trazabilidad de Cambios | M00 | F0 | complementario | I-097, I-120 | — |
| Q-6.18 | Integración de Outlook (Plugin) e Historial Unificado de Correos y WhatsApp en el Chatter | M12 | F4 | equivalente | I-097, I-114, I-116 | — |
| Q-6.19 | Coordinación Automatizada entre el Departamento Legal y Facturación/Contabilidad tras Resolución Estimatoria | M14 | F5 | contradictorio | I-019, I-020, I-087 | D-05 |
| Q-6.2 | Alta y Estructura del Expediente (Campos Obligatorios, Secuencia Consecutiva y Selección de Especialidad) | M05 | F2 | equivalente | I-007, I-008, I-010 | — |
| Q-6.20 | Código de Colores de Agendas por Urgencia en Extranjería | M09 | F2 | equivalente | I-073, I-076 | — |
| Q-6.20B | Control de vencimiento de plazos en tareas y ordenacion prioritaria por fecha límite | M09 | F2 | equivalente | I-073, I-076 | — |
| Q-6.21 | Esquema de Pagos Escalados en Extranjería (Pago Inicial y Pago Final) | M14 | F5 | sin_definicion | I-020 | D-16 |
| Q-6.22 | Descarga y Firma de Documentación Específica por Trámite | M07 | F2 | equivalente | I-028, I-078 | — |
| Q-6.23 | Restricción de Edición y Eliminación en Agendas y Tareas Ajenas | M00 | F0 | complementario | I-089, I-120 | — |
| Q-6.3 | Mensaje Automático de Bienvenida por WhatsApp y Solicitud Inicial de Pruebas | M12 | F4 | contradictorio | I-081, I-090, I-091, I-095 | D-10 |
| Q-6.4 | Fases del Expediente e Indicador Visual de Inactividad (Control de Expedientes Estancados) | M05 | F2 | equivalente | I-089, I-092, I-098 | — |
| Q-6.5 | Estado de Preapertura y Requisitos por Trámite en Extranjería | M11 | F4 | complementario | I-080, I-081 | — |
| Q-6.6 | Firma Digital Unificada del Paquete Documental Inicial mediante Un Único Enlace (Multi-document Sign) | M07 | F2 | contradictorio | I-028, I-052, I-078 | D-08, D-22 |
| Q-6.7 | Certificación Legal de Firma Digital (Audit Trail: IP, Sello de Tiempo y Hash) para Validez Procesal | M07 | F2 | contradictorio | I-052, I-078 | D-08 |
| Q-6.8 | Automatización e Integración de Plantillas Editables (Word/PDF) para Papeleta de Conciliación y Demanda | M08 | F3 | equivalente | I-021, I-028, I-033, I-046 | — |
| Q-6.9 | Control y Cálculo Automatizado de Plazos Procesales Pre- Juicio (Burofax, CMAC/Conciliación y Demanda) | M09 | F2 | contradictorio | I-027, I-073 | D-04 |

## Acuerdos 18

| ID | Necesidad | Mód. | Fase | Cobertura | Relaciones | Decisiones |
|---|---|---|---|---|---|---|
| U-01 | Tres fichas diferenciadas | M04 | F2 | complementario | Q-2.9, Q-6.1, I-004 | — |
| U-02 | Carga inteligente de nóminas | M04 | F2 | complementario | I-002, I-079, Q-5.5 | — |
| U-03 | Lenguaje simple para asesores | M04 | F2 | complementario | I-004, Q-6.1 | — |
| U-04 | Orden de ficha | M04 | F2 | complementario | I-004, Q-6.1 | — |
| U-05 | Datos de empadronamiento | M04 | F2 | complementario | I-004 | — |
| U-06 | Períodos con y sin papeles | M04 | F2 | complementario | I-004 | — |
| U-07 | Varios centros de trabajo | M04 | F2 | complementario | I-004 | — |
| U-08 | Hogar: desglose de tareas | M04 | F2 | complementario | I-004 | — |
| U-09 | Jornada real detallada | M04 | F2 | complementario | I-004, I-015 | — |
| U-10 | Preguntas de hechos accesibles | M04 | F2 | complementario | I-004, Q-6.1 | — |
| U-11 | Conciliacion previa y otro letrado | M04 | F2 | complementario | I-004, Q-6.1 | — |
| U-12 | Eliminaciones en formulario | M04 | F2 | complementario | I-004, Q-6.1 | — |
| U-13 | Control de ATC | M13 | F0 | contradictorio | Q-3.8, Q-3.9 | D-13 |
| U-14 | Política de videollamada | M03 | F1 | contradictorio | Q-3.7 | D-11 |
| U-15 | Comunicación al cliente | M12 | F4 | complementario | Q-6.3, I-091 | — |
| U-16 | Control de tareas y motivacion | M09 | F2 | complementario | I-089, Q-6.20B | — |
| U-17 | Restriccion operacional | M00 | F0 | nuevo | — | — |
| U-18 | Atención telematica multisedes | M00 | F0 | complementario | Q-1.1 | — |
