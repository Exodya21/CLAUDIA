# 11 · Versiones y cambios (Changelog)

Sistema Propio · 12/11/2026. Formato inspirado en *Keep a Changelog*. Las versiones siguen los incrementos del plan
(F0.1 … F5.6). Los cambios de base de datos se indican con su migración.

## [DOC-1] · 13/11/2026 — Documentación en el repositorio y evaluación de Odoo 20
Trabajo de documentación y evaluación; no cambia el código de Sistema Propio.
### Añadido
- Paquete de documentación F5.6 en `docs/entrega/` (Markdown como fuente, Word en `docs/entrega/word/`,
  `openapi.json`). Los Word se regeneran con `python3 herramientas/docs_a_word.py`.
- **18 · Alineación con el charter de QUBIQ**: 13 diferencias abiertas (AL-01…AL-13) entre esta documentación y el
  *Project Charter* del 08/09/2026.
- Skill `sistema-odoo-despacho` con el resumen del charter (77 necesidades, reglas, plazos y puntos abiertos).
- `documentacion/Odoo 20 - Community vs Enterprise por fase.xlsx`: cada necesidad con su fase y su disponibilidad,
  más una hoja de Contabilidad y facturación.
- Prueba de **Odoo 20.0 Community** con Facturación y la localización española (plan de pymes, IVA 21 %, retención
  de IRPF 15 %, series de factura), con datos ficticios. Capturas en `documentacion/odoo20_facturacion_demo/`.
- Guía de instalación de Docker Desktop y de Odoo 20 en Windows para pruebas locales (ver 09 §Anexo).
### Comprobado
- En Odoo 20.0 Community **sí** existen Verifactu (`l10n_es_edi_verifactu`), SII, Redsys (`payment_redsys`), el
  plan contable de Colombia (`l10n_co`), CRM, Proyectos, RRHH básico y la sincronización con el calendario de Outlook.
- **No** existen (son Enterprise): Citas, Firma, Documentos, Helpdesk, WhatsApp, VoIP, intercompañía automática,
  tipos de cambio automáticos, activos, sincronización bancaria, SEPA, informes contables y modelos de la AEAT.

## [F5.6b] · 12/11/2026 — Arreglos de la puesta en marcha real en Windows
### Corregido
- `INICIAR_REAL.bat`: claves generadas con `ops/crear_env_real.ps1`, con un contenedor `alpine` como respaldo. Antes,
  una función de PowerShell en línea dejaba secretos vacíos.
- Detecta un `.env.real` incompleto y lo rehace si aún no hay base de datos real.
- Pide la primera administración siempre que no existe la base real.
- La validación de `.env.real` usa `findstr /b` y `/x` en lugar de expresiones regulares largas, que fallan en Windows.

## [F5.6] · 09/11/2026 — Puesta en marcha con datos reales
### Añadido
- Instalación real separada (`-p sistemapropio_real`, `.env.real`, `copias_real`), con `INICIAR_REAL`, `DETENER_REAL`
  y `COPIA_SEGURIDAD_REAL`.
- `primer_admin --sedes`: crea la entidad, sus sedes y los departamentos.
- Alta de cuentas bancarias con IBAN completo (cifrado).
- Importación de **varios extractos a la vez**, repartidos por los últimos dígitos del IBAN.
- Registro de varias facturas a la vez, con lectura automática y alta rápida del proveedor.
- `OWN_TAX_IDS` (CIF propio).
### Cambiado
- La semilla ficticia solo corre con `APP_ENV=development`.
- La interfaz indica «versión F5.6 (demostración)» fuera de producción.

## [F5.4c – F5.4d] · 09/11/2026 — Extractos en Excel y lectura de facturas v2
### Añadido
- Extractos `.xlsx`, `.xls` y «.xls» en HTML, con cabecera tras filas de título y columnas Importe o Cargo/Abono.
- **Comprobar sin importar**: no guarda nada.
- Lectura de facturas recibidas v2: etiquetas, fechas en letra, NIF/CIF con puntos, cuadre por aritmética, OCR a
  300 ppp y descarte del CIF propio.

## [F5.4b] · 09/11/2026 — Rutina de Contabilidad e informes · migración `0012`
### Añadido
- Rutina diaria, semanal, quincenal y mensual, con pasos comprobados por el sistema, responsables y tareas en la Agenda.
- Informes semanal, quincenal y mensual inmutables, en PDF y CSV, con aviso por correo sin cifras.
- Tablas `accounting_routine_owner`, `accounting_routine_item` y `accounting_report`, con los triggers de protección.

## [F5.4] · 09/11/2026 — Contabilidad · migración `0011`
### Añadido
- Proveedores y facturas recibidas (check base + IVA − retención = total).
- Tesorería con remesas de **doble firma** y fichero SEPA pain.001.
- Cierre del mes con revisiones y aprobación inmutable.

## [F5.2 + F5.3] · 08/11/2026 — Recepción y RRHH · migraciones `0009`, `0010`
### Añadido
- Recepción: cobros (también de consultas sin expediente), justificante no fiscal inmutable, cobros repetidos con
  explicación, cierre de caja validado por otra persona e informe.
- RRHH: ficha única, carpeta cifrada, lectura de nóminas sin cálculo, ausencias, avisos y salario protegido.
- Los pendientes de los agentes se muestran dentro de cada departamento.

## [F5.1] · 08/11/2026 — Agentes, banco y conciliación · migración `0008`
### Añadido
- Motor de agentes con bandeja de propuestas.
- Cuentas e importación de extractos (Norma 43, CAMT.053, CSV).
- Conciliación propuesta y explicada.
- Mensajes automáticos por el portal con plantillas versionadas.

## [F2.3] · 06/11/2026 — Portal del cliente · migración `0007`
### Añadido
- Portal propio con código por correo, conversaciones por expediente, adjuntos, avisos urgentes con plantilla y
  textos cifrados. Sin WhatsApp (T-31).

## [F4.1 – F4.3] · 05/11/2026 — Extranjería · migraciones `0005`, `0006`
### Añadido
- Expediente de extranjería con el catálogo versionado de trámites.
- Documentos cifrados.
- Lectura de pasaporte (MRZ), contrato, padrón, TIE y tasa.
- Ficha EX (modelos oficiales) y **extensión de Chrome** que rellena Mercurio sin presentar (versión 0.2, con los
  identificadores reales de Mercurio).
- Revisión de la lectura por expediente, con un informe sin datos.
### Corregido
- Tras la prueba real: padrón en tabla, pasaporte girado, duplicados, «Volver a leer» y diagnóstico sin datos.

## [F5.0] · 03/11/2026 — Economía no fiscal y gastos · migración `0004`
### Añadido
- Cobros, devoluciones con doble rol y caja.
- Gastos con el justificante leído en el servidor (OCR local).

## [F1.2 + F2.1 + F2.2] · 02/11/2026 — CRM, expedientes, tareas y agenda · migración `0002`
## [F0.2] · 02/11/2026 — Acceso seguro · migración `0003`
### Añadido
- Acceso local con TOTP, OIDC con PKCE y MFA, sesiones revocables y límite de intentos.
- Administración de usuarios.
- Copias verificadas por restauración (AT-29).
- Arranque en Windows con doble clic.

## [F0.1] · 02/11/2026 — Núcleo · migración `0001`
### Añadido
- Multientidad, sedes, departamentos, roles y política de permisos en el backend.
- Auditoría encadenada inmutable.
- Directorio de contactos con aviso de duplicados.

## Historial de commits
| Fecha | Commit | Descripción |
|---|---|---|
| 2026-11-12 | `d1173d1` | INICIAR_REAL: validación de .env.real sin expresiones largas de findstr (fallaban en Windows) |
| 2026-11-12 | `1ad359a` | INICIAR_REAL: pide la primera administración siempre que aún no hay base de datos real |
| 2026-11-12 | `7bd1a71` | INICIAR_REAL: claves generadas con un script PowerShell (y Docker como respaldo); detecta y rehace un .env.real incompleto |
| 2026-11-09 | `647610b` | F5.6 Puesta en marcha real: instalación separada, 13 cuentas, varios extractos y facturas |
| 2026-11-09 | `6d63b32` | Lectura de facturas recibidas v2: formatos reales, escaneados y CIF del despacho |
| 2026-11-09 | `0df310f` | Banco: «Comprobar sin importar» para probar extractos reales sin guardar nada |
| 2026-11-09 | `df505b3` | F5.4b Contabilidad: rutina de trabajo, informes periódicos y extractos en Excel |
| 2026-11-09 | `35ff088` | F5.4 Contabilidad completa: proveedores, tesorería con doble firma y cierre del mes |
| 2026-11-08 | `daa5839` | F5.2 Recepción, F5.3 RRHH y pendientes de los agentes dentro de cada departamento |
| 2026-11-08 | `30821dd` | F5.1 agentes, bandeja de propuestas, banco y conciliación, mensajes automáticos por el portal |
| 2026-11-06 | `b3bf52e` | F2.3 portal del cliente y conversaciones por expediente (portal propio, sin WhatsApp: T-31) |
| 2026-11-05 | `94b9684` | F4.3 revisión automática de la lectura por expediente con informe sin datos |
| 2026-11-05 | `28ebbc0` | F4.3 correcciones tras la prueba real: padrón en tabla, pasaporte completo girado, duplicados, volver a leer y diagnóstico sin datos |
| 2026-11-05 | `c7f876b` | F4.3 lectura de documentos → ficha del formulario (contrato, padrón, TIE, tasa, pasaporte escaneado) |
| 2026-11-05 | `8ba5ddd` | Extensión Mercurio 0.2: reconocimiento por los identificadores reales de Mercurio |
| 2026-11-05 | `670453c` | F4.2 ficha del modelo EX y extensión de Chrome que rellena Mercurio sin presentar (T-24) |
| 2026-11-05 | `b74f5d5` | F4.1 expediente de extranjería (fase 1): trámites, documentos leídos y paquete para Mercurio |
| 2026-11-03 | `75f3ee6` | F5.0 interfaz Economía y Gastos, recorrido en navegador y documentación |
| 2026-11-03 | `b9b0a1a` | F5.0 API: control económico no fiscal (cobros, devoluciones, caja) y gastos con justificante leído en el servidor |
| 2026-11-03 | `a4cf050` | REINICIAR_DATOS_DEMO.bat funciona sin .env y no anuncia un borrado que no ha hecho; nombre de proyecto fijo |
| 2026-11-02 | `12f6a3b` | F0.2 interfaz, recorrido en navegador, documentación y copias de seguridad para Windows |
| 2026-11-02 | `a8395c7` | F0.2 API: acceso local con TOTP, OIDC con PKCE y MFA, sesiones revocables, límite de intentos, administración de usuarios y copias AT-29 |
| 2026-11-02 | `d512c11` | INICIAR.bat detecta base anterior sin su .env; healthcheck sin errores en el registro |
| 2026-11-02 | `c76915f` | Corrige arranque de la API en Docker: zonas horarias propias (tzdata) |
| 2026-11-02 | `8f5a5ba` | F1.2 CRM, F2.1 expedientes y F2.2 tareas y agenda |
| 2026-11-02 | `8f0f8bc` | Arranque en Windows con doble clic y corrección del empaquetado de la API |
| 2026-11-02 | `92c4a14` | F0.1: núcleo de seguridad, multientidad, auditoría y directorio de clientes |

## Próximas versiones previstas
- Migración a **Odoo Community** en el servidor definitivo (ver 02, apartado 8).
- Módulos pendientes: Dirección (cuadro de mando), Citas, Documentos, Fichas laborales y Facturación (con un
  programa certificado).
