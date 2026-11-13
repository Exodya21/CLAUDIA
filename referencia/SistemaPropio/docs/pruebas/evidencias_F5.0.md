# Evidencias de pruebas · F5.0 (control económico no fiscal y gastos de empresa)

Ejecutadas el 03/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Tesseract 5 con español, Chrome).
Datos ficticios; los tickets se generan en la propia prueba con proveedores y NIF inventados.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, PostgreSQL real, migraciones 0001→0004 con bajada y subida) | **127 / 127** (106 anteriores + 21 nuevas) |
| Web (vitest) + tipos (tsc) + build de producción | **15 / 15**, sin errores |
| Recorridos en Chrome sobre base vacía: F0.1, F1.2+F2, F0.2 y F5.0 | **11 + 11 + 13 + 12 = 47 / 47** |
| Copia de seguridad con justificantes de gasto | Válida; una copia sin los justificantes que menciona la base se marca **no válida** |

## Qué se ha comprobado

| Criterio | Prueba automática | Captura |
|---|---|---|
| La economía de un expediente solo la ve quien tiene acceso completo o Contabilidad/Dirección; Recepción cobra sin verla | `test_economia_visible_segun_rol`, `test_recepcion_cobra_…` | f50_02, f50_06 |
| Los importes los introduce una persona; nada se calcula; anular exige motivo y permiso | `test_importe_pactado_y_saldo_pendiente` | f50_06 |
| Cobro en efectivo entra en la caja de la sede; transferencia exige referencia | `test_recepcion_cobra_en_efectivo_y_entra_en_caja` | f50_02 |
| Solo Contabilidad confirma o anula cobros y anota el nº de factura del programa homologado | `test_solo_contabilidad_confirma_y_anula_cobros` | recorrido paso 6 |
| **Devoluciones (A-09)**: ATC registra, revisa y escala; el letrado informa sin decidir; solo Contabilidad aprueba/rechaza y paga; quien solicita no decide | `test_devolucion_atc_registra_contabilidad_decide`, `test_quien_solicita_no_decide` | f50_03 |
| No se aprueba una devolución mayor que lo cobrado y confirmado | `test_no_se_devuelve_mas_de_lo_cobrado` | — |
| Caja por sede: solo la propia sede; no se saca más de lo que hay; arqueo con diferencia exige motivo y deja ajuste | `test_caja_arqueo_con_diferencia_exige_motivo` | f50_02 |
| Resumen económico solo para Dirección y Contabilidad | `test_resumen_solo_direccion_y_contabilidad` | — |
| Reglas en la base de datos aunque se salte la API (sin borrados, importes positivos, misma entidad) | `test_reglas_en_base_de_datos` | — |
| **Gastos**: la lectura en el servidor propone fecha, NIF, proveedor, total e IVA con su confianza; la persona confirma | `test_lectura_propone_y_la_persona_confirma`, `test_parser_de_tickets` | f50_01 |
| Un mismo justificante no se presenta dos veces (sin revelar el gasto ajeno) | `test_justificante_duplicado_rechazado` | — |
| Solo JPG, PNG o PDF reales (por su firma, no por la extensión) | `test_formato_no_admitido` | — |
| Nadie ve gastos ajenos ni se revisa a sí mismo; ver un justificante queda auditado | `test_gastos_ajenos_y_autorrevision_prohibidos` | — |
| Contabilidad devuelve con motivo, la persona corrige y reenvía | `test_contabilidad_devuelve_con_motivo…` | — |
| Gasto en efectivo descuenta de la caja; anularlo lo repone; aprobado queda conciliado con la caja | `test_efectivo_descuenta_de_la_caja…` | — |
| Tarjeta: solo la del titular; extracto CSV sin duplicar al reimportar; propone el ticket; importe distinto no concilia; cargo sin justificante queda señalado | `test_tarjeta_de_empresa_y_extracto` | f50_04 |
| Resumen mensual por persona, sede, concepto y forma de pago; exportación auditada | `test_resumen_mensual_y_exportacion` | f50_05 |
| Sin motor de lectura instalado: se dice y se rellena a mano (no se simula) | `test_sin_motor_de_lectura_se_rellena_a_mano` | — |

## Fallos encontrados y corregidos durante esta entrega
- Los totales salían como texto (suma decimal de PostgreSQL): ahora son enteros en céntimos.
- Un líder podía haber informado devoluciones de expedientes de otra rama: el informe jurídico exige acceso completo al
  expediente.
- Recorrido: los importes usan espacio no separable antes de «€»; el selector «Tarjeta» coincidía con una opción de
  «Forma de pago».

## Límites conocidos
- **No hay facturación fiscal**: el sistema no emite facturas ni aplica criterios de IVA, honorarios o suplidos
  (D-05, D-07, D-16, D-18, D-25). Solo guarda el número de la factura emitida en el programa homologado.
- **Lectura de tickets**: con tickets impresos y PDF con texto es fiable; con fotos torcidas o arrugadas acierta
  menos. Por eso todo se confirma. Para mejorarla se puede conectar un servicio de IA aprobado (decisión T-20).
- **Extracto bancario**: formato CSV genérico (`fecha;concepto;importe;tarjeta`). El formato real de su banco se
  añadirá cuando Contabilidad facilite un extracto de ejemplo anonimizado (T-19).
- **Móvil**: la subida desde el móvil funciona cuando el sistema esté alojado en un servidor accesible (T-02). Hoy
  solo funciona en el ordenador donde está instalado.
- No probado aquí: la imagen Docker con Tesseract (el entorno de construcción no tiene Docker).
