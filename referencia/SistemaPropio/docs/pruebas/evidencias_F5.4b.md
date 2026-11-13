# Evidencias F5.4b: rutina de trabajo de Contabilidad, informes periódicos y extractos en Excel (09/11/2026)

Petición de Dirección del 09/11/2026: «un sistema de trabajo para Contabilidad, así se mejora el trabajo, e informes
semanales, quincenales y mensuales». Elegido por la usuaria: **checklist en Contabilidad y tareas en la Agenda**;
informes **en pantalla, PDF y aviso por correo**. Ese mismo día se pidió además **importar extractos en Excel**.
Datos FICTICIOS.

## Qué se ha construido
- **Rutina de trabajo** (pestaña inicial de Contabilidad) con el calendario del manual de Dirección:
  - Cada día: extractos del día anterior y conciliaciones pendientes.
  - Cada lunes: facturas por validar, pagos de la semana, cierres de caja e informe semanal.
  - Días 1 y 16: informe quincenal.
  - Días 2, 3, 4 y 5: extractos de fin de mes, conciliar el mes, nóminas y facturas, y cierre provisional.
  - Día 7: aprobación del cierre e informe mensual.

  Cada paso tiene responsable (los asigna Dirección) y fecha objetivo. Se da por hecho **solo cuando el sistema lo
  comprueba** en los datos, y explica qué ha comprobado. Los pasos semanales, quincenales y mensuales crean su tarea en
  la **Agenda**, que se cierra sola. «No aplica» exige motivo. El cumplimiento se mide a tiempo, tarde o vencido, por
  persona.
- **Informes** semanal (lunes), quincenal (1–15 y 16–fin) y mensual (día 5). La rutina los genera sola y también se
  pueden generar a mano (versión nueva).
  - Contenido: cifras por actividad y oficina, comparación con el periodo anterior, tesorería, previsión de pagos,
    remesas, pendientes, fiabilidad y cumplimiento de la rutina.
  - Formato: foto inmutable con huella; en pantalla, PDF y CSV.
  - Aviso: correo **sin cifras** a quien puede leer Contabilidad.
  - Revisión: Dirección los marca como revisados desde sus pendientes.
- **Extractos en Excel**: `.xlsx`, `.xls` (Excel 97-2003) y el «`.xls`» que en realidad es una página HTML (lo que
  descargan muchos bancos). La cabecera se busca aunque haya filas de título y se admite Importe o Cargo/Abono. La
  cuenta se comprueba con el IBAN del título. Una línea ilegible se informa y no se importa.

- **Comprobar sin importar** (botón junto a «Importar extracto»): lee el archivo en memoria y muestra el formato, las
  columnas reconocidas, el número de movimientos, el periodo, los abonos y cargos, el cuadre de saldos, la cuenta del
  archivo, las líneas sin leer y los cinco primeros movimientos. **No guarda nada**, ni el archivo ni los movimientos.
  La auditoría registra solo que se comprobó, sin el contenido. Sirve para probar el formato de un extracto real en
  una instalación de prueba.

- **Lectura de facturas recibidas, versión 2** (petición del 09/11/2026: «no ha podido leer» tres facturas reales).
  - **Las facturas reales se usaron solo para ver su FORMATO**, sin guardarlas ni copiar sus datos. Las pruebas usan
    textos ficticios con la misma forma: billete de transporte «Factura simplificada», minuta escaneada con OCR
    defectuoso y minuta con el bloque del cliente antes que el emisor.
  - Etiquetas: «Nº/N°/n* factura», «Fecha emisión», fecha en letra («Sevilla, 5 de noviembre de 2026»), «Base
    imponible EUR», «Importe IVA», «I.V.A. 21 % sobre…», «Total, Honorarios», «Líquido a mi favor», IRPF y total en
    la línea siguiente.
  - NIF/CIF con puntos y guiones; IBAN con espacios o guiones; nombre del proveedor propuesto (razón social, «Fdo.:»
    o membrete).
  - El CIF del despacho se descarta (T-59).
  - PDF escaneado con capa de texto mala: se vuelve a leer por OCR a 300 ppp y se queda la lectura que cuadra.
  - Si las etiquetas son ilegibles, se identifica qué cifra es la base, el IVA y la retención porque base + IVA −
    retención = total con un tipo habitual. Solo con cifras impresas; si la base no se lee, se deduce únicamente
    cuando IVA y retención la confirman a la vez. En ese caso se marca «compruébela» y la confianza baja a media.
  - Resultado en las tres facturas reales: las tres cuadran (dos con confianza alta y una media, la escaneada).

## Resultado de las pruebas
- API: **251/251** (`resultado_pytest.txt`). Nuevas: `test_f54b_rutina_informes.py` (7) y
  `test_f55_extractos_excel.py` (6). La migración `0012` se ha probado arriba → abajo → arriba.
- Web: `tsc` sin errores, vitest 19/19, `next build` correcto.
- Recorridos e2e sobre base recién sembrada: recorrido 11, f2 11, f02 13, f41 10, f42 10, f43 11, f50 12, f51 9,
  f52_f53 10, f23 10, f54 12, **f54b 9** → **128/128 pasos** (`resultado_e2e_*.txt`).

## Criterios de aceptación
| Criterio | Prueba | Captura |
|---|---|---|
| Pasos del día, la semana, la quincena y el mes, con responsable, fecha y comprobación explicada; no se duplican | `test_rutina_crea_pasos_con_responsable_y_tarea`, paso 1 | f54b_01 |
| Pasos no diarios en la Agenda del responsable; los diarios no (para no saturarla) | ídem, paso 2 | — |
| Un paso no se marca a mano: al validar las facturas, el sistema lo da por hecho y cierra su tarea | `test_paso_se_da_por_hecho…`, paso 2 | f54b_02 |
| «No aplica» con motivo (≥ 10 caracteres, también en la base de datos); un paso cerrado no vuelve atrás | `test_no_aplica…`, paso 3 | — |
| Responsables asignados por Dirección entre quienes tienen permiso para ese paso | `test_responsables…`, paso 6 | f54b_05 |
| Informes automáticos (lunes, 1, 5, 16) sin duplicar; versión nueva al regenerar; PDF y CSV | `test_informes_se_generan_solos…`, pasos 4–5 | f54b_03 |
| Correo de aviso sin cifras; Dirección revisa desde «Pendientes de decidir»; la rutina lo da por hecho | ídem | f54b_04 |
| Informe inmutable (cifras y revisión, base de datos); nada se borra | ídem, `test_nada_se_borra_rutina_informes` | — |
| Coste de personal agrupado en el informe mensual para quien no ve salarios | `test_informe_mensual_protege_salarios` | — |
| Lectura de facturas: simplificada con tabla de IVA; minuta escaneada con OCR defectuoso (base deducida y marcada); cliente antes que emisor (CIF del despacho descartado; si no se sabe, se ofrecen los candidatos); no inventa | `test_f55_lectura_facturas.py` (4) | — |
| «Comprobar sin importar» no guarda archivo ni movimientos; avisa de una cuenta distinta y de las líneas ilegibles; la auditoría no lleva contenido | `test_comprobar_sin_importar_no_guarda_nada` | — |
| Excel con título, fechas de Excel y saldos; .xls con Cargo/Abono y orden inverso; .xls en HTML; cabecera desconocida rechazada; cuenta equivocada rechazada | `test_f55_extractos_excel.py`, paso 3b | f54b_06 |

## Decisiones
T-57 (calendario de la rutina), T-58 (destinatarios y correo de los informes) y T-39 (formatos de extracto,
actualizada) en [`decisiones.md`](../producto/decisiones.md). Si el Excel de un banco real usa otros nombres de columna,
el error indica cuáles faltan: basta enviar **solo la fila de cabecera**, sin movimientos.
