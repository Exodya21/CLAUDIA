# Evidencias F5.2 Recepción y F5.3 RRHH (08/11/2026)

Origen: plan de Recepción (DR-REC) y guion de RRHH (DR-RH) de Dirección, en
[`plan_motores_direccion.md`](../producto/plan_motores_direccion.md). Datos FICTICIOS: clientes «Demo», 5 fichas de
empleados inventadas con sus nóminas generadas por el propio sistema (`app/hr/samples.py`).

En la misma ronda, a petición de la usuaria, **cada pendiente aparece en su departamento** (Contabilidad, Comunicaciones,
expediente, Recepción, RRHH y un resumen en Inicio) y la configuración de agentes pasa a **Administración → Agentes
automáticos**. Desaparecen del menú «Agentes» y «Bandeja de propuestas».

## Resultado de las pruebas
- API: **224/224** (`resultado_pytest.txt`): 8 nuevas de Recepción (`test_f52_recepcion.py`) y 9 de RRHH (`test_f53_rrhh.py`).
- Web: `tsc` sin errores, vitest 18/18, `next build` correcto.
- Recorridos e2e sobre base recién sembrada: recorrido 11, f2 11, f02 13, f41 10, f42 10, f43 11, f50 12, f51 9,
  **f52_f53 10**, f23 10 → **107/107 pasos**.

## Recepción (F5.2)
| Criterio | Prueba | Captura |
|---|---|---|
| Consulta cobrada sin expediente; provisión y servicio solo con expediente; transferencia y Bizum con referencia | `test_consulta_sin_expediente…`, `test_cobro_a_expediente…` | f52_01 |
| Justificante numerado por sede y año (REC-BCN-2026-000001), «NO ES UNA FACTURA», idéntico al volver a descargarlo, inmutable | `test_numeracion_correlativa…` | f52_01 |
| Cobro que parece repetido (cliente, importe y forma en 2 días, o misma referencia): aviso y solo se guarda con explicación; Contabilidad decide y «es repetido» lo anula | `test_cobro_repetido…`, pasos 2 y 5 | f52_02, f52_04 |
| Caja del día: saldo inicial, entradas, salidas, saldo según registros; cierre con diferencia explicada, uno por día | `test_cierre_del_dia…`, paso 3 | f52_03 |
| Cierre validado por un responsable distinto de quien contó (también en la base de datos); con diferencia exige nota; rechazado → se vuelve a contar | `test_cierre_del_dia…`, `test_quien_cuenta_no_valida…` | f52_04 |
| Cada sede, su caja: Recepción de Madrid no ve Barcelona; Contabilidad y Dirección ven todas | `test_sede_ajena_y_permisos`, paso 4 | — |
| Recepción ve lo pendiente de cobro de un expediente (solo importes) | `test_sede_ajena_y_permisos` | f52_01 |
| Informe diario y semanal por sede: cobros por concepto y forma de pago, anulados, repetidos, cierre | `test_informe_diario_por_sede`, paso 6 | f52_05 |

## RRHH (F5.3)
| Criterio | Prueba | Captura |
|---|---|---|
| 5 fichas (Barcelona, Madrid, Valencia, Colombia) con sede, categoría, antigüedad, jornada, salario y situación | `test_plantilla_y_permisos…` | f53_01 |
| Permisos por función: RRHH y Dirección todo; el líder ve a su equipo sin salario; cada persona su ficha y sus nóminas; Recepción y Contabilidad nada; los datos de personal no aparecen como clientes | `test_plantilla_y_permisos…` | — |
| Bajas médicas: solo RRHH y la propia persona; el calendario del líder dice «ausencia» | `test_baja_medica_solo_la_ve_rrhh` | — |
| Alta con aviso de duplicados, letra del DNI comprobada, temporal con fecha de fin; cambios con versión y motivo; salario oculto en la auditoría | `test_alta_valida_y_avisa_duplicados` | — |
| Nómina leída (periodo, devengado, deducciones, líquido, titular); RRHH la confirma solo si cuadra; el mismo archivo no se duplica | `test_nomina_se_lee…`, paso 7 | f53_01 |
| Vacaciones con saldo (no deja pedir más de lo que queda), sin solapes propios, aviso de coincidencias en el equipo; decide el líder del departamento o RRHH, nunca uno mismo | `test_vacaciones_saldo…`, paso 10 | f53_04 |
| Avisos con persona, motivo, fecha y responsable: contrato que vence, fin de prueba, contrato que falta, nómina que falta, diferencia ≥ 10 %, solicitudes sin responder; aprobar crea la tarea | `test_avisos_de_vencimientos…`, paso 8 | f53_02 |
| Resumen mensual de nóminas para la gestoría con diferencias; el sistema no calcula nóminas | `test_resumen_de_nominas…`, paso 9 | f53_03 |
| Importación CSV: previsualiza nuevas, duplicadas y con errores; solo crea las nuevas | `test_importacion…` | — |
| Nada se borra | `test_nada_se_borra` | — |

## Cómo repetir
```bash
cd apps/web
NOMINA=/ruta/nomina_ficticia.pdf node e2e/recorrido_f52_f53.mjs ../../docs/pruebas/capturas
# NOMINA: app.hr.samples.payslip_pdf("Despacho Demo …", "Daniel Ortiz Prueba", "Titulado superior", 2026, 7, 216667, 39000)
```

## Límites conocidos (no se presentan como hechos)
- Citas y llegada de clientes a recepción (DR-REC-1, 2) y el agente que clasifica llamadas y mensajes (DR-REC-6, 7): F5.5.
- Control horario (DR-RH-3, T-41), formación y exámenes (DR-RH-7, D-24), cuadro de mando de plantilla (DR-RH-8): pendientes.
- Festivos por sede (T-49) y días de vacaciones por convenio (T-50): hoy se cuentan lunes a viernes con los días informados en la ficha.
- Formato real de exportación de MN Program (T-10): la importación usa columnas documentadas; se ajustará con un ejemplo anonimizado.
