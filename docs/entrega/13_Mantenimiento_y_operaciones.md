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

**Odoo 20 · servidor propio** (`despliegue/`; 11 · DOC-21):

| Proceso | Frecuencia | Dónde | Qué hace |
|---|---|---|---|
| Copia de seguridad cifrada | Cada día a las 02:30 | `/etc/cron.d/odoo-despacho-copias` → `despliegue/copia_seguridad.sh`; registro en `/var/log/odoo-despacho-copias.log` | Copia cifrada de la base y del almacén de archivos, con huellas y rotación (§4.2) |
| Certificado HTTPS | Automático | Caddy | Obtiene y renueva el certificado de Let's Encrypt. Necesita el puerto 80 abierto |

## 2. Rutinas de operación
### Diaria
- Comprobar que la copia de la noche figura como **Válida** en Administración → Copias de seguridad.
- Revisar «Pendientes de decidir» de cada departamento (lo hace cada responsable).
- Contabilidad: la rutina indica qué falta, sin que nadie tenga que acordarse.
- Odoo 20 · servidor propio: revisar en `/var/log/odoo-despacho-copias.log` que la copia de la noche termina en
  «Copia correcta». Mientras no haya avisos automáticos, es la única forma de saberlo (12 · ABI-10).
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
- Odoo 20 · servidor propio: **restaurar una copia** en una base aparte con `restaurar.sh` (§4.2), comprobarla en Odoo
  (por ejemplo, un IBAN y un adjunto) y borrarla después. Anote la fecha y el resultado.
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

### Odoo 20 · servidor propio (`despliegue/actualizar.sh`)
```bash
cd /opt/despacho/despliegue && sudo bash actualizar.sh
```
Hace, en este orden:
1. **Copia previa** con `copia_seguridad.sh` (§4.2).
2. `git pull --ff-only`: descarga la versión nueva de GitHub con la clave de despliegue de solo lectura. Si la rama
   local se ha desviado, se para sin mezclar nada.
3. Reconstruye la imagen `despacho/odoo:20`, para Odoo, instala o actualiza los módulos `sp_*` (`-i` y `-u`) y
   arranca todo.

Si algo falla, la copia previa está en `/var/backups/odoo-despacho` y se restaura con `restaurar.sh`. Hágalo siempre
antes en preproducción. `instalar.sh` también se puede repetir: no cambia las claves ni borra datos (09 §8).

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

### 4.2 Odoo 20 · servidor propio: copias cifradas y custodia de `.env`
Desde el 16/11/2026 (11 · DOC-21). Topología y resumen: 03 §6.1. Guía: `despliegue/LEEME.md` §4 y §5.

**Copia diaria** (`despliegue/copia_seguridad.sh`, a las 02:30):

| Qué | Cómo |
|---|---|
| Contenido | `<base>_AAAAMMDD_HHMM.base.enc` (`pg_dump -Fc`), `<base>_AAAAMMDD_HHMM.archivos.enc` (almacén de archivos) y `<base>_AAAAMMDD_HHMM.sha256` (huellas) |
| Cifrado | `openssl` AES-256-CBC, PBKDF2 con 200 000 iteraciones, clave `CLAVE_COPIAS` de `.env`. El archivo empieza por `Salted__` (comprobado) |
| Dónde | `/var/backups/odoo-despacho` (permisos 700) |
| Rotación | 14 días; los domingos, 8 semanas; los días 1, 12 meses |
| Copia manual | `sudo bash /opt/despacho/despliegue/copia_seguridad.sh` |
| Fuera del servidor | **A mano por ahora**, a un NAS o almacenamiento externo en la UE (regla 3-2-1). Ya van cifradas. **Pendiente** decidir dónde (T-17; 18 · AL-17) |

**Restauración de comprobación (cada trimestre, §2):**
```bash
sudo bash /opt/despacho/despliegue/restaurar.sh /var/backups/odoo-despacho/sp_preproduccion_AAAAMMDD_HHMM
```
- Comprueba las huellas SHA-256 y restaura la base y los archivos en una base **nueva**
  (`<base>_restaurada_<fecha>`). Indica cuántos asientos tiene.
- La restauración no toca la base en uso ni sus archivos (defecto 12 · ABI-11 resuelto el 16/11/2026 y comprobado).
- Compruébela y bórrela con el comando que muestra al terminar.
- Comprobado el 16/11/2026 en el servidor simulado: huellas correctas y base restaurada aparte.

**Recuperar de verdad** (sustituir la base en uso), solo con autorización de Dirección y con ayuda: restaurar en una
base nueva, comprobarla, parar Odoo, cambiar `BASE` en `.env` por el nombre de la restaurada y ejecutar otra vez
`instalar.sh` (LEEME §5).

**Custodia de `despliegue/.env`:**

| Clave | Para qué | Si se pierde |
|---|---|---|
| `POSTGRES_PASSWORD` | Acceso de Odoo a PostgreSQL | Se puede cambiar con acceso al servidor |
| `ADMIN_PASSWD` | Contraseña maestra de Odoo (gestor de bases, cerrado en el servidor) | Se puede cambiar con acceso al servidor |
| `SP_CLAVE_CIFRADO` | Cifrado de los IBAN y de los extractos (§4.1) | **Los IBAN y los extractos originales no se pueden leer** |
| `CLAVE_COPIAS` | Cifrado de las copias | **Las copias no se pueden restaurar** |

1. Al terminar la instalación, **copie `.env` fuera del servidor** en un gestor de contraseñas o en un USB cifrado en
   la caja fuerte (`sudo cat /opt/despacho/despliegue/.env`). Nunca por correo ni por chat, ni en el repositorio.
2. **Nunca junto a las copias:** `SP_CLAVE_CIFRADO` y `CLAVE_COPIAS` no van dentro de la copia; si viajaran juntas,
   el cifrado no protegería nada.
3. No cambie `SP_CLAVE_CIFRADO` (12 · ABI-06). `instalar.sh` no la toca nunca.
4. **Pendiente:** quién la custodia y dónde (18 · AL-17). Mientras tanto: Administración del sistema (TI), con
   conocimiento de Dirección (§4.1).

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
| Odoo 20 · servidor propio | `/var/log/odoo-despacho-copias.log`, espacio en disco, caducidad del certificado de Caddy | **Sin avisos automáticos todavía** (12 · ABI-10): revisión manual (§2) |
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
