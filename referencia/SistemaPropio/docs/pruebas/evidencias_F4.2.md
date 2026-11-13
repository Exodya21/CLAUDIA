# Evidencias de pruebas · F4.2 (ficha del modelo EX y extensión que rellena Mercurio)

Ejecutadas el 05/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Chrome con la extensión cargada).
Datos ficticios. La «página de Mercurio» del recorrido es una **página de prueba inventada** servida en la dirección
de Mercurio mediante interceptación de Playwright (no sale nada a Internet).

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, migraciones 0001→0006 con bajada y subida) | **153 / 153** (142 anteriores + 11 nuevas) |
| Web (vitest: 3 pruebas nuevas de la extensión) + tipos + build | **18 / 18** |
| Recorridos en Chrome sobre base vacía: F0.1, F1.2+F2, F0.2, F5.0, F4.1 y **F4.2** | **47 + 10 + 10 = 67 / 67** |
| Lectura de MRZ sobre 40 pasaportes ficticios (PNG y JPEG) | 32 correctas, 8 marcadas «MRZ con errores» para revisión manual, **0 aceptadas con un número erróneo** |

## Qué se ha comprobado

| Criterio | Prueba | Captura |
|---|---|---|
| 16 modelos EX con mapa de campos; NIE en 3 casillas y fecha en 3; la firma queda en blanco | `test_dieciseis_modelos_con_mapa_y_pdf_relleno`, `test_mapa_de_campos_reproducible` | — |
| La ficha propone (cliente, pasaporte leído, despacho, fecha) y solo guarda lo confirmado; validación de NIE, fechas, opciones | `test_ficha_propone_desde_pasaporte_y_despacho…` | f42_01 |
| La auditoría guarda las claves cambiadas, nunca los valores | ídem | — |
| Modelos sin PDF (EX-26) usan la ficha general de Mercurio | `test_ficha_general_para_modelos_sin_pdf` | — |
| Vista previa del EX con domicilio compuesto | `test_borrador_pdf_y_permisos`, `test_domicilio_compuesto_en_el_pdf` | — |
| Permisos: Laboral 403 auditado, otra entidad 404, Recepción no ve ni genera códigos; datos del despacho solo Dirección/Líder | `test_borrador_pdf_y_permisos`, `test_datos_del_despacho…`, `test_codigo_para_extension` | — |
| Código: sin sesión, caduca, se agota, inventado → 404 auditado; en BD solo el hash | `test_codigo_para_extension` | f42_02 |
| Extensión: trae la ficha con el código; rellena pestaña a pestaña; listas dependientes; no sobrescribe | `recorrido_f42.mjs` | f42_03…f42_06 |
| Extensión: no pulsa ningún botón, no marca «NO CONSIENTO», no elige el supuesto, no toca contraseñas ni «Persona tutelada» | `recorrido_f42.mjs`, `extension_mercurio.test.ts` | f42_05 |

## Ajuste con Mercurio real (05/11/2026, extensión 0.2.0)
Primera prueba del despacho en Mercurio (EX-10, datos inventados): la versión 0.1 reconocía las etiquetas pero tomaba
la pestaña equivocada (las pestañas de Mercurio no usan los marcadores estándar) y no rellenó nada. Con el diagnóstico
(estructura sin valores) se ve que Mercurio usa identificadores fijos por apartado (`extPasaporte`,
`preNombrePresentador`, `notEmailNotificacion`…). La versión 0.2 reconoce por identificador, rellena todas las
pestañas con un clic, normaliza el móvil a 9 cifras y el N.I.E. sin guiones, ignora los controles auxiliares
(`…-ts-control`, `…Aux`) y no toca `chkConsientoConsultaDocumentos` («NO CONSIENTO») ni los supuestos (`datosForAut`).
La página de prueba usa ahora esos identificadores; pruebas unitarias en `extension_mercurio.test.ts`.

## Pendiente (no se simula)
- Ver el relleno completo funcionando en Mercurio real con la versión 0.2 (T-27). Campos con buscador (CNAE, CNO) se rellenan a mano.
- El supuesto de «Tipo de autorización» lo marca el profesional; la extensión solo lo recuerda.
