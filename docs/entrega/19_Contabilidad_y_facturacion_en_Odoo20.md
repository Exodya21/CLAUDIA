# 19 · Contabilidad y facturación: de Sistema Propio a Odoo 20 Community

Sistema Propio · 13/11/2026

Este documento toma como **referencia** lo que Sistema Propio ya tiene construido y probado en economía, banco y
contabilidad (versión F5.6c, código en `referencia/SistemaPropio/`) y explica cómo implantarlo en **Odoo 20
Community**. Para cada función indica qué trae Odoo de serie, qué hay en la comunidad OCA y qué hay que programar en
un módulo propio `sp_*`.

**Fuentes:**
- Sistema Propio: documentos 05 §7–§10, 07, 08 y el código de `apps/api/app/` (`models_economy.py`,
  `models_reception.py`, `models_bank.py`, `models_accounting.py`, `bank/`, `accounting/`, `reception/`).
- Presentación de la versión de referencia: el artifact «economía» de Sistema Propio (capturas con datos ficticios).
- Charter de QUBIQ: bloque 4 (skill `sistema-odoo-despacho`).
- **Comprobado el 13/11/2026:** el código de Odoo 20.0 Community (`odoo/odoo`) y las ramas 18.0, 19.0 y 20.0 de los
  repositorios de la OCA.

## 1. Lo más importante antes de empezar

### 1.1 En Odoo 20, la OCA todavía no tiene casi nada de contabilidad
En la rama **20.0** de la OCA, a 13/11/2026, **no están publicados** los módulos que necesita la contabilidad del
despacho. En la **19.0** sí están casi todos, y en la **18.0**, todos.

| Módulo de la OCA (para qué sirve) | 18.0 | 19.0 | 20.0 |
|---|---|---|---|
| `account_statement_import_camt`, `account_statement_import_sheet_file` (importar extractos CAMT, CSV y Excel) | ✅ | ✅ | ❌ |
| `l10n_es_account_statement_import_n43` (Norma 43) | ✅ | ✅ | ❌ |
| `account_reconcile_oca` (pantalla de conciliación bancaria) | ✅ | ✅ | ❌ |
| `account_payment_order`, `account_banking_sepa_credit_transfer` (remesas SEPA) | ✅ | ✅ | ❌ |
| `base_tier_validation` (aprobaciones con varias firmas) | ✅ | ❌ | ❌ |
| `l10n_es_aeat_mod303`, `mod111`, `mod347` (modelos de la AEAT) | ✅ | ✅ | ❌ |
| `l10n_es_aeat_sii_oca` (SII) | ✅ | ✅ | ❌ |
| `account_financial_report` (balance, mayor, antigüedad de saldos) | ✅ | ✅ | ❌ |
| `account_asset_management` (activos) | ✅ | ✅ | ❌ |
| `auditlog` (registro de cambios) | ✅ | ✅ | ❌ |
| `mis_builder` (informes de gestión), `auto_backup` (copias) | ✅ | ✅ | ✅ |

**Consecuencia (decidido el 13/11/2026, 18 · AL-01 y AL-02):** el proyecto usa **Odoo 20.0 Community** y no se
espera a que la OCA publique estos módulos. Todo lo que en las tablas de abajo figura como «OCA … no en 20.0» se
**desarrolla nosotros** en los módulos `sp_*` (apartado 5). Cuando convenga, en lugar de programarlo desde cero se
**porta a la 20.0 el módulo de la OCA de la 19.0** (licencia AGPL/LGPL; se conservan la autoría y la licencia). Solo
si algo no se puede desarrollar se estudia externalizarlo (criterio en 18 §2).

### 1.2 Lo que Odoo 20 Community sí trae de serie (comprobado en su código)
- **Contabilidad base** (`account`): diarios, asientos, facturas de cliente y de proveedor, rectificativas, pagos y
  cobros parciales, impuestos, analítica con varios planes, multicompañía, multimoneda.
- **Fechas de bloqueo** (ejercicio, impuestos y ventas): sirven para congelar un mes cerrado.
- **Aviso de factura de proveedor con referencia repetida** (`duplicated_ref_ids`).
- **Localización española** `l10n_es` (plan de pymes, IVA, retenciones de IRPF), **Verifactu**
  (`l10n_es_edi_verifactu`) y **SII** (`l10n_es_edi_sii`).
- **Redsys** (`payment_redsys`) y enlaces de pago (`account_payment`).
- **Gastos de empleados** (`hr_expense`), sin lectura automática del ticket.
- **Pagos intercompañía** (`account_payment_interco`): concilia pagos entre empresas del grupo. La facturación
  intercompañía automática **no** está en Community. En este proyecto la intercompañía queda **solo entre la filial de
  Colombia y la S.L.**: el autónomo del titular queda fuera de Odoo (18 · AL-06, decidido provisionalmente el
  13/11/2026).
- **No trae:** la pantalla de conciliación bancaria, la importación de extractos, las remesas SEPA ni los informes
  contables (balance, pérdidas y ganancias, modelos de la AEAT). Todo eso es Enterprise o de la OCA.

### 1.3 Facturación a clientes: decidido, Odoo emite con Verifactu
Sistema Propio **no emite facturas ni calcula el IVA**: registra el número de la factura que emite un programa
homologado (D-07, D-25). **Decidido el 13/11/2026 por la persona responsable del proyecto (18 · AL-03):** en el
sistema en Odoo, **Odoo 20 Community emite las facturas a clientes, con Verifactu** (módulo estándar
`l10n_es_edi_verifactu`). Odoo calcula el IVA de **sus** facturas de venta. Las **facturas recibidas** siguen con el IVA
que figura en ellas (01 §4 regla 11 y §4 regla 4 de este documento).

**Comprobado el 13/11/2026 en el código de Odoo 20.0 Community** (`addons/l10n_es_edi_verifactu`):

| Aspecto | Qué hay |
|---|---|
| Autor y licencia | Odoo S.A., LGPL-3 |
| Dependencias | `l10n_es` y `certificate` |
| Activación | Por compañía («Enable Veri*Factu»). Se activa **solo en la S.L.**: el autónomo queda fuera de Odoo y sus pocas facturas a clientes siguen en su programa actual (18 · AL-06, decidido provisionalmente el 13/11/2026) |
| Certificado | Cada compañía que emite necesita su certificado electrónico cargado en Odoo (modelo `certificate.certificate`); en este proyecto, solo el de la S.L. |
| Entornos de la AEAT | Pruebas (prewww1/prewww2.aeat.es), **activado por defecto**, y producción (www1/www2.agenciatributaria.gob.es) |
| Funcionamiento | Envío por tarea programada (`ir_cron`), encadenamiento de registros, QR en el PDF de la factura, panel en el diario y asistente de renumeración |
| Declaración responsable | En los ajustes hay un enlace «Access Declaración Responsable» a la documentación de Odoo: la emite Odoo S.A. para su módulo estándar |

**Precaución (por confirmar con la gestoría o un asesor fiscal; no comprobado):** la declaración responsable de Odoo
cubre su módulo estándar. Los módulos propios **no deben alterar** el registro, el encadenamiento, la numeración ni el
envío de Verifactu. Si un desarrollo propio tocara esa parte, el despacho podría pasar a considerarse productor del
software, con sus obligaciones. **Regla de diseño:** `sp_facturacion` solo **prepara** facturas (cuota litis, suplidos,
factura global de extranjería) y deja la emisión y el envío al estándar. La facturación se monta como se indica en
§3.7 y se pone en marcha según §3.8.

## 2. Principio de diseño
1. **Lo contable va en el modelo contable de Odoo** (`account.move`, `account.payment`, `account.bank.statement.line`,
   diarios y analítica). No se duplica en tablas propias.
2. **Las reglas del despacho van en módulos `sp_*`** que extienden esos modelos: separación de funciones (quien
   propone no aprueba), motivos obligatorios, cuadres, inmutabilidad y propuestas que valida una persona.
3. **Lo que ya funciona en Sistema Propio se reutiliza:** lectores de extractos (`bank/parsers.py`), reglas de
   conciliación (`bank/matcher.py`), lectura de facturas (`accounting/invoices.py`), rutina e informes
   (`accounting/routine.py`, `reports.py`, `close.py`). Son Python sin dependencia de FastAPI.
4. **Las pruebas de Sistema Propio son la especificación:** `apps/api/tests/test_f5*.py` se reescriben como
   `TransactionCase` de Odoo.

## 3. Correspondencia función por función

Columnas:
- **Odoo 20 de serie:** comprobado en el código de Odoo 20.0 Community.
- **OCA:** módulo de la comunidad. Si en 20.0 no existe, se indica.
- **Módulo propio `sp_*`:** lo que hay que programar.
- **Charter:** la necesidad del charter de QUBIQ con la que se relaciona.

### 3.1 Economía y Recepción (cobros no fiscales, cajas y devoluciones)
**Estado (13/11/2026):** `sp_recepcion` versión 20.0.1.1.0 hecha y probada (11 · DOC-8 y DOC-10; código en
`odoo/addons/sp_recepcion/`; 26 pruebas automáticas sin fallos). La columna «Estado» indica qué está hecho y con qué modelo o campo real.

| Función en Sistema Propio | Tabla | Odoo 20 de serie | OCA | Módulo propio `sp_*` | Charter | Estado |
|---|---|---|---|---|---|---|
| Importe pactado por expediente (lo introduce una persona; anular exige motivo) | `charge` | Presupuesto de venta (`sale.order`) o factura en borrador ligada al proyecto y a su cuenta analítica | — | `sp_recepcion`: motivo obligatorio al anular; solo lo ven Contabilidad, Dirección y quien tiene acceso completo al expediente | 2.7, 6.21 | **Pendiente:** necesita el módulo de expedientes |
| Sedes con su caja y su numeración | `branch` | Diario de efectivo por sede | — | Modelo `sp.sede` (código, `journal_id`, `receipt_sequence_id` con `no_gap`); sede habitual del usuario `res.users.sp_sede_id` y sedes en las que trabaja `res.users.sp_sede_ids` (la habitual se añade sola) | 4.14 | **Hecho** |
| Cobro registrado por Recepción y **confirmado por Contabilidad** | `payment` | `account.payment` (cobro de cliente) | — | Campos `sp_sede_id`, `sp_tipo` (consulta, provisión, servicio, otro) y `sp_estado` (registrado → confirmado / anulado). Recepción registra con «Confirmar» de Odoo; Contabilidad confirma con `action_sp_confirmar` (`sp_confirmado_por`, `sp_confirmado_fecha`). Pendiente el campo «nº de factura del programa homologado» | 4.3 | **Hecho en parte** (falta el nº de factura externa) |
| Anular un cobro con motivo, sin borrar | `payment` | Cancelar pago | — | Asistente `sp.anular.cobro` → `sp_anulado_motivo` (≥ 10 caracteres), `sp_anulado_por`; no si la caja de ese día o posterior está validada; bloquea «Restablecer a borrador», «Cancelar» y borrar en cobros con justificante | 4.3 | **Hecho** |
| Cobro sin expediente solo si es una consulta | `payment` (check) | — | — | Restricción en `account.payment` | 2.6 | **Pendiente:** necesita el módulo de expedientes |
| **Aviso de cobro repetido** (seguir solo con motivo; avisa a Contabilidad) | `payment.duplicate_reason` | — | — | `_sp_posibles_duplicados()` en `action_post` (mismo cliente, importe y diario ±2 días, o misma referencia `memo` en 90 días); motivo `sp_motivo_duplicado` ≥ 10 caracteres; actividad para el grupo responsable | — | **Hecho** |
| **Justificante numerado por sede, no fiscal, inmutable** | `payment_receipt`, `receipt_counter` | Secuencias (`ir.sequence` con rango por año) e informes PDF | — | `sp_justificante_numero` (único por compañía, `REC-BCN-2026-000001`); informe `action_report_justificante` con `save_as_attachment` y `attachment_use`: el PDF se genera una vez y se reutiliza. Dice «NO ES UNA FACTURA». En Sistema Propio además iba cifrado | 4.18 | **Hecho** |
| **Caja por sede** con movimientos solo de inserción | `cash_movement` | Diario de efectivo por sede (Caja Barcelona, Madrid, Valencia) | — | Los cobros con justificante no se borran ni vuelven a borrador. Los apuntes publicados de una caja con fecha de un día validado no vuelven a borrador ni se cancelan (`account.move.button_draft` y `button_cancel`); los movimientos nuevos sí se registran y cuentan en el siguiente cierre (saldo acumulado). Cada persona de Recepción solo ve y registra cobros y cierres de **sus** sedes (`sp_sede_ids` + sede habitual; regla `sp_payment_sede_rule` y permiso por sede en `sp.cierre.caja`); Contabilidad, todas (08 §10) | 4.14 | **Hecho** (11 · DOC-10) |
| **Cierre de caja diario** contado por una persona y **validado por otra** | `cash_closing` | — | — | Modelo **`sp.cierre.caja`** (`esperado`, `contado`, `diferencia`, `notas`, `contado_por`, `validado_por`, `ajuste_move_id`): saldo según los apuntes de la cuenta de la caja hasta el final del día; quien valida ≠ quien cuenta; ajuste a las cuentas de diferencias de la caja; uno por sede y día salvo rechazados; validado = inmutable. En la base de datos, como en Sistema Propio: CHECK «quien valida o rechaza ≠ quien contó» y trigger `sp_cierre_caja_proteger` (no se modifica un cierre validado o rechazado ni se borra uno contado o validado) | 4.14 | **Hecho** (Python y base de datos; 11 · DOC-10) |
| **Devoluciones** con estados (registrada → en revisión → escalada a letrado → aprobada o rechazada → pagada) y permisos distintos | `refund`, `refund_event` | Factura rectificativa y pago de salida | — | Modelo **`sp.devolucion`** (`DEV/año/nnnn`, `no_gap`): registrada → en revisión → [escalada al letrado → informe → en revisión] → aprobada o rechazada → pagada; rechazada se reabre con motivo; el estado solo cambia con los botones y no se borra. Grupos: Recepción (solicita, ve las suyas), «Atención al cliente · revisar devoluciones» (`refund.review`), «Letrado · informe de devoluciones» (`refund.legal_opinion`) y responsable de Contabilidad (`refund.decide`); nunca decide quien solicita (Python y CHECK en BD). Pago (`action_pagar`): factura cobrada del todo e importe total → rectificativa automática y pago conciliado; parcial → rectificativa vinculada a mano; factura sin cobrar → no se paga; sin factura → pago de salida. TPV/Redsys fuera de Odoo. Tareas que se cierran en cada paso. Sustituye al Helpdesk (Enterprise) del charter | 3.9, 4.4 | **Hecho** (11 · DOC-10). Quién aprueba: Contabilidad, como en Sistema Propio (18 · AL-14, decidido 13/11/2026) |
| Informe diario y semanal de Recepción por sede | — | Análisis de pagos (pivote); la lista de cobros ya agrupa por sede | `mis_builder` (sí en 20.0) | Informe QWeb por sede en PDF | — | **Pendiente** (siguiente iteración) |

**Rectificativas de las devoluciones (comprobado en `models/devolucion.py`):** `sp_recepcion` no emite ni numera la
rectificativa por su cuenta. Usa el método estándar de Odoo (`_reverse_moves` y `action_post`), así que la serie, la
numeración y el registro en Verifactu son los del estándar (§1.3, 01 §4). Falta comprobarlo contra la AEAT
(12 · ABI-04).

### 3.2 Gastos de empresa
**Hecho en parte · 13/11/2026** con `sp_gastos` 20.0.1.0.0 (11 · DOC-14). Base: «Gastos» estándar de Odoo 20
Community (`hr_expense`). En Odoo 20 no hay «informes de gastos»: cada gasto se aprueba por separado.

| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| Ticket subido por la persona → propuesta de datos → confirma → se aprueba o se devuelve | `expense`, `expense_event` | `hr_expense`: borrador → enviado → aprobado (crea el asiento en borrador) → contabilizado. Aprueba el aprobador de la ficha del empleado (08 §11) | — | **Hecho (DOC-14).** Lectura del ticket en el servidor (`sp_gastos/lectura/tickets.py`, copia de `services/receipts.py`) con la extracción y el OCR de `sp_contabilidad/lectura/extraer.py`. Se lee al subir el ticket o con **Leer ticket**. Propone fecha, comercio, proveedor por NIF, total y el «IVA que figura en el ticket»; elige el impuesto de bienes que reproduce ese IVA y lo mantiene si se cambia la categoría | 4.13 |
| Aviso de gasto repetido | — | **De serie:** aviso por misma categoría, fecha, importe y empleado; al aprobar pide confirmarlo | — | — (comprobado en el escenario repetido) | — |
| Forma de pago: pagado por la persona, efectivo o tarjeta de empresa | `expense` | `payment_mode` (`own_account` / `company_account`) y método de pago | — | **Hecho (DOC-14).** Campo `sp_forma_pago`: «Pagado por la persona» → reembolso; «Tarjeta de empresa» → pagado por la empresa con el banco que se elija | 4.13 |
| Gasto en efectivo que mueve la caja de su sede | `cash_movement` | Pago del gasto con el diario de caja | — | **Hecho (DOC-14).** «Efectivo de la caja de la sede»: usa el método de pago de salida de la caja de la sede (`sp_sede_id`, por defecto la sede habitual). El asiento abona la 570… de esa caja y entra en su cierre diario (`sp_recepcion`). Sin sede no se permite | 4.14 |
| Categorías de gasto con su cuenta | — | Productos «se puede incluir en gastos» | — | **Hecho (configuración).** `odoo/configuracion/gastos.py`: 9 categorías con cuenta del PGC **provisional** (T-40, 18 · AL-13) | — |
| **Tarjetas de empresa** (cada titular ve la suya; cargos sin justificante señalados) | `company_card`, `card_transaction` | — | — | **Pendiente (siguiente iteración).** Modelo `sp.company.card` e importación del extracto de la tarjeta | — |
| Resumen mensual por persona, sede, concepto y forma de pago | — | Análisis de gastos | `mis_builder` | **Pendiente.** De momento, los informes estándar de Gastos. Después, exportación registrada en la auditoría | — |
| Límites y políticas de gasto | — | — | — | **Pendiente** | — |

**Separación de funciones (resuelto en 11 · DOC-15):** en Odoo estándar el grupo «Gastos: Administrador» puede
aprobar sus propios gastos; `sp_gastos` lo impide, como en Sistema Propio (§4, regla 1). Los gastos de Contabilidad 1
los aprueba Contabilidad 2 en la configuración de demostración (08 §11).

### 3.3 Banco y conciliación
| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| Cuentas bancarias con **IBAN cifrado** (solo se ven los 4 últimos dígitos) | `bank_account` | Diario de banco y `res.partner.bank` (**el IBAN se guarda sin cifrar**) | — | Decidir si basta con permisos o se cifra (riesgo frente a 07 y 08) | 4.5 |
| Importar **Norma 43, CAMT.053, CSV, Excel** (Caixa, BBVA, «.xls» en HTML); varios a la vez por IBAN; «comprobar sin importar»; sin duplicados | `bank_import`, `bank_movement` | ❌ (en Community no se importan extractos) | `account_statement_import_*` y `l10n_es_..._n43`: **no en 20.0** | `sp_banco`: portar `bank/parsers.py` (ya lee todos esos formatos) y crear `account.bank.statement.line`; guardar el original cifrado | 4.5 |
| **Propuestas de conciliación explicadas** (traspaso, referencia del expediente, Bizum, TPV con comisión, devolución, importe y fecha) que **valida Contabilidad** | `bank_match` | ❌ (la pantalla de conciliación es Enterprise) | `account_reconcile_oca`: **no en 20.0** | `sp_banco`: portar `bank/matcher.py` y una pantalla de propuestas «aceptar o rechazar con motivo»; validar confirma el cobro | 4.5 |
| Estados del movimiento (pendiente, propuesto, parcial, sin justificar, conciliado, traspaso, ignorado) | `bank_movement.status` | Línea de extracto conciliada o no | — | Campo de estado propio | — |
| Un traspaso entre cuentas propias nunca cuenta como ingreso | — | Cuenta de transferencias internas | — | Regla «traspaso» del matcher | — |
| Exportación CSV para la gestoría | — | Exportar desde las listas | — | — | 4.10 |

### 3.4 Facturas de proveedores
**Estado (13/11/2026):** `sp_contabilidad` versión 20.0.1.0.0, primera parte hecha y probada (11 · DOC-13; código en
`odoo/addons/sp_contabilidad/`; 5 pruebas automáticas sin fallos y escenario `odoo/pruebas/prueba_facturas_proveedor.py`
correcto). Captura: `documentacion/odoo20_contabilidad/1_factura_proveedor_leida.png`. La lectura se hace en el
propio servidor (imagen `despacho/odoo:20`, `odoo/Dockerfile`), sin servicios externos.

| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter | Estado |
|---|---|---|---|---|---|---|
| Subir varias facturas y **leerlas** (número, CIF, fechas, base, IVA, retención, total, IBAN; descarta el CIF propio) | `supplier_invoice.extracted` | Factura de proveedor (`in_invoice`) y botón **Subir**; la lectura automática es de pago | — | `sp_contabilidad`: `lectura/facturas.py` (lector v2 de Sistema Propio) con `pdftotext` y OCR Tesseract. Se lee al **Subir** (`_extend_with_attachments`) o con **Leer factura**. Solo rellena campos vacíos: proveedor por CIF, `ref`, fecha, vencimiento, `sp_total_documento` y una línea con la base y los impuestos. Descarta el CIF de la compañía y los de `sp_contabilidad.cif_propios`. Resumen y confianza en el historial | 4.17 | **Hecho en parte.** Falta comprobar varias a la vez (Subir admite varios archivos). El IBAN se lee pero no se pasa al proveedor |
| **El IVA es el de la factura**, nunca se calcula; solo se registra si base + IVA − retención = total | check en BD | Odoo calcula el impuesto desde el tipo, pero permite **ajustar el importe del impuesto** en la factura de proveedor | `account_move_line_tax_editable` (**sí en 20.0**) | Se elige el impuesto cuyo tipo reproduce la cifra impresa (IVA 21/10/5/4 % de servicios; IRPF 15/7/19/1/2 %). `action_post` exige «Total que figura en la factura» igual al total de Odoo | 4.17 | **Hecho** (en Python, no en la base de datos) |
| **Duplicados** (mismo archivo, o mismo proveedor, importe y fecha) | — | Aviso por referencia repetida (de serie) | — | `_sp_posibles_duplicados()`: mismo proveedor y número (sin distinguir mayúsculas), mismo proveedor, importe y fecha, o mismo archivo (checksum). Motivo `sp_motivo_duplicado` ≥ 10 caracteres | — | **Hecho** |
| Estados recibida → validada → programada (en remesa) → pagada (al conciliar el cargo) | `supplier_invoice.status` | Borrador → publicada → pagada | — | Paso «validada» con permiso propio | — | **Pendiente.** De momento, los estados de Odoo; «programada» llegará con las remesas (§6 paso 5) |
| Proveedor con actividad, sede, plazo de pago, recurrente | `supplier` | Contacto proveedor, plazos de pago | — | Alta automática del proveedor leído (avisada en el historial). Falta el alta rápida con revisión y los campos actividad y sede por defecto | 4.11 | **Hecho en parte** |
| Imputación a **actividad** (laboral, extranjería, compartida) y **sede** | `activity`, `branch_id` | **Analítica con dos planes**: Actividad y Sede; modelos de distribución analítica | — | Sin código propio: modelos de distribución analítica de Odoo o a mano en la línea (el escenario lo hace a mano) | 4.11, 4.17 | **Hecho con el estándar** |

**Facturas del autónomo del titular y de la filial de Colombia (18 · AL-06, decidido provisionalmente el
13/11/2026):** el autónomo no es compañía en Odoo; sus facturas a la S.L. se registran en la S.L. como **facturas de
proveedor** normales, con el IVA y la retención que figuren en ellas. La intercompañía (charter 1.1 y 4.16) queda solo
entre la filial de Colombia y la S.L.: como la facturación intercompañía automática es Enterprise, se cubrirá con
desarrollo propio o se registrará a mano (18 §2).

### 3.5 Tesorería y remesas
| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| Saldos según extracto y cajas | — | Saldo de los diarios | — | — | 4.14 |
| **Previsión de pagos** (vencidos, 7, 30, 60, 90 días) | `accounting/treasury.py` | Vencimientos en la lista de facturas | `account_financial_report`: no en 20.0 | Vista e informe propios | — |
| **Remesa** propuesta por Contabilidad, **dos firmas de Dirección distintas** y ninguna de quien propone | `payment_batch`, `…_approval` | ❌ | `account_payment_order` (no en 20.0), `base_tier_validation` (no en 19.0 ni en 20.0) | `sp_contabilidad`: modelo de remesa con doble firma (portar la regla del trigger) | 4.9 |
| Generar el **fichero SEPA pain.001** que una persona sube al banco; nunca se envía solo | — | ❌ | `account_banking_sepa_credit_transfer`: no en 20.0 | Generador pain.001 en `sp_contabilidad` | 4.9 |
| El cargo del extracto marca las facturas de la remesa como pagadas | `paid_movement_id` | Conciliar el cargo con los pagos | — | Regla del matcher para remesas | — |

### 3.6 Cierre del mes, rutina e informes
| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| **Cierre del mes** por actividad y sede (ingresos, cobros, gastos, personal, pagos), comparado con el mes anterior; Contabilidad prepara, Dirección aprueba; queda **congelado con huella**; recalcular crea otra revisión | `month_close` | **Fechas de bloqueo** para congelar el periodo | `mis_builder` (sí en 20.0) para las cifras | `sp_contabilidad_rutina`: foto del cierre con huella y revisiones | 4.11 |
| Coste de personal agrupado si hay menos de 3 personas y quien mira no tiene `hr.salary` | — | — | — | Regla en el informe | — |
| **Rutina** (cada día, cada lunes, días 1 y 16, días 2 a 5, día 7) con responsable, tarea en la agenda y **hecho solo si el sistema lo comprueba** | `accounting_routine_*` | Actividades (`mail.activity`) y tareas programadas (`ir.cron`) | — | Portar `accounting/routine.py` (comprobaciones automáticas, «no aplica» con motivo de 10 caracteres o más) | — |
| **Informes** semanal, quincenal y mensual, inmutables, en PDF y CSV, aviso por correo **sin cifras**, revisión de Dirección | `accounting_report` | Informes QWeb y correo | `mis_builder` | Portar `accounting/reports.py` | — |
| Asientos con el plan de cuentas de la gestoría | pendiente (T-40) | Asientos de Odoo con `l10n_es` | — | Cuentas de la gestoría; suplidos 554/555 y cuenta de mediación del 80 % | 4.7, 4.8 |
| Modelos de la AEAT (303, 111, 347…) para la gestoría | — | ❌ | `l10n_es_aeat_*`: no en 20.0 | Mientras tanto: exportación para la gestoría | 4.10 |

### 3.7 Facturación a clientes (decidido, 18 · AL-03)
Odoo emite las facturas de venta con Verifactu (§1.3). Los suplidos, la cuota litis y la factura global de extranjería
siguen como en esta tabla. Los puntos 4.1, 6.19 y 6.21 del charter siguen abiertos **en cuanto al flujo** (no en
cuanto a quién factura).

| Función | Odoo 20 de serie | Módulo propio | Charter |
|---|---|---|---|
| Series separadas: citas `CIT/…` y expedientes `EXP/…` | Un diario de ventas por serie (secuencias sin saltos) | — | 4.1 |
| Verifactu (hash, encadenamiento, envío a la AEAT) | `l10n_es_edi_verifactu` | — | 4.2 |
| **Extranjería:** una factura global del trámite y cobros parciales sobre ella | Cobros parciales de serie | — | 6.21 (punto abierto) |
| **Tasas oficiales como suplidos** (no son ingreso) | Línea con cuenta 554/555 y sin IVA | Producto «Suplido» | 4.8 |
| **Laboral (cuota litis):** entra el 100 %, se factura el 20 % + IVA y el 80 % sale desde la cuenta de mediación | Factura y asiento manual | Campo «Total del acuerdo ganado» obligatorio y asistente que prepara la factura del 20 % y el asiento del 80 % | 4.7, 6.19 |
| Cobro con tarjeta a distancia | Enlace de pago con Redsys | — | 4.3 |
| Rectificativas | Nota de crédito de serie | Enlazarla con `sp.refund` | 4.4 |

`sp_facturacion` solo prepara el borrador de la factura. La validación, la numeración, el registro, el encadenamiento y
el envío a la AEAT los hace siempre el estándar (`account` y `l10n_es_edi_verifactu`), sin modificarlos (§1.3).

### 3.8 Puesta en marcha de Verifactu
Plan acordado el 13/11/2026 (18 · AL-03). Ningún paso se da por hecho hasta que se anote en 11 · Changelog.

| Paso | Qué se hace | Quién | Estado |
|---|---|---|---|
| a | Probar con el **entorno de pruebas de la AEAT** (el de defecto del módulo) y **datos ficticios** (CLIENTE_01, EXPEDIENTE_01) | Equipo del proyecto | **En curso · 13/11/2026:** entorno de pruebas configurado en la S.L., la única compañía española en Odoo (`odoo/configuracion/base_contable.py`; 18 · AL-06). Con el certificado de pruebas público de la AEAT que trae Odoo, la huella se calcula, pero el documento no se completa: el entorno en la nube no llega a `prewww2.aeat.es` (12 · INC-64). **Pendiente:** repetir la prueba en un equipo con Internet |
| b | Definir los **diarios y series** de venta: `CIT/…` (citas) y `EXP/…` (expedientes), correlativas y sin saltos, en la S.L. (única compañía que emite con Verifactu; 18 · AL-06) | Contabilidad y equipo del proyecto | **Hecho en la base de prueba · 13/11/2026:** diarios CIT y EXP con rectificativas RCIT y REXP (11 · DOC-5). Se validan en el paso d |
| c | Cargar el **certificado electrónico** de la S.L. en Odoo | La persona autorizada del despacho, directamente en Odoo | Pendiente |
| d | **Validar con la gestoría** (series, IVA, suplidos, cuota litis y la precaución de §1.3) | Gestoría y Dirección | Pendiente |
| e | **Pasar a producción**, con la fecha de inicio anotada en 11 · Changelog y en 18 · AL-03 | Persona responsable del proyecto | Pendiente |

**El certificado nunca se comparte** por chat, correo ni repositorio, ni se pasa al equipo de desarrollo: lo carga
directamente en Odoo la persona autorizada (01 §4 regla 8).

## 4. Reglas de Sistema Propio que hay que mantener en Odoo
1. **Separación de funciones:** quien registra un cobro no lo confirma; quien cuenta la caja no la valida; quien
   solicita una devolución no la aprueba; quien propone una remesa no la firma, y las dos firmas son de personas
   distintas.
2. **Nada contable se borra.** Se anula o se rectifica con motivo, y queda el historial.
3. **El sistema propone y una persona decide:** conciliación, cobros, devoluciones y pagos.
4. **El IVA de una factura recibida es el que figura en ella.** Solo se registra si cuadra.
5. **Ningún envío al banco ni a la AEAT** sin una persona, salvo el envío de Verifactu de las facturas emitidas
   (decidido, 18 · AL-03), que hace el módulo estándar.
6. **Los correos no llevan cifras.**
7. **Importes en céntimos enteros** en la lógica propia, para evitar redondeos.
8. **Permisos en el servidor** (grupos y reglas de registro), no solo ocultando botones; revisar cada `sudo()`.

## 5. Módulos propios propuestos
La columna «Sustituye a (OCA no en 20.0)» indica qué módulos de la OCA cubre cada `sp_*` mientras no estén en la
rama 20.0. Para esas piezas se puede partir del código de la OCA 19.0 portado (18 §2, paso 3).

| Módulo | Depende de | Contenido | Sustituye a (OCA no en 20.0) | Código de referencia |
|---|---|---|---|---|
| `sp_base` | `account`, `hr`, `mail` | Sedes, actividad, roles y separación de funciones, auditoría | `auditlog` (en parte) | `security/`, `audit.py` |
| `sp_recepcion` · **hecho en parte (13/11/2026, 11 · DOC-8 y DOC-10; versión 20.0.1.1.0)** | `account` (de momento; las sedes viven en este módulo hasta que exista `sp_base`) | Hecho: sedes y sedes por persona, cobros con confirmación, aviso de repetidos, justificante por sede, anulación con motivo, cierre de caja con doble persona (también en BD), protección de apuntes de caja de días validados y devoluciones con su flujo. Pendiente: informe por sede y vínculo con expedientes (§3.1) | — | `reception/`, `routers/economy.py`, `routers/reception.py` |
| `sp_gastos` · **hecho en parte (13/11/2026, 11 · DOC-14; versión 20.0.1.0.0)** | `hr_expense`, `sp_recepcion`, `sp_contabilidad` (de momento; `sp_base` cuando exista) | Hecho: lectura del ticket en el servidor (con la extracción de `sp_contabilidad/lectura/`), IVA del ticket, forma de pago del despacho y efectivo desde la caja de la sede (§3.2). Pendiente: tarjetas de empresa, resumen mensual, límites y políticas | — | `routers/expenses.py`, `services/receipts.py` |
| `sp_banco` | `sp_base`, `account` | Importación de extractos y conciliación con propuestas | `account_statement_import_camt`, `account_statement_import_sheet_file`, `l10n_es_account_statement_import_n43`, `account_reconcile_oca` | `bank/parsers.py`, `bank/matcher.py`, `bank/service.py` |
| `sp_contabilidad` · **hecho en parte (13/11/2026, 11 · DOC-13; versión 20.0.1.0.0)** | `account`, `l10n_es` (de momento; `sp_banco` cuando lleguen las remesas) | Hecho: facturas de proveedor con lectura en el servidor (`lectura/`), cuadre con el total de la factura y aviso de repetidas (§3.4). Pendiente: estado «validada», alta rápida del proveedor, remesas con doble firma y SEPA, previsión | `account_payment_order`, `account_banking_sepa_credit_transfer`, `base_tier_validation` | `accounting/invoices.py`, `accounting/treasury.py` |
| `sp_contabilidad_rutina` | `sp_contabilidad`, `mis_builder` | Cierre del mes, rutina comprobada e informes | `account_financial_report`, `l10n_es_aeat_mod303`, `mod111`, `mod347` (y demás `l10n_es_aeat_*`) | `accounting/close.py`, `routine.py`, `reports.py` |
| `sp_facturacion` (decidido, AL-03) | `account`, `l10n_es_edi_verifactu` | Prepara facturas: cuota litis, suplidos, factura global de extranjería. **No toca** el registro, el encadenamiento, la numeración ni el envío de Verifactu (§1.3) | — | — |

Quedan sin asignar a un `sp_*` concreto `l10n_es_aeat_sii_oca` (Odoo 20 Community trae `l10n_es_edi_sii`) y
`account_asset_management` (activos): se decidirá con el criterio de 18 §2 cuando se aborden.

## 6. Orden de implantación recomendado
1. **Base contable:** compañías, `l10n_es`, diarios (ventas por serie, bancos, cajas por sede), planes analíticos
   Actividad y Sede, grupos y permisos. *Todo de serie.* **Hecho · 13/11/2026** con datos ficticios (11 · DOC-5):
   cómo montarlo en [`odoo/LEEME.md`](../../odoo/LEEME.md); script `odoo/configuracion/base_contable.py` y prueba
   `odoo/pruebas/prueba_base_contable.py`. Quedan pendientes: los **grupos y permisos** (no se han configurado aún),
   las cuentas 555001 y 555002, que son provisionales (T-40, 18 · AL-13), y la confirmación de la gestoría de que el
   autónomo queda fuera de Odoo (18 · AL-06, decidido provisionalmente el 13/11/2026; el script ya crea solo la S.L. y
   la filial de Colombia). Para cerrarlos se ha preparado el cuestionario para la gestoría
   (`documentacion/cuestionarios/Cuestionario_gestoria_plan_de_cuentas.docx`, 13/11/2026; 11 · DOC-6).
2. **Recepción y cajas** (`sp_recepcion`): es lo que más usan las sedes cada día. **Hecho en parte · 13/11/2026**
   (11 · DOC-8 y DOC-10): sedes, cobros con justificante, aviso de repetidos, confirmación y anulación por
   Contabilidad, cierre de caja validado por otra persona (con CHECK y trigger en la base de datos), cada persona de
   Recepción limitada a sus sedes, apuntes de caja de días validados protegidos y **devoluciones** con revisión,
   letrado, aprobación y pago; 26 pruebas automáticas sin fallos y escenarios `odoo/pruebas/prueba_recepcion.py` y
   `odoo/pruebas/prueba_devoluciones.py` correctos. Cómo instalarlo: `odoo/LEEME.md` («Recepción y cajas»); capturas
   en `documentacion/odoo20_recepcion/`. **Pendiente:** informe diario y semanal por sede en PDF, vínculo con
   expedientes (y con él la regla «cobro sin expediente solo si es consulta»). Quién aprueba las devoluciones ya está
   decidido: Contabilidad, como en Sistema Propio (18 · AL-14, 13/11/2026).
3. **Proveedores y gastos** (`sp_contabilidad` sin remesas, `sp_gastos`). **Hecho en parte · 13/11/2026**
   (11 · DOC-13 y DOC-14):
   - **Facturas de proveedores** en `sp_contabilidad` 20.0.1.0.0. Se leen en el servidor al subirlas (PDF con texto o
     escaneado, OCR en español), se registran solo si cuadran con el total de la factura y avisan de posibles
     repetidas; 5 pruebas automáticas sin fallos y escenario `odoo/pruebas/prueba_facturas_proveedor.py` correcto.
     Cómo instalarlo: `odoo/LEEME.md` («Facturas de proveedores», pasos 10 y 11).
   - **Gastos de empleados** en `sp_gastos` 20.0.1.0.0 (§3.2): lectura del ticket en el servidor, IVA del ticket y
     forma de pago del despacho, con el efectivo saliendo de la caja de la sede; 6 pruebas sin fallos (38 en total
     con los otros dos módulos) y escenario `odoo/pruebas/prueba_gastos.py` correcto. Cómo instalarlo:
     `odoo/LEEME.md` («Gastos de empleados», pasos 12 y 13).
   - **Pendiente:** estado «validada» y «programada» (esta con las remesas), alta rápida y revisión del proveedor
     nuevo, comprobar la subida de varias facturas a la vez, **tarjetas de empresa** (siguiente iteración), resumen
     mensual de gastos, límites y políticas, y quién aprueba los gastos de Contabilidad (§3.2, aviso).
4. **Banco y conciliación** (`sp_banco`): la pieza más grande en Odoo 20 (decidido, 18 · AL-02).
5. **Remesas SEPA con doble firma.**
6. **Cierre, rutina e informes.**
7. **Facturación a clientes** con Verifactu (decidido, 18 · AL-03), siguiendo el plan de §3.8. Las pruebas en el
   entorno de la AEAT (paso a) pueden empezar antes, en paralelo.

## 7. Cómo consultar la referencia
- **Código:** `referencia/SistemaPropio/apps/api/app/` (modelos `models_*.py`, lógica en `bank/`, `accounting/`,
  `reception/`, rutas en `routers/`).
- **Pruebas:** `referencia/SistemaPropio/apps/api/tests/` (las de economía y contabilidad empiezan por `test_f5`).
- **Evidencias con capturas:** `referencia/SistemaPropio/docs/pruebas/evidencias_F5.*.md`.
- **Guía de Contabilidad:** `referencia/SistemaPropio/docs/pruebas/guia_manual_contabilidad.md`.
- **Decisiones (T-nn, D-nn):** `referencia/SistemaPropio/docs/producto/decisiones.md`.
- **Arrancarla en local** (datos ficticios): ver 09 §Anexo B.
