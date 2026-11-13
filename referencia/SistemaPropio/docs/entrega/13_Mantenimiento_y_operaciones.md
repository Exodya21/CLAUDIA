# 13 · Documentación de mantenimiento y operaciones

Sistema Propio · versión F5.6 · 12/11/2026

## 1. Procesos automáticos
| Proceso | Frecuencia | Dónde | Qué hace |
|---|---|---|---|
| Agentes programados | Cada 5 min | Contenedor `avisos` → `python -m app.ops.agents` | Rutina de Contabilidad, informes que tocan, avisos de RRHH, mensajes pendientes |
| Cola de correo | Cada 5 min | `python -m app.ops.outbox` | Envía los avisos pendientes con reintentos; marca «no configurado» si falta SMTP |
| Avisos urgentes sin leer | Cada 5 min | `comm.core.sweep_urgent` (desde `outbox`) | Escala los avisos urgentes no leídos |
| Migraciones y roles | En cada arranque | Orden del contenedor `api` | `alembic upgrade head` + `catalog_sync` |
| Copia de seguridad | Diaria (programada) | `COPIA_SEGURIDAD(_REAL).bat` o `ops/copia.sh` + `app.ops.backup` | `pg_dump`, restauración de comprobación y verificación de la auditoría |

En Odoo, estos procesos pasan a `ir.cron` (agentes, cola `mail.mail`) y a una tarea del sistema (copias).

## 2. Rutinas de operación
### Diaria
- Comprobar que la copia de la noche figura como **Válida** en Administración → Copias de seguridad.
- Revisar «Pendientes de decidir» de cada departamento (lo hace cada responsable).
- Contabilidad: la rutina indica qué falta, sin que nadie tenga que acordarse.

### Semanal
- Copiar la copia más reciente fuera del servidor (cifrada).
- Revisar las alertas: disco, certificados, errores 5xx.
- Revisar en la auditoría los accesos denegados (`outcome = denied`) por si hay patrones extraños.

### Mensual
- Verificar la integridad de la auditoría (Ajustes → Auditoría → **Verificar integridad**).
- Revisar los usuarios activos: bajas, cambios de rol y autorizaciones puntuales caducadas.
- Aplicar las actualizaciones de seguridad del sistema operativo y de Docker o Odoo, en preproducción primero.

### Trimestral
- **Simulacro de recuperación** completo en un servidor aparte (ver §5).
- Revisar los permisos por rol con Dirección y el DPO.

## 3. Actualizar a una versión nueva
### Windows (instalación actual)
1. `COPIA_SEGURIDAD(_REAL).bat`.
2. Sustituya los archivos del programa por los de la versión nueva, **conservando** `.env`, `.env.real`, `copias` y
   `copias_real`.
3. `INICIAR(_REAL).bat`: reconstruye y aplica las migraciones pendientes automáticamente.
4. Compruebe que se puede entrar y que la copia siguiente sale válida.

### Servidor
```bash
docker compose exec -T db sh /ops/copia.sh            # copia previa
git pull && docker compose up -d --build              # migra al arrancar
docker compose logs -f api | grep -i error            # revisar
```
Las migraciones son reversibles: `docker compose exec api alembic downgrade -1`. Hágalo **solo** con una copia previa
y si la versión anterior no escribió datos que dependan del cambio.

### Odoo
`odoo-bin -u sp_modulo -d base --stop-after-init`, siempre antes en preproducción con una copia anonimizada o
ficticia. Hay que fijar las versiones de los módulos OCA.

## 4. Copias de seguridad
Procedimiento detallado: `docs/operacion/copias_y_restauracion.md`. En resumen:
1. `pg_dump -Fc` a `copias/sp_AAAAMMDDTHHMMSSZ.dump`.
2. Restauración en `<base>_comprobacion`. Se comprueba el esquema, que la cadena de auditoría se verifica entera y que
   su último evento coincide con el de producción.
3. Registro en `backup_run` (solo inserción) y en la auditoría. Se conservan las 14 últimas.
4. **Los archivos** (volúmenes `documentos` y `justificantes`) se copian aparte. En el servidor:
   `docker run --rm -v sistemapropio_documentos:/d -v /backup:/b alpine tar czf /b/docs_$(date +%F).tgz -C /d .`
5. **Las claves** (`.env` / `.env.real`) se guardan aparte, en un gestor de secretos. Sin ellas, los documentos y los
   IBAN no se pueden descifrar.

## 5. Recuperación ante desastre
Solo con autorización de Dirección; queda anotado en la auditoría.
1. Parar `api`, `web` y `avisos`.
2. Arrancar `db`, borrar y crear la base, y `pg_restore --no-owner --exit-on-error`.
3. Restaurar los volúmenes de archivos y el `.env` con sus claves.
4. Arrancar y **Verificar integridad** de la auditoría.
5. Objetivos: **RPO ≤ 24 h** (copia diaria; se puede bajar con WAL o más copias) y **RTO ≤ 4 h**.

## 6. Supervisión
| Qué | Cómo | Umbral |
|---|---|---|
| Disponibilidad | `GET /api/v1/health` cada minuto | 2 fallos seguidos → aviso |
| Disco | Monitor del sistema | > 80 % |
| Copias | Resultado en `backup_run` | Una no válida o ausente durante 24 h |
| Certificado TLS | Caducidad | < 15 días |
| Errores | Registro de la API (5xx, con `request_id`) | Picos |
| Seguridad | Auditoría `denied`, bloqueos por intentos fallidos | Picos de una IP o un usuario |
| Cola de correo | Pendientes en `comm_outbox` | > 1 h sin enviar |

## 7. Tareas de mantenimiento de datos
- **Nada se borra físicamente.** Para «limpiar», se anula o se archiva con motivo.
- **Usuarios que dejan el despacho:** desactivar (no borrar), cerrar sus pertenencias y revocar sus sesiones.
  Reasignar sus expedientes y tareas.
- **Restablecer el segundo factor** de alguien que cambia de móvil: Administración → Usuarios → «Restablecer
  credenciales». La persona vuelve a enrolarse.
- **Catálogo de trámites de extranjería:** cada cambio se valida en la aplicación por Legal Extranjería.
- **Retención de datos:** pendiente de la política del DPO (D-17). Hasta entonces, se conserva todo.

## 8. Contactos de operación
| Rol | Responsabilidad |
|---|---|
| Administración del sistema (TI) | Servidor, copias, actualizaciones, supervisión |
| Dirección | Autorizar restauraciones, roles, agentes y excepciones |
| DPO | Permisos, retención, incidentes de datos personales (notificación a la AEPD en 72 h si procede) |
| Equipo de desarrollo | Versiones, incidencias (ver 12) |
