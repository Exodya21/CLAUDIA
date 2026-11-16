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

## 4b. Evaluación de Odoo 20 (pruebas locales)
| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-50 | 13/11 | Docker Desktop muestra «WSL not installed» al abrirse | Windows no tenía el Subsistema de Windows para Linux | PowerShell como administrador: `wsl --install --no-distribution` y reiniciar; comprobar con `docker run hello-world` | Paso incluido en la guía de instalación (09 §Anexo) |
| INC-51 | 12/11 | `psycopg2` no compila al instalar Odoo 20 desde el código con Python 3.13 | Faltan las cabeceras de PostgreSQL para compilar | Usar `psycopg2-binary` en el entorno de pruebas | En el servidor, usar la imagen Docker oficial `odoo:20` |
| INC-52 | 12/11 | El navegador automático no abre `localhost:8069` en el entorno en la nube | El proxy del entorno intercepta también `localhost` | Lanzar Chromium con `--no-proxy-server` | Solo afecta a las pruebas automáticas |
| INC-53 | 12/11 | «No tienes acceso al tablero de Contabilidad» con el usuario de demostración | Sin comprobar (probablemente el tablero de Contabilidad está restringido en Community) | Trabajar desde Facturación → Facturas | Comprobarlo dentro de AL-01 |
| INC-54 | 13/11 | El enlace público de la demo de Sistema Propio (túnel `trycloudflare`) no abre desde el entorno en la nube | El proxy del entorno no responde para ese dominio (sin comprobar más) | Trabajar con la copia local de `referencia/SistemaPropio/` (09 §Anexo B) | No publicar nunca en Internet una instalación con datos reales; el túnel, solo con la demo de datos ficticios |

## 4c. Odoo 20 · base contable
Al montar la base contable con `odoo/configuracion/base_contable.py` (11 · DOC-5). Entorno: Odoo 20.0 Community en el
entorno en la nube (sin Docker) y en Docker con la imagen oficial `odoo:20`.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-60 | 13/11 | El script falla al crear una compañía con país: primero por la dependencia `phonenumbers` y después con la transacción rota | Al crear una compañía con país, Odoo 20 instala solo módulos de localización (p. ej. `account_peppol`) a mitad del script y recarga el registro. En el entorno sin Docker no estaba instalada `phonenumbers` (la imagen Docker oficial sí la trae) | Crear la compañía con el contexto `install_mode=True` y cargar el plan contable con `try_loading` | Instalar los módulos de localización al crear la base (`-i account,l10n_es,l10n_co,l10n_es_edi_verifactu`, `odoo/LEEME.md` paso 2) y usar la imagen Docker oficial |
| INC-61 | 13/11 | No encuentra las cuentas del autónomo al buscarlas por código | En Odoo 20 el código de la cuenta depende de la compañía (`code_store`); sin `with_company(co)` se busca con el código de otra compañía | Búsquedas con `with_company(co)` y contexto con todas las compañías permitidas (`allowed_company_ids`) | En los `sp_*`, buscar siempre cuentas por código con `with_company` |
| INC-62 | 13/11 | Error al crear el certificado de Verifactu de pruebas | En Odoo 20 los campos binarios exigen `BinaryValue`/`BinaryBytes`, no `bytes` | Crear el contenido con `BinaryBytes(...)` | Tenerlo en cuenta en los `sp_*` que guarden archivos |
| INC-63 | 13/11 | La cuenta de ingresos por defecto no está en la categoría de producto, donde estaba en versiones anteriores | En Odoo 20 la cuenta de ingresos por defecto está en la compañía (`income_account_id`), no en la categoría | Poner 705000 en `income_account_id` de la compañía y como cuenta por defecto de los diarios CIT y EXP | La prueba comprueba que los honorarios van a 705000 |
| INC-64 | 13/11 | Verifactu: Odoo calcula la huella pero el documento no se completa («Error de red»); la rectificativa no genera documento | El entorno en la nube no resuelve `prewww2.aeat.es` (entorno de pruebas de la AEAT). La rectificativa depende del documento de la factura original | **Pendiente:** repetir la prueba en un equipo con Internet (p. ej. el PC del despacho con Docker) | La prueba avisa cuando no hay conexión con la AEAT. Estado: **abierta** (19 §3.8 paso a) |

## 4d. Odoo 20 · sp_recepcion
Al desarrollar el primer módulo propio, `odoo/addons/sp_recepcion` (11 · DOC-8 y DOC-10). Entorno: Docker con la imagen
oficial `odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-65 | 13/11 | Los permisos escritos como en versiones anteriores (`ir.model.access.csv` e `ir.rule`) no son válidos en Odoo 20 | Odoo 20 sustituye `ir.model.access` e `ir.rule` por un único modelo, **`ir.access`** | Archivo `security/ir.access.csv` con columnas `id,name,model_id,group_id/id,operation,domain`. Una fila **sin grupo y con dominio** es una regla global (p. ej. multicompañía) | Usar este formato en todos los `sp_*`. 08 §9 y §10 |
| INC-66 | 13/11 | El campo `report_file` de los informes no existe en Odoo 20; sin él, el justificante no queda guardado como adjunto | En `ir.actions.report` de Odoo 20 ya no existe `report_file`; guardar el PDF exige `save_as_attachment` | `attachment` + `save_as_attachment=True` + `attachment_use=True` (se reutiliza el adjunto y el PDF no se regenera) | Igual en todo informe que deba ser inmutable |
| INC-67 | 13/11 | Los grupos no se pueden declarar con la categoría como en versiones anteriores | En Odoo 20 los grupos se agrupan con **`res.groups.privilege`** (campo `privilege_id`), no con la categoría | Registro `res.groups.privilege` «Recepción y cajas» y `privilege_id` en los dos grupos | Usar `privilege_id` en los grupos de los `sp_*` |
| INC-68 | 13/11 | El saldo de la cuenta de la caja no incluía los cobros en efectivo recién registrados | En Odoo 20 un cobro en un diario de efectivo va por defecto a una cuenta de **cobros pendientes** (572…), no a la cuenta de la caja | `odoo/configuracion/base_contable.py`: los métodos de pago de entrada y salida de cada caja usan la cuenta de la caja (570…) | Lo comprueba el escenario `odoo/pruebas/prueba_recepcion.py` (saldo esperado 300 €) |
| INC-69 | 13/11 | Tras añadir `sp_recepcion`, Odoo no encuentra el módulo; el registro dice «invalid addons directory» | El servidor arrancó con la carpeta `addons` vacía y la descartó | `docker compose restart odoo` | Reiniciar el contenedor después de añadir el primer módulo (`odoo/LEEME.md`) |
| INC-70 | 13/11 | Las pruebas automáticas fallan al crear usuarios (login duplicado) | Los logins de los usuarios de prueba coincidían con los usuarios de demostración creados por `configuracion/recepcion.py` | Logins propios de los tests (`test.sp.*`) | En los tests de los `sp_*`, logins con prefijo `test.` |
| INC-71 | 13/11 | Tras un rato, Docker y PostgreSQL ya no están en marcha en el entorno en la nube | El entorno en la nube se reinicia a veces y pierde los procesos (sin comprobar más) | `bash herramientas/odoo_dev.sh` vuelve a levantar Docker, los contenedores y la base | Usar siempre ese script al empezar a trabajar en el entorno en la nube |
| INC-72 | 13/11 | El trigger del cierre de caja (versión 20.0.1.1.0) falla con «too many parameters specified for RAISE» (11 · DOC-10) | En `init()` el SQL se ejecuta **sin parámetros**, así que `%%` no se convierte en `%` y llega literal a PostgreSQL, que lo cuenta como marcador del `RAISE` | Escribir `%` (un solo signo) en el `RAISE EXCEPTION` de `sp_cierre_caja_proteger` (`models/cierre_caja.py`) | En SQL ejecutado sin parámetros, `%` simple; `%%` solo si la consulta lleva parámetros. Lo comprueba `test_bd_impide_cambiar_o_borrar_cierre_validado` |
| INC-73 | 13/11 | Al pagar la devolución de una factura **no cobrada**, la rectificativa queda conciliada con la factura y no hay nada que pagar | Al revertir una factura con saldo pendiente, Odoo concilia la rectificativa con ella: anula la deuda, no devuelve dinero | `action_pagar` exige que la factura esté cobrada por completo; si no, avisa de que no hay dinero que devolver y de que se haga una rectificativa sin devolución | Lo comprueba `test_devolucion_total_de_factura_crea_rectificativa` (primero intenta pagar con la factura sin cobrar) |
| INC-74 | 13/11 | Las tareas de aviso de las devoluciones se acumulaban: no se cerraban al dar el paso y llegaban a todos los responsables | Cada paso creaba tareas nuevas sin cerrar las anteriores, y la revisión se asignaba a todo el grupo de revisión, que incluye a Contabilidad | `_cerrar_tareas()` marca como hechas las tareas pendientes en cada paso (constan en el historial); la revisión va primero a Atención al cliente y solo si no hay nadie a Contabilidad (`_avisar(..., excluir_xmlid=...)`) | Escenario `prueba_devoluciones.py` y captura `5_devolucion.png` (tareas hechas en el historial) |
| INC-75 | 13/11 | Dudas al limitar Recepción por sede con `ir.access`, y huecos en la numeración de devoluciones tras las pruebas | Comprobado en el código de Odoo 20: los permisos **con grupo** se suman (O) y las restricciones **sin grupo** se aplican a todos (Y). Las secuencias `standard` usan una secuencia de PostgreSQL, que no se deshace al revertir la transacción de las pruebas | Restricción sin grupo sobre `account.payment` con dominio condicional (solo limita a Recepción no responsable) y permiso de Recepción en `sp.cierre.caja` con dominio por sede. Secuencias de justificantes y de devoluciones con `implementation = no_gap` | En los `sp_*`, restricciones que no deban afectar a todos se escriben con dominio condicional. Numeraciones legales o de control, siempre `no_gap`. En la base de pruebas actual la secuencia de devoluciones (dato `noupdate`) conserva los huecos; en una instalación nueva no |

## 4e. Odoo 20 · sp_contabilidad
Al desarrollar `odoo/addons/sp_contabilidad` (facturas de proveedores; 11 · DOC-13). Entorno: Docker con la imagen
propia `despacho/odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-76 | 13/11 | No se pueden leer los PDF ni hacer OCR dentro del contenedor de Odoo | La imagen oficial `odoo:20` no trae `pdftotext` (poppler) ni Tesseract | Imagen propia `despacho/odoo:20` (`odoo/Dockerfile`: oficial + `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-spa`) y `build: .` en `odoo/docker-compose.yml`. En el entorno de Claude se construye pasando el proxy como argumento de construcción (`herramientas/odoo_dev.sh`) | Arrancar con `docker compose up -d --build` (`odoo/LEEME.md` paso 1). El módulo declara `pdftotext`, `pdftoppm` y `tesseract` en `external_dependencies` |
| INC-77 | 13/11 | Error al crear un adjunto: aserción «_check_contents should handle that» | En Odoo 20, `ir.attachment` ya no admite `datas` al crear | Crear con `raw` (bytes) y leer `raw`, que puede ser un `BinaryValue`: usar `.content` | En los `sp_*`, adjuntos siempre con `raw`. Relacionada con INC-62 |
| INC-78 | 13/11 | Error al leer un parámetro del sistema con `get_param` | En Odoo 20, `ir.config_parameter.get_param` no existe | Usar `get_str` (y los métodos equivalentes para otros tipos) | Usar `get_str` en todos los `sp_*` |
| INC-79 | 13/11 | Las pruebas no se ejecutan: «0 tests» | Los decoradores `setup_country` y `setup_chart_template` de `AccountTestInvoicingCommon` se pusieron sobre la clase. Así la clase deja de ser una clase y no se ejecuta ninguna prueba | Poner los decoradores sobre `setUpClass` (`tests/test_facturas_proveedor.py`) | Comprobar siempre el número de pruebas ejecutadas, no solo que no haya fallos |
| INC-80 | 13/11 | Al instalar el módulo por primera vez con `-i`, las pruebas `post_install` no se ejecutaron («0 tests»); con `-u`, sí | **Sin comprobar** | Pasar las pruebas con `-u sp_contabilidad` después de instalarlo | Comprobar el número de pruebas ejecutadas. Revisar el paso 10 de `odoo/LEEME.md`, que instala con `-i` |

## 4f. Odoo 20 · sp_gastos
Al desarrollar `odoo/addons/sp_gastos` (gastos de empleados; 11 · DOC-14). Entorno: Docker con la imagen propia
`despacho/odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-81 | 13/11 | No se puede guardar un gasto sin categoría («Select a product to proceed»), y `action_post` no existe en el gasto | En Odoo 20, Gastos exige la categoría (producto) para guardar, y el asiento se crea **al aprobar**, no con un paso de contabilizar en el gasto | Las pruebas crean el gasto con categoría; en el escenario se elige la categoría antes de enviar. Se contabiliza el asiento que crea la aprobación (`account_move_id.action_post()`) | Categorías creadas por `odoo/configuracion/gastos.py`; flujo descrito en 15 §9b |
| INC-82 | 13/11 | Tras leer el ticket, al cambiar la categoría desaparecía el IVA reconocido | Al cambiar de producto, Odoo vuelve a poner los impuestos del producto | `write` vuelve a aplicar el impuesto que reproduce el IVA leído (`_sp_aplicar_iva_leido`) | Prueba `test_iva_leido_se_mantiene_al_elegir_categoria`. La captura `2_gasto_ticket_efectivo.png` es anterior a la corrección (impuesto 0,00 €) |
| INC-83 | 13/11 | Las pruebas fallaban al crear usuarios y al editar el gasto con otro usuario | Con `hr` instalado, crear usuarios toca el campo `employee_ids` y exige `sudo()`. En Gastos, solo la propia persona (o su aprobador) puede editar su gasto | Crear usuarios y empleados con `sudo()` y leer el ticket con el entorno de la propia persona (`self.env(user=...)`) | Seguir este patrón en las pruebas de los `sp_*` que dependan de `hr` |

## 4g. Odoo 20 · sp_banco
Al desarrollar `odoo/addons/sp_banco` (banco y conciliación; 11 · DOC-16). Entorno: Docker con la imagen propia
`despacho/odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-84 | 16/11 | Error al buscar o crear la cuenta bancaria por `acc_number` | En Odoo 20, `res.partner.bank` usa `account_number` y `sanitized_account_number`; `acc_number` ya no existe | Usar `account_number` al crear (`odoo/configuracion/banco.py`) y `sanitized_account_number` al comparar (`models/importacion.py`) | Usar esos campos en todos los `sp_*` |
| INC-85 | 16/11 | Al validar, Odoo intentaba borrar apuntes publicados | Cambiar el socio (`partner_id`) de un movimiento ya conciliado dispara la sincronización del movimiento con su asiento | Al validar no se toca el socio del movimiento; la empresa va en las contrapartidas | No escribir campos sincronizados con el asiento en movimientos conciliados |
| INC-86 | 16/11 | El escenario no encontraba los extractos subidos | Los adjuntos sin registro asociado solo los lee quien los subió | En `odoo/pruebas/prueba_banco.py` los adjuntos se suben como el usuario de Contabilidad (en pantalla ya es así) | Subir los adjuntos con el mismo usuario que ejecuta el asistente |
| INC-87 | 16/11 | El grupo de Contabilidad del despacho no podía crear extractos | Crear extractos exige las funciones contables completas de Odoo (`account.group_account_user`) | `security/sp_banco_security.xml`: el grupo «Responsable de caja y cobros (Contabilidad)» implica «Mostrar características de contabilidad completas» | Descrito en 08 §12. Recepción no recibe ese grupo |
| INC-88 | 16/11 | `herramientas/odoo_dev.sh` fallaba al montar de cero | Ponía `shell` después de las opciones (`odoo --db_host… shell`) | `shell` va antes de las opciones (`SHELL_ODOO`). `odoo/MONTAR_ODOO.bat` ya estaba bien | Montaje completo de cero comprobado el 16/11/2026 |

## 4h. Odoo 20 · sp_expediente y sp_facturacion
Al desarrollar la facturación y el cobro por número de expediente (11 · DOC-18). Entorno: Docker con la imagen propia
`despacho/odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-89 | 16/11 | No se podía usar una casilla «Es una empresa» del contacto para decidir si el cliente retiene IRPF | En Odoo 20, `is_company` se calcula a partir del NIF; ya no es una casilla | La retención se propone según el NIF del cliente («Cliente con retención de IRPF (15 %)», campo calculado que se puede cambiar a mano) | Prueba `test_honorarios_con_y_sin_retencion`. En la ficha se indica que hay que comprobarlo |
| INC-90 | 16/11 | Odoo 20 no dejaba emitir facturas | La cuenta bancaria propia que muestra la factura no estaba verificada («de confianza», `allow_out_payment`). Solo pueden verificarla los administradores o el grupo que valida cuentas | `odoo/configuracion/banco.py` marca como verificadas las cuentas propias de prueba (con `install_mode`, como superusuario) | En la instalación real, una persona autorizada verifica la cuenta en Odoo tras comprobar el IBAN con el banco (09; 08 §13) |
| INC-91 | 16/11 | La factura de honorarios salía en dólares | La tarifa «Por defecto» se crea al instalar Odoo, antes de cargar el plan contable, y quedó en USD | El pedido de honorarios usa siempre una tarifa en la moneda de la compañía (`_sp_tarifa`), y `odoo/configuracion/facturacion.py` corrige la tarifa por defecto | Prueba `test_moneda_de_la_compania_aunque_la_tarifa_sea_otra` |
| INC-92 | 16/11 | No se podía poner a la factura la fecha del pago | La serie de facturas debe ir en orden de fechas: un pago antiguo validado hoy rompería el orden | La factura lleva la fecha de emisión y la del pago va como «fecha de entrega», que Verifactu envía como FechaOperacion (devengo del anticipo) | Prueba `test_anticipos_y_factura_final`. **Sin comprobar en la AEAT** (ABI-05) |

## 4i. Odoo 20 · sp_cifrado y extractos cifrados en sp_banco
Al desarrollar el cifrado del IBAN y de los extractos originales (11 · DOC-19). Entorno: Docker con la imagen propia
`despacho/odoo:20`, en el entorno en la nube.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-93 | 16/11 | El hook de instalación esperaba la tabla del historial de seguimiento `mail_tracking_value` para enmascarar el IBAN y no la encontraba | En Odoo 20 no existe esa tabla: el seguimiento se guarda de otra forma (no se ha estudiado cómo) | `hooks.py` comprueba si existe el modelo antes de tocarlo. Además se **desactiva el seguimiento automático** del IBAN (`tracking=False`) y el alta o el cambio se anota enmascarado en el historial del contacto | Prueba de historial enmascarado en `tests/test_cifrado.py` y comprobación «ningún IBAN completo en los mensajes» de `odoo/pruebas/prueba_cifrado.py` |
| INC-94 | 16/11 | Error al importar `content_disposition` en el controlador de descarga del original | En Odoo 20 está en `odoo.http.stream`, no en `odoo.http` | `controllers/original.py` (`sp_banco`) lo importa de `odoo.http.stream` | Comprobar en el código de Odoo 20 la ruta de las utilidades HTTP antes de usarlas |
| INC-95 | 16/11 | El descifrado previsto al pasar el valor a la caché del ORM (`convert_to_cache`) no se aplicaba a los IBAN leídos de la base de datos | Odoo 20 carga los valores leídos de la base de datos con `_insert_cache`, sin pasar por `convert_to_cache` | `CharCifrado` (`models/campo.py`) descifra en `_insert_cache` y cifra en `convert_to_column` | Prueba «IBAN cifrado en la base y en claro en Odoo» (`tests/test_cifrado.py`). Revisarlo al actualizar Odoo: es un método interno del ORM |

## 4j. Odoo 20 · sp_banco_psd2 (conexión directa con el banco)
Al desarrollar la conexión directa con el banco por PSD2 a través de Enable Banking (11 · DOC-20). Entorno: Docker
con la imagen propia `despacho/odoo:20`, en el entorno en la nube, con el agregador simulado.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-96 | 16/11 | La tarea programada de descarga fallaba por permisos al leer las conexiones | El modelo `sp.banco.conexion` solo lo puede leer el grupo de Contabilidad, y la tarea no se ejecutaba con ese grupo | `_sp_cron` (`models/conexion.py`) lee las conexiones como sistema (`sudo()`); las acciones de pantalla siguen exigiendo el grupo de Contabilidad (`_sp_exigir`) | La prueba `test_aviso_antes_de_caducar_y_caducada` (`tests/test_psd2.py`) ejecuta la tarea, pero con el usuario de la prueba: no consta una prueba que la ejecute con un usuario sin el grupo de Contabilidad (por añadir). `sudo()` anotado en 08 §15.1 |
| INC-97 | 16/11 | No se pudo leer la documentación web de la API de enablebanking.com | El entorno en la nube bloquea la resolución DNS de ese dominio | Se verificó la API con la muestra oficial publicada en GitHub (`enablebanking/enablebanking-api-samples`, `python_example/account_information.py`, 30/03/2026) | Revisar la documentación oficial al darse de alta y probar con su entorno de pruebas desde un equipo con Internet (ABI-08) |

## 4k. Odoo 20 · despliegue en el servidor propio
Al preparar y probar el paquete `despliegue/` (11 · DOC-21). Entorno: entorno en la nube, simulando el servidor con
el dominio `localhost`.

| ID | Fecha | Síntoma | Causa | Solución | Prevención |
|---|---|---|---|---|---|
| INC-98 | 16/11 | El paso 5 de `instalar.sh` (dirección pública) fallaba al llamar a `set_param` y `get_param` de `ir.config_parameter` | En Odoo 20 `ir.config_parameter` ya no tiene `set_param` ni `get_param`: usa métodos por tipo | `instalar.sh` usa `set_str`, `set_bool` y `get_bool` | Revisar en el código de Odoo 20 la API de los parámetros antes de usarla en scripts o módulos |
| INC-99 | 16/11 | Caddy respondía **502 Bad Gateway** | Con un `odoo.conf` propio, Odoo escuchaba solo en 127.0.0.1 **dentro del contenedor** y Caddy no llegaba a él | `http_interface = 0.0.0.0` en `odoo.conf.plantilla`. Odoo sigue sin publicar puertos: solo se llega por la red interna de Docker. Comprobado que el 8069 no es accesible desde fuera | Comentario en la plantilla. Comprobación de que el 8069 no responde desde fuera en cada instalación nueva |
| INC-100 | 16/11 | Odoo rechazaba `without_demo = all` del archivo de configuración | Ese valor ya no es válido desde la 19.0 | `without_demo = True` | Revisar las opciones de `odoo.conf` en cada cambio de versión de Odoo |
| INC-101 | 16/11 | Al repetir la instalación, el paso de las contraseñas fallaba y **vaciaba** `credenciales_preproduccion.txt` | No había contraseñas nuevas: `grep` no encontraba nada y, con `pipefail`, el paso fallaba después de que la redirección hubiera vaciado el archivo | Se escribe en un archivo temporal (`credenciales.nuevas`) y solo sustituye al de credenciales si hay contraseñas nuevas | Comprobado que la segunda ejecución no cambia nada (11 · DOC-21) |
| INC-102 | 16/11 | La descarga de la imagen de Caddy fallaba con **429** | Límite de descargas de Docker Hub en el entorno de pruebas | Reintentar; la segunda vez funcionó | En el servidor no se espera (supuesto, sin comprobar). Si ocurre, esperar y repetir `instalar.sh`, que es idempotente |

## 5. Incidencias abiertas o conocidas
| ID | Tema | Estado |
|---|---|---|
| ABI-01 | Secreto TOTP del primer administrador mostrado en una captura compartida | **Restablecer el TOTP** de esa cuenta desde Administración y volver a enrolarlo |
| ABI-02 | En la carpeta real quedaron `ops\DIAGNOSTICO_REAL.bat`, `ops\_diag_iniciar.bat` y `ops\diag_real.txt` (diagnóstico, sin secretos) | Se pueden borrar |
| ABI-03 | Si un banco cambia el formato de su Excel | «Comprobar sin importar» indica las columnas que no reconoce. Enviar **solo la fila de cabecera** |
| ABI-04 | Verifactu sin probar contra la AEAT: el entorno en la nube no llega a `prewww2.aeat.es` (INC-64) | Repetir `odoo/pruebas/prueba_base_contable.py` en un equipo con Internet (19 §3.8 paso a) |
| ABI-05 | Facturas por expediente sin probar en la AEAT: facturas de anticipo, factura final a 0 € con líneas negativas y FechaOperacion (11 · DOC-18) | Probarlas en el entorno de pruebas de la AEAT desde un equipo con Internet, junto con ABI-04, y validarlas con la gestoría (18 · AL-15) |
| ABI-06 | Clave de cifrado de Odoo 20 (`SP_CLAVE_CIFRADO`, `sp_cifrado`) sin procedimiento de **rotación** (11 · DOC-19) | Hasta que exista, no cambie la clave: con otra clave los IBAN cifrados no se leen («[cifrado: no se puede leer]»). Custodia y copia: 13 §4 y 14 §11 |
| ABI-07 | Lo que el cifrado de Odoo 20 no cubre: concepto, ordenante e importe de los movimientos (en claro, hacen falta para conciliar), PDF de facturas y justificantes, y el archivo temporal del asistente de importación hasta la limpieza automática de Odoo (11 · DOC-19) | Disco cifrado en el servidor (LUKS o BitLocker) y copias cifradas (08 §3) |
| ABI-08 | Conexión directa con el banco (`sp_banco_psd2`) sin probar contra el agregador real ni contra su entorno de pruebas: solo con el agregador simulado (11 · DOC-20; INC-97) | Tras el alta en Enable Banking (18 · AL-16), probar con su entorno de pruebas (`SP_EB_API`) desde un equipo con Internet. No usar con datos reales hasta firmar el encargo del tratamiento |
| ABI-09 | Despliegue (`despliegue/`) sin probar en un servidor Ubuntu real con un dominio real: DNS, puertos 80 y 443 y emisión del certificado de Let's Encrypt (11 · DOC-21) | Lo prueba el despacho siguiendo `despliegue/LEEME.md` §1 a §4. Si el certificado falla: LEEME §10 |
| ABI-10 | Servidor propio sin supervisión ni avisos (disco, certificados, resultado de las copias) y sin `fail2ban` (11 · DOC-21) | Mientras no estén: revisar a mano `/var/log/odoo-despacho-copias.log` y el espacio en disco (13 §2 y §6) |
| ABI-11 | **`restaurar.sh` deja sin almacén de archivos a la base en uso** (detectado al documentar 11 · DOC-21; deducido del código y reproducido con los mismos comandos en carpetas de prueba, **sin comprobar en Docker**). Extrae la copia dentro de `filestore/<base en uso>` y después hace `mv '<base en uso>' '<base nueva>'`: la carpeta de la base en uso pasa a la restaurada, y esa base se queda sin adjuntos (PDF, extractos cifrados) | Extraer en una carpeta temporal y mover solo esa. **Resuelto el 16/11/2026:** los archivos se extraen en una carpeta temporal y solo esa pasa a la base nueva; comprobado en Docker: la base en uso conserva sus 166 archivos, la restaurada tiene los suyos y no quedan temporales. Prevención: la prueba de restauración comprueba también la base en uso |

## 6. Procedimiento de soporte
1. Reproducir con **datos ficticios**.
2. Buscar el `request_id` del error. Aparece en el mensaje y en el registro de la API, sin datos personales.
3. Para un documento que no se lee: usar el diagnóstico sin datos (`GET /documents/{id}/diagnostic` o «Comprobar sin
   importar»). Nunca se envía el documento.
4. Crear la prueba que falla, corregir y añadir una fila a este documento.
