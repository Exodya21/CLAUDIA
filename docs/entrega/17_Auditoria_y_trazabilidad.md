# 17 · Documentación de auditorías y trazabilidad

Sistema Propio · versión F5.6 · 12/11/2026 (ADR-0005; requisitos Q-6.17, AT-03)

## 1. Registro de auditoría inmutable
Todo lo relevante queda en la tabla `audit_event`.

| Campo | Contenido |
|---|---|
| `occurred_at` | Fecha y hora UTC |
| `actor_user_id` | Quién (nulo solo en procesos del sistema: agentes, copias, semilla) |
| `organization_id` | Entidad |
| `action` | Qué, por ejemplo `case.transition`, `bank.import`, `immig.document.read`, `auth.login` |
| `resource_type`, `resource_id` | Sobre qué registro |
| `outcome` | `ok` o `denied` |
| `reason` | Motivo (obligatorio en aplazamientos, anulaciones, «no aplica», duplicados, rechazos) |
| `before`, `after` | Estado anterior y posterior. Los documentos de identidad van enmascarados; salarios y contraseñas nunca aparecen |
| `ip`, `request_id` | Origen y correlación con el registro técnico |
| `prev_hash`, `hash` | **Cadena SHA-256**: cada evento incluye el hash del anterior |

### 1.1 Garantías
1. **Misma transacción.** El evento se escribe junto al cambio: si el cambio se deshace, el evento también, y al
   revés.
2. **Denegaciones en transacción propia** (`audit.record_independent`): un intento denegado queda registrado aunque la
   operación falle.
3. **Cadena.** `hash = SHA-256(prev_hash + contenido canónico)`. Un bloqueo consultivo de PostgreSQL serializa la
   escritura. Modificar o eliminar un evento rompe la cadena desde ese punto.
4. **La base de datos lo impide.** Los triggers `audit_event_no_update` y `audit_event_no_truncate` bloquean UPDATE,
   DELETE y TRUNCATE, aunque se entre directamente con SQL.
5. **Verificación.** `GET /api/v1/audit-events/verify` (Ajustes → Auditoría → Verificar integridad) y en cada copia
   de seguridad restaurada (ver 13).

### 1.2 Qué se audita
| Ámbito | Ejemplos de acciones |
|---|---|
| Acceso | Inicio y cierre de sesión, MFA, fallos, bloqueos, revocaciones, cambios de contraseña, restablecimientos |
| Administración | Altas, cambios y bajas de usuarios, pertenencias, autorizaciones puntuales, configuración de agentes |
| Lectura sensible | Ficha completa de contacto, expediente, documentos de extranjería, carpeta de RRHH, salarios |
| Descargas | Documentos, justificantes, extractos originales, PDF y CSV de informes y cierres, fichero SEPA |
| Cambios | Contactos, leads, expedientes, tareas, plazos, ficha EX (claves cambiadas, nunca los valores), cobros, devoluciones, caja, gastos, banco, conciliación, facturas, remesas y firmas, cierres, rutina, informes |
| Denegaciones | Toda respuesta 403 o 404 por permiso, con el motivo (`requiere case.transition.legal`, etc.) |
| Sistema | Copias y su verificación, ejecuciones de agentes, propuestas aceptadas o rechazadas, envíos de correo |

En el código hay 28 familias de acciones: `auth`, `session`, `admin`, `grant`, `contact`, `lead`, `case`, `task`,
`deadline`, `immig`, `comm`, `payment`, `charge`, `refund`, `cash`, `reception`, `expense`, `card`, `economy`,
`bank`, `supplier`, `invoice`, `treasury`, `accounting`, `hr`, `agent`, `backup` y `seed`.

### 1.3 Otros registros de solo inserción
| Tabla | Qué guarda |
|---|---|
| Historiales de estado (`*_event`, `immig_stage_event`) | Cada transición con actor, fecha y motivo |
| `cash_movement` | Movimientos de caja |
| `backup_run` | Resultado de cada copia |
| `payment_batch_approval` | Firmas de remesas |
| `comm_dispatch`, `comm_message` (versiones) | Envíos y versiones de mensajes |
| `month_close`, `accounting_report` | Fotos inmutables con huella |
| `agent_run`, `agent_proposal` | Qué revisó cada agente y qué propuso |

### 1.4 Consulta
- Ajustes → Auditoría (permiso `audit.read`), con filtros. `GET /api/v1/audit-events`.
- Los accesos de Dirección también se auditan, y Dirección no puede borrar nada.

## 2. Trazabilidad de requisitos
### 2.1 Fuentes y regla
- 208 referencias con identificador propio: I-001…I-120 (informe de automatización), Q-1.1…Q-6.23 y Q-6.20B
  (Qubiq), y U-01…U-18 (superficha laboral).
- **Ningún identificador se elimina.** Los solapes se relacionan entre sí (equivalente o complementario) y no se
  fusionan sin acta.
- Además hay requisitos de departamento (`DR-CON-*`, `DR-REC`, `DR-RH`, `DR-MSG`, `DR-PLT`) y criterios de
  aceptación (`AT-01`…`AT-29`).

### 2.2 Documentos de trazabilidad
| Documento | Qué relaciona |
|---|---|
| `docs/fuentes/02_Matriz_Maestra_208_Requisitos.xlsx` | Matriz original |
| `docs/producto/requisitos_208.json` | Inventario estructurado |
| `docs/producto/mapa_cobertura.md` / `.csv` | Cada ID: módulo, fase, clasificación y decisiones. Generado con `scripts/build_coverage.py` |
| `docs/producto/trazabilidad_codigo.md` | Requisito → archivo de código → prueba, por incremento |
| `docs/producto/registro_decisiones_matriz.md` | D-01…D-25 con riesgo e IDs afectados |
| `docs/producto/decisiones.md` | Decisiones del proyecto T-01…T-60 y su estado |
| `docs/pruebas/evidencias_*.md` | Criterio de aceptación → prueba → captura |
| `apps/web/lib/modules.ts` | Cada módulo del menú con sus requisitos, pruebas y decisiones |
| `apps/api/app/agents/registry.py` | Cada agente con los requisitos que cubre |

### 2.3 Cobertura de la matriz (clasificación)
| Fuente | Equivalente | Complementario | Nuevo | Contradictorio | Sin definición | Total |
|---|---|---|---|---|---|---|
| Informe 120 | 24 | 22 | 43 | 2 | 29 | 120 |
| Qubiq 70 | 17 | 24 | 0 | 15 | 14 | 70 |
| Acuerdos 18 | 0 | 15 | 1 | 2 | 0 | 18 |
| **Total** | **41** | **61** | **44** | **19** | **43** | **208** |

- **Contradictorio** quiere decir que el requisito contiene una afirmación jurídica, fiscal u operativa que hay que
  corregir antes de programarlo.
- **Sin definición** quiere decir que depende de una decisión abierta.

### 2.4 Implementado y vinculado a código (F5.6)
`trazabilidad_codigo.md` vincula a código y pruebas **68 identificadores de la matriz** (30 I, 34 Q, 4 U), además de
los requisitos de departamento DR y los criterios AT. El resto está planificado por fase o bloqueado por una
decisión (ver `mapa_cobertura.md`).

### 2.5 Cómo mantener la trazabilidad (también en Odoo)
1. Cada cambio cita sus IDs en el mensaje del commit y en la descripción de la *pull request*.
2. Cada módulo `sp_*` lleva en su `README` la lista de IDs que cubre, y cada prueba lleva el ID en su nombre o
   docstring.
3. Al cerrar un incremento: actualizar `trazabilidad_codigo.md`, regenerar `mapa_cobertura.md` y escribir las
   evidencias.
4. Un requisito con decisión abierta no se implementa «a ojo»: se escala.

## 3. Auditoría en Odoo Community
| Necesidad | Solución recomendada |
|---|---|
| Cambios de campos | OCA `auditlog` (reglas por modelo: crear, escribir, borrar; lectura en modelos sensibles) |
| Inmutabilidad | Modelo propio `sp.audit.event` (solo `create`; `write` y `unlink` lanzan error) **y** triggers SQL creados en `init()` que bloquean UPDATE y DELETE |
| Cadena de hash | Calcular `hash` en `create` con un bloqueo `pg_advisory_xact_lock` (copiar `compute_hash` de `app/audit.py`) |
| Denegaciones | Registrar en un cursor aparte (`self.env.registry.cursor()`) al capturar `AccessError` en los controladores |
| Descargas | Controlador propio de descarga de adjuntos que audita antes de servir |
| Accesos | Inicios de sesión (`res.users.log`) + eventos propios de MFA y fallos |
| Chatter | Útil para el usuario, pero **no** sirve como auditoría: se puede editar o borrar con permisos |

## 4. Auditorías externas recomendadas
- **Seguridad**: prueba de intrusión antes de abrir el servidor a Internet y después de cada cambio importante.
  Prioridades: aislamiento entre entidades y roles, `sudo()` en Odoo y el portal del cliente.
- **Protección de datos (RGPD/LOPDGDD)**: registro de actividades, evaluación de impacto (hay datos de extranjería y
  de salud en las bajas), contratos de encargado del tratamiento (servidor, correo, Callbell) y política de retención
  (D-17).
- **Fiscal**: facturación solo con un sistema certificado (VeriFactu, D-07).
