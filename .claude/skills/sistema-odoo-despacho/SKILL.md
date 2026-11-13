---
name: sistema-odoo-despacho
description: Alcance acordado (Project Charter del 08/09/2026, consultora QUBIQ) para el sistema del despacho en Odoo 20: multicompañía, CRM y captación, citas con pago, atención al cliente, facturación y contabilidad, RRHH, expedientes de Laboral y Extranjería, plazos procesales y migración desde MN Program. Úsala siempre que se diseñe, configure, desarrolle, pruebe o valore cualquier parte del sistema del despacho (Odoo, la ficha laboral, la facturación, los expedientes, los plazos, las plantillas Word), o cuando pregunten «qué se acordó», «está en el alcance», «en qué fase va» o «cómo debe funcionar X».
---

# Sistema del despacho en Odoo 20 · Alcance acordado

Fuente: *Project Charter* de 08/09/2026, redactado por la consultora QUBIQ (implantadora de Odoo). Es **lo acordado** para construir el sistema. Todo diseño, desarrollo o prueba debe encajar con él. Si algo choca con el charter, dilo explícitamente en lugar de cambiarlo en silencio.

El detalle de las 77 necesidades (bloques 1 a 6) está en `referencias/necesidades.md`. Léelo cuando trabajes en un área concreta y cita el número de necesidad (p. ej. «Necesidad 6.9»).

## Confidencialidad

- Usa referencias genéricas: **S.L. principal**, **filial de Colombia**, **autónomo del titular**, CLIENTE_01, EXPEDIENTE_01.
- No metas datos personales reales en pruebas, ejemplos ni capturas.
- Las instrucciones de la organización sobre minimización de datos prevalecen sobre esta skill.

## El despacho en una página

- **Actividad:**
  - Derecho Laboral: defensa de trabajadores en despidos y reclamaciones de cantidad.
  - Extranjería: arraigos, residencias, nacionalidad y menores nacidos en España.
- **Entidades (multicompañía en una sola base de datos):**
  1. **S.L. principal**: sede en Barcelona, con delegaciones en Madrid y Valencia.
  2. **Filial de Colombia**: soporte administrativo; crea leads y oportunidades y da asesoría laboral. Trabaja en COP y factura cada mes a la S.L. en EUR.
  3. **Autónomo del titular** (Barcelona): factura a la S.L. El charter dice que tiene 2 empleados; **corregido: tiene 1**.
     **Decisión (13/11/2026, provisional hasta que la confirme la gestoría; `docs/entrega/18_…` AL-06): queda FUERA de
     Odoo.** No es compañía (sin series, Verifactu ni certificado en Odoo); sus pocas facturas a clientes siguen en su
     programa actual hasta que se acaben; sus facturas a la S.L. se registran en la S.L. como facturas de proveedor; su
     empleado no entra en RRHH del despacho. La intercompañía (1.1, 4.16) queda solo entre Colombia y la S.L.
- **Plantilla: 47 personas según el charter, incluido el empleado del autónomo; 46 en Odoo** (el autónomo y su
  empleado quedan fuera; `docs/entrega/18_…` AL-06). El reparto del charter no indica en qué área está ese empleado.

  | Área | Personas |
  |---|---|
  | Laboral | 15 |
  | Extranjería | 10 |
  | Atención al cliente / recepción | 6 |
  | Marketing | 3 |
  | RRHH | 2 |
  | Contabilidad | 2 |
  | Dirección y soporte | 7 |

- **Volumen:**
  - Laboral: unos 150 clientes activos y unas 300 demandas al mes.
  - Extranjería: entre 100 y 200 trámites al mes.
  - Base de datos: más de 100.000 contactos.
- **Modelos de cobro:**
  - **Laboral:** cuota litis del **20 % + IVA** sobre lo obtenido. El 100 % del dinero entra en la cuenta del despacho, que factura el 20 % + IVA y devuelve el 80 % al cliente con un asiento en una cuenta de mediación (Necesidad 4.7).
  - **Extranjería:** precio fijo con **pago inicial** (estudio y recogida de documentación) y **pago final** (antes de la presentación telemática). La preferencia anotada es **una factura global del trámite con varios cobros sobre ella**, por transferencia nacional o internacional y en efectivo. Las tasas oficiales van como **suplidos** (cuentas 554/555), no como ingreso.
  - **Consulta previa obligatoria:** **40 €** en Extranjería y **50 €** en Laboral. Se cobra antes de confirmar la cita (Redsys).
  - **Venta del expediente:** de 390 € a 400 € (Extranjería) u honorarios a éxito (Laboral).
- **Herramientas que se sustituyen:**
  - MN Program (expedientes y agenda judicial).
  - Bookitic (citas web, con fallos en los pagos).
  - Callbell y Excel (WhatsApp y leads).
  - Varios Excel de plazos.
  - La app de fichajes de la gestoría.
- **Migración, «corte limpio»:**
  - Los expedientes antiguos siguen en MN Program hasta archivarse.
  - Desde el día 1 de puesta en marcha, todo lo nuevo se abre en Odoo.
  - Fase 1: contactos, asiento de apertura, efectos pendientes y mandatos SEPA.
  - Fase 2: expedientes activos de MN Program.
  - El catálogo de servicios lo da de alta el propio despacho.
- **Gestoría externa:** tendrá un usuario auditor/contable en Odoo. Hace los modelos fiscales y el Intrastat de servicios.

## Reglas de negocio que no se pueden romper

1. **Campo Origen/Canal obligatorio** en toda iniciativa u oportunidad: Meta Ads/WhatsApp, Web, TikTok Live «Teléfono Rojo», llamada, recepción, redes sociales o secretaría virtual.
2. **Embudo comercial:**
   1. Lead.
   2. Oportunidad con la cita pagada.
   3. Si es viable: presupuesto del expediente.
   4. Al confirmarlo se crea el **proyecto/expediente** desde la plantilla de su rama.
   5. **La cuenta analítica de la cita se hereda** en el presupuesto del expediente (Necesidad 2.7).
   6. Si no es viable: la oportunidad se marca como perdida, con el motivo.
3. **Citas web: filtrado en cascada.** Rama → Modalidad/ubicación (Presencial BCN/MAD/VLC, Llamada o Videollamada) → por día o por asesor → franja fija. La cita **solo se confirma con el pago** hecho.
4. **Numeración de expedientes:** consecutiva y sin saltos, por rama, con el formato `EXP-LAB-2026-001` / `EXP-EXT-2026-001`.
5. **Series de factura:** correlativas, sin saltos y compatibles con **Verifactu**. Por ejemplo, `CIT/2026/00001` para las citas web y `EXP/2026/00001` para los expedientes.
   - **Decisión AL-03 (13/11/2026, persona responsable del proyecto):** Odoo 20 Community **emite las facturas a clientes con Verifactu** (módulo estándar `l10n_es_edi_verifactu`, de Odoo S.A.), por compañía y con el certificado de cada una cargado en Odoo por la persona autorizada (nunca por chat, correo ni repositorio). Odoo calcula el IVA de sus facturas; las recibidas conservan el IVA que figura en ellas.
   - **Regla de diseño:** los módulos propios **no alteran** el registro, el encadenamiento, la numeración ni el envío de Verifactu. `sp_facturacion` solo **prepara** facturas (cuota litis, suplidos, factura global de extranjería) y deja la emisión y el envío al estándar. Motivo (precaución por confirmar con la gestoría o un asesor fiscal): la declaración responsable de Odoo cubre su módulo estándar; si un desarrollo propio tocara esa parte, el despacho podría pasar a considerarse productor del software. Detalle y plan de puesta en marcha: `docs/entrega/19_Contabilidad_y_facturacion_en_Odoo20.md` §1.3 y §3.8.
6. **Plazos procesales en días hábiles** (sin fines de semana ni festivos):
   - **Despido:** caduca a los **20 días hábiles**. Se calculan los límites de la papeleta (CMAC) a 15 y 20 días hábiles desde la fecha fin laboral.
   - **Alertas:** se crean tareas **5 días y 2 días** antes de cada vencimiento.
   - **Juicio:**
     - Aportación de pruebas **12 días hábiles antes** (la ley exige 10; el despacho usa un margen de 12 a 13).
     - WhatsApp al cliente **30 días y 24 h antes**.
     - Mensaje después de la vista.
     - Revisión de la sentencia a los **60 días**.
   - **Sentencia estimatoria:** alertas de ejecución a los **2 meses** y a los **9 meses** (averiguación patrimonial o insolvencia).
   - **Decreto de insolvencia (FOGASA, plazo de 1 año):** alertas a los **90, 180, 270 y 330 días**. La de 330 días, en prioridad alta (roja).
7. **Firma:**
   - Un **único enlace** para todo el paquete inicial: hoja de encargo, RGPD y autorizaciones.
   - El PDF firmado lleva **adjunto su certificado** y se genera en **PDF/A con OCR**, para que lo acepten los juzgados.
   - La papeleta y la demanda **no necesitan una segunda firma**: se anexa la autorización ya firmada.
8. **Plantillas Word:**
   - La papeleta y la demanda se rellenan desde los campos del expediente (unas 100 variables: cliente, NIF, salario diario, convenio, fecha de despido, demandado…).
   - La ficha de viabilidad se exporta a un .docx editable para que el letrado lo revise.
9. **Estructura del expediente** (Odoo Proyectos):
   - **Campos:** Tipo/Especialidad, Cliente, Parte contraria/Demandado, Creador, Letrado asignado (gerente del proyecto), Fecha de alta, relación entre expedientes, y el ID como identificador.
   - **Estados por etapas:** Abierto, En tramitación, Pausado, Cerrado. En Extranjería hay además una **Preapertura**.
   - **Alerta de inactividad:** la tarjeta se pone en rojo tras **15 días** sin cambios.
10. **Tareas:**
    - Llevan Tipología (con color), Subtipología y nombre predeterminado o manual.
    - Colores: **Rojo** para lo urgente o lo que vence hoy, **Verde** para revisión y presentación, **Azul** para aperturas y seguimiento.
    - Las tareas de juicio pasan de *Pendiente* (rojo) a *Preparado* (verde), y solo cuando las pruebas están validadas.
    - Se ordenan por fecha límite (`deadline`).
    - Cada usuario solo puede editar sus propias tareas. Todos los cambios quedan registrados en el historial (chatter).
11. **Documentos del expediente:**
    - Carpetas por plantilla según la tipología, solo de lectura: `01. Pruebas Cliente`, `02. Selección Juicio`, `03. Notificaciones`.
    - El cliente sube sus pruebas por el portal o por un enlace.
    - Las pruebas se comparten con letrados sustitutos mediante un enlace con acceso restringido (cumplimiento RGPD; nada de WeTransfer).
12. **Extranjería: recordatorios automáticos** a partir de las fechas guardadas en el contacto:
    - Renovación de la residencia, 2 o 3 meses antes de que caduque la tarjeta.
    - Nacionalidad, al cumplirse 2 años desde la fecha de residencia inicial.
    - En ambos casos se crea una oportunidad y se envía una plantilla por WhatsApp o correo.
13. **Roles:**
    - **Fase 1:** Dirección, Administrador de Atención al Cliente, Colaborador de Atención al Cliente, RRHH, Marketing y Contabilidad.
    - **Fase 2:** Administrador y Colaborador de Extranjería y de Laboral. Los colaboradores solo ven lo que tienen asignado.
14. **Devoluciones (charter 3.9 y 4.4):**
    - **Decisión AL-14 (13/11/2026, persona responsable del proyecto):** se sigue el circuito de Sistema Propio, no el del charter. Atención al cliente revisa, el letrado informa si hace falta, **Contabilidad aprueba** y después paga. Nunca aprueba quien hizo la solicitud. Ya implementado en `sp_recepcion` (`docs/entrega/18_…` AL-14).
15. **No se puede hacer en Odoo:** la lista negra de WhatsApp (Necesidad 3.4). Los chats privados de redes sociales tampoco se atienden desde Odoo en esta fase.

## Puntos abiertos (anotados en el charter, pendientes de decidir)

- **4.1:** ¿la cuenta analítica va ligada al expediente o al contacto? ¿Cómo se controla qué está pagado y en qué estado? Propuesta anotada, pendiente de que la evalúe Dirección: una factura por el coste total y cobros a medida que avanza el proceso.
- **6.19:** el aviso a Contabilidad después de una sentencia está pendiente de revisar con ellos. En Laboral no es un aviso manual: el dinero entra al despacho y se devuelve el 80 %.
- **6.21:** cómo se avisa del pago final en Extranjería. Se prefiere una factura global con varios cobros.
- **4.1, 6.19 y 6.21** siguen abiertos solo en cuanto al **flujo**. **Quién factura ya está decidido** (AL-03, 13/11/2026): Odoo con Verifactu.
- **1.4:** alojamiento en la nube. QUBIQ presentará un presupuesto y el cliente decide.

## Community o Enterprise: compruébalo antes de prometer nada

**Decisión del 13/11/2026 (persona responsable del proyecto):** se usa **Odoo 20 Community para todo el proyecto**,
sin licencias Enterprise (`docs/entrega/18_Alineacion_con_el_charter.md`, AL-01 y AL-02). Para cada necesidad, este
orden:
1. Estándar de Odoo 20 Community.
2. Módulo de la OCA publicado en 20.0.
3. Desarrollo propio `sp_*` sobre Odoo 20 (incluido portar a la 20.0 un módulo de la OCA de la 19.0, conservando
   autoría y licencia AGPL/LGPL).
4. Externalizar (servicio o proveedor externo integrado con Odoo), solo si no se puede desarrollar, documentando el
   motivo, el proveedor, los datos que salen (RGPD, encargo de tratamiento) y la integración.

Las necesidades del charter que dependían de Enterprise (Citas, Firma, Documentos, Helpdesk, WhatsApp, VoIP,
intercompañía, sincronización bancaria, activos, SEPA, informes y modelos de la AEAT, evaluaciones…) pasan a
desarrollo propio o a externalización. «Pasar a Enterprise» ya no es una alternativa.

El charter da por hecho funciones que **no están en Odoo 20 Community**. Lo he comprobado en el código de la rama 20.0 (`odoo/odoo`):

| En Community 20 | Solo en Enterprise (de pago) o de terceros |
|---|---|
| CRM, Email Marketing, Encuestas, Sitio web, Proyectos, Partes de horas, Asistencias, Ausencias, Gastos, Reclutamiento, Contabilidad básica y facturación, Multicompañía, **Verifactu** (`l10n_es_edi_verifactu`), SII, **Redsys** (`payment_redsys`), plan contable de Colombia (`l10n_co`), sincronización con el calendario de Outlook, plugin de correo, Fidelización y cupones (`loyalty`), Venta con proyecto | **Citas** (Appointments), **Firma** (Sign), **Documentos**, **Helpdesk**, **WhatsApp**, **VoIP**, Marketing social, **Facturación intercompañía automática**, **tipos de cambio automáticos**, **Activos fijos**, **Sincronización bancaria**, Pagos SEPA/ISO 20022, Evaluaciones, Nóminas |

La tabla completa, necesidad por necesidad y con su fase, está en `referencias/community_enterprise.md`.

Si una necesidad depende de una app Enterprise y se está trabajando o probando en Community, avísalo. Propón una alternativa según el orden de arriba: un módulo de la OCA en 20.0, un desarrollo propio `sp_*` o externalizar. No lo des por disponible.

## Relación con este repositorio

La **Super Ficha Laboral** (`super_ficha_laboral.html` y `fuente/`) es el prototipo de lo que piden las necesidades **6.1** (ficha de viabilidad), **6.8** (papeleta y demanda desde los datos del expediente) y **6.9** (plazos en días hábiles). Cuando se pase a Odoo:

- Sus campos son los candidatos a las aproximadamente 100 variables de la plantilla.
- Sus cálculos de plazos deben coincidir con las reglas de arriba.
