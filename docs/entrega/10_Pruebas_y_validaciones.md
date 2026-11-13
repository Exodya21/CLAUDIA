# 10 · Documentación de pruebas y validaciones

Sistema Propio · versión F5.6 · 12/11/2026. Resultados guardados en `docs/pruebas/resultado_*.txt`; evidencias con
capturas en `docs/pruebas/evidencias_*.md`.

## 1. Estrategia
| Nivel | Herramienta | Contra qué | Qué asegura |
|---|---|---|---|
| API (integración) | pytest + httpx | **PostgreSQL real** (base `*_test`), migrada desde cero | Reglas de negocio, permisos (permitido, 403, 404), auditoría, triggers, no borrado |
| Migraciones | pytest | Subida → bajada → subida de 0001…0012 | Reversibilidad |
| Web (unidad) | vitest | Funciones de interfaz y extensión | Formatos, estado de módulos, que la extensión **nunca** pulsa ni envía |
| Recorridos (e2e) | playwright-core | Sistema completo con semilla ficticia | Lo que hace una persona en el navegador, paso a paso, con capturas |
| Tipos y estilo | tsc, ruff, next build | Código | Sin errores |
| Manual | Guía `guia_manual_contabilidad.md` (28 pasos) | Instalación de demostración | Validación por el usuario |

**Principios**
- Todas las pruebas usan **datos ficticios**, generados en la propia prueba: pasaportes del país «UTO» (OACI) con
  números ZZ, facturas y extractos con CIF e IBAN de prueba válidos, y nóminas ficticias.
- Cada permiso se prueba en los dos sentidos: quien debe poder y quien no. Hay una batería de ataques
  (`test_multiempresa_y_ataques.py`): entidad ajena, IDs adivinados, escalada, manipulación de importes.
- Las reglas críticas se prueban **también contra la base de datos**, saltándose la API: un UPDATE o un DELETE
  directos deben fallar.

## 2. Resultado de la última ejecución (12/11/2026, versión F5.6)
| Conjunto | Resultado |
|---|---|
| API (pytest) | **254/254** correctas (4 min 13 s) |
| Web (vitest) | **19/19** |
| Recorridos e2e | **12 recorridos, 128/128 pasos** |
| `tsc`, `ruff`, `next build` | Sin errores |

## 3. Inventario de pruebas de API
244 funciones de prueba en 25 archivos (con los casos parametrizados se ejecutan 254).

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `test_at01_aislamiento_ramas.py` | 10 | AT-01 Seguridad transversal: Laboral no lee Extranjería (ni por URL ni por API) y se registra. |
| `test_at02_recepcion_minimo.py` | 7 | AT-02 Recepción localiza por teléfono con datos minimizados, sin pruebas ni historial jurídico. |
| `test_at03_auditoria.py` | 5 | AT-03 Auditoría: altas, cambios, permisos y denegaciones generan eventos irreversibles. |
| `test_at04_duplicados.py` | 4 | AT-04 Duplicados: mismo documento => alerta, nunca fusión. Teléfono compartido no fusiona. |
| `test_f02_acceso.py` | 16 | F0.2 — Acceso con contraseña + doble verificación, sesiones revocables y límite de intentos. Requisitos: Q-1.2, I-120. Datos ficticios. |
| `test_f02_admin.py` | 12 | F0.2 — Administración de usuarios y pertenencias (Dirección). Cambios inmediatos, auditados y acotados. |
| `test_f02_copias.py` | 5 | AT-29 — Copia de seguridad restaurada en una base auxiliar y comprobada (esquema + auditoría íntegra). Usa pg_dump/pg_restore del sistema y la base RESTORE_DATABASE_URL (nombre terminado en _test). |
| `test_f02_oidc.py` | 6 | F0.2 — Acceso corporativo OIDC (código + PKCE) contra un proveedor SIMULADO en memoria (sin red). Comprueba firma, nonce, estado, MFA exigido y que no se crean cuentas automáticamente. |
| `test_f12_crm.py` | 7 | F1.2 CRM: AT-05 (origen obligatorio), AT-06 (trazabilidad lead → expediente), permisos y seguimiento. |
| `test_f23_portal_comunicaciones.py` | 17 | F2.3 + M12 fase 1: portal del cliente y conversaciones por expediente (T-31: portal propio, sin WhatsApp). Todo con datos FICTICIOS. Comprueba acceso separado del cliente, permisos reales en el servidor, notas internas,  |
| `test_f2_expedientes_tareas.py` | 13 | F2.1 expedientes (AT-15, AT-16) y F2.2 tareas (AT-19, AT-20, Q-6.23, I-074). |
| `test_f41_extranjeria.py` | 14 | F4.1 — Expediente de extranjería: catálogo validado, fases, lectura de documentos (MRZ), avisos de caducidad, paquete para Mercurio y permisos. Pasaportes FICTICIOS (país «UTO» de la especificación OACI) generados aquí. |
| `test_f42_formularios.py` | 9 | F4.2 — Ficha de datos del modelo EX, borrador del PDF oficial, datos del despacho y código para la extensión de Mercurio. Todo con datos ficticios. |
| `test_f43_lectura_documentos.py` | 18 | F4.3 — Lectura de contrato, padrón, TIE, tasa y pasaporte para proponer datos a la ficha del formulario. Todo con documentos FICTICIOS generados en `app/immigration/samples.py` (empresa, CIF y N.I.E. inventados pero con  |
| `test_f50_economia.py` | 10 | F5.0 — Control económico no fiscal: cobros, devoluciones (A-09), caja por sede y resumen. Datos ficticios. |
| `test_f50_gastos.py` | 10 | F5.0 — Gastos de empresa con justificante: lectura propuesta, confirmación humana, revisión de Contabilidad, caja y conciliación con el extracto de la tarjeta. Tickets FICTICIOS generados en la prueba. |
| `test_f51_agentes_banco.py` | 16 | F5.1: motor de agentes, bandeja única, conciliación bancaria y agente de mensajes al cliente. Todo con datos FICTICIOS (cuentas 1111/2222/3333, extractos generados). Comprueba lectura de los tres formatos, cuadre de sald |
| `test_f52_recepcion.py` | 8 | F5.2 Recepción: cobros (también consulta sin expediente), duplicados, justificante NO fiscal numerado, caja del día, cierre validado por otra persona, separación por sede e informe diario. Datos FICTICIOS. |
| `test_f53_rrhh.py` | 9 | F5.3 RRHH: ficha única, permisos por función (salario y salud restringidos), carpeta con lectura de nóminas confirmada por una persona, vacaciones con saldo y decisión de otra persona, avisos de vencimientos, resumen de  |
| `test_f54_contabilidad.py` | 10 | F5.4 Contabilidad: proveedores (CIF e IBAN comprobados), facturas recibidas con lectura y duplicados, remesas con doble autorización y fichero SEPA, pago conciliado con el banco, cuadro de mando por actividad y oficina,  |
| `test_f54b_rutina_informes.py` | 7 | F5.4b Contabilidad: rutina de trabajo (pasos comprobados por el sistema, tareas en la Agenda, «no aplica» con motivo, responsables) e informes semanales, quincenales y mensuales (inmutables, versiones, PDF/CSV, correo si |
| `test_f55_extractos_excel.py` | 6 | Extractos bancarios en Excel: .xlsx, .xls (Excel 97-2003) y el «.xls» que en realidad es una tabla HTML. Formato típico de la banca electrónica española: filas de título (titular, cuenta, periodo) antes de la cabecera, f |
| `test_f55_lectura_facturas.py` | 4 | Lectura de facturas recibidas (lector v2) con formatos habituales en España. Textos FICTICIOS que reproducen la FORMA de facturas reales (etiquetas, orden, OCR defectuoso), nunca sus datos: - billete de transporte «Factu |
| `test_f56_puesta_en_marcha.py` | 3 | Puesta en marcha con datos de la empresa: alta de cuentas con IBAN, importación de varios extractos a la vez reconociendo la cuenta, y alta de la primera persona administradora con sus sedes y departamentos. Datos FICTIC |
| `test_multiempresa_y_ataques.py` | 18 | Multiempresa, IDOR, inyección SQL, enumeración, CSRF, borrado y configuración. |

## 4. Recorridos en navegador (e2e)
| Recorrido | Incremento | Pasos |
|---|---|---|
| `recorrido.mjs` | F0.1 núcleo y clientes | 11 |
| `recorrido_f02.mjs` | F0.2 acceso seguro | 13 |
| `recorrido_f2.mjs` | F1.2 + F2 CRM, expedientes, tareas | 11 |
| `recorrido_f23.mjs` | F2.3 portal | 10 |
| `recorrido_f41.mjs` | F4.1 extranjería | 10 |
| `recorrido_f42.mjs` | F4.2 ficha EX + extensión | 10 |
| `recorrido_f43.mjs` | F4.3 lectura de documentos | 11 |
| `recorrido_f50.mjs` | F5.0 economía y gastos | 12 |
| `recorrido_f51.mjs` | F5.1 agentes y banco | 9 |
| `recorrido_f52_f53.mjs` | F5.2 recepción + F5.3 RRHH | 10 |
| `recorrido_f54.mjs` | F5.4 contabilidad | 12 |
| `recorrido_f54b.mjs` | F5.4b rutina e informes | 9 |

### Pasos verificados

**recorrido** (F0.1 núcleo y clientes)
1. Recepción entra en modo demo y ve su panel
2. Recepción no puede listar el directorio sin criterio
3. Búsqueda por teléfono compartido devuelve 2 personas distintas con datos enmascarados
4. Recepción ve ficha mínima y solo metadatos de los dos expedientes
5. Alta de cliente con NIE válido
6. Validación de letra de control en el formulario
7. Documento repetido: aviso previo y bloqueo hasta confirmar con motivo
8. El listado del asesor laboral no contiene Extranjería
9. Forzar la URL de un expediente de Extranjería devuelve 403 y lo muestra
10. Dirección ve las denegaciones registradas y verifica la cadena de auditoría
11. Módulo futuro: 'Pendiente de desarrollar', sin datos simulados

**recorrido_f02** (F0.2 acceso seguro)
1. Alta de usuario con contraseña provisional mostrada una sola vez (recepcion.f027nqax)
2. Código incorrecto al activar la doble verificación: rechazado
3. Primer acceso completado: contraseña definitiva + doble verificación
4. Ajustes → Seguridad muestra la sesión y el método de acceso
5. Acceso con contraseña + código del móvil
6. Dirección cierra la sesión con motivo
7. La persona pierde el acceso al instante y ve el motivo
8. Bloqueo tras 5 intentos fallidos (también con la contraseña correcta)
9. Cambio de rol: se añade el nuevo y se retira el anterior; el historial se conserva
10. Restablecimiento: nueva contraseña provisional y doble verificación a configurar de nuevo
11. Autorización puntual concedida desde Ajustes, con motivo y caducidad
12. Administración muestra la última copia comprobada (AT-29)
13. Líder Laboral: sin menú de Administración y 403 en la API

**recorrido_f2** (F1.2 + F2 CRM, expedientes, tareas)
1. Lead de TikTok Live sin campaña: rechazado (AT-05)
2. Lead registrado con origen y campaña, y marcado como contactado
3. Bandeja de seguimiento 24 h / 72 h / 7 días
4. Lead → expediente en preapertura con código consecutivo (AT-06)
5. Apertura exige encargo confirmado; el asesor no ve fases jurídicas (AT-16)
6. Tarea con plazo legal propuesto: queda SIN VALIDAR (AT-19)
7. Aplazar exige motivo; la fecha anterior queda en el historial (AT-20)
8. Agenda semanal con solapamientos y vencidas
9. Otro letrado valida el plazo legal propuesto (doble control)
10. Fase jurídica «Resuelto» solo por perfil autorizado y con motivo
11. Marketing ve el embudo y recibe 403 en expedientes

**recorrido_f23** (F2.3 portal)
1. Bandeja del equipo: conversación del expediente, estado del portal y nota interna visible solo para el equipo
2. Solicitud de documentos con plantilla (trato de usted, lista del trámite) y nota interna
3. Cliente: acceso con código de un solo uso, condiciones aceptadas, sus asuntos con mensajes nuevos y documentos que faltan
4. Cliente: no ve notas internas; envía el contrato pedido en la lista y un mensaje
5. Equipo: mensaje del cliente sin leer en la bandeja; el adjunto pasa al expediente con su lectura automática
6. Avisos urgentes solo con plantilla y fecha de una tarea; un plazo legal sin validar no se comunica
7. Aviso urgente de señalamiento enviado con la fecha y el lugar de la agenda; queda pendiente de confirmar
8. Cliente confirma el aviso urgente; el equipo ve la confirmación con fecha y hora
9. Exportación PDF con huella; en la ficha, el acceso al portal y los correos (sin contenido; aquí sin servidor de correo)
10. La sesión del cliente no da acceso a nada del equipo

**recorrido_f41** (F4.1 extranjería)
1. Bandeja de trámites por fase, con documentos por revisar y caducidades
2. Pasaporte leído en el servidor: MRZ correcta, tipo propuesto con confianza alta
3. La persona confirma; la lista de documentación exigida se actualiza
4. Aviso de pasaporte que caduca en menos de 90 días
5. Paquete: indica lo que falta y permite un borrador registrado (.zip con índice y ficha de datos)
6. Presentado con número de registro; si faltan documentos se exige y guarda el motivo
7. Requerimiento registrado: tarea de plazo para el letrado, sin fecha legal inventada
8. Legal Extranjería valida la lista de documentos del trámite (con fuente oficial)
9. Resolución favorable registrada por el letrado, con fecha
10. Laboral no ve el módulo ni ningún trámite de extranjería (comprobado en el servidor)

**recorrido_f42** (F4.2 ficha EX + extensión)
1. La ficha del EX-10 llega con propuestas (cliente, pasaporte leído, despacho) pendientes de confirmar
2. La persona confirma la ficha y marca el supuesto (el sistema no lo elige)
3. Vista previa interna del EX-10 rellenado (no sustituye al que emite Mercurio)
4. Código temporal generado (MKU6-…), caduca a los 15 minutos
5. La extensión trae la ficha con el código (sin sesión ni contraseña)
6. Reconocimiento por los identificadores reales de Mercurio: un clic rellena extranjero/a, presentador y notificación
7. Formatos de Mercurio: N.I.E. sin guiones, fecha dd/mm/aaaa, móvil de 9 cifras; no sobrescribe ni toca contraseña ni «Persona tutelada»
8. Domicilio de notificación: espera a que se carguen municipio y localidad tras la provincia
9. No marca «NO CONSIENTO» ni elige el supuesto; ningún botón pulsado (Continuar, Concluir, Firmar y registrar, Presentación electrónica)
10. «Olvidar datos» borra la ficha de la extensión

**recorrido_f43** (F4.3 lectura de documentos)
1. Cuatro documentos leídos: tipo propuesto para cada uno (contrato, padrón, tasa, TIE con MRZ)
2. Se ve qué se ha leído de cada documento (empresa, CIF, cuenta de cotización… y el NRC de la tasa)
3. Mientras el documento no esté validado, la ficha no lo usa
4. La persona confirma los tres documentos como válidos
5. Pestaña Empleador: empresa, CIF, domicilio y representante propuestos desde el contrato
6. Pestaña Contrato: cuenta de cotización, puesto, código de contrato y centro de trabajo
7. Pestaña Extranjero/a: N.I.E. de la TIE y domicilio del padrón, cada uno con su origen
8. Diagnóstico de la lectura sin datos (etiquetas visibles, valores como XXX/999) y «Volver a leer»
9. El mismo archivo subido dos veces no se duplica
10. Revisión automática: por cada documento qué se ha leído, qué falta o se ha descartado; informe para Claude sin datos
11. La persona guarda la ficha: ya puede generar el código para la extensión de Mercurio

**recorrido_f50** (F5.0 economía y gastos)
1. Ticket leído en el servidor: total 14,00 € e IVA 2,43 € propuestos (confianza visible)
2. La persona revisa, completa y envía a Contabilidad
3. Recepción registra un cobro en efectivo sin ver la economía del expediente
4. Arqueo: si no cuadra exige motivo y deja el ajuste registrado
5. ATC registra y revisa la devolución; no tiene botón de aprobar (A-09)
6. Contabilidad confirma el cobro y anota el nº de factura del programa homologado
7. Contabilidad aprueba con motivo y registra el pago de la devolución
8. Contabilidad ve el justificante y aprueba el gasto
9. Extracto importado: el cargo con ticket se concilia y el que no tiene justificante queda señalado
10. Resumen mensual por persona, sede, concepto y forma de pago (descargable)
11. Ficha del expediente: pactado, cobrado y pendiente
12. Marketing no ve el módulo de Economía

**recorrido_f51** (F5.1 agentes y banco)
1. Extracto importado: saldo inicial + movimientos = saldo final; resumen importados / conciliados / pendientes / errores
2. El mismo extracto otra vez se rechaza: no se duplican movimientos
3. Referencia del expediente: propuesta explicada, validada por Contabilidad y cobro confirmado
4. TPV con comisión: la liquidación neta cuadra con los cobros con tarjeta y la comisión se concilia a la vez
5. Ingreso sin identificar: excepción para Contabilidad; la conciliación manual exige cuadre exacto
6. Pendientes de Contabilidad: excepción del banco (TGSS) aprobada y justificada con su categoría
7. Traspaso entre cuentas propias conciliado en las dos cuentas; pestaña de errores vacía
8. Bienvenida (DR-PLT-1) propuesta al abrir el expediente, aprobada por la asesora y publicada en su conversación
9. Dirección: agentes (en Administración) con sus límites y medición semanal; ve el banco sin poder conciliar (separación de funciones)

**recorrido_f52_f53** (F5.2 recepción + F5.3 RRHH)
1. Cobro de consulta sin expediente con justificante numerado por sede (documento interno, no es factura)
2. Cobro que parece repetido: aviso con los anteriores y solo se guarda con explicación (va a Contabilidad)
3. Caja del día: cobros, saldo según registros y cierre con diferencia explicada, pendiente de validar
4. Recepción de Madrid trabaja solo con su sede (la caja de Barcelona no le aparece)
5. Contabilidad valida el cierre (nunca quien contó) y anula el cobro repetido con motivo
6. Informe diario por sede: cobros por concepto y forma de pago, anulados, repetidos y estado del cierre
7. Plantilla con avisos; nómina leída (periodo, devengado, deducciones, líquido que cuadran) y confirmada por RRHH
8. Avisos: vencimiento de contrato, fin del periodo de prueba y diferencia de nómina; uno pasa a tarea en la agenda
9. Resumen de nóminas: confirmadas, por revisar y variación del +18 % señalada (sin calcular nóminas)
10. Vacaciones: el asesor las pide con su saldo a la vista y su líder las aprueba

**recorrido_f54** (F5.4 contabilidad)
1. Lectura de factura: propone número, fechas, base, IVA de la factura y total; alta rápida del proveedor con su IBAN
2. Base + IVA − retención debe dar el total para registrar; el sistema nunca calcula el IVA
3. Subir el mismo archivo otra vez: aviso de factura ya registrada
4. Factura validada con actividad y oficina (centro de coste)
5. Previsión de pagos (vencido, 7, 30, 60, 90 días) y remesa REM-2026-0002 propuesta; quien la propone no puede firmarla
6. Primera firma de Dirección desde «Pendientes de decidir»
7. Quien ya firmó no puede dar la segunda firma
8. Segunda firma de otra persona de Dirección: remesa autorizada
9. Contabilidad descarga el fichero SEPA pain.001 y lo marca como subido al banco (lo sube una persona, nunca el sistema)
10. Cierre preparado, recalculado (la revisión anterior queda sustituida, nunca se borra) y revisado con nota
11. Dirección aprueba el cierre: cifras congeladas con huella, exportación CSV; asientos «No disponible aún» (T-40)
12. Sin permiso: Contabilidad no aparece y la API deniega (registrado en auditoría)

**recorrido_f54b** (F5.4b rutina e informes)
1. La rutina abre Contabilidad: pasos de hoy, de la semana y del cierre (días 1–5) con responsable y lo que el sistema ha comprobado
2. Validar la factura basta: el sistema comprueba y da el paso por hecho (con evidencia); no se marca a mano
3. «No aplica» solo con motivo (queda quién y por qué)
4. Extracto en Excel (.xlsx con titular, cuenta y periodo antes de la cabecera) importado y comprobado
5. Informe semanal: cifras por oficina y actividad, comparación, pendientes, pagos y cumplimiento de la rutina; PDF y CSV
6. Los pasos semanales y mensuales están en la Agenda de su responsable
7. La rutina genera el quincenal (y el semanal y mensual que tocan); Dirección lo revisa desde sus pendientes de Contabilidad
8. Dirección asigna el responsable de cada paso (solo personas con permiso para ese paso)
9. Recepción no ve la rutina ni los informes (403 auditado)

## 5. Cómo ejecutarlas
```bash
# API
cd apps/api && TEST_DATABASE_URL=postgresql+psycopg://…/sistema_propio_test pytest -q
# Web
cd apps/web && npx tsc --noEmit && npx vitest run && npx next build
# Recorrido (con el sistema en marcha y la semilla recién cargada)
node e2e/recorrido_f54b.mjs
# Los que suben archivos necesitan fixtures FICTICIOS por variable: PASAPORTE, TICKET, EXTRACTO, NOMINA, FACTURA
```

## 6. Criterios de aceptación
Cada incremento tiene una tabla «criterio → prueba → captura» en su archivo de evidencias. Un incremento solo se da
por terminado si cumple todo esto:
1. Pruebas en verde.
2. Datos ficticios.
3. Revisión de seguridad (permisos en los dos sentidos y auditoría).
4. Migración reversible.
5. Documentación y trazabilidad actualizadas.

## 7. Validaciones pendientes de profesionales
| Qué | Quién | Decisión |
|---|---|---|
| Catálogo de trámites de extranjería (cada versión) | Legal Extranjería | Validación en la aplicación |
| Plazos legales de cada tarea | Letrado | `deadline.validate` |
| Matriz de roles y permisos | Dirección + DPO | D-13, D-17 |
| Plan de cuentas y asientos | Gestoría | T-40 |
| Superficha laboral (3 rutas) | Dirección laboral | U-01…U-18 |
| Facturación certificada | Dirección + asesoría fiscal | D-07, D-25 |

## 8. Pruebas para la versión en Odoo
- Reescribir cada archivo de §3 como `TransactionCase`, con un usuario por rol y la comprobación de `AccessError`.
- Equivalente a `test_multiempresa_y_ataques.py`: usuario de la entidad Colombia sin acceso a nada de España,
  incluidos `search_count` y `read_group`.
- *Tours* (`HttpCase`) para los recorridos de §4.
- Prueba de que los triggers impiden UPDATE y DELETE de la auditoría, los cierres y las firmas.
