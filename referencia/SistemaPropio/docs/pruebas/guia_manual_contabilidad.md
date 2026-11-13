# Guía para probar Contabilidad a mano (F5.4 y F5.4b)

Solo datos ficticios. Facturas de prueba en `docs/pruebas/muestras/`:
`FICTICIO_factura_limpieza.pdf` (proveedor nuevo, 242,00 €) y `FICTICIO_factura_gestoria_con_retencion.pdf`
(proveedor existente, base 400 + IVA 84 − retención 60 = 424,00 €). Extracto en Excel:
`FICTICIO_extracto_cuenta_A_octubre.xlsx` (cuenta terminada en 1111, 4 movimientos).

## Antes de empezar
1. `DETENER.bat` → descomprimir el zip nuevo en la misma carpeta (sin borrar `.env`) → `INICIAR.bat`.
2. `REINICIAR_DATOS_DEMO.bat` para partir de los datos ficticios limpios (incluye el usuario nuevo «Socio Director»).
3. Abrir `http://localhost:3000` y elegir el usuario en la lista de acceso demo. Para cambiar de persona: «Cerrar sesión».

| Usuario demo | Papel en la prueba |
|---|---|
| Contabilidad (demo) | Registra facturas, propone remesas, descarga el SEPA, prepara y revisa el cierre |
| Dirección (demo) | Primera firma de la remesa, aprueba el cierre |
| Socio Director (demo) | Segunda firma de la remesa |
| Recepción Barcelona (demo) | Comprobar que NO ve Contabilidad |

## Pruebas
| # | Quién | Qué hacer | Qué debe pasar |
|---|---|---|---|
| 1 | Contabilidad | Proveedores y facturas → subir `FICTICIO_factura_limpieza.pdf` → «Leer factura» | Rellena número LF-2026-118, fechas, 200,00 / 42,00 / 242,00 y ofrece dar de alta el proveedor B66666660 con su IBAN |
| 2 | Contabilidad | Crear el proveedor; cambiar el total a 250,00 | Etiqueta roja «Las cifras no cuadran» y el botón se desactiva. Volver a 242,00 → se puede registrar |
| 3 | Contabilidad | Desmarcar «He comprobado…» y registrar | Queda «Por validar» |
| 4 | Contabilidad | Subir otra vez el mismo PDF y leerlo | Aviso «Este archivo ya está registrado» |
| 5 | Contabilidad | Subir `FICTICIO_factura_gestoria_con_retencion.pdf` | Reconoce el proveedor existente y la retención 60,00; total 424,00 |
| 6 | Contabilidad | Filtro «Por validar» → «Revisar» → elegir actividad y oficina → «Validar» | Pasa a «Validada» |
| 7 | Contabilidad | Proveedores → «Nuevo proveedor» con un CIF o IBAN inventado al azar | Lo rechaza (dígitos de control) |
| 8 | Contabilidad | Tesorería y remesas | Saldos, previsión (vencido, 7, 30, 60, 90 días) y la remesa REM-2026-0001 ya subida al banco |
| 9 | Contabilidad | Marcar facturas validadas → «Proponer remesa» | REM-2026-0002 «Pendiente de firmas»; Contabilidad NO tiene botón «Autorizar» |
| 10 | Dirección | Contabilidad → Pendientes de decidir → «Firma 1 de 2» → «Autorizar (mi firma)» | Firma registrada; en Tesorería ya no le aparece «Autorizar» (no puede firmar dos veces) |
| 11 | Socio Director | Tesorería → nota → «Autorizar» | Remesa «Autorizada» |
| 12 | Contabilidad | «Descargar fichero SEPA» → «Ya la he subido al banco» | Se descarga un XML; la remesa queda «Subida al banco». Nada se envía al banco solo |
| 13 | Contabilidad | Banco y conciliación → Cuenta A → «Importar extracto FICTICIO de prueba» | Aparece el cargo «REMESA TRANSFERENCIAS REM-2026-0001»; al validar la propuesta, las facturas de Alquiler y Energía pasan a «Pagada» |
| 14 | Contabilidad | Cierre del mes → mes anterior → «Preparar el cierre» → «Recalcular» | Revisión 1 «Sustituido», revisión 2 vigente |
| 15 | Contabilidad | Escribir nota y «Dar por revisado» | Pendiente de aprobación de Dirección |
| 16 | Dirección | Cierre del mes → «Aprobar cierre» → «Exportar CSV» | «Aprobado por Dirección», ya no se puede recalcular; CSV descargado |
| 17 | Recepción Barcelona | Abrir `/contabilidad` | «Su rol no tiene acceso a Contabilidad» |
| 18 | Dirección | Ajustes → Auditoría (filtro «Solo denegaciones» para el intento de Recepción) | Constan registro, firmas, descargas del SEPA y del CSV, y el intento denegado |


## Rutina de trabajo, informes y Excel (F5.4b)
| # | Quién | Qué hacer | Qué debe pasar |
|---|---|---|---|
| 19 | Contabilidad | Entrar en Contabilidad | Se abre «Rutina de trabajo»: pasos de hoy, de la semana y del cierre del mes, cada uno con responsable, fecha y «Comprobación: …» |
| 20 | Contabilidad | Agenda | Aparecen las tareas «Rutina Contabilidad · …» de la semana y del mes |
| 21 | Contabilidad | Validar la factura de Telefonía (prueba 6) → volver a Rutina → «Ver lo hecho» | «Validar las facturas recibidas» pasa a **Hecho** solo, con la evidencia; su tarea de la Agenda queda completada |
| 22 | Contabilidad | En un paso diario, «No aplica…» con un motivo de menos de 10 letras | No deja confirmar; con motivo largo queda «No aplica» con su nombre |
| 23 | Contabilidad | Banco y conciliación → Cuenta A → subir `FICTICIO_extracto_cuenta_A_octubre.xlsx` → «Importar extracto» | Se importan 4 movimientos y el saldo cuadra (10.000,00 → 9.677,60) |
| 24 | Contabilidad | Subir el mismo Excel en la Cuenta B | Lo rechaza: el extracto es de la cuenta terminada en 1111 |
| 25 | Contabilidad | Informes → «Semanal», un día de la semana pasada → «Generar ahora» | Informe con cifras por oficina y actividad, comparación, pendientes, pagos y cumplimiento de la rutina; botones PDF y CSV |
| 26 | Dirección | Contabilidad → Pendientes de decidir | Avisos «Informe … listo» (la rutina los genera los lunes y los días 1, 5 y 16) → «Marcar como revisado» |
| 27 | Dirección | Rutina → «Responsables de cada paso» | Puede cambiar el responsable; solo salen personas con permiso para ese paso |
| 28 | Recepción Barcelona | Intentar ver informes | Sin acceso |

Si algo no coincide: captura de pantalla + número de prueba. Nunca usar facturas, extractos, CIF ni IBAN reales en esta instalación.
