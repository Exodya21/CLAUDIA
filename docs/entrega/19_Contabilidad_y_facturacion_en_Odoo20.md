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

**Consecuencia:** con Odoo 20 Community, todo lo que en la tabla de abajo figura como «OCA» hay que **esperar a que
se migre, migrarlo nosotros o programarlo** en los módulos `sp_*`. Esto hay que tenerlo en cuenta al decidir la
versión (punto **AL-02** del documento 18).

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
  intercompañía automática **no** está en Community.
- **No trae:** la pantalla de conciliación bancaria, la importación de extractos, las remesas SEPA ni los informes
  contables (balance, pérdidas y ganancias, modelos de la AEAT). Todo eso es Enterprise o de la OCA.

### 1.3 Facturación a clientes: depende de una decisión
Sistema Propio **no emite facturas ni calcula el IVA**. Registra el número de la factura que emite un programa
homologado (D-07, D-25; ver AL-03). En Odoo, **Odoo puede ser ese programa**, porque Verifactu está en Community 20.
Si la Dirección lo aprueba, la facturación a clientes se monta con lo estándar de Odoo (apartado 3.7). Si no, Odoo
solo registra cobros y el número de la factura externa, como hace hoy Sistema Propio.

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
| Función en Sistema Propio | Tabla | Odoo 20 de serie | OCA | Módulo propio `sp_*` | Charter |
|---|---|---|---|---|---|
| Importe pactado por expediente (lo introduce una persona; anular exige motivo) | `charge` | Presupuesto de venta (`sale.order`) o factura en borrador ligada al proyecto y a su cuenta analítica | — | `sp_recepcion`: motivo obligatorio al anular; solo lo ven Contabilidad, Dirección y quien tiene acceso completo al expediente | 2.7, 6.21 |
| Cobro registrado por Recepción y **confirmado por Contabilidad** | `payment` | `account.payment` en borrador → Contabilidad lo publica | — | Grupo «Registrar cobro» separado de «Confirmar cobro»; campo «nº de factura del programa homologado» si no se factura en Odoo | 4.3 |
| Cobro sin expediente solo si es una consulta | `payment` (check) | — | — | Restricción en `account.payment` | 2.6 |
| **Aviso de cobro repetido** (seguir solo con motivo; avisa a Contabilidad) | `payment.duplicate_reason` | — | — | Comprobación antes de guardar y actividad para Contabilidad | — |
| **Justificante numerado por sede, no fiscal, inmutable** | `payment_receipt`, `receipt_counter` | Recibo de pago en PDF (`account.payment`) y secuencias | — | Secuencia por sede y año; PDF adjunto que no se regenera | 4.18 |
| **Caja por sede** con movimientos solo de inserción | `cash_movement` | Diario de efectivo por sede (Caja Barcelona, Madrid, Valencia) | — | Impedir editar o borrar movimientos de caja publicados | 4.14 |
| **Cierre de caja diario** contado por una persona y **validado por otra** | `cash_closing` | — | — | Modelo `sp.cash.closing` (esperado, contado, diferencia, motivo) con la regla «quien valida ≠ quien cuenta» | 4.14 |
| **Devoluciones** con estados (registrada → en revisión → escalada a letrado → aprobada o rechazada → pagada) y permisos distintos | `refund`, `refund_event` | Factura rectificativa y pago de salida | — | Modelo `sp.refund` con su flujo y permisos (`refund.request`, `review`, `legal_opinion`, `decide`); nunca aprueba quien solicita. Sustituye al Helpdesk (Enterprise) del charter | 3.9, 4.4 |
| Informe diario y semanal de Recepción por sede | — | Análisis de pagos (pivote) | `mis_builder` (sí en 20.0) | Informe QWeb por sede | — |

### 3.2 Gastos de empresa
| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| Ticket subido por la persona → propuesta de datos → confirma → Contabilidad aprueba o devuelve | `expense`, `expense_event` | `hr_expense` (borrador → enviado → aprobado → contabilizado) | — | Lectura del ticket en el servidor (OCR local de `services/receipts.py`), en lugar del OCR de pago de Enterprise | 4.13 |
| Gasto en efectivo que mueve la caja de su sede | `cash_movement` | Pago del gasto con el diario de caja | — | Elegir la caja según la sede de la persona | 4.14 |
| **Tarjetas de empresa** (cada titular ve la suya; cargos sin justificante señalados) | `company_card`, `card_transaction` | — | — | Modelo `sp.company.card` e importación del extracto de la tarjeta | — |
| Resumen mensual por persona, sede, concepto y forma de pago | — | Análisis de gastos | `mis_builder` | Exportación registrada en la auditoría | — |

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
| Función | Tabla | Odoo 20 de serie | OCA | Módulo propio | Charter |
|---|---|---|---|---|---|
| Subir varias facturas y **leerlas** (número, CIF, fechas, base, IVA, retención, total, IBAN; descarta el CIF propio) | `supplier_invoice.extracted` | Factura de proveedor (`in_invoice`); la lectura automática es de pago | — | `sp_lectura`: servicio con `accounting/invoices.py` (lectura v2) que rellena el borrador | 4.17 |
| **El IVA es el de la factura**, nunca se calcula; solo se registra si base + IVA − retención = total | check en BD | Odoo calcula el impuesto desde el tipo, pero permite **ajustar el importe del impuesto** en la factura de proveedor | `account_move_line_tax_editable` (**sí en 20.0**) | Comprobación del cuadre al publicar | 4.17 |
| **Duplicados** (mismo archivo, o mismo proveedor, importe y fecha) | — | Aviso por referencia repetida (de serie) | — | Ampliar a archivo e importe+fecha; motivo obligatorio para seguir | — |
| Estados recibida → validada → programada (en remesa) → pagada (al conciliar el cargo) | `supplier_invoice.status` | Borrador → publicada → pagada | — | Paso «validada» con permiso propio | — |
| Proveedor con actividad, sede, plazo de pago, recurrente | `supplier` | Contacto proveedor, plazos de pago | — | Campos actividad y sede por defecto para la analítica | 4.11 |
| Imputación a **actividad** (laboral, extranjería, compartida) y **sede** | `activity`, `branch_id` | **Analítica con dos planes**: Actividad y Sede | — | Rellenar la analítica desde el proveedor | 4.11 |

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

### 3.7 Facturación a clientes (solo si se aprueba AL-03)
| Función | Odoo 20 de serie | Módulo propio | Charter |
|---|---|---|---|
| Series separadas: citas `CIT/…` y expedientes `EXP/…` | Un diario de ventas por serie (secuencias sin saltos) | — | 4.1 |
| Verifactu (hash, encadenamiento, envío a la AEAT) | `l10n_es_edi_verifactu` | — | 4.2 |
| **Extranjería:** una factura global del trámite y cobros parciales sobre ella | Cobros parciales de serie | — | 6.21 (punto abierto) |
| **Tasas oficiales como suplidos** (no son ingreso) | Línea con cuenta 554/555 y sin IVA | Producto «Suplido» | 4.8 |
| **Laboral (cuota litis):** entra el 100 %, se factura el 20 % + IVA y el 80 % sale desde la cuenta de mediación | Factura y asiento manual | Campo «Total del acuerdo ganado» obligatorio y asistente que prepara la factura del 20 % y el asiento del 80 % | 4.7, 6.19 |
| Cobro con tarjeta a distancia | Enlace de pago con Redsys | — | 4.3 |
| Rectificativas | Nota de crédito de serie | Enlazarla con `sp.refund` | 4.4 |

## 4. Reglas de Sistema Propio que hay que mantener en Odoo
1. **Separación de funciones:** quien registra un cobro no lo confirma; quien cuenta la caja no la valida; quien
   solicita una devolución no la aprueba; quien propone una remesa no la firma, y las dos firmas son de personas
   distintas.
2. **Nada contable se borra.** Se anula o se rectifica con motivo, y queda el historial.
3. **El sistema propone y una persona decide:** conciliación, cobros, devoluciones y pagos.
4. **El IVA de una factura recibida es el que figura en ella.** Solo se registra si cuadra.
5. **Ningún envío al banco ni a la AEAT** sin una persona, salvo el envío de Verifactu si se aprueba AL-03.
6. **Los correos no llevan cifras.**
7. **Importes en céntimos enteros** en la lógica propia, para evitar redondeos.
8. **Permisos en el servidor** (grupos y reglas de registro), no solo ocultando botones; revisar cada `sudo()`.

## 5. Módulos propios propuestos
| Módulo | Depende de | Contenido | Código de referencia |
|---|---|---|---|
| `sp_base` | `account`, `hr`, `mail` | Sedes, actividad, roles y separación de funciones, auditoría | `security/`, `audit.py` |
| `sp_recepcion` | `sp_base`, `account_payment` | Cobros con confirmación, justificante por sede, cierre de caja con doble persona, devoluciones | `reception/`, `routers/economy.py`, `routers/reception.py` |
| `sp_gastos` | `sp_base`, `hr_expense` | Lectura del ticket, tarjetas de empresa | `routers/expenses.py`, `services/receipts.py` |
| `sp_banco` | `sp_base`, `account` | Importación de extractos y conciliación con propuestas | `bank/parsers.py`, `bank/matcher.py`, `bank/service.py` |
| `sp_contabilidad` | `sp_banco` | Facturas de proveedor con lectura y cuadre, remesas con doble firma y SEPA, previsión | `accounting/invoices.py`, `accounting/treasury.py` |
| `sp_contabilidad_rutina` | `sp_contabilidad`, `mis_builder` | Cierre del mes, rutina comprobada e informes | `accounting/close.py`, `routine.py`, `reports.py` |
| `sp_facturacion` (si AL-03) | `account`, `l10n_es_edi_verifactu` | Cuota litis, suplidos, factura global de extranjería | — |

## 6. Orden de implantación recomendado
1. **Base contable:** compañías, `l10n_es`, diarios (ventas por serie, bancos, cajas por sede), planes analíticos
   Actividad y Sede, grupos y permisos. *Todo de serie.*
2. **Recepción y cajas** (`sp_recepcion`): es lo que más usan las sedes cada día.
3. **Proveedores y gastos** (`sp_contabilidad` sin remesas, `sp_gastos`).
4. **Banco y conciliación** (`sp_banco`): la pieza más grande si se queda en Odoo 20.
5. **Remesas SEPA con doble firma.**
6. **Cierre, rutina e informes.**
7. **Facturación a clientes**, cuando se decida AL-03.

## 7. Cómo consultar la referencia
- **Código:** `referencia/SistemaPropio/apps/api/app/` (modelos `models_*.py`, lógica en `bank/`, `accounting/`,
  `reception/`, rutas en `routers/`).
- **Pruebas:** `referencia/SistemaPropio/apps/api/tests/` (las de economía y contabilidad empiezan por `test_f5`).
- **Evidencias con capturas:** `referencia/SistemaPropio/docs/pruebas/evidencias_F5.*.md`.
- **Guía de Contabilidad:** `referencia/SistemaPropio/docs/pruebas/guia_manual_contabilidad.md`.
- **Decisiones (T-nn, D-nn):** `referencia/SistemaPropio/docs/producto/decisiones.md`.
- **Arrancarla en local** (datos ficticios): ver 09 §Anexo B.
