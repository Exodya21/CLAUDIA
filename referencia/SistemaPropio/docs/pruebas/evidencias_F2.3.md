# Evidencias de pruebas · F2.3 Portal del cliente y conversaciones por expediente (M12 fase 1)

Ejecutadas el 06/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Chrome). **Solo datos ficticios.**
Decisión T-31 (Dirección, 06/11/2026): portal propio, sin depender de WhatsApp. Diseño: ADR-0009.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, migraciones 0001→0007 con bajada y subida) | **191 / 191** (174 anteriores + 17 nuevas en `test_f23_portal_comunicaciones.py`) |
| Web (vitest) + tipos + build de producción | **18 / 18** |
| Recorridos en Chrome: F0.1, F1.2+F2, F0.2, F4.1, F4.2, F4.3 y **F2.3** | **11 + 11 + 13 + 10 + 10 + 11 + 10 = 76 / 76** (F5.0 no cambia y no se repitió) |

## Qué se ha comprobado

| Criterio | Prueba | Captura |
|---|---|---|
| Invitar al portal solo con un correo que esté en la ficha; mensaje de bienvenida; la invitación no se duplica | `test_invitacion_solo_con_correo…` | f23_07 |
| Pedir código no revela quién es cliente; el código se guarda solo como hash | `test_pedir_codigo_no_revela…` | f23_02 |
| Código anulado tras 5 intentos fallidos | `test_codigo_incorrecto_caduca…` | — |
| Condiciones obligatorias (consentimiento registrado); la sesión del cliente no abre nada del equipo ni al revés | `test_condiciones_obligatorias_y_sesiones_separadas`, recorrido paso 9 | f23_02 |
| El cliente solo ve lo suyo: sin notas internas ni mensajes ocultos; otro cliente → 404 auditado | `test_cliente_solo_ve_lo_suyo…`, recorrido paso 4 | f23_04 |
| Nada se borra (trigger) y los textos se guardan cifrados | `test_nada_se_borra…` | — |
| Lista de documentos que faltan del trámite; el cliente envía uno «para la lista»; el equipo lo pasa al expediente y se lee como cualquier documento | `test_pendientes_del_tramite…`, recorrido pasos 4–5 | f23_03, f23_04 |
| Permisos reales: asesora sin asignación 403, Recepción 403, otra entidad 404, Laboral no ve Extranjería, urgentes solo Líder/Dirección y siempre con plantilla | `test_permisos_reales_en_el_servidor` | — |
| Urgente con plazo legal sin validar → rechazado; con plazo validado o señalamiento → fecha y hora de Madrid desde la tarea; correo sin contenido; confirmación única | `test_urgente_solo_con_fecha_validada…`, recorrido pasos 6–7 | f23_05, f23_06 |
| Urgente sin confirmar en 24 h → una sola tarea de llamada | `test_urgente_sin_confirmar_en_24h…` | — |
| Importante sin abrir en 48 h → marcado | `test_importante_sin_abrir_48h…` | — |
| Mensajes del día a día: como mucho un correo por conversación y hora | `test_correos_del_dia_a_dia…` | — |
| Corrección 15 minutos con versión anterior guardada (equipo y cliente); los avisos con plantilla no se corrigen | `test_correccion_15_minutos…`, `test_aviso_con_plantilla_no_se_corrige` | — |
| Exportación PDF con huella SHA-256 estable; alcance «cliente» sin notas internas; auditada | `test_exportacion_con_huella_y_alcance`, recorrido paso 8 | — |
| Cola de envíos idempotente con reintentos; con correo configurado el código ya no aparece en pantalla | `test_cola_de_envios_idempotente…` | — |
| Bloquear el acceso cierra las sesiones y deja de dar códigos | `test_bloquear_cierra_sesiones…` | f23_07 |

## Límites conocidos (no se presentan como hechos)
- **Correo**: sin `SMTP_HOST` no sale ningún correo (estado «no configurado» visible en la ficha). En desarrollo el
  código se muestra en pantalla; en producción no (T-33).
- **SMS, notas de voz con transcripción, centralita e importación de WhatsApp**: fase 2 (T-35, opciones A/B/C de
  telefonía del documento de diseño). No hay botones que simulen estas funciones.
- **Contactos autorizados** (familiar, empresa): pendiente; hoy solo accede la propia persona.
- **Tiempo real**: la conversación se actualiza cada 15–20 s; no hay indicador de «escribiendo».
- **Horario de atención** visible para el cliente: pendiente de que Dirección fije el texto.
- Textos al cliente pendientes de validar (T-32).
