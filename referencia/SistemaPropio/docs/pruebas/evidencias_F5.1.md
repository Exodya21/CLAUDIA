# Evidencias F5.1 — Agentes, bandeja de propuestas, banco y mensajes automáticos (08/11/2026)

Origen: documentos de Dirección del 08/11/2026 (transcritos y analizados en
[`plan_motores_direccion.md`](../producto/plan_motores_direccion.md)). La «Instrucción final» pedía empezar por una
prueba real de **conciliación bancaria de una cuenta** con una pantalla de importados, conciliados, pendientes y
errores. Todo con datos FICTICIOS: cuentas terminadas en 1111/2222/3333, extractos generados por el propio sistema
(solo en desarrollo), clientes «Demo».

> **Actualización 08/11/2026 (F5.2/F5.3):** los pendientes ya no están en una bandeja aparte: cada uno aparece en su
> departamento (Contabilidad → «Pendientes de decidir», Comunicaciones → «Mensajes por aprobar», el expediente, Recepción,
> RRHH; resumen en Inicio) y los agentes se configuran en Administración → «Agentes automáticos». El recorrido F5.1 ya
> navega así.

## Resultado de las pruebas
- API: **207/207** (`resultado_pytest.txt`), de ellas 16 nuevas en `tests/test_f51_agentes_banco.py`.
- Web: vitest 18/18; `tsc` sin errores; `next build` correcto.
- Recorridos e2e sobre base recién sembrada: recorrido 11, f2 11, f02 13, f41 10, f42 10, f43 11, f50 12,
  **f51 9**, f23 10 → **97/97 pasos**.

## Qué se comprueba
| Criterio | Prueba | Captura |
|---|---|---|
| Lectura de Norma 43, CAMT.053 y CSV (orden normal o inverso, formato español); una línea ilegible se informa y no se importa; XML con declaraciones se rechaza | `test_n43_lectura…`, `test_camt053_y_csv` | — |
| Saldo inicial + movimientos = saldo final; si no cuadra se marca y se lista en «Errores» (no se corrige solo); continuidad con el extracto anterior | `test_importacion_cuadra…`, `test_saldo_que_no_cuadra_se_marca` | f51_01 |
| Reimportar el mismo extracto: rechazado; extracto solapado: solo entran las líneas nuevas; extracto de otra cuenta: rechazado | `test_importacion_cuadra_y_no_duplica`, recorrido paso 2 | — |
| El agente propone con explicación (referencia, Bizum, TPV bruto − comisión = neto, importe y fecha) y deja excepciones (ingreso sin identificar, referencia sin cobro, traspaso sin pareja, cargo con categoría sugerida). **Nada se concilia solo** | `test_reglas_proponen_y_explican` | f51_02, f51_04 |
| Validar confirma el cobro (como «Confirmar cobro») y concilia a la vez la comisión del TPV; repetir la decisión: conflicto | `test_validar_confirma_cobro_y_cierra_comision`, pasos 3–4 | f51_02 |
| Rechazar exige motivo; el agente no vuelve a proponer lo mismo y deja una excepción para resolver a mano | `test_rechazar_pide_motivo_y_no_se_repite` | — |
| Conciliación manual solo con cuadre exacto; un ingreso de cliente no se «justifica» por categoría | `test_conciliacion_manual_cuadre_exacto`, paso 5 | f51_03 |
| Traspaso A → C: se concilian las dos caras y nunca cuenta como ingreso | `test_excepcion_aprobada_justifica_cargo_y_traspaso…`, paso 7 | f51_05 |
| Permisos: Recepción y asesores sin acceso (403 auditado); Dirección ve pero no concilia; cuenta de otra entidad 404 | `test_permisos_banco`, paso 9 | — |
| Nada se borra (`bank_*`, `agent_proposal`); el original del extracto se descarga idéntico; exportación CSV para la gestoría auditada | `test_nada_se_borra_y_exportacion` | — |
| Bienvenida al abrir el expediente (DR-PLT-1): propuesta a quien lleva el expediente (Contabilidad no la ve), sin duplicados, publicada al aprobar, trazada en `comm_dispatch` | `test_bienvenida_se_propone_sin_duplicar`, paso 8 | f51_06 |
| Aviso de conciliación con fecha, hora y **lugar** de la agenda; sin lugar → «falta un dato»; recordatorio a las 10:00 (Madrid) del día anterior; al aplazar se cancela lo viejo y se programa lo nuevo; al desistir se cancela todo | `test_avisos_de_fecha_y_recordatorio` | — |
| Modo automático solo en el agente de mensajes y solo por Dirección; envío como «Despacho» | `test_modo_automatico_solo_donde_se_permite` | — |
| Seguimiento a los 75 días sin mensajes del despacho, una sola vez | `test_seguimiento_75_dias` | — |
| Panel de agentes con límites, actividad y medición semanal | `test_panel_de_agentes_y_metricas`, paso 9 | f51_07 |

## Cómo repetir el recorrido
```bash
# base recién sembrada + API y web en marcha
cd apps/web && node e2e/recorrido_f51.mjs ../../docs/pruebas/capturas
# Los recorridos que suben archivos usan fixtures FICTICIOS generados al momento:
#   PASAPORTE: app.seed_immigration.passport_image("PRUEBA", "RECORRIDO", "ZZ1234567", …)
#   TICKET: tests/test_f50_gastos.ticket(...) con TOTAL 14,00 e IVA 21 % 2,43 y fecha de hoy
#   EXTRACTO: fecha;concepto;importe;tarjeta con «APARCAMIENTO FICTICIO;14,00;0042» y «RESTAURANTE SIN TICKET»
```
Nota: en esta ronda se corrigió el recorrido F4.1, que esperaba el texto antiguo «MRZ correcta: PRUEBA RECORRIDO»
(la pantalla muestra «PRUEBA, RECORRIDO» desde F4.3); no afectaba al funcionamiento.

## Límites conocidos (no se presentan como hechos)
- Formatos reales de cada banco: falta un extracto de ejemplo **anonimizado** (T-39).
- Sin plan de cuentas no se proponen asientos; solo exportación (T-40).
- Textos de las plantillas pendientes de validar (T-32); modo automático desactivado hasta el piloto (T-47).
- Recepción (F5.2), RRHH (F5.3), proveedores y tesorería (F5.4) y citas (F5.5) siguen «Pendiente» en el menú.
