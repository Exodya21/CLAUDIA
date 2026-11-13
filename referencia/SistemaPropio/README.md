# SISTEMA PROPIO

Plataforma jurídica y empresarial del despacho del abogado Rafael Serrano, para sustituir de forma progresiva
MNProgram (MNP). Monolito modular: **Next.js + TypeScript** (web), **FastAPI + SQLAlchemy + Alembic** (API) y
**PostgreSQL**.

> **Estado: F0.1 + F0.2 + F1.2 + F2.1 + F2.2 + F2.3 + F4.1 + F4.2 + F4.3 + F5.0 + F5.1 + F5.2 + F5.3 + F5.4 + F5.4b — entorno de desarrollo con datos ficticios.** La parte técnica de
> acceso seguro ya está (contraseña + código del móvil, sesiones revocables, copias comprobadas). Para usar datos
> reales faltan decisiones, no código: alojamiento y región (T-02), copia externa cifrada (T-17), privacidad
> (T-04, D-17) y roles reales (T-08). Ver [`docs/producto/decisiones.md`](docs/producto/decisiones.md).

## Qué funciona hoy

| Módulo | Implementado de verdad (BD + API + interfaz + permisos + tests) |
|---|---|
| **Acceso seguro (F0.2)** | Usuario + contraseña + **código del móvil** obligatorio (primer acceso con QR); acceso corporativo OIDC con MFA listo a falta de proveedor; **sesiones revocables** al instante y cierre por inactividad; **bloqueo** tras 5 intentos; **Administración** de usuarios, roles por entidad/sede/departamento y sesiones; **copias de seguridad restauradas y verificadas** (AT-29); alta de autorizaciones puntuales desde la pantalla |
| Núcleo (F0.1) | Acceso DEMO solo en desarrollo; 3 entidades ficticias, 3 sedes + soporte Colombia; permisos por entidad, sede, rama, rol y asignación; auditoría inmutable y verificable |
| Clientes (F0.1) | Búsqueda con ficha mínima o completa según rol, alta con validación y aviso de duplicado, edición con motivo; pestañas de expedientes, leads e historial |
| **CRM (F1.2)** | Leads con **origen obligatorio** (campaña obligatoria en TikTok Live y Google Ads), UTM, estados con motivo, reapertura, **seguimiento a 24 h / 72 h / 7 días**, **embudo** por estado y origen, conversión a expediente trazable |
| **Expedientes (F2.1)** | Apertura desde cliente o lead con código consecutivo; **fases** (preapertura → abierto con encargo confirmado → trámite → resuelto…) donde las de efecto jurídico solo las cambia un letrado/Dirección; responsables por rama; relaciones; indicador de **inactividad** |
| **Agenda y tareas (F2.2)** | Tareas, señalamientos y conciliaciones con horario y **detección de solapes**; aplazar exige motivo y nueva fecha (se conserva la anterior); **plazo legal separado de la fecha interna, propuesto por una persona y validado por otra**; nadie modifica tareas ajenas sin permiso |
| **Economía (F5.0)** | Control interno **sin facturas fiscales**: importes pactados (los introduce una persona), cobros con confirmación de Contabilidad y nº de factura del programa homologado, **devoluciones** (ATC registra y escala, el letrado informa, solo Contabilidad aprueba y paga), **cajas por sede** con arqueo, resumen por sede y periodo |
| **Gastos (F5.0)** | Foto o PDF del ticket → **lectura en el servidor** que propone fecha, proveedor, NIF, total e IVA → la persona confirma → Contabilidad aprueba o devuelve → conciliación con la caja, con el **extracto de la tarjeta** de empresa o con el reembolso; **resumen mensual** por persona, sede, concepto y forma de pago, descargable para Excel |
| **Extranjería (F4.1)** | 14 trámites (arraigos, renovaciones, modificaciones, reagrupación, larga duración, estudios, nacionalidad) con la **documentación exigida** de su hoja oficial; **subida múltiple** y **lectura en el servidor** (MRZ de pasaporte/TIE con dígitos de control, tipo y fechas) que una persona confirma; **avisos** de caducidad, titular distinto, duplicados y formato; fases hasta la **resolución favorable**, el requerimiento (crea tarea de plazo para el letrado, sin inventar la fecha) o el recurso; **paquete para Mercurio** (orden, PDF/JPG ≤ 6 MB, índice y ficha de datos). No presenta ni descarga nada en portales oficiales por sí mismo |
| **Rellenar Mercurio (F4.2)** | **Ficha de datos del formulario** en cada expediente (16 modelos EX analizados, incluido el EX-10 de arraigos, más los datos comunes que Mercurio pide aparte): se propone desde el cliente, el pasaporte leído y los datos del despacho y una persona la confirma. **Extensión de Chrome** (`apps/extension-mercurio`, ver su LEEME) que, con un código temporal, rellena las pestañas de Mercurio. **No pulsa ningún botón, no marca «NO CONSIENTO» ni elige el supuesto**: el profesional revisa, firma y presenta. Vista previa interna del EX relleno |
| **Leer documentos (F4.3)** | Al subir **contrato, padrón, TIE, pasaporte (también PDF escaneado de varias páginas), tasa 790 y vida laboral**, el sistema lee y muestra qué ha encontrado (empresa, CIF, cuenta de cotización, centro, puesto, domicilio, N.I.E., NRC…). Cuando una persona marca el documento **válido**, esos datos llegan a la ficha del formulario como propuestas con su origen; se avisa de contradicciones y de documentos de otra persona; lo que no tiene forma de dato se descarta. «Volver a leer» y «Diagnóstico de la lectura (sin datos)» en cada documento, y **revisión automática de la lectura** por expediente con informe sin datos para soporte. Muestras ficticias en `docs/pruebas/muestras/` |
| **Portal del cliente y comunicaciones (F2.3)** | **Portal propio, sin WhatsApp** (decisión T-31): el cliente entra en `/portal` con un **código de un solo uso** a su correo; ve sus asuntos, la **lista de documentos que faltan** de su trámite y los envía; escribe y recibe mensajes. El equipo tiene una **bandeja** y la conversación dentro de cada expediente: mensajes al cliente, **notas internas**, adjuntos que **pasan al expediente** con su lectura automática, avisos **importantes** y **urgentes** (con plantilla y fecha de la agenda; plazo legal solo si está validado) que el cliente **confirma**; sin confirmar en 24 h se crea una tarea de llamada. **Nada se borra** (se oculta con motivo; correcciones 15 min con versión guardada). Correos **sin contenido**, por cola idempotente (SMTP configurable). Exportación PDF con **huella**. Pendiente: SMS, notas de voz, centralita, importación de WhatsApp |
| **Agentes, bandeja de propuestas y banco (F5.1)** | Los «motores» de Dirección como **agentes** del sistema (ADR-0010): reaccionan a hechos (extracto importado, expediente abierto, fecha en la agenda) y dejan su trabajo como **pendiente en el departamento que corresponde** (Contabilidad, Comunicaciones, el expediente, Recepción, RRHH; resumen en Inicio), donde una persona aprueba o rechaza con motivo; se configuran en Administración. **Banco**: cuentas A/B/C, importación de **Norma 43, CAMT.053 y CSV** con el original cifrado, **cuadre de saldos** y sin duplicados al reimportar; el agente de conciliación propone con su **explicación** (referencia del expediente, Bizum, **TPV con comisión**, **traspasos** entre cuentas, devoluciones, importe y fecha) y Contabilidad valida (confirma el cobro); pantalla de importados, conciliados, pendientes y errores; exportación CSV para la gestoría. **Mensajes al cliente por el portal**: bienvenida al abrir, aviso de conciliación/juicio con fecha y **lugar** de la agenda, recordatorio a las 10:00 del día anterior, seguimiento cada 75 días; sin duplicados, se cancela al cambiar la fecha o cerrar el expediente, medición semanal. Pendiente: Recepción (F5.2), RRHH (F5.3), Contabilidad completa en F5.4 (fila siguiente) |
| **Contabilidad (F5.4)** | **Facturas de proveedores**: se suben y la lectura propone número, CIF, fechas, base, **IVA de la factura** (nunca lo calcula), retención y total; solo se registra si base + IVA − retención = total; avisa de duplicados; validación con actividad, oficina y centro de coste. **Tesorería**: saldos según extracto, cajas, previsión de pagos a 7/30/60/90 días; **remesas con dos firmas de Dirección** distintas de quien propone, **fichero SEPA** que una persona sube al banco, y el cargo del extracto marca las facturas como pagadas. **Cierre del mes** (el agente lo propone el día 5): resultado por actividad y oficina, comparación y desviaciones, pendientes y fiabilidad; Contabilidad prepara y revisa, Dirección aprueba y queda congelado; exportación CSV. Pendiente: asientos (T-40) y facturas por correo (T-48) |
| **Rutina e informes de Contabilidad (F5.4b)** | **Sistema de trabajo** con el calendario del manual de Dirección (cada día extractos y conciliación; cada lunes facturas, pagos, cajas e informe; días 1–5 del mes extractos, conciliación, nóminas/facturas y cierre): cada paso tiene responsable, está en su **Agenda** y se da por hecho **solo cuando el sistema lo comprueba**; cumplimiento a tiempo/tarde por persona. **Informes semanales, quincenales y mensuales** automáticos, inmutables, en pantalla, PDF y CSV, con aviso por correo sin cifras y revisión de Dirección. Extractos del banco en **Excel** |
| **Recepción (F5.2)** | Cobro de consultas (también sin expediente), provisiones y servicios con **justificante numerado que no es factura**; aviso si un cobro **parece repetido** (solo se guarda con explicación y lo revisa Contabilidad); **caja del día** con saldo según registros y **cierre validado por un responsable distinto** de quien cuenta; cada sede su caja; **informe diario/semanal** por sede. Pendiente: citas y llegada (F5.5) |
| **RRHH (F5.3)** | **Ficha única** con 5 empleados ficticios (también Colombia), **carpeta** con lectura de nóminas que RRHH confirma, **vacaciones y ausencias** con saldo y aprobación del responsable (nadie aprueba las suyas; bajas solo para RRHH), **avisos** de contratos que vencen, periodos de prueba, documentos y nóminas que faltan o varían, **resumen de nóminas** para la gestoría (sin calcularlas) e **importación** con duplicados. Pendiente: control horario, formación y cuadro de mando |
| Resto de módulos | Visibles en el menú como **"Pendiente de desarrollar"**, sin datos simulados (Citas, Fichas laborales, Documentos, Facturación fiscal, RRHH, Dirección) |

Pruebas ejecutadas: **191/191 API**, **18/18 web**, build de producción y **76/76 pasos** (F5.0 sin cambios) de recorrido en Chrome.
Evidencias: [`evidencias_F0.1.md`](docs/pruebas/evidencias_F0.1.md),
[`evidencias_F1.2_F2.md`](docs/pruebas/evidencias_F1.2_F2.md), [`evidencias_F0.2.md`](docs/pruebas/evidencias_F0.2.md) y
[`evidencias_F5.0.md`](docs/pruebas/evidencias_F5.0.md) y [`evidencias_F4.1.md`](docs/pruebas/evidencias_F4.1.md) y [`evidencias_F4.2.md`](docs/pruebas/evidencias_F4.2.md) y [`evidencias_F4.3.md`](docs/pruebas/evidencias_F4.3.md) y [`evidencias_F2.3.md`](docs/pruebas/evidencias_F2.3.md) y [`evidencias_F5.1.md`](docs/pruebas/evidencias_F5.1.md) y [`evidencias_F5.2_F5.3.md`](docs/pruebas/evidencias_F5.2_F5.3.md) y [`evidencias_F5.4.md`](docs/pruebas/evidencias_F5.4.md) y [`evidencias_F5.4b.md`](docs/pruebas/evidencias_F5.4b.md).

### Actualizar una instalación existente en Windows
1. Ejecute `DETENER.bat`.
2. Descomprima el zip nuevo **en la misma carpeta**, aceptando reemplazar archivos. **No borre el archivo `.env`**: contiene la clave de su base de datos local.
3. Ejecute `INICIAR.bat`. Reconstruye, aplica la migración nueva y añade los datos ficticios nuevos sin tocar lo que usted haya creado.

## Trabajar con los datos REALES del despacho
Instalación separada de la demostración: **`INICIAR_REAL.bat`** (sin datos ficticios, acceso con contraseña y código
del móvil, claves en `.env.real`, copias con `COPIA_SEGURIDAD_REAL.bat`). Guía paso a paso, incluidas las 13 cuentas
bancarias, la importación de varios extractos y las facturas: [`docs/operacion/puesta_en_marcha_real.md`](docs/operacion/puesta_en_marcha_real.md).
Estado de cada módulo y plan para cerrarlos: [`docs/producto/plan_cierre_modulos.md`](docs/producto/plan_cierre_modulos.md).

## Puesta en marcha

### Windows — doble clic (recomendado)
1. Instale **Docker Desktop** desde https://www.docker.com/products/docker-desktop/ (acepte la opción WSL 2; puede pedir reiniciar).
2. Abra Docker Desktop y espere a que indique que el motor está en marcha ("Engine running").
3. Descomprima este zip en una carpeta sin espacios raros (p. ej. `C:\SistemaPropio`).
4. Doble clic en **`INICIAR.bat`**. La primera vez tarda varios minutos; después se abre `http://localhost:3000`.
5. Para apagar: **`DETENER.bat`**. Para volver a los datos ficticios iniciales: **`REINICIAR_DATOS_DEMO.bat`**.
6. Copia de seguridad comprobada: **`COPIA_SEGURIDAD.bat`** (con el sistema en marcha). Guía completa en
   [`docs/operacion/copias_y_restauracion.md`](docs/operacion/copias_y_restauracion.md).

`INICIAR.bat` crea un `.env` con claves aleatorias solo para su ordenador; no lo comparta ni lo suba a ningún sitio.

**Correo del portal (opcional):** para que los clientes reciban el código y los avisos por correo, añada al `.env`
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` y `SMTP_FROM` de un proveedor con contrato de encargo en la UE
(T-33) y vuelva a `INICIAR.bat`. Sin ellos no sale ningún correo; en desarrollo el código se ve en pantalla. El
servicio `avisos` de Docker entrega la cola y escala los urgentes sin confirmar cada 5 minutos
(`python -m app.ops.outbox` en una instalación local).

### Opción A — Docker Compose (cualquier sistema)
> Verificado por partes sin servicio Docker: instalación de la API, migración y carga en una base nueva, y la web en modo `standalone` con el recorrido completo en navegador. La construcción de las imágenes Docker en sí se probará en la primera máquina con Docker.

```bash
cp .env.example .env            # rellene POSTGRES_PASSWORD y SESSION_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # genera SESSION_SECRET
docker compose up --build       # migra, carga datos ficticios y arranca
# Web: http://localhost:3000   ·   API: http://localhost:8000/api/v1/docs
```

### Opción B — Local (la que se ha verificado)
Requisitos: Python ≥3.12, Node 22, PostgreSQL 16 y, para leer tickets, Tesseract con español y poppler-utils.

```bash
# 1. Bases de datos (desarrollo y pruebas separadas)
createuser -P sistema
createdb -O sistema sistema_propio
createdb -O sistema sistema_propio_test

# 2. API
cd apps/api
cp .env.example .env            # complete DATABASE_URL, TEST_DATABASE_URL y SESSION_SECRET
pip install -e ".[dev]"
alembic upgrade head            # migración reversible: alembic downgrade base la deshace
python -m app.seed              # datos ficticios (se niega fuera de development/test)
uvicorn app.main:app --reload --port 8000

# 3. Web (otra terminal)
cd apps/web
npm install
npm run dev                     # http://localhost:3000  (reenvía /api/v1 a API_URL, por defecto :8000)
```

### Pruebas
```bash
cd apps/api && pytest -v            # usa TEST_DATABASE_URL (debe terminar en _test; se borra y recrea)
cd apps/web && npm test && npm run lint && npm run build
cd apps/web && npm run e2e          # con API y web en marcha; necesita Chrome (CHROME_PATH)
# Recorridos: e2e/recorrido.mjs (F0.1), e2e/recorrido_f2.mjs (F1.2+F2), e2e/recorrido_f02.mjs (F0.2),
# e2e/recorrido_f50.mjs (F5.0; TICKET=imagen ficticia de 14,00 € EXTRACTO=csv)
# e2e/recorrido_f41.mjs (F4.1; PASAPORTE=imagen ficticia generada con app.seed_immigration.passport_image)
# e2e/recorrido_f42.mjs (F4.2; carga la extensión y rellena la página de prueba servida en la dirección de Mercurio)
# e2e/recorrido_f43.mjs (F4.3; sube las muestras ficticias de docs/pruebas/muestras y comprueba la ficha)
# e2e/recorrido_f23.mjs (F2.3; equipo y cliente en dos navegadores: portal, documentos, avisos urgentes, exportación)
# e2e/recorrido_f52_f53.mjs (F5.2/F5.3; NOMINA=… cobro y justificante, repetido, cierre validado, informe, RRHH)
# e2e/recorrido_f54b.mjs (F5.4b; rutina comprobada, agenda, «no aplica», informes, revisión, responsables)
# e2e/recorrido_f54.mjs (F5.4; FACTURA=factura ficticia de app.accounting.invoices.invoice_pdf: factura, remesa con dos firmas, SEPA, cierre)
# e2e/recorrido_f51.mjs (F5.1; extracto ficticio de la cuenta A, conciliación, bandeja, traspaso A→C, bienvenida, agentes)
# Agentes fuera de las peticiones (el contenedor «avisos» lo hace cada 5 min):  python -m app.ops.agents
python scripts/build_coverage.py    # regenera el mapa de los 208 requisitos desde la matriz
```

## Guía de navegación (perfiles ficticios)

| Perfil | Qué comprobar |
|---|---|
| Recepción Barcelona | CRM → Nuevo lead (pruebe TikTok Live sin campaña). Pendientes de seguimiento. Clientes → buscar `611000999` (dos personas, mismo teléfono). Expedientes de Lucía: solo metadatos |
| Asesor Laboral Barcelona | CRM: solo sus leads → abra uno → **Abrir expediente** → confirme el encargo → cree una tarea con plazo legal (queda SIN VALIDAR) → aplácela. Agenda: solapes y vencidas. Forzar un expediente de Extranjería → 403 |
| Líder Laboral | Agenda: plazos pendientes de su validación. Expedientes: puede resolver, archivar y asignar responsables de Laboral; nunca Extranjería |
| Asesora Extranjería Madrid / Gestor Laboral Valencia | Lo suyo; el gestor ve tareas de otros en sus expedientes pero no puede modificarlas |
| Asesora Extranjería Madrid (Extranjería) | Bandeja de trámites; en EXT-2026-0001 suba `docs/pruebas/muestras/pasaporte_ficticio_UTO.png` (inventado) y vea la lectura de la MRZ; en EXT-2026-0003 compruebe el paquete para Mercurio; registre un requerimiento en EXT-2026-0004 y vea la tarea de plazo |
| Líder Extranjería | Valide la lista de un trámite en «Catálogo de trámites» y registre una resolución favorable |
| Marketing | CRM → Embudo por origen y conversión. Ningún acceso a expedientes |
| Dirección | Todo en sus dos entidades; **Administración**: dar de alta a una persona (anote la contraseña provisional), ver sus sesiones y cerrarlas, cambiar su rol, copias de seguridad. Ajustes → auditoría y alta de autorizaciones puntuales |
| Asesor Laboral Barcelona (gastos) | **Gastos** → suba la foto de un ticket inventado: el sistema propone los datos; elija concepto y forma de pago (tiene una tarjeta de empresa ficticia ··0042) y envíe |
| Recepción Barcelona (cobros) | **Economía** → busque `LAB-2026-0001` → Registrar cobro en efectivo → pestaña **Caja** → Arqueo |
| Atención al cliente | **Economía → Devoluciones**: hay una solicitud ficticia; puede revisarla y escalarla, no aprobarla |
| Contabilidad | **Economía**: cobros por confirmar, decidir devoluciones, cajas y resumen. **Gastos**: revisión, tarjetas y extractos (importe un CSV `fecha;concepto;importe;tarjeta`), resumen mensual |
| Persona creada por Dirección | Cierre sesión y entre con **usuario y contraseña provisional**: el sistema le pedirá su contraseña y escanear un QR con Microsoft/Google Authenticator. Ajustes → Seguridad |
| **Cliente ficticio en el portal** | Abra `http://localhost:3000/portal` (mejor en otra ventana o en el móvil) con el correo **`carla.13@ejemplo.invalid`** (clienta de EXT-2026-0001): sin correo configurado, el código aparece en pantalla. Acepte las condiciones, vea los documentos que faltan, envíe uno de `docs/pruebas/muestras/` y escriba |
| Asesora Extranjería Madrid (comunicaciones) | **Comunicaciones**: la conversación de EXT-2026-0001 (con una nota interna que la clienta no ve). Pida documentos con la plantilla, pase al expediente lo que envíe la clienta, exporte el PDF. En la ficha del cliente, pestaña **Portal y mensajes**, dé o bloquee el acceso |
| Líder Extranjería (avisos urgentes) | Cree en la agenda un señalamiento del expediente y envíelo como **aviso urgente** con su plantilla; la clienta lo confirma en el portal |
| Asesor Laboral otra entidad / Soporte Colombia | No ven nada de la entidad española |

## Reglas del proyecto
Ver [`CLAUDE.md`](CLAUDE.md). En resumen: trazabilidad de los 208 IDs, permisos reales en backend, auditoría de todo
acceso sensible, solo datos ficticios en desarrollo, ninguna regla legal o fiscal sin fuente, versión y aprobador, y la
IA nunca decide.

## Mapa de la documentación
| Carpeta | Contenido |
|---|---|
| `docs/producto/` | [arquitectura](docs/producto/arquitectura.md) (módulos, ER, flujo), [estados](docs/producto/estados.md), [mapa de cobertura 208](docs/producto/mapa_cobertura.md), [decisiones](docs/producto/decisiones.md), [backlog por fases](docs/producto/backlog_fases.md), [trazabilidad código](docs/producto/trazabilidad_codigo.md), [prompts siguientes](docs/producto/PROMPT_02_03_siguientes_incrementos.md) |
| `docs/operacion/` | [copias y restauración](docs/operacion/copias_y_restauracion.md), primera persona administradora |
| `docs/seguridad/` | [política de permisos](docs/seguridad/politica_permisos.md), [amenazas y privacidad](docs/seguridad/amenazas_y_privacidad.md) |
| `docs/adr/` | Decisiones de arquitectura 0001–0007 |
| `docs/pruebas/` | [evidencias F0.1](docs/pruebas/evidencias_F0.1.md), salidas de pytest/vitest, capturas |
| `docs/fuentes/` | Matriz maestra de 208 requisitos (fuente del mapa de cobertura) |

## Estructura
```
apps/api    FastAPI · app/{models,security,routers,audit,seed} · alembic/ · tests/
apps/web    Next.js · app/(app)/{clientes,expedientes,ajustes,[modulo]} · lib/ · tests/ · e2e/
docs/       adr · producto · seguridad · pruebas · fuentes
scripts/    build_coverage.py (mapa de cobertura y registro de decisiones)
```
