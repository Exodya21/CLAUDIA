# Evidencias F5.4 Contabilidad: proveedores, tesorería y cierre del mes (09/11/2026)

Origen: manual de Contabilidad de Dirección (DR-CON-1 … DR-CON-8) en
[`plan_motores_direccion.md`](../producto/plan_motores_direccion.md). Datos FICTICIOS: 5 proveedores «Demo», facturas
generadas por el propio sistema (`app/accounting/invoices.invoice_pdf`), IBAN de la entidad inexistente 9999 con
dígitos de control válidos (`demo_iban`). Ninguna factura, CIF ni cuenta es real.

## Qué cubre y qué no
| Requisito | Estado |
|---|---|
| DR-CON-1 Lectura y clasificación | Facturas recibidas (subida manual) y nóminas (F5.3). **Pendiente**: entrada por correo (T-48) |
| DR-CON-2, DR-CON-3 Conciliación y cobros | F5.1/F5.2; ahora también **pagos a proveedores y remesas** |
| DR-CON-4 Proveedores y facturas | **Hecho**: alta con CIF/IBAN comprobados, lectura, duplicados, validación, centro de coste, vencimientos y avisos |
| DR-CON-5 Coste de personal | **Hecho**: desde las nóminas confirmadas por RRHH, por actividad y oficina, agrupado si hay menos de 3 personas (T-53) |
| DR-CON-6 Asientos | **Bloqueado** hasta el plan de cuentas de la gestoría (T-40). En pantalla: «No disponible aún» |
| DR-CON-7 Tesorería y pagos | **Hecho**: saldos, previsión, remesas con doble firma, fichero SEPA; el sistema nunca ordena transferencias |
| DR-CON-8 Cierre del día 5 | **Hecho**: cuadro de mando, comparación, desviaciones, pendientes, fiabilidad, revisión y aprobación, CSV |

## Resultado de las pruebas
- API: **234/234** (`resultado_pytest.txt`), 10 nuevas en `test_f54_contabilidad.py`. Migración `0011` probada arriba → abajo → arriba.
- Web: `tsc` sin errores, vitest **19/19**, `next build` correcto.
- Recorridos e2e sobre base recién sembrada (con copia de seguridad previa para f02): recorrido 11, f2 11, f02 13, f41 10,
  f42 10, f43 11, f50 12, f51 9, f52_f53 10, f23 10, **f54 12** → **119/119 pasos**.

## Criterios de aceptación
| Criterio | Prueba | Captura |
|---|---|---|
| Proveedores con CIF/NIF e IBAN comprobados (letra de control y módulo 97); IBAN cifrado y siempre enmascarado | `test_proveedores_validan_cif_e_iban` | f54_03 |
| La lectura de la factura **propone** número, CIF del emisor (no el del despacho), fechas, base, IVA de la factura, retención, total e IBAN; confianza alta/media/baja; alta rápida del proveedor si no existe | `test_factura_se_lee_y_se_registra_sin_duplicados`, paso 1 | f54_01 |
| Solo se registra si base + IVA − retención = total (también en la base de datos); **el sistema no calcula el IVA** | paso 2 | f54_01 |
| Duplicados: el mismo archivo se detecta al leerlo; mismo proveedor, importe y fecha → solo con explicación | `test_factura_se_lee…`, paso 3 | f54_02 |
| Validar o rechazar con motivo; actividad, oficina y centro de coste | `test_validar_o_rechazar_factura_recibida`, paso 4 | f54_03 |
| Avisos del agente: factura sin validar (2 días), que vence en 7 días o vencida, proveedor mensual sin factura (desde el día 10), cierre del mes (desde el día 5) | `test_agente_avisa_y_propone_cierre` | f54_05 |
| Previsión: vencido, 7, 30, 60, 90 días y sin vencimiento; bancos + cajas − pagos a 30 días | paso 5 | f54_04 |
| Remesa: la propone Contabilidad; **dos firmas de personas distintas** de Dirección; quien propone no firma y nadie firma dos veces (API y base de datos) | `test_remesa_con_doble_autorizacion_y_fichero_sepa`, pasos 5–7 | f54_04, f54_05, f54_06 |
| «No autorizar» con nota libera las facturas para otra remesa | `test_remesa_rechazada_libera_facturas` | — |
| Fichero SEPA pain.001.001.03 con los IBAN completos; lo descarga Contabilidad y lo sube una persona a la banca | `test_remesa_con_doble…`, paso 7 | f54_06 |
| El cargo de la remesa en el extracto se concilia (regla «remesa») y marca las facturas como **pagadas** | `test_cargo_de_la_remesa_en_el_banco_paga_las_facturas` | — |
| Cuadro de mando por actividad (laboral, extranjería, compartida, sin asignar) y oficina; mes anterior y desviaciones ≥ 15 %; coste de personal agrupado si < 3 personas sin permiso de salarios | `test_cuadro_de_mando_por_actividad_y_oficina` | f54_07, f54_08 |
| Cierre: Contabilidad prepara (cifras congeladas con huella) y revisa (nota obligatoria si hay pendientes); recalcular crea una revisión nueva y la anterior queda «sustituida»; Dirección aprueba y ya no cambia; CSV para la gestoría | `test_cierre_del_mes_preparar_revisar_aprobar`, paso 8 | f54_07, f54_08 |
| Nada se borra: proveedores, facturas, remesas, firmas, líneas y cierres | `test_nada_se_borra` | — |
| Sin permiso: Contabilidad no aparece y la API deniega con auditoría | pasos 9 y `_need` en los tests | — |

## Corrección encontrada durante las pruebas
La lista de pendientes (`components/proposals.tsx`) recargaba en bucle cuando el departamento contaba los pendientes
(Contabilidad, Recepción, RRHH): unas 5.000 peticiones en un recorrido y botones que a veces no respondían. Se corrigió
guardando el contador en una referencia; ahora son 7 peticiones en el mismo recorrido.

## Decisiones
T-53 (coste de personal agrupado), T-54 (quién firma las remesas), T-55 (IBAN completos cifrados), T-56 (límites y
calendario de pagos) en [`decisiones.md`](../producto/decisiones.md). Siguen abiertas T-40 (plan de cuentas) y T-48
(buzón de facturas).
