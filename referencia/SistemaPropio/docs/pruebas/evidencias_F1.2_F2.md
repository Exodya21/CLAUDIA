# Evidencias de pruebas · F1.2 (CRM) + F2.1 (expedientes) + F2.2 (tareas y agenda)

Ejecutadas el 02/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16). Datos ficticios. Salidas completas en
`resultado_pytest.txt` y `resultado_vitest.txt`.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, PostgreSQL real, migración 0001→0002 reversible) | **69 / 69** (49 de F0.1 siguen en verde + 20 nuevas) |
| Web (vitest) + tipos (tsc) + build de producción | **10 / 10**, sin errores |
| Recorrido F0.1 en Chrome sobre base **vacía** | **11 / 11** |
| Recorrido F1.2 + F2 en Chrome sobre base **vacía** | **11 / 11** |
| Migración 0002 aplicada sobre una base con datos de F0.1, revertida y reaplicada | Correcto |
| Carga incremental de datos (semilla) ejecutada dos veces sobre base existente | Idempotente |

## Pruebas de aceptación

| Prueba | Criterio | Evidencia automática | Captura | Estado |
|---|---|---|---|---|
| **AT-05** Origen CRM | No se guarda un lead sin origen; UTM registrado | `test_at05_sin_origen_no_se_guarda` (sin origen, origen inventado y TikTok/Google Ads sin campaña → 422; UTM guardado) | f2_02 | ✅ |
| **AT-06** Conversión | Lead conserva la trazabilidad hasta el expediente | `test_at06_lead_a_expediente_trazable` (lead → expediente, lead convertido con código, embudo +1, recepción ve solo metadatos, no se reutiliza) | f2_04, f2_08 | ✅ parcial: cita pagada e ingresos llegan con F1.3 y F5 |
| **AT-15** Código de expediente | Dos expedientes del mismo cliente: IDs y códigos distintos, vinculación opcional | `test_at15_*` (consecutivos, relación, sin duplicar), `test_relacion_no_revela_expedientes_de_otra_rama` | — | ✅ |
| **AT-16** Cambio de fases | Solo el rol designado; queda registrado; las tareas persisten | `test_at16_*` (encargo obligatorio, asesor 403 en «resuelto» auditado, líder con motivo, historial inmutable, tareas intactas) | f2_04, f2_07 | ✅ |
| **AT-19** Alerta de plazo | La fecha jurídica queda pendiente hasta su validación; interna y legal separadas | `test_at19_*`, `test_quien_propone_no_valida` | f2_04, f2_06 | ✅ |
| **AT-20** Tarea pospuesta | Exige motivo, responsable y fecha nueva; traza de la fecha previa | `test_at20_*` | — | ✅ |
| Q-6.23 | No se modifican tareas ajenas | `test_q623_no_se_modifican_tareas_ajenas` | — | ✅ |
| I-074 | Detección de solapamientos | `test_agenda_solapes_y_orden` | f2_05 | ✅ |
| Q-2.8 | Seguimiento 24 h / 72 h / 7 días | `test_seguimiento_24h_72h_7d` | f2_03 | ✅ |
| Q-6.4 | Indicador de inactividad | `test_indicador_de_inactividad` (y se reinicia con actividad) | — | ✅ (umbral 30 días pendiente de T-11) |

## Recorrido F1.2 + F2 en navegador
1. Lead de TikTok Live sin campaña: rechazado (AT-05).
2. Lead registrado con origen y campaña, y marcado como contactado — `f2_02_lead_recepcion.png`.
3. Bandeja de seguimiento 24 h / 72 h / 7 días — `f2_03_seguimiento.png`.
4. Lead → expediente en preapertura con código consecutivo (AT-06).
5. La apertura exige confirmar el encargo; el asesor no ve fases jurídicas (AT-16).
6. Tarea con plazo legal propuesto: queda SIN VALIDAR (AT-19) — `f2_04_expediente_asesor.png`.
7. Aplazar exige motivo; la fecha anterior queda en el historial (AT-20).
8. Agenda semanal con solapamientos y tareas vencidas — `f2_05_agenda_asesor.png`.
9. Otro letrado valida el plazo propuesto (doble control) — `f2_06_validacion_lider.png`.
10. La fase «Resuelto» solo la ejecuta un perfil autorizado y con motivo — `f2_07_expediente_resuelto.png`.
11. Marketing ve el embudo y recibe 403 en expedientes — `f2_08_embudo_marketing.png`.

## Fallos encontrados y corregidos durante esta entrega
- Dirección no podía abrir expedientes: su pertenencia está en el departamento «Dirección» y la regla exigía coincidir con la rama. Corregido: el alcance de entidad no queda acotado a un departamento (test `test_at15_*`).
- La prueba de inactividad dependía del orden de ejecución; ahora comprueba también que la actividad reinicia el indicador.

## No probado (y por qué)
- **Imágenes Docker de esta versión**: el entorno de construcción no tiene Docker. En su Windows, `INICIAR.bat` reconstruye y aplica la migración 0002 al arrancar; es la primera ejecución real de ese camino.
- **Cita pagada** (estado `cita_pagada`): depende del módulo de Citas con pasarela en modo prueba (F1.3). La API responde «No disponible aún».

## Incidencia en la primera instalación en Windows (02/11/2026)
- **Síntoma**: tras actualizar, la web cargaba pero decía «No se puede contactar con la API».
- **Causa**: los datos ficticios de la agenda usan la zona horaria Europe/Madrid. La imagen Docker ligera de Python no incluye la base de zonas horarias del sistema, así que la carga de datos fallaba y la API no llegaba a arrancar.
- **Corrección**: el paquete `tzdata` pasa a ser dependencia de la API (zonas horarias propias, independientes del sistema).
- **Verificación**: simulada la situación exacta (base creada con la versión instalada F0.1 + sin zonas horarias del sistema) y aplicada la actualización: migración 0002 y datos nuevos correctos (23 leads, 12 tareas, 30 expedientes). 69/69 pruebas en verde.
