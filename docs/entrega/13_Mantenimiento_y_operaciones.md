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

**Odoo 20 · conexión directa con el banco** (`sp_banco_psd2`; 11 · DOC-20; activa solo cuando se decida
18 · AL-16):

| Proceso | Frecuencia | Dónde | Qué hace |
|---|---|---|---|
| Descarga de movimientos (PSD2) | Cada 6 horas | Tarea «Banco: descargar movimientos de las conexiones directas (PSD2)» (`ir.cron`, `_sp_cron`) | Descarga los movimientos contabilizados de cada cuenta unida a un diario: la primera vez, 90 días; después, desde la última fecha menos 3 días, sin duplicar. Los registra como un extracto y el agente propone. Avisa 15 días antes de caducar la autorización y marca «Caducada» al vencer |

- **Límite de consultas:** los bancos permiten unas **4 consultas al día** por cuenta sin el titular presente. Por
  eso la tarea va cada 6 horas: **no acorte el intervalo**. Si el banco responde que se ha superado el límite (429),
  la conexión sigue activa y se reintenta en la siguiente vuelta. «Descargar movimientos ahora» también consulta
  al banco: úselo con moderación.
- **Renovación cada 180 días:** cada banco exige volver a autorizar la lectura de cuentas como máximo cada 180 días
  (modificación de las RTS de la EBA). Odoo pide 179 días y avisa a Contabilidad 15 días antes con una actividad.

## 2. Rutinas de operación
### Diaria
- Comprobar que la copia de la noche figura como **Válida** en Administración → Copias de seguridad.
- Revisar «Pendientes de decidir» de cada departamento (lo hace cada responsable).
- Contabilidad: la rutina indica qué falta, sin que nadie tenga que acordarse.
- Odoo 20 · Contabilidad: si hay conexiones directas con el banco, comprobar que ninguna está en «Caducada» o
  «Error» y atender las actividades de renovación (15 §10e).

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

### 4.1 Odoo 20 · clave de cifrado (`sp_cifrado`)
Desde el 16/11/2026 (11 · DOC-19), Odoo 20 guarda cifrados los IBAN y los extractos originales (08 §3.1). La clave
`SP_CLAVE_CIFRADO` está en `odoo/.env`, fuera de la base de datos y del repositorio.

| Qué | Cómo |
|---|---|
| Copia de la clave | Una copia segura aparte, en un gestor de secretos, **separada** de las copias de la base y del almacén de archivos. Hágala al montar el sistema, no después |
| Copia de la base | `pg_dump` de la base **y** del almacén de archivos (los extractos cifrados son adjuntos). Sin la clave, esa copia no deja leer los IBAN ni los extractos: es lo que se busca |
| Restaurar | Restaure la base, el almacén de archivos **y** `odoo/.env` con la **misma** clave. Compruebe después un IBAN en Odoo: si aparece «[cifrado: no se puede leer]», la clave no es la de esa base; si aparece «[cifrado: falta la clave]», Odoo no la recibe |
| Quién la custodia | Administración del sistema (TI), con conocimiento de Dirección. **Por decidir:** persona concreta y gestor de secretos |
| Rotación (cambiar la clave) | **Sin procedimiento todavía** (12 · ABI-06). Hasta que exista, **no cambie la clave**: lo ya cifrado dejaría de leerse. No desinstale `sp_cifrado` para «volver atrás»: descifra los IBAN, pero `sp_banco` depende de él |
| Sin cifrar | Concepto, ordenante e importe de los movimientos, PDF de facturas y justificantes (12 · ABI-07). Por eso siguen haciendo falta el disco cifrado del servidor y las copias cifradas |

## 5. Recuperación ante desastre
Solo con autorización de Dirección; queda anotado en la auditoría.
1. Parar `api`, `web` y `avisos`.
2. Arrancar `db`, borrar y crear la base, y `pg_restore --no-owner --exit-on-error`.
3. Restaurar los volúmenes de archivos y el `.env` con sus claves (en Odoo 20, también `odoo/.env` con
   `SP_CLAVE_CIFRADO`; §4.1).
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
| Odoo 20 · conexión directa con el banco | Estado de cada conexión y «Última sincronización» (`sp_banco_psd2`) | Una conexión «Caducada» o «Error», o más de 24 h sin sincronizar |

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
