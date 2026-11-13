# Evidencias de pruebas · F4.1 (expediente de extranjería, fase 1)

Ejecutadas el 05/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Tesseract 5 con español, Chrome).
Datos ficticios: los pasaportes son imágenes generadas con el país «UTO» de la especificación OACI 9303 y números
con prefijo ZZ; los certificados son PDF con la marca «DOCUMENTO FICTICIO — SIN VALOR». Ningún dato real.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, PostgreSQL real, migraciones 0001→0005 con bajada y subida) | **142 / 142** (127 anteriores + 15 nuevas) |
| Web (vitest) + tipos (tsc) + build de producción | **15 / 15**, sin errores |
| Recorridos en Chrome sobre base vacía: F0.1, F1.2+F2, F0.2, F5.0 y **F4.1** | **47 + 10 = 57 / 57** |
| Copia de seguridad con documentos de expedientes | Válida (esquema 0005, `_documentos.tar`); sin el `.tar` se marca **no válida** |

## Qué se ha comprobado

| Criterio | Prueba automática | Captura |
|---|---|---|
| 14 trámites con su hoja oficial, fecha y base legal; todos «pendientes de validar» hasta que Legal Extranjería los apruebe | `test_catalogo_pendiente_de_validacion_y_solo_legal_lo_aprueba` | f41_06 |
| Un cambio en el catálogo crea versión nueva sin alterar los expedientes abiertos | `test_cambio_en_el_catalogo_crea_version_nueva_sin_tocar_expedientes` | — |
| El trámite se elige según la materia (nacionalidad ≠ extranjería) | `test_alta_de_tramite_por_materia` | — |
| **Lectura de pasaporte** en el servidor: MRZ con dígitos de control, tipo propuesto con confianza alta, caducidad; la persona confirma | `test_lectura_de_pasaporte_…`, `test_mrz_especimen_oaci_y_generada` | f41_02, f41_03 |
| Reparación de confusiones del OCR (O/0, I/1) solo si una única variante supera el control | `test_mrz_especimen_oaci_y_generada` | — |
| Avisos: documento caducado, titular distinto del cliente, archivo duplicado, pasaporte que caduca en < 90 días (T-22) | `test_avisos_caducado_titular_distinto_y_duplicado`, `test_bandeja_y_semilla` | f41_01, recorrido paso 4 |
| Rechazar exige motivo; retirar no borra (trigger impide DELETE) | `test_avisos_…` | — |
| Archivos cifrados en disco; ver o descargar queda auditado | `test_lectura_de_pasaporte_…` | — |
| Fases: no se salta pasos; «Presentado» con documentos que faltan exige motivo y guarda la lista; historial solo inserción | `test_fases_requerimiento_crea_tarea_sin_calcular_plazo` | recorrido paso 6 |
| **Requerimiento**: crea tarea de plazo para el letrado **sin fecha legal** (D-01, D-03) | ídem | f41_05 |
| Resolución favorable/desfavorable, recurso y cierre solo con `case.transition.legal`; denegación auditada | ídem | f41_07 |
| **Paquete Mercurio**: bloquea si falta lo obligatorio; PNG→JPG; ≤ 6 MB por archivo; índice y ficha de datos; descarga forzada registrada | `test_paquete_mercurio` | f41_04 |
| Permisos: Laboral 403 auditado, otra entidad 404, ATC sin paquete, Recepción sube pero no ve ni revisa | `test_permisos_por_departamento_y_entidad`, `test_recepcion_sube_pero_no_ve_ni_revisa` | recorrido paso 10 |
| Copia AT-29 incluye los documentos | `test_at29_copia_incluye_documentos_de_expedientes` | — |

## Límites conocidos (no se simulan)

- No hay presentación en Mercurio ni descarga de DEHú: el sistema prepara el paquete y el profesional presenta con
  su certificado (A-11, D-09). Fase 2 (extensión que **rellena** Mercurio, T-24) y fase 3 (notificaciones, LEMA y
  calendario de días hábiles, T-25 y T-26) pendientes.
- La lectura reconoce bien MRZ impresas y documentos con texto; fotos torcidas o con reflejos pueden necesitar
  indicar el tipo a mano (la interfaz lo pide).
- El recorrido F0.2 necesita una copia previa (`python -m app.ops.backup completa` o `COPIA_SEGURIDAD.bat`) en una base recién creada.

Resultado del recorrido: [`resultado_e2e_recorrido_f41.txt`](resultado_e2e_recorrido_f41.txt).
