# 11 · Versiones y cambios (Changelog)

Sistema Propio · 12/11/2026. Formato inspirado en *Keep a Changelog*. Las versiones siguen los incrementos del plan
(F0.1 … F5.6). Los cambios de base de datos se indican con su migración.

## [DOC-12] · 13/11/2026 — AL-14: devoluciones con el circuito de Sistema Propio
### Cambiado
- **Decisión** (persona responsable del proyecto): las devoluciones siguen el circuito de Sistema Propio. Atención al
  cliente revisa, el letrado informa si hace falta, **Contabilidad aprueba** y después paga. Nunca aprueba quien hizo
  la solicitud. Difiere del charter 3.9 (Atención al cliente pasaba el ticket a «Aprobado para devolución»).
- Sin cambios de código: es lo que ya hace `sp_recepcion` (11 · DOC-10 y DOC-11).
- Documentación: 18 §1 (AL-14 decidido), 19 §3.1 y §6, 08 §10.2, 05 §7 y skill `sistema-odoo-despacho`.

## [DOC-11] · 13/11/2026 — Devoluciones: «Enviar a Contabilidad»
### Añadido
- Botón **Enviar a Contabilidad** (`action_enviar_a_contabilidad`) en las devoluciones en revisión: exige el informe de
  la revisión, cierra la tarea de Atención al cliente y crea la de decidir para Contabilidad. Cubre el hueco anotado
  en DOC-10 (sin letrado, Contabilidad no recibía tarea). Prueba nueva: 27 pruebas automáticas, 0 fallos.

## [DOC-10] · 13/11/2026 — sp_recepcion: sedes por persona, refuerzos en BD y devoluciones
Segunda iteración de `odoo/addons/sp_recepcion` (versión **20.0.1.1.0**). Corrige las dos diferencias con Sistema
Propio anotadas en DOC-8 y añade las **devoluciones** (charter 3.9 y 4.4; referencia Sistema Propio F5.0,
REFUND_FLOW). Todo con datos ficticios.
### Añadido
- **Sedes por persona:** campo `sp_sede_ids` («Sedes en las que trabaja») en el usuario (`models/res_users.py`). La
  sede habitual (`sp_sede_id`) se añade sola a la lista al crear o modificar el usuario.
- **Devoluciones** (`models/devolucion.py`, modelo `sp.devolucion`, con historial y tareas):
  - Número `DEV/año/nnnn` (`data/sp_devolucion_data.xml`, secuencia `no_gap`). Motivo obligatorio (≥ 10 caracteres).
    Importe > 0 (CHECK en BD).
  - Estados: registrada → en revisión → [escalada al letrado → informe → en revisión] → aprobada o rechazada →
    pagada. Una rechazada se reabre con motivo. El estado solo cambia con los botones y nada se borra.
  - **Separación de funciones:** aprueba o rechaza solo Contabilidad (grupo responsable), **nunca quien la
    solicitó** (en Python y con CHECK `decidido_por <> solicitado_por` en BD). Rechazar y reabrir exigen motivo.
  - **Pago** (`action_pagar`, solo Contabilidad), desde la caja de la sede o un banco: con factura cobrada por
    completo e importe igual al total → rectificativa automática (método estándar de Odoo) y pago conciliado con
    ella; devolución parcial → hay que vincular la rectificativa hecha a mano desde la factura; factura no cobrada del
    todo → no se paga; sin factura → pago de salida al cliente. Las devoluciones por TPV/Redsys se hacen fuera de
    Odoo (charter 4.4) y aquí se registra su salida por el banco.
  - **Tareas:** cada paso cierra las del paso anterior (quedan como hechas en el historial) y crea las del
    siguiente: revisión → Atención al cliente (si no hay nadie, Contabilidad); escalado → letrado; informe del
    letrado → Contabilidad. Máximo 5 personas por tarea.
  - Vistas `views/devolucion_views.xml` (lista, formulario con pestañas Revisión, Informe del letrado y Decisión y
    pago; filtros Abiertas, Por decidir, Escaladas, Aprobadas sin pagar) y menú *Recepción → Devoluciones*
    (`views/menus.xml`).
- **Grupos nuevos** (`security/sp_recepcion_security.xml`): «Atención al cliente · revisar devoluciones» (implica
  Facturación) y «Letrado · informe de devoluciones» (implica Usuario interno). El grupo responsable implica también
  el de revisión. Detalle en 08 §10.
- **Refuerzos en la base de datos** en `sp.cierre.caja` (`models/cierre_caja.py`): restricción CHECK «quien valida o
  rechaza ≠ quien contó» y trigger PostgreSQL `sp_cierre_caja_proteger` (creado en `init()`) que impide modificar un
  cierre validado o rechazado y borrar uno contado o validado.
- **Apuntes de caja de días validados** (`models/account_move.py`): un apunte publicado en una caja con fecha igual o
  anterior a un cierre validado no vuelve a borrador ni se cancela. Sí se pueden registrar movimientos nuevos: cuentan
  en el siguiente cierre, porque el saldo es acumulado.
- Pruebas `tests/test_sedes_y_protecciones.py` (6) y `tests/test_devoluciones.py` (8); datos comunes en
  `tests/common.py` (dos sedes, Recepción de cada sede, dos de Contabilidad, Atención al cliente y letrado).
- `odoo/configuracion/recepcion.py`: usuarios de demostración `atc.demo` y `letrado.demo`.
- `odoo/pruebas/prueba_devoluciones.py`: escenario completo de una devolución con datos ficticios.
- Captura `documentacion/odoo20_recepcion/5_devolucion.png`.
### Cambiado
- **Cada persona de Recepción solo ve y registra cobros y cierres de sus sedes** (`security/ir.access.csv`): regla
  sin grupo `sp_payment_sede_rule` sobre `account.payment` (solo afecta a quien es Recepción y no responsable; los
  pagos sin sede siguen visibles) y permiso de Recepción en `sp.cierre.caja` limitado a sus sedes. Contabilidad los
  ve todos.
- **Numeración sin huecos:** las secuencias de justificantes (`models/sede.py`) y de devoluciones usan
  `implementation = no_gap`. En la base de pruebas actual la secuencia de devoluciones ya existía (dato `noupdate`) y
  conserva huecos de las pruebas (la captura muestra `DEV/2026/0037`); en una instalación nueva no (12 · INC-75).
- `odoo/LEEME.md`: usuarios de demostración nuevos y escenario de devoluciones.
- Documentación: 19 §3.1, §5 y §6; 08 §10; 15 §8b; 05 §7; 18 §1 (AL-14) y §3; 00 · Índice; 12 §4d.
### Corregido
- Las dos diferencias con Sistema Propio pendientes de **DOC-8** quedan **resueltas**: 1) cada persona de Recepción
  solo ve la caja de su sede; 2) la regla «otra persona valida» y la inmutabilidad del cierre tienen también
  restricción en la base de datos.
- Las tareas de aviso de devoluciones ya no se acumulan (12 · INC-74).
### Comprobado
- **26 pruebas automáticas, 0 fallos** (12 de recepción, 6 de sedes y protecciones, 8 de devoluciones), según la
  ejecución de quien hizo el trabajo. El número de pruebas coincide con el código de `tests/`.
- **Escenario** `prueba_devoluciones.py`: `recepcion.bcn` solicita 50 € para CLIENTE_03, `atc.demo` revisa y escala,
  `letrado.demo` informa, `contabilidad.1` aprueba y paga desde Caja Barcelona. Resultado: devolución pagada.
- Revisado en el navegador, sin errores.
### Pendiente
- Informe diario y semanal de Recepción por sede en PDF.
- Vínculo con expedientes (y la regla «cobro sin expediente solo si es consulta», charter 2.6). Cuando exista, el
  informe jurídico debería limitarse a quien tiene acceso completo al expediente, como en Sistema Propio (08 §10).
- **18 · AL-14** (abierto): el charter deja la aprobación de la devolución en Atención al cliente; el módulo sigue a
  Sistema Propio (aprueba Contabilidad).
- Comprobar con Verifactu (12 · ABI-04) la rectificativa que crea `action_pagar`.

## [DOC-9] · 13/11/2026 — Plantilla en Odoo: 46 personas
### Cambiado
- **18 · AL-06:** respuesta de la persona responsable del proyecto: las **47 personas** del charter incluyen al
  empleado del autónomo del titular. Como el autónomo y su empleado quedan fuera de Odoo, la plantilla que se
  gestiona en Odoo (permisos, usuarios y RRHH del despacho) es de **46 personas**.
- **01 §2:** nota con la cifra de 46 personas en Odoo. Skill `sistema-odoo-despacho`: «47 según el charter, 46 en
  Odoo». `referencias/necesidades.md` no cambia (es el texto del charter).
- **Pendiente:** el reparto por departamentos del charter no indica en qué departamento está ese empleado; queda por
  saber cuál, si hace falta.

## [DOC-8] · 13/11/2026 — Odoo 20: módulo sp_recepcion (Recepción y cajas)
Primer módulo propio en Odoo 20 Community: **Recepción y cajas** (19 §6 paso 2; 19 §3.1; charter 4.3 y 4.14). Todo
con datos ficticios. Referencia funcional: Sistema Propio F5.2.
### Añadido
- **`odoo/addons/sp_recepcion/`** (versión 20.0.1.0.0, LGPL-3, depende solo de `account`):
  - **Sedes** (`sp.sede`): código, caja (diario de efectivo) y numeración de justificantes por sede y año
    (`REC-BCN-2026-000001`). Campo `sp_sede_id` («Sede habitual») en el usuario.
  - **Cobro de recepción** = pago de cliente de Odoo (`account.payment`) con sede (`sp_sede_id`) y tipo (`sp_tipo`:
    consulta, provisión de fondos, servicio, otro). Al «Confirmar» de Odoo: comprueba tipo y cliente; busca posibles
    repetidos (mismo cliente, importe y diario en ±2 días, o la misma referencia en 90 días); si los hay, exige un
    motivo de al menos 10 caracteres (`sp_motivo_duplicado`) y crea una actividad para Contabilidad. Asigna el número
    de justificante y genera el PDF **una sola vez** (adjunto guardado y reutilizado). El justificante dice «NO ES
    UNA FACTURA».
  - **Confirmar** (`action_sp_confirmar`) y **anular** (asistente `sp.anular.cobro`): solo el grupo responsable;
    anular exige motivo de al menos 10 caracteres, no se permite si hay un cierre validado de esa caja en la fecha
    del cobro o posterior, conserva el número y nunca borra. «Restablecer a borrador» y «Cancelar» de Odoo no sirven
    para cobros con justificante, y no se pueden borrar.
  - **Cierre de caja** (`sp.cierre.caja`): Recepción registra el recuento; el sistema calcula el saldo con los
    apuntes publicados de la cuenta de la caja hasta el final del día; la diferencia exige notas; valida o rechaza
    un responsable **distinto** de quien contó; al validar con diferencia crea el asiento de ajuste contra las
    cuentas de diferencias de la caja; no se valida si hubo movimientos tras el recuento; un cierre por sede y día
    (salvo rechazados); validado o rechazado no se modifica.
  - **Grupos:** «Recepción» (implica Facturación) y «Responsable de caja y cobros (Contabilidad)» (implica
    Recepción). Permisos en `security/ir.access.csv` con reglas multicompañía (08 §10).
  - Menú Contabilidad → Recepción (Cobros, Cierres de caja, Sedes) e informe `report/justificante.xml`.
  - 12 pruebas automáticas en `tests/test_recepcion.py`.
- `odoo/configuracion/recepcion.py`: crea las sedes Barcelona (BCN), Madrid (MAD) y Valencia (VLC) sobre las cajas
  de la S.L. y **usuarios de demostración** (`recepcion.bcn`, `recepcion.mad`, `recepcion.vlc`, `contabilidad.1`,
  `contabilidad.2`). Solo para la base de pruebas.
- `odoo/pruebas/prueba_recepcion.py`: escenario completo con datos ficticios.
- `herramientas/odoo_dev.sh`: levanta Docker, Odoo 20 y la base `sp_contable` en Linux (entorno en la nube) y,
  opcionalmente, instala o actualiza módulos (`bash herramientas/odoo_dev.sh sp_recepcion`).
- Capturas en `documentacion/odoo20_recepcion/` (`1_cobros.png`, `2_cobro_con_justificante.png`,
  `3_cierre_caja.png`, `4_justificante.png`).
### Cambiado
- `odoo/configuracion/base_contable.py`: los métodos de pago de las cajas usan la **cuenta de la caja (570…)** como
  cuenta de cobros y pagos, para que el saldo sea real en cuanto se registra un cobro (12 · INC-68).
- `odoo/LEEME.md`: apartado «Recepción y cajas».
- Documentación: 19 §3.1, §5 y §6 paso 2; 05 §7; 08 §10; 15 §8b; 09 Anexo C; 18 §3; 00 · Índice; 12 §4d.
### Comprobado
- **12 pruebas automáticas** (`TransactionCase` sobre `AccountTestInvoicingCommon`): 0 fallos.
- **Escenario** `prueba_recepcion.py` con usuarios ficticios: `recepcion.bcn` cobra 50 € y 200 €; un tercer cobro
  parecido avisa de repetido y se registra con motivo; `contabilidad.1` confirma; recuento de 295 € frente a 300 €
  registrados (diferencia −5 €); `contabilidad.2` valida y se crea el ajuste `CBAR/2026/00001`. Resultado: «todo
  correcto».
- Revisado en el navegador, sin errores.
### Pendiente (siguiente iteración)
- Devoluciones con su flujo (registrada → en revisión → escalada al letrado → aprobada o rechazada → pagada).
- Informe diario y semanal de Recepción por sede en PDF.
- Vínculo con expedientes (aún no hay módulo de expedientes): por eso no se aplica todavía la regla «cobro sin
  expediente solo si es consulta» (charter 2.6).
- Restringir a cada persona de Recepción a la caja de **su** sede (en Sistema Propio, Recepción de Madrid no ve la
  caja de Barcelona; 08 §Recepción F5.2). Hoy solo hay reglas por compañía (comprobado en `ir.access.csv`).
  **Resuelto en DOC-10.**
- (Diferencia anotada en 08 §10) La regla «quien valida ≠ quien cuenta» solo estaba en Python, sin restricción en la
  base de datos. **Resuelto en DOC-10** (CHECK y trigger). Las devoluciones también se hicieron en DOC-10.

## [DOC-7] · 13/11/2026 — AL-06: el autónomo queda fuera de Odoo
### Cambiado
- **18 · AL-06:** «Decidido provisionalmente · 13/11/2026 · persona responsable del proyecto (respuestas del abogado);
  confirmar con la gestoría (cuestionario, bloque 9)». Respuestas recibidas: el autónomo factura sobre todo a la S.L.
  y, de forma residual, a algún cliente (terminará pronto); su contabilidad la lleva la misma gestoría, de momento;
  su personal se gestiona aparte y tiene **1 empleado** (el charter dice 2); sus cuentas bancarias son propias y la
  contabilidad del despacho no tiene acceso.
- **Consecuencias en el sistema:** el autónomo **no es compañía en Odoo** (sin series, sin Verifactu ni certificado
  propios); sus facturas a clientes siguen en su programa actual hasta que se acaben; sus facturas a la S.L. se
  registran en la S.L. como **facturas de proveedor**; la intercompañía queda solo entre la filial de Colombia y la
  S.L.; su empleado no entra en RRHH del despacho en Odoo.
- `odoo/configuracion/base_contable.py`: la entrada del autónomo queda con `"incluir": False` (se puede reactivar).
- **18 · AL-03:** Verifactu solo en la S.L. **19 §1.2, §1.3, §3.4, §3.8 y §6:** Verifactu solo en la S.L.;
  intercompañía solo Colombia → S.L.; facturas del autónomo como facturas de proveedor. **01 §6:** nota de que el
  autónomo queda fuera de Odoo. `odoo/LEEME.md`: tabla con la S.L. y Colombia. Skill `sistema-odoo-despacho`: nota
  en entidades (decisión y 1 empleado).
### Comprobado
- Montada la base de cero con Docker: el script crea solo «Despacho S.L. (demo)» y «Filial Colombia (demo)», y
  `odoo/pruebas/prueba_base_contable.py` da «todo correcto».

## [DOC-6] · 13/11/2026 — Cuestionario para la gestoría (T-40 y AL-06)
### Añadido
- `documentacion/cuestionarios/Cuestionario_gestoria_plan_de_cuentas.docx`: Word de 6 páginas para que la persona
  responsable lo envíe a la gestoría. **33 preguntas en 11 bloques:** plan contable y dígitos; clientes (430 única o
  por cliente), proveedores (400/410) y retenciones; cuentas propias (suplidos, fondos de clientes en mediación de la
  cuota litis, ingresos 705, factura global con cobros parciales); bancos 572 y cajas 570 por sede; cuentas de
  gastos; impuestos y modelos (303, 390, 111/190, 115/180, 347, 349), criterio de caja o prorrata, Verifactu y series
  CIT/EXP/RCIT/REXP; forma de trabajo con Odoo (usuario propio o exportación, programa, frecuencia); puesta en marcha
  (fecha de inicio, asiento de apertura, efectos pendientes, sesión de validación); autónomo del titular (AL-06);
  filial de Colombia (contador, tipo de cambio de sus facturas a la S.L.); otros comentarios.
- Cada pregunta muestra lo configurado ahora («Ahora en Odoo», 11 · DOC-5) y casillas para responder. El documento
  pide expresamente **no enviar datos personales ni saldos**.
### Cambiado
- **18 · AL-06 y AL-13:** nota de que el cuestionario está preparado; siguen abiertos. **19 §6 paso 1:** referencia
  al cuestionario. **00 · Índice:** nueva línea `documentacion/cuestionarios/`.

## [DOC-5] · 13/11/2026 — Odoo 20: base contable montada y probada
Primer paso de la implantación en Odoo 20 Community: la **base contable** (19 §6, paso 1). Todo con datos ficticios.
### Añadido
- **Carpeta `odoo/`** (ver `odoo/LEEME.md`):
  - `odoo/docker-compose.yml`: Odoo 20 + PostgreSQL 16, con el puerto 8069 abierto **solo en el propio ordenador**
    (`127.0.0.1`) y las carpetas `addons/`, `configuracion/` y `pruebas/` montadas en el contenedor.
  - `odoo/configuracion/base_contable.py`: script para `odoo shell` que monta la base contable. Es **idempotente**
    (busca antes de crear; se puede repetir sin duplicar).
  - `odoo/pruebas/prueba_base_contable.py`: prueba con datos ficticios (CLIENTE_01, EMPRESA_01 S.L., EXPEDIENTE_01).
  - `odoo/addons/`: carpeta vacía para los módulos propios `sp_*` (19 §5).
  - `odoo/LEEME.md`: cómo montarlo en Windows con Docker Desktop, paso a paso.
- **Capturas** con datos ficticios en `documentacion/odoo20_base_contable/` (`1_facturas.png`,
  `2_factura_expediente_suplido.png`, `3_diarios.png`).
- **Qué monta el script:**

| Elemento | Despacho S.L. (demo) | Autónomo del titular (demo) | Filial Colombia (demo) |
|---|---|---|---|
| Plan contable y moneda | `es_pymes` · EUR | `es_pymes` · EUR (AL-06 abierto) | `co` · COP |
| Diarios de venta | CIT (citas web) y EXP (expedientes); rectificativas en serie propia (RCIT, REXP) | Igual | — |
| Cuenta de ingresos por defecto | 705000 «Prestaciones de servicios» (diarios y `income_account_id` de la compañía, en lugar de 700000 mercaderías) | Igual | — |
| Diario genérico INV | Archivado (solo se factura con CIT y EXP) | Igual | — |
| Bancos | Banco A · Laboral (BCA), Banco B · Extranjería (BCB), Banco C · Tesorería (BCC) | Banco A (BCA) | Los del plan |
| Cajas | CBAR, CMAD, CVAL | CBAR | — |
| Cuentas propias (**provisionales**, T-40) | 555001 «Suplidos por cuenta de clientes» y 555002 «Fondos de clientes en mediación (80 % cuota litis)» | Igual | — |
| Verifactu | Activado en **entorno de pruebas** | Igual | — |

Comunes a todo el grupo: analítica con los planes **Actividad** (Laboral, Extranjería, Compartida) y **Sede**
(Barcelona, Madrid, Valencia, Colombia); productos de ejemplo (consultas de 50 € y 40 € con IVA 21 % S, honorarios
de expediente, honorarios cuota litis y suplido sin IVA a la 555001).

- **12 §4c (nuevo):** INC-60…INC-64; **12 §5:** ABI-04 (Verifactu sin probar contra la AEAT). **09 · Anexo C:** remite a `odoo/LEEME.md`. **00 · Índice:** nueva sección «Implantación en Odoo 20». **18 §3:** fila
  de la carpeta `odoo/`.
### Cambiado
- **19 §6:** paso 1 (base contable) marcado como hecho, con enlace a `odoo/LEEME.md`; quedan pendientes los grupos y
  permisos. **19 §3.8:** paso a en curso (entorno de pruebas configurado; falta la prueba con conexión a la AEAT) y
  paso b hecho en la base de prueba (se valida en el paso d).
- **18 · AL-06 y AL-13:** siguen abiertos; se anota cómo los refleja la base contable de prueba.
### Comprobado
- 13/11/2026, **ejecutado de cero con los pasos de `odoo/LEEME.md` en Docker**, resultado «todo correcto»:

| Prueba | Resultado |
|---|---|
| Cita web (serie CIT) | CIT/2026/00001: consulta 40 € + IVA = 48,40 € |
| Expediente con suplido (serie EXP) | EXP/2026/00001: 400 € + IVA 84 € + suplido 38,28 € = 522,28 €. Suplido a 555001, honorarios a 705000 |
| Cobro parcial | 200 € por Banco B → «pagado parcialmente», pendiente 322,28 € |
| Empresa con retención | EXP/2026/00002: 1.200 € + IVA 252 € − IRPF 15 % 180 € = 1.272 € |
| Rectificativa | RCIT/2026/00001 (serie propia) |

**Pendiente (no comprobado):**
- **Verifactu:** con el certificado de **pruebas** público de la AEAT que trae Odoo (entidad ficticia «ENTIDAD
  PRUEBAS», solo para el entorno de pruebas) Odoo calcula la huella, pero el documento no se completa porque el
  entorno en la nube no resuelve `prewww2.aeat.es` (12 · INC-64). La rectificativa no genera documento porque la factura
  original no lo tiene (consecuencia del mismo problema). **Hay que repetir la prueba en un equipo con Internet** (p.
  ej. el PC del despacho con Docker).
- Cuentas 555001 y 555002: provisionales hasta cerrar el plan de cuentas con la gestoría (T-40, 18 · AL-13).
- Compañía del autónomo: de prueba; se quita si AL-06 se decide en contra.
- Grupos y permisos de la base contable (parte del paso 1 de 19 §6): no se han tocado en este trabajo.

## [DOC-4] · 13/11/2026 — Decisión: Odoo emite las facturas con Verifactu
Decisión del proyecto, tomada por la persona responsable del proyecto. No cambia el código de Sistema Propio ni hay
incidencias asociadas (12 sin cambios).
### Cambiado
- **18 · AL-03** (facturación a clientes): **Decidido · 13/11/2026**. Odoo 20 Community emite las facturas a clientes
  con Verifactu (`l10n_es_edi_verifactu`). Incluye la precaución sobre los módulos propios.
- **01 §4 regla 11:** se mantiene para Sistema Propio; se anota que en Odoo aplica la decisión AL-03 (Odoo calcula el
  IVA de sus facturas; las recibidas, el que figura en ellas). **01 §3:** nota en la fila «Facturación a clientes».
- **05 §13:** fila «IVA, honorarios, facturación» con la decisión.
- **19 §1.3** reescrito («decidido»), con lo comprobado del módulo y la precaución. **19 §3.7** deja de ser
  condicional. **19 §3.8 (nuevo):** plan de puesta en marcha (pruebas en el entorno de la AEAT con datos ficticios,
  diarios y series CIT y EXP, certificado de cada compañía cargado por la persona autorizada, validación con la
  gestoría, paso a producción con fecha anotada en 11 y 18). **19 §4 regla 5, §5 (`sp_facturacion`) y §6 paso 7**
  actualizados.
- **02 §8:** fila «Facturación a clientes» con el módulo estándar y la decisión.
- Skills `sistema-odoo-despacho` (regla 5 de series y puntos abiertos 4.1, 6.19, 6.21) y `documentacion-proyecto`
  (lista de reglas): decisión AL-03 y regla de diseño.
### Comprobado
- 13/11/2026, en el código de Odoo 20.0 Community (`addons/l10n_es_edi_verifactu`): módulo de Odoo S.A., LGPL-3;
  depende de `l10n_es` y `certificate`; se activa por compañía («Enable Veri*Factu») con un certificado electrónico
  por compañía (`certificate.certificate`); entorno de pruebas de la AEAT activado por defecto y entorno de
  producción; envío por tarea programada, encadenamiento de registros, QR en el PDF, panel en el diario y asistente de
  renumeración; enlace «Access Declaración Responsable» en los ajustes (la emite Odoo S.A. para su módulo estándar).

**Pendiente de confirmar (no comprobado):**
- Con la gestoría o un asesor fiscal: que los módulos propios que solo preparan facturas no alteran la cobertura de la
  declaración responsable de Odoo (19 §1.3).
- AL-06 sigue abierto: si el autónomo es una compañía aparte (Verifactu se activa por compañía).

## [DOC-3] · 13/11/2026 — Decisión: Odoo 20 Community para todo el proyecto
Decisión del proyecto, tomada por la persona responsable del proyecto en la sesión de trabajo. No cambia el código de
Sistema Propio.
### Cambiado
- **18 · AL-01** (edición): **Decidido · 13/11/2026**. Odoo Community para todo el proyecto, sin licencias
  Enterprise.
- **18 · AL-02** (versión): **Decidido · 13/11/2026**. Odoo **20.0 Community**. Los módulos de la OCA que aún no están
  en 20.0 se cubren con desarrollo propio `sp_*`; una vía es portar los de la 19.0 (AGPL/LGPL, conservando autoría y
  licencia).
- **18 §2 (nuevo) · Criterio para cada necesidad:** (1) estándar de Odoo 20 Community → (2) OCA publicada en 20.0 →
  (3) desarrollo propio `sp_*` (incluido portar un módulo de la OCA) → (4) externalizar solo si no se puede
  desarrollar, documentando motivo, proveedor, datos que salen (RGPD, encargo de tratamiento) e integración. Los
  apartados siguientes se renumeran (§3 piezas, §4 cómo se cierra un punto).
- **18 · AL-06, AL-09, AL-10 y AL-12:** siguen abiertos; se anota que la opción Enterprise queda descartada y que la
  alternativa es desarrollo propio o externalizar.
- **19 §1.1:** la conclusión pasa de «esperar, migrar o programar» a desarrollar (o portar desde la OCA 19.0) lo que
  falte. **19 §5:** nueva columna con los módulos de la OCA que sustituye cada `sp_*`.
- **02 §8, 04 §2 y 01 §7:** la versión destino es Odoo **20.0** Community (ver 18 · AL-02).
- Skill `sistema-odoo-despacho`, sección «Community o Enterprise»: añadida la decisión y el criterio de 4 pasos.
- 00 · Índice: la descripción del documento 18 menciona las decisiones tomadas y el criterio de §2.

## [DOC-2] · 13/11/2026 — Versión de referencia en el repositorio y contabilidad en Odoo 20
Trabajo de documentación y evaluación; no cambia el código de Sistema Propio.
### Añadido
- **Versión de referencia F5.6c** de Sistema Propio en `referencia/SistemaPropio/`: código (`apps/api` con FastAPI,
  `apps/web` con Next.js, `apps/extension-mercurio`) y documentación interna (`docs/producto` con `decisiones.md`,
  `docs/adr` ADR-0001…0010, `docs/seguridad`, `docs/operacion`, `docs/fuentes` con la matriz de 208 requisitos y
  `docs/pruebas` con evidencias y capturas). Es una copia congelada.
- `herramientas/arrancar_sistema_propio.sh`: arranca la referencia en Linux sin Docker (PostgreSQL 16, Python,
  Node 22) con datos ficticios; API en el puerto 8000 y web en el 3000. Ver 09 §Anexo B.
- **19 · Contabilidad y facturación en Odoo 20**: correspondencia función por función de economía, recepción,
  gastos, banco, proveedores, tesorería, cierre, rutina e informes con Odoo 20 Community, OCA y módulos `sp_*`.
- `herramientas/paquete_documentacion.py`: crea en `documentacion/entregas/` un zip (Markdown, Word y
  `openapi.json`) y un solo Word con todos los documentos.
- Agente `.claude/agents/documentador.md`: registra cada trabajo en la documentación y prepara los paquetes de entrega.
### Cambiado
- 00 · Índice: fila del documento 19; las rutas del material de referencia apuntan ahora a `referencia/SistemaPropio/`.
- 18 · AL-02: añadida la disponibilidad de los módulos contables de la OCA por versión (sin decidir).
- Skill `documentacion-proyecto`: mapa con 19 y `referencia/SistemaPropio/`; menciona el agente y el paquete.
### Comprobado
- Antes de incorporarla, la referencia no contiene claves (solo `.env.example` con valores vacíos) ni datos
  personales reales (solo ficticios: dominios `.invalid`, NIE de ejemplo). Los documentos 00–17 que traía son
  idénticos a los de `docs/entrega/`.
- La referencia arranca en el entorno en la nube sin Docker: acceso como `contabilidad.demo` y pantalla Contabilidad
  correctos. El script se probó de principio a fin.
- 13/11/2026, en GitHub: los módulos contables de la OCA (extractos, Norma 43, conciliación, remesas SEPA, modelos de
  la AEAT, SII, informes, activos, `auditlog`) **no** están publicados en la rama 20.0; sí en 19.0 (salvo
  `base_tier_validation`) y en 18.0. En el código de Odoo 20 Community no hay pantalla de conciliación bancaria ni
  importación de extractos. Detalle en 18 (AL-02) y 19 §1.

## [DOC-1] · 13/11/2026 — Documentación en el repositorio y evaluación de Odoo 20
Trabajo de documentación y evaluación; no cambia el código de Sistema Propio.
### Añadido
- Paquete de documentación F5.6 en `docs/entrega/` (Markdown como fuente, Word en `docs/entrega/word/`,
  `openapi.json`). Los Word se regeneran con `python3 herramientas/docs_a_word.py`.
- **18 · Alineación con el charter de QUBIQ**: 13 diferencias abiertas (AL-01…AL-13) entre esta documentación y el
  *Project Charter* del 08/09/2026.
- Skill `sistema-odoo-despacho` con el resumen del charter (77 necesidades, reglas, plazos y puntos abiertos).
- `documentacion/Odoo 20 - Community vs Enterprise por fase.xlsx`: cada necesidad con su fase y su disponibilidad,
  más una hoja de Contabilidad y facturación.
- Prueba de **Odoo 20.0 Community** con Facturación y la localización española (plan de pymes, IVA 21 %, retención
  de IRPF 15 %, series de factura), con datos ficticios. Capturas en `documentacion/odoo20_facturacion_demo/`.
- Guía de instalación de Docker Desktop y de Odoo 20 en Windows para pruebas locales (ver 09 §Anexo).
### Comprobado
- En Odoo 20.0 Community **sí** existen Verifactu (`l10n_es_edi_verifactu`), SII, Redsys (`payment_redsys`), el
  plan contable de Colombia (`l10n_co`), CRM, Proyectos, RRHH básico y la sincronización con el calendario de Outlook.
- **No** existen (son Enterprise): Citas, Firma, Documentos, Helpdesk, WhatsApp, VoIP, intercompañía automática,
  tipos de cambio automáticos, activos, sincronización bancaria, SEPA, informes contables y modelos de la AEAT.

## [F5.6b] · 12/11/2026 — Arreglos de la puesta en marcha real en Windows
### Corregido
- `INICIAR_REAL.bat`: claves generadas con `ops/crear_env_real.ps1`, con un contenedor `alpine` como respaldo. Antes,
  una función de PowerShell en línea dejaba secretos vacíos.
- Detecta un `.env.real` incompleto y lo rehace si aún no hay base de datos real.
- Pide la primera administración siempre que no existe la base real.
- La validación de `.env.real` usa `findstr /b` y `/x` en lugar de expresiones regulares largas, que fallan en Windows.

## [F5.6] · 09/11/2026 — Puesta en marcha con datos reales
### Añadido
- Instalación real separada (`-p sistemapropio_real`, `.env.real`, `copias_real`), con `INICIAR_REAL`, `DETENER_REAL`
  y `COPIA_SEGURIDAD_REAL`.
- `primer_admin --sedes`: crea la entidad, sus sedes y los departamentos.
- Alta de cuentas bancarias con IBAN completo (cifrado).
- Importación de **varios extractos a la vez**, repartidos por los últimos dígitos del IBAN.
- Registro de varias facturas a la vez, con lectura automática y alta rápida del proveedor.
- `OWN_TAX_IDS` (CIF propio).
### Cambiado
- La semilla ficticia solo corre con `APP_ENV=development`.
- La interfaz indica «versión F5.6 (demostración)» fuera de producción.

## [F5.4c – F5.4d] · 09/11/2026 — Extractos en Excel y lectura de facturas v2
### Añadido
- Extractos `.xlsx`, `.xls` y «.xls» en HTML, con cabecera tras filas de título y columnas Importe o Cargo/Abono.
- **Comprobar sin importar**: no guarda nada.
- Lectura de facturas recibidas v2: etiquetas, fechas en letra, NIF/CIF con puntos, cuadre por aritmética, OCR a
  300 ppp y descarte del CIF propio.

## [F5.4b] · 09/11/2026 — Rutina de Contabilidad e informes · migración `0012`
### Añadido
- Rutina diaria, semanal, quincenal y mensual, con pasos comprobados por el sistema, responsables y tareas en la Agenda.
- Informes semanal, quincenal y mensual inmutables, en PDF y CSV, con aviso por correo sin cifras.
- Tablas `accounting_routine_owner`, `accounting_routine_item` y `accounting_report`, con los triggers de protección.

## [F5.4] · 09/11/2026 — Contabilidad · migración `0011`
### Añadido
- Proveedores y facturas recibidas (check base + IVA − retención = total).
- Tesorería con remesas de **doble firma** y fichero SEPA pain.001.
- Cierre del mes con revisiones y aprobación inmutable.

## [F5.2 + F5.3] · 08/11/2026 — Recepción y RRHH · migraciones `0009`, `0010`
### Añadido
- Recepción: cobros (también de consultas sin expediente), justificante no fiscal inmutable, cobros repetidos con
  explicación, cierre de caja validado por otra persona e informe.
- RRHH: ficha única, carpeta cifrada, lectura de nóminas sin cálculo, ausencias, avisos y salario protegido.
- Los pendientes de los agentes se muestran dentro de cada departamento.

## [F5.1] · 08/11/2026 — Agentes, banco y conciliación · migración `0008`
### Añadido
- Motor de agentes con bandeja de propuestas.
- Cuentas e importación de extractos (Norma 43, CAMT.053, CSV).
- Conciliación propuesta y explicada.
- Mensajes automáticos por el portal con plantillas versionadas.

## [F2.3] · 06/11/2026 — Portal del cliente · migración `0007`
### Añadido
- Portal propio con código por correo, conversaciones por expediente, adjuntos, avisos urgentes con plantilla y
  textos cifrados. Sin WhatsApp (T-31).

## [F4.1 – F4.3] · 05/11/2026 — Extranjería · migraciones `0005`, `0006`
### Añadido
- Expediente de extranjería con el catálogo versionado de trámites.
- Documentos cifrados.
- Lectura de pasaporte (MRZ), contrato, padrón, TIE y tasa.
- Ficha EX (modelos oficiales) y **extensión de Chrome** que rellena Mercurio sin presentar (versión 0.2, con los
  identificadores reales de Mercurio).
- Revisión de la lectura por expediente, con un informe sin datos.
### Corregido
- Tras la prueba real: padrón en tabla, pasaporte girado, duplicados, «Volver a leer» y diagnóstico sin datos.

## [F5.0] · 03/11/2026 — Economía no fiscal y gastos · migración `0004`
### Añadido
- Cobros, devoluciones con doble rol y caja.
- Gastos con el justificante leído en el servidor (OCR local).

## [F1.2 + F2.1 + F2.2] · 02/11/2026 — CRM, expedientes, tareas y agenda · migración `0002`
## [F0.2] · 02/11/2026 — Acceso seguro · migración `0003`
### Añadido
- Acceso local con TOTP, OIDC con PKCE y MFA, sesiones revocables y límite de intentos.
- Administración de usuarios.
- Copias verificadas por restauración (AT-29).
- Arranque en Windows con doble clic.

## [F0.1] · 02/11/2026 — Núcleo · migración `0001`
### Añadido
- Multientidad, sedes, departamentos, roles y política de permisos en el backend.
- Auditoría encadenada inmutable.
- Directorio de contactos con aviso de duplicados.

## Historial de commits
| Fecha | Commit | Descripción |
|---|---|---|
| 2026-11-12 | `d1173d1` | INICIAR_REAL: validación de .env.real sin expresiones largas de findstr (fallaban en Windows) |
| 2026-11-12 | `1ad359a` | INICIAR_REAL: pide la primera administración siempre que aún no hay base de datos real |
| 2026-11-12 | `7bd1a71` | INICIAR_REAL: claves generadas con un script PowerShell (y Docker como respaldo); detecta y rehace un .env.real incompleto |
| 2026-11-09 | `647610b` | F5.6 Puesta en marcha real: instalación separada, 13 cuentas, varios extractos y facturas |
| 2026-11-09 | `6d63b32` | Lectura de facturas recibidas v2: formatos reales, escaneados y CIF del despacho |
| 2026-11-09 | `0df310f` | Banco: «Comprobar sin importar» para probar extractos reales sin guardar nada |
| 2026-11-09 | `df505b3` | F5.4b Contabilidad: rutina de trabajo, informes periódicos y extractos en Excel |
| 2026-11-09 | `35ff088` | F5.4 Contabilidad completa: proveedores, tesorería con doble firma y cierre del mes |
| 2026-11-08 | `daa5839` | F5.2 Recepción, F5.3 RRHH y pendientes de los agentes dentro de cada departamento |
| 2026-11-08 | `30821dd` | F5.1 agentes, bandeja de propuestas, banco y conciliación, mensajes automáticos por el portal |
| 2026-11-06 | `b3bf52e` | F2.3 portal del cliente y conversaciones por expediente (portal propio, sin WhatsApp: T-31) |
| 2026-11-05 | `94b9684` | F4.3 revisión automática de la lectura por expediente con informe sin datos |
| 2026-11-05 | `28ebbc0` | F4.3 correcciones tras la prueba real: padrón en tabla, pasaporte completo girado, duplicados, volver a leer y diagnóstico sin datos |
| 2026-11-05 | `c7f876b` | F4.3 lectura de documentos → ficha del formulario (contrato, padrón, TIE, tasa, pasaporte escaneado) |
| 2026-11-05 | `8ba5ddd` | Extensión Mercurio 0.2: reconocimiento por los identificadores reales de Mercurio |
| 2026-11-05 | `670453c` | F4.2 ficha del modelo EX y extensión de Chrome que rellena Mercurio sin presentar (T-24) |
| 2026-11-05 | `b74f5d5` | F4.1 expediente de extranjería (fase 1): trámites, documentos leídos y paquete para Mercurio |
| 2026-11-03 | `75f3ee6` | F5.0 interfaz Economía y Gastos, recorrido en navegador y documentación |
| 2026-11-03 | `b9b0a1a` | F5.0 API: control económico no fiscal (cobros, devoluciones, caja) y gastos con justificante leído en el servidor |
| 2026-11-03 | `a4cf050` | REINICIAR_DATOS_DEMO.bat funciona sin .env y no anuncia un borrado que no ha hecho; nombre de proyecto fijo |
| 2026-11-02 | `12f6a3b` | F0.2 interfaz, recorrido en navegador, documentación y copias de seguridad para Windows |
| 2026-11-02 | `a8395c7` | F0.2 API: acceso local con TOTP, OIDC con PKCE y MFA, sesiones revocables, límite de intentos, administración de usuarios y copias AT-29 |
| 2026-11-02 | `d512c11` | INICIAR.bat detecta base anterior sin su .env; healthcheck sin errores en el registro |
| 2026-11-02 | `c76915f` | Corrige arranque de la API en Docker: zonas horarias propias (tzdata) |
| 2026-11-02 | `8f5a5ba` | F1.2 CRM, F2.1 expedientes y F2.2 tareas y agenda |
| 2026-11-02 | `8f0f8bc` | Arranque en Windows con doble clic y corrección del empaquetado de la API |
| 2026-11-02 | `92c4a14` | F0.1: núcleo de seguridad, multientidad, auditoría y directorio de clientes |

## Próximas versiones previstas
- Migración a **Odoo Community** en el servidor definitivo (ver 02, apartado 8).
- Módulos pendientes: Dirección (cuadro de mando), Citas, Documentos, Fichas laborales y Facturación (con un
  programa certificado).
