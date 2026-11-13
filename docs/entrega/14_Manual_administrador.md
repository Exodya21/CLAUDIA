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
