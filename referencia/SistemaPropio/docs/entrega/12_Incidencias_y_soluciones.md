# 12 · Documentación de incidencias y soluciones

Sistema Propio · versión F5.6 · 12/11/2026

Registro de los problemas encontrados durante el desarrollo y la puesta en marcha, con la causa y la solución
aplicada. Sirve como base de conocimiento para el soporte y como lista de trampas que hay que evitar al
reimplementar en Odoo.

**Plantilla para nuevas incidencias:** ID · fecha · entorno · síntoma (lo que ve la persona) · causa · solución ·
prevención (prueba o regla añadida) · estado.

## 1. Instalación y arranque (Windows)
| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-01 | 02/11 | La API no arranca en Docker | La imagen ligera de Python no trae zonas horarias | Dependencia `tzdata` | Recorrido e2e sobre Docker |
| INC-02 | 02/11 | Error de empaquetado de la API en la imagen | Paquete mal declarado | `pyproject.toml` corregido | Construcción en cada versión |
| INC-03 | 02/11 | `INICIAR.bat` arranca con una base anterior sin su `.env` y no puede leer los datos | Volumen de una instalación previa | El script detecta el caso y avisa | — |
| INC-04 | 02/11 | Errores en el registro por el *healthcheck* | Comprobación mal formada | `pg_isready` con usuario y base | — |
| INC-05 | 03/11 | `REINICIAR_DATOS_DEMO.bat` falla sin `.env` y anuncia un borrado que no ha hecho | Orden de los pasos | Funciona sin `.env`; solo informa lo que hace; nombre de proyecto fijo | — |
| INC-06 | 12/11 | «SESSION_SECRET … at least 32 characters» al arrancar la instalación real | La función de PowerShell en línea del `.bat` generaba claves vacías | Script `ops/crear_env_real.ps1` + respaldo con un contenedor `alpine` | Validación de las 3 claves antes de arrancar |
| INC-07 | 12/11 | La persona usuaria no podía descargar `.bat`/`.ps1` | El navegador bloquea ejecutables | Se entrega en `.zip` o se colocan directamente en la carpeta | — |
| INC-08 | 12/11 | No pedía la primera administración | `PRIMERA` no se activaba si `.env.real` ya existía sin base | `set PRIMERA=1` siempre que no haya volumen de datos real | — |
| INC-09 | 12/11 | `findstr` daba error con la expresión de validación | `findstr` de Windows no admite expresiones regulares largas | Comprobación con `/b` (empieza por) y `/x` (línea exacta vacía) | — |
| INC-10 | 12/11 | El `.bat` quedó cortado tras una edición automática | La búsqueda de `:env_valido` encontró antes `call :env_valido` | Restaurado desde el repositorio | No editar `.bat` con sustituciones por posición; usar la copia del repositorio |
| INC-11 | 12/11 | La aplicación de autenticación pide «nombre del código» y no lee el QR | Comportamiento de la aplicación del móvil | Introducir la clave de configuración a mano: nombre `Sistema Propio`, tipo «Basado en tiempo» | Añadido al manual (09 y 14) |

## 2. Lectura de documentos con archivos reales
Regla aplicada en todos los casos: **el documento real solo se usa para ver su formato**. No se guarda. La prueba se
escribe con un documento ficticio de la misma forma.

| ID | Fecha | Síntoma | Causa | Solución |
|---|---|---|---|---|
| INC-20 | 05/11 | Padrón no leído | Datos en formato tabla | Lectura por columnas (F4.3) |
| INC-21 | 05/11 | Pasaporte escaneado sin MRZ | Página girada o en otra página | Se buscan todas las páginas y los cuatro giros |
| INC-22 | 05/11 | Documento duplicado en el expediente | Misma subida dos veces | sha256 por expediente |
| INC-23 | 09/11 | «No ha podido leer» 3 facturas reales y pide los datos a mano | Etiquetas no previstas, OCR defectuoso en un escaneado, bloque del cliente antes que el emisor | Lectura v2: etiquetas, fechas en letra, cuadre por aritmética, OCR a 300 ppp, descarte del CIF propio |
| INC-24 | 09/11 | Nombre de proveedor tomado del bloque del cliente | La línea contenía el CIF del despacho | Se saltan las líneas con un CIF propio |
| INC-25 | 09/11 | Se eliminaban líneas válidas como «basura de OCR» | Expresión demasiado amplia | Solo líneas de 16 o más caracteres con al menos 85 % de letras c/n/o/i/r/u |
| INC-26 | 09/11 | Extracto Excel de banco rechazado | Cabecera tras filas de título; nombres con tildes y puntos | Búsqueda de la cabecera y normalización (`_norm_header`) |

## 3. Interfaz
| ID | Fecha | Síntoma | Causa | Solución |
|---|---|---|---|---|
| INC-30 | 09/11 | Miles de peticiones y clics que fallan en «Pendientes» | `onCount` se recreaba en cada render y recargaba la lista en bucle | `onCount` guardado en una ref |
| INC-31 | 09/11 | El proveedor recién creado no aparece en el desplegable | La lista no se fusionaba ni se remontaba | Lista combinada y `key` del `select` |
| INC-32 | 09/11 | Retención obligatoria en facturas sin retención | Campo de importe sin opción vacía | `MoneyInput` con `optional` |
| INC-33 | 09/11 | El texto en negrita del aviso aparecía partido | `.notice strong` es de bloque | Uso de `<b>` |
| INC-34 | 09/11 | Seguía apareciendo «Mínimo» en módulos completos | Estado en `lib/modules.ts` desactualizado | Contabilidad marcada como operativo; etiqueta «En curso» |

## 4. Pruebas automáticas
| ID | Síntoma | Causa | Solución |
|---|---|---|---|
| INC-40 | Un e2e pulsaba «No autorizar» en lugar de «Autorizar» | Selector por texto parcial | `exact: true` |
| INC-41 | El e2e de la descarga SEPA fallaba | Lo hacía un rol sin permiso | Lo hace el rol Contabilidad |
| INC-42 | «Resultado provisional» aparecía varias veces | Selector ambiguo | Selector de la celda de la tabla |
| INC-43 | El e2e de la agenda fallaba según el día de la semana | Cambio de semana | Se decide por el día de la semana |
| INC-44 | Las pruebas de Excel contaminaban otras | Orden de ejecución | Archivo renombrado (`test_f55_*`) |

## 5. Incidencias abiertas o conocidas
| ID | Tema | Estado |
|---|---|---|
| ABI-01 | Secreto TOTP del primer administrador mostrado en una captura compartida | **Restablecer el TOTP** de esa cuenta desde Administración y volver a enrolarlo |
| ABI-02 | En la carpeta real quedaron `ops\DIAGNOSTICO_REAL.bat`, `ops\_diag_iniciar.bat` y `ops\diag_real.txt` (diagnóstico, sin secretos) | Se pueden borrar |
| ABI-03 | Si un banco cambia el formato de su Excel | «Comprobar sin importar» indica las columnas que no reconoce. Enviar **solo la fila de cabecera** |

## 6. Procedimiento de soporte
1. Reproducir con **datos ficticios**.
2. Buscar el `request_id` del error. Aparece en el mensaje y en el registro de la API, sin datos personales.
3. Para un documento que no se lee: usar el diagnóstico sin datos (`GET /documents/{id}/diagnostic` o «Comprobar sin
   importar»). Nunca se envía el documento.
4. Crear la prueba que falla, corregir y añadir una fila a este documento.
