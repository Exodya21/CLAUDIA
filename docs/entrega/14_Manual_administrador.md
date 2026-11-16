# 14 · Manual del administrador

Sistema Propio · versión F5.6 · 12/11/2026. Para personas con rol **Dirección**, que es el que incluye
`admin.users.manage`, `agents.manage`, `audit.read` y `admin.backups.read`.

## 1. Primer acceso
1. Entre en `http://localhost:3000` (o en la dirección del servidor) con el usuario y la contraseña provisional que
   dio la instalación.
2. **Cambie la contraseña.** Mínimo 12 caracteres, sin datos personales.
3. **Active el código del móvil (TOTP).**
   - Abra Google Authenticator o Microsoft Authenticator → «Añadir» → **Escanear QR**.
   - Si no puede escanear, elija **«Introducir clave de configuración»**:
     - nombre de la cuenta: `Sistema Propio`;
     - clave: la que aparece bajo el QR, sin espacios;
     - tipo: **Basado en tiempo**.
   - Escriba el código de 6 dígitos para confirmar.
4. **Nunca comparta capturas** de la pantalla del QR ni de la clave: quien la tenga puede generar sus códigos.

## 2. Usuarios
**Administración → Usuarios**

| Acción | Cómo | Qué pasa |
|---|---|---|
| Alta | «Nuevo usuario»: usuario (`nombre.apellido`), nombre, correo | Se muestra **una vez** una contraseña provisional; al entrar, la persona cambia la contraseña y activa el TOTP |
| Dar acceso | «Añadir pertenencia»: entidad, rol, departamento y sede (vacío = todas las sedes de la entidad) | Una persona puede tener varias pertenencias (por ejemplo, Laboral en Barcelona y en Madrid) |
| Quitar acceso | «Terminar pertenencia» | Queda la fecha de fin; no se borra |
| Móvil perdido o nuevo | «Restablecer credenciales» | Nueva contraseña provisional y nuevo TOTP; se cierran sus sesiones |
| Cerrar sesiones | «Revocar sesiones» | Útil si alguien dejó la sesión abierta en otro equipo |
| Baja | «Desactivar» | No puede entrar; su historial se conserva. «Reactivar» la deshace |

**Roles disponibles:** Dirección, Líder Laboral, Líder Extranjería, Recepción, Atención al cliente, Asesor Laboral,
Asesor Extranjería, Gestor Laboral, Contabilidad, Marketing, RRHH y Soporte Colombia. Qué puede hacer cada uno:
08 · Seguridad, matriz del apartado 5.

**Buenas prácticas**
- Separación de funciones. Contabilidad necesita al menos una persona con rol **Contabilidad**: Dirección autoriza y
  aprueba, pero no importa extractos ni registra facturas.
- Para firmar remesas hacen falta **dos personas de Dirección distintas** de quien propone.
- Para validar cajas, la persona que valida debe ser distinta de quien cuenta.

## 3. Autorizaciones puntuales
**Expediente → Autorizaciones.** Permiten a alguien ver un expediente concreto que no tiene asignado, con motivo y
fecha de caducidad. Se pueden revocar. Todo queda en la auditoría.

## 4. Entidades, sedes y departamentos
- Se crean en la instalación (`primer_admin --sedes`). Los departamentos (Laboral, Extranjería, Contabilidad,
  Dirección, etc.) salen del catálogo.
- Por ahora **no hay pantalla** para añadir sedes después. Una sede nueva la da de alta el equipo técnico (o se
  incluirá en la versión Odoo).

## 5. Agentes
**Administración → Agentes**
- Activar o desactivar cada agente.
- Ver sus ejecuciones y el número de propuestas.
- **Modo automático de mensajes al cliente** (T-47): solo si Dirección lo decide. Sin él, cada mensaje es una
  propuesta que alguien aprueba.
- «Ejecutar ahora»: lanza una revisión inmediata.

## 6. Contabilidad: configuración de Dirección
- **Rutina → Responsables:** asigne una persona a cada paso. Solo aparecen quienes tienen permiso para ese paso.
- **Cierre del mes:** revise y apruebe. Una vez aprobado no se puede cambiar; si hay un error, Contabilidad prepara
  una revisión nueva.
- **Remesas:** firme desde los pendientes de Contabilidad. Quien ya firmó no puede dar la segunda firma.
- **Informes:** márquelos como revisados desde sus pendientes.

## 7. Copias de seguridad
**Administración → Copias de seguridad** muestra cada copia, con estado **Válida** o **No válida** y el motivo.
- Programe `COPIA_SEGURIDAD_REAL.bat` cada día en el Programador de tareas de Windows (en el servidor, con `cron`).
- Guarde fuera del equipo la carpeta `copias_real` **y**, por separado, `.env.real`.
- Restaurar: ver 13 · Mantenimiento, §5. Solo con su autorización.

## 8. Auditoría
**Ajustes → Auditoría** (permiso `audit.read`)
- Filtros por persona, acción, recurso, resultado (`ok`, `denied`) y fechas.
- **Verificar integridad:** recorre la cadena y confirma que ningún evento se ha alterado ni eliminado.
- Los accesos de Dirección también se registran.

## 9. Configuración que se hace en el archivo `.env.real`
| Línea | Para qué |
|---|---|
| `OWN_TAX_IDS=` | CIF del despacho, para que la lectura de facturas no lo confunda con el del proveedor |
| `SMTP_HOST=`, `SMTP_USER=`, `SMTP_PASSWORD=`, `SMTP_FROM=` | Correo saliente de avisos (T-33) |

Después de cambiarlo, vuelva a ejecutar `INICIAR_REAL.bat`. **No cambie** `FIELD_ENCRYPTION_KEY`,
`SESSION_SECRET` ni `POSTGRES_PASSWORD`: con otra clave de cifrado, los documentos y los IBAN dejan de poder leerse.

## 10. Ante un incidente de seguridad
1. Desactive la cuenta afectada y revoque sus sesiones.
2. Revise la auditoría: qué vio o descargó, y cuándo.
3. Avise al DPO. Si hay datos personales afectados, puede ser obligatorio notificarlo a la AEPD en 72 horas.
4. Restablezca las credenciales y anote lo ocurrido (12 · Incidencias).

## 11. Odoo 20 · clave de cifrado de los IBAN y extractos
Desde el 16/11/2026 (11 · DOC-19), el módulo `sp_cifrado` guarda cifrados en la base de datos los IBAN (clientes,
proveedores, personal, cuentas propias y contrapartidas de los movimientos) y `sp_banco` guarda cifrado el extracto
original (08 §3.1).

**Dónde vive la clave.** En el archivo `odoo/.env` del servidor, línea `SP_CLAVE_CIFRADO=…` (o en la opción
`sp_clave_cifrado` del archivo de configuración de Odoo). **Nunca** en la base de datos ni en el repositorio. El
montaje la crea la primera vez (09 · Anexo C). Guarde enseguida una copia segura aparte (13 §4.1).

**Qué pasa si falta o no es la buena:**

| Situación | Qué se ve | Qué hacer |
|---|---|---|
| Falta la clave | Los IBAN aparecen como «[cifrado: falta la clave]» y Odoo **no deja guardar** ningún IBAN nuevo (mensaje de error). No se puede importar un extracto ni descargar su original | Restaure `odoo/.env` desde la copia segura y reinicie Odoo |
| Clave equivocada (de otra base o cambiada) | Los IBAN aparecen como «[cifrado: no se puede leer]» | Ponga la clave correcta de esa base. **No la sustituya por una nueva**: lo cifrado no se recupera sin la original |
| Clave perdida sin copia | Los IBAN de esa base y los extractos originales no se pueden leer | Volver a dar de alta los IBAN comprobándolos con su titular o con el banco. Por eso la copia de la clave es obligatoria |

- **No cambie la clave:** no hay todavía procedimiento de rotación (12 · ABI-06).
- **Descargar un extracto original:** solo Contabilidad, con el botón **Descargar el original** de la importación
  (08 §12).
- Si sospecha que la clave se ha expuesto: trátelo como incidente de seguridad (§10) y avise al equipo de desarrollo
  (hace falta la rotación, aún sin procedimiento).

## 12. Odoo 20 · conexión directa con el banco (PSD2)
Desde el 16/11/2026 (11 · DOC-20), el módulo `sp_banco_psd2` descarga solo los movimientos de las cuentas del
despacho a través del agregador **Enable Banking** (18 §2.1). Está instalado pero **desactivado**: no se activa hasta
que la Dirección decida 18 · AL-16.

**Activarlo (una vez):**
1. **Decisión de la Dirección (AL-16):** alta de la empresa en Enable Banking y **encargo del tratamiento** firmado
   (art. 28 RGPD), con la confirmación por escrito de la gratuidad para cuentas propias. Anótelo en el registro de
   actividades de tratamiento (con el DPO).
2. En el portal de Enable Banking, la persona autorizada crea la **aplicación** en el modo restringido y registra la
   **URL de vuelta**: la dirección de Odoo seguida de `/sp_banco_psd2/vuelta`, con `https` en producción (la muestra
   la pantalla de la conexión, en «Dirección de vuelta», solo a los administradores del sistema).
3. La **clave privada `.pem`** de la aplicación la genera y la guarda esa persona directamente en el servidor, en
   `odoo/secretos/`. **Nunca** se envía por correo ni por chat, ni se sube al repositorio. Haga una copia en el gestor
   de secretos, como la clave de cifrado (§11).
4. Ponga `SP_EB_APP_ID` (id de la aplicación) y `SP_EB_CLAVE` (ruta del `.pem` dentro del contenedor, en
   `/secretos/`) y reinicie Odoo (09 · Anexo C).
5. **Pruebe antes con el entorno de pruebas del agregador** (`SP_EB_API`) desde un equipo con Internet (12 · ABI-08).
6. Contabilidad crea una conexión por banco y la autoriza en la banca del despacho (15 §10e). Compruebe que cada
   cuenta queda unida a su diario.

**Renovarlo:** la autorización de cada banco dura como máximo **180 días** (Odoo la pide por 179). Quince días antes,
Odoo crea una actividad para Contabilidad; la renueva Contabilidad con **Renovar la autorización** (15 §10e). Si
caduca, la conexión pasa a «Caducada» y deja de descargar hasta que se renueve; los extractos se pueden seguir
importando a mano.

**Cambiar o retirar las credenciales:**

| Situación | Qué hacer |
|---|---|
| La clave `.pem` se ha expuesto o hay que cambiarla | Trátelo como incidente de seguridad (§10). Genere otra clave en el portal del agregador, sustituya el archivo en `odoo/secretos/`, actualice `SP_EB_CLAVE` si cambia el nombre y reinicie Odoo. Revoque la clave antigua en el agregador |
| Dejar de usar la conexión | Contabilidad pulsa **Revocar** en cada conexión (cierra la sesión en el agregador). Después, vacíe `SP_EB_APP_ID` y `SP_EB_CLAVE` y reinicie Odoo |
| Cambia la dirección de Odoo | Cambie la URL de vuelta registrada en el agregador |

- **Límite de consultas:** los bancos permiten unas 4 consultas al día sin el titular presente; la tarea va cada 6
  horas (13 §1). No acorte ese intervalo.
- **Respaldo sin PSD2:** pedir a cada banco el envío diario de la Norma 43 (SFTP, EDITRAN o banca electrónica), que
  entra por el importador ya hecho.
