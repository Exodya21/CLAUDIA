# Amenazas, privacidad y límites (F0.1 + F0.2)

Este documento identifica requisitos de diseño. **No declara cumplimiento** de RGPD, LOPDGDD ni de ninguna otra
norma: eso exige la revisión del DPO y de asesoría jurídica sobre el sistema real y sus contratos.

## Amenazas consideradas y control aplicado

| Amenaza | Control F0.1 | Evidencia |
|---|---|---|
| Acceso cruzado Laboral ↔ Extranjería forzando URL o API | Política en backend + filtro SQL; 403 auditado | AT-01 (`test_at01_*`), captura 06 |
| Recepción leyendo estrategia jurídica | Nivel `metadata` / `minimal`, enmascarado en servidor | AT-02 (`test_at02_*`), captura 03 |
| Enumeración de contactos o documentos | Criterio ≥3 caracteres, documento exacto, paginación ≤50, UUID | `test_paginacion_limitada`, `test_recepcion_no_puede_listar…` |
| IDOR entre entidades | Frontera por entidad, 404 sin confirmar existencia | `test_usuario_de_otra_entidad_no_enumera_ni_lee` |
| Inyección SQL / comodines | Parámetros enlazados, escape de `%` `_` `\` | `test_inyeccion_sql_*` (6 cargas) |
| Manipulación de la auditoría | Triggers anti UPDATE/DELETE/TRUNCATE + cadena SHA-256 | `test_bitacora_no_admite…`, `/audit-events/verify` |
| Borrado de expedientes | Sin endpoint DELETE (405) + trigger en BD | `test_no_existe_borrado…` |
| Fusión errónea de personas | Sin fusión automática; cola `duplicate_review` | AT-04 |
| Sobrescritura concurrente | Control de versión optimista + bloqueo de fila | `test_control_de_version…` |
| CSRF | Cookie `SameSite=Strict` + cabecera propia | `test_sin_sesion_401_y_csrf` |
| Modo demo en producción | Validación de configuración al arrancar | `test_demo_prohibido_en_produccion` |
| Fuga de datos en errores | Manejador único sin trazas | `errors.py` |

## Riesgos abiertos (no resueltos en F0.1)

| Riesgo | Mitigación prevista | Incremento |
|---|---|---|
| ~~Sin MFA real~~ | **Resuelto F0.2**: contraseña + TOTP obligatorio; OIDC con MFA listo a falta del proveedor (T-01) | F0.2 ✅ |
| ~~Sesión no revocable~~ | **Resuelto F0.2**: `user_session`, revocación inmediata, cierre por inactividad | F0.2 ✅ |
| ~~Sin límite de intentos de acceso~~ | **Resuelto F0.2** para acceso (usuario e IP). Pendiente: límite general de peticiones en búsquedas | F0.2 ✅ / despliegue |
| ~~Sin copia y restauración probadas~~ | **Resuelto F0.2**: AT-29 con restauración real y verificación de la cadena de auditoría | F0.2 ✅ |
| La IP del límite por IP la aporta la web (`X-Forwarded-For`); un cliente puede falsear esa cabecera y esquivar **solo** el límite por IP (el límite por usuario sigue) | En producción, un proxy inverso que **sobrescriba** `X-Forwarded-For` delante de la web (T-02) | Despliegue |
| Copias en el mismo ordenador que el sistema y sin cifrar | Copia externa cifrada (disco cifrado o nube en la UE con contrato de encargo); cifrado de las copias con clave fuera del servidor | T-02 / producción |
| Recuperación del segundo factor depende de Dirección (restablecer) | Sin códigos de recuperación por ahora: evita otra credencial que custodiar. Revisar con DPO | T-15 |
| Sin cifrado de columnas sensibles | Evaluar cifrado de `identifier.number_normalized` (hoy protegido por permisos y enmascarado) | F0.2 (decisión T-09) |
| Auditoría guarda teléfonos y nombres en claro | Acceso solo Dirección; documentos ya enmascarados. Revisar con DPO la minimización | T-04 |
| Logs de servidor | No registran cuerpos de petición; revisar configuración de proxy en despliegue | Despliegue |

## Amenazas añadidas en F0.2 y su control

| Amenaza | Control | Prueba |
|---|---|---|
| Robo de contraseña | Segundo factor TOTP obligatorio; OIDC solo con MFA declarado | `test_acceso_normal_pide_codigo…`, `test_oidc_sin_mfa_denegado` |
| Fuerza bruta de contraseña o código | Bloqueo por usuario e IP, mensaje genérico, auditoría | `test_bloqueo_*` |
| Reutilización de un código TOTP | Se guarda el último paso aceptado | `test_acceso_normal…reutilizarlo` |
| Robo de cookie de sesión | Revocación inmediata, cierre por inactividad, `httpOnly` + `SameSite=Strict` | `test_cerrar_sesion_invalida_la_cookie…` |
| Paso intermedio usado como sesión | Token de tipo distinto (`pending`) y ruta limitada a `/api/v1/auth` | `test_paso_intermedio_no_sirve_como_sesion` |
| Empleado dado de baja con sesión abierta | Desactivar revoca todas sus sesiones al instante | `test_desactivar_cierra_sesiones…` |
| Escalada desde Administración a otra entidad | Ámbito por entidad, 404/403 auditados | `test_no_se_gestiona_a_usuarios_de_otra_entidad` |
| Dejar la entidad sin administración | Bloqueo del último administrador | `test_ultima_persona_administradora_protegida` |
| OIDC: CSRF, sustitución de token o firma falsa | `state`, `nonce`, PKCE S256, firma JWKS, emisor y audiencia | `test_oidc_*` |
| Alta automática de cuentas por el proveedor | Solo se enlazan cuentas creadas por Dirección | `test_oidc_sin_cuenta_no_crea_usuario` |
| Copia corrupta o manipulada | Restauración + verificación de la cadena + coincidencia con la base en uso | AT-29 |

## Amenazas añadidas en F5.0 (economía y gastos)

| Amenaza | Control |
|---|---|
| Fuga de justificantes (tickets con datos de terceros) | Cifrados en disco (Fernet), servidos solo a la persona y a Contabilidad/Dirección, cada consulta auditada; lectura OCR dentro del servidor, sin servicios externos |
| Archivo malicioso disfrazado de ticket | Tipo comprobado por la firma del archivo (JPG/PNG/PDF), 10 MB máximo, se sirve con `Content-Security-Policy: sandbox` |
| Presentar el mismo ticket dos veces | Huella SHA-256 por entidad: segunda subida rechazada |
| Autoaprobación de gastos o devoluciones | Doble control en API (`doble_control`) y auditoría |
| Descuadre de caja oculto | Arqueo con diferencia exige motivo y deja movimiento de ajuste; movimientos de caja solo de inserción |
| Números de tarjeta | Solo los 4 últimos dígitos (restricción en base de datos) |

## Reglas de datos
- Desarrollo y pruebas solo con datos ficticios: documentos `PASAPORTE ZZDEMO…` con país `XX` (código ISO reservado), correos en dominios `.invalid`. Los DNI/NIE de los tests (`12345678Z`, `X1234567L`) son ejemplos de cálculo de letra, no de personas.
- Nunca pegar datos reales en prompts, issues, commits ni logs.
- Antes de usar datos reales: DPIA/evaluación de impacto si procede, contratos de encargo con proveedores, decisión D-17 para Colombia, entorno de producción separado con copias cifradas y restauración probada.
