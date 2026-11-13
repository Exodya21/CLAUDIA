# Evidencias de pruebas · F4.3 (lectura de documentos → ficha del formulario, incluido el empleador)

Ejecutadas el 05/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Tesseract y poppler locales, Chrome).
**Solo documentos FICTICIOS** generados por `app/immigration/samples.py` (copias en `docs/pruebas/muestras/`,
regenerables con `scripts/muestras_f43.py`): empresa «Construcciones Ficticias Demo SL», CIF B12345674, N.I.E.
Y7654321G, país «UTO». Los documentos reales que el usuario adjuntó en la conversación **no se usaron** ni se
guardaron en el repositorio.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, migraciones 0001→0006 con bajada y subida) | **174 / 174** (153 anteriores + 21 nuevas) |
| Web (vitest) + tipos + build de producción | **18 / 18** |
| Recorridos en Chrome: F0.1, F1.2+F2, F0.2, F4.1, F4.2 y **F4.3** | **11 + 11 + 13 + 10 + 10 + 11 = 66 / 66** (F5.0 no cambia y no se repitió) |

## Qué se ha comprobado

| Criterio | Prueba | Captura |
|---|---|---|
| NIE, DNI y CIF solo se aceptan si su letra o dígito de control es correcto | `test_validadores_de_documentos_espanoles` | — |
| El domicilio se descompone como lo pide Mercurio (tipo de vía, número, piso, letra, escalera, C.P., provincia por el C.P.) | `test_domicilio_se_descompone…` (3 casos) | — |
| Contrato con texto y **escaneado**: empresa, CIF, cuenta de cotización, CNAE, domicilio, centro de trabajo, puesto, código de contrato, retribución, representante y N.I.E. del trabajador | `test_contrato_texto_y_escaneado` | f43_01 |
| Padrón escaneado → domicilio completo; tasa 790-052 → NRC e importe; TIE → MRZ TD1 con N.I.E. | `test_padron_escaneado_tasa_y_tie` | f43_01 |
| Pasaporte en **PDF escaneado de varias páginas**: la MRZ se busca página a página (hasta 5) | `test_pasaporte_en_pdf_escaneado…` | — |
| MRZ: «Q» leído en lugar de «0» se corrige solo si el dígito de control lo confirma | `test_mrz_q_por_cero_en_el_numero` | — |
| Lo leído **solo pasa a la ficha cuando una persona marca el documento «válido»**, y la ficha solo vale cuando se guarda | `test_datos_leidos_solo_pasan…`, `recorrido_f43.mjs` | f43_02, f43_03 |
| Cada propuesta indica su origen («documento leído: Contrato de trabajo») | ídem | f43_02 |
| Dos documentos que se contradicen: se ve la otra versión; un documento que contradice un dato ya guardado se avisa y **no cambia nada** | `test_documentos_que_se_contradicen…` | — |
| Si la persona corrige el tipo, se vuelve a extraer con las reglas del tipo correcto | `test_tipo_corregido_vuelve_a_extraer…` | — |
| Tasa sin NRC visible → aviso «compruebe que la tasa está pagada» | ídem | — |
| Documento de **otra persona** (titular de la MRZ distinto del cliente): aviso y sus datos personales no se proponen | `test_documento_de_otra_persona…` | — |
| La auditoría no guarda lo leído (ni CIF ni N.I.E.) | `test_la_auditoria_no_guarda_lo_leido` | — |

## Correcciones tras la primera prueba del despacho con documentos reales (05/11/2026)
La prueba se hizo en el ordenador del despacho; aquí solo se vieron capturas de pantalla y **ningún documento real
se ha usado para programar ni para probar**. Problemas observados y corrección:

| Problema observado | Causa | Corrección | Prueba |
|---|---|---|---|
| Padrón: en Domicilio, Provincia y Municipio aparecía texto del certificado («Fecha alta…», «RESIDENCIA origen…», «aparecen en el día de la fecha…») | Padrón en formato de tabla: la etiqueta y su valor no van juntos | Se toma la línea que empieza por un tipo de vía (con la del C.P. si va debajo); provincia por el C.P.; **todo valor sin forma de dato se descarta** (`extract.sanitize`), también en lo ya leído | `test_padron_en_tabla…`, `test_datos_mal_leidos_ya_guardados…` |
| Ese texto erróneo tapaba el dato bueno de la ficha del cliente | La propuesta del documento se ponía por encima | Al descartarse, queda la de la ficha del cliente | ídem |
| Pasaporte completo (muchas páginas) sin leer | La MRZ solo se buscaba en las 5 primeras páginas y en vertical | Todas las páginas (hasta 40); si no aparece, giro según la orientación del texto y boca abajo | `test_pasaporte_completo_con_la_hoja_de_datos_girada…` (90° y 180°, página 8 de 9) |
| MRZ con un dígito borroso: no se aprovechaba nada | Todo o nada | Se usan las partes cuyo control cuadra (nunca el número si su control falla) | `test_mrz_con_un_control_fallido…` |
| 18 avisos «archivo subido más de una vez» | Se subieron los mismos archivos dos veces | El mismo archivo ya no se guarda dos veces; los duplicados antiguos se resumen en un solo aviso | `test_no_se_duplica_un_archivo…` |
| Documentos ya subidos con la lectura anterior | — | Botón **«Volver a leer»** (no cambia el estado ni el tipo confirmado) | `test_volver_a_leer_y_diagnostico…` |
| No sabemos cómo es el formato real de cada documento | No se pueden usar documentos reales | **«Diagnóstico de la lectura (sin datos)»**: las palabras del formulario quedan visibles; nombres, números y direcciones salen como XXX/999 | ídem, `recorrido_f43.mjs` (f43_04) |

## Revisión automática de la lectura (05/11/2026)
Para que el despacho no tenga que buscar los errores: en cada expediente, el apartado **«Revisión automática de la
lectura»** dice, documento por documento, qué se ha leído, qué falta, qué se ha descartado, si el pasaporte no tiene
zona MRZ (y en cuántas páginas se ha buscado), qué documentos se leyeron con una versión anterior (botón para
volver a leerlos todos) y qué datos importantes de la ficha siguen vacíos. El botón **«Copiar informe para Claude
(sin datos)»** copia ese resultado con el texto leído enmascarado (`GET /cases/{id}/reading-review`, auditado,
permiso `immig.document.review`). Prueba: `test_revision_automatica_de_la_lectura_sin_datos`, `recorrido_f43.mjs` (f43_05).

## Límites conocidos
- **Formatos**: las reglas siguen la estructura de los modelos públicos (contrato del SEPE, certificado de padrón,
  790-052, TIE). Un modelo distinto (p. ej. el padrón de otro ayuntamiento) puede leer menos campos: quedan vacíos
  y la persona los escribe. Mejorar el reconocimiento requiere ejemplos **anonimizados** (sin datos reales) de cada formato.
- **Vida laboral**: solo se reconoce el tipo y se toman los días cotizados y si hay alta; no se interpretan periodos
  ni se decide si cumple un requisito (eso lo valora el profesional).
- **CNAE/CNO** de Mercurio (listas con buscador) se eligen a mano.
- La **extensión** ya rellena por identificador los datos de la empresa (`emp…Empresa`: nombre, NIF, domicilio,
  representante). Puesto y retribución se reconocen por etiqueta; **cuenta de cotización, código de contrato y centro
  de trabajo están en la ficha pero en Mercurio se escriben a mano** hasta tener el diagnóstico (sin datos) de esa
  pestaña de Mercurio real (T-29). No se inventan identificadores de Mercurio.
- La retribución se propone como aparece en el contrato; si Mercurio exige solo cifras, la persona la ajusta.
