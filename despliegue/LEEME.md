# Odoo 20 del despacho en el servidor propio

Instalación en un servidor **Ubuntu Server 22.04 o 24.04**, con acceso desde Internet por un dominio y HTTPS.
De momento solo se instala la **preproducción**: datos **ficticios** y Verifactu en el **entorno de pruebas** de la
AEAT. Sirve para probarlo todo con Internet de verdad (AEAT, banco) y para que el equipo practique. La producción
con datos reales se instalará más adelante, en una base limpia (§9).

| Archivo | Qué es |
|---|---|
| `instalar.sh` | Instala o actualiza todo. Es seguro repetirlo: nunca cambia las claves ni borra datos |
| `docker-compose.yml` | PostgreSQL 16, Odoo 20 (imagen `despacho/odoo:20`) y Caddy (HTTPS automático) |
| `Caddyfile` | HTTPS con Let's Encrypt, cabeceras de seguridad, gestor de bases de datos cerrado |
| `odoo.conf.plantilla` | Configuración de Odoo; `instalar.sh` crea `odoo.conf` con las claves del servidor |
| `copia_seguridad.sh` | Copia diaria **cifrada** de la base de datos y de los archivos, con rotación |
| `restaurar.sh` | Restaura una copia en una base nueva, sin tocar la que está en uso |
| `actualizar.sh` | Copia previa, descarga de la versión nueva y actualización de los módulos |

Se crean **solo en el servidor**, nunca en el repositorio (están en `.gitignore`):

| Archivo | Qué contiene |
|---|---|
| `.env` | Contraseña de PostgreSQL, contraseña maestra de Odoo, clave de cifrado de los IBAN y clave de las copias |
| `odoo.conf` | La configuración de Odoo con esas contraseñas |
| `credenciales_preproduccion.txt` | Las contraseñas iniciales de los usuarios |
| `secretos/` | La clave privada del agregador bancario, si se activa PSD2 |

## 1. Antes de empezar

| Qué | Cómo |
|---|---|
| Servidor | Ubuntu 22.04/24.04, 4 núcleos y 16 GB como mínimo (recomendado: 8 núcleos y 32 GB), 100 GB libres o más. En la UE (documento 03 §3) |
| Dominio | Un registro DNS **A** de, por ejemplo, `odoo.midespacho.es` que apunte a la IP pública del servidor |
| Puertos | 80 y 443 abiertos hacia el servidor (en el router o en el proveedor). El 80 solo sirve para obtener el certificado y redirigir a HTTPS |
| Acceso | SSH con clave a un usuario con `sudo` |
| Correo | Una dirección para los avisos del certificado HTTPS, por ejemplo `sistemas@midespacho.es` |

## 2. Descargar el proyecto desde GitHub

El repositorio es privado. El servidor lo descarga con una **clave de despliegue de solo lectura**.

1. En el servidor, cree la clave (sin contraseña) y muestre la parte pública:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/despacho_github -N "" -C "servidor-odoo-despacho"
   ```
   ```bash
   cat ~/.ssh/despacho_github.pub
   ```
2. En GitHub: repositorio → **Settings** → **Deploy keys** → **Add deploy key**. Pegue la clave pública y deje
   **sin marcar** «Allow write access».
3. Descargue el proyecto en `/opt/despacho`:
   ```bash
   sudo mkdir -p /opt/despacho && sudo chown "$USER" /opt/despacho
   ```
   ```bash
   GIT_SSH_COMMAND="ssh -i ~/.ssh/despacho_github" git clone git@github.com:exodya21/claudia.git /opt/despacho
   ```
   ```bash
   cd /opt/despacho && git config core.sshCommand "ssh -i ~/.ssh/despacho_github"
   ```
4. Mientras el trabajo no esté unido a la rama principal, cambie a la rama de desarrollo:
   ```bash
   git checkout claude/practical-bardeen-k9ipgh
   ```

## 3. Instalar

```bash
cd /opt/despacho/despliegue && sudo bash instalar.sh --dominio odoo.midespacho.es --correo sistemas@midespacho.es --con-ejemplos
```

Tarda entre 5 y 10 minutos la primera vez. Hace esto:
1. Instala Docker si falta.
2. Crea `.env` con claves aleatorias.
3. Crea `odoo.conf`.
4. Construye la imagen y crea la base `sp_preproduccion` con:
   - contabilidad, España, Colombia y Verifactu;
   - los 8 módulos del despacho;
   - la configuración de demostración;
   - con `--con-ejemplos`, además, cobros, una devolución, facturas, gastos, extractos y un expediente pagado.
5. Pone la dirección pública y una **contraseña aleatoria a cada usuario**.
6. Arranca Odoo con HTTPS y abre los puertos 80, 443 y SSH en `ufw`.
7. Programa la copia diaria a las 02:30.

Al terminar, abra `https://odoo.midespacho.es`.

> Sin `--con-ejemplos` la base queda solo con la configuración, sin movimientos de ejemplo.

## 4. Inmediatamente después (importante)

1. **Copie `.env` a un lugar seguro y separado del servidor**, como un gestor de contraseñas o un USB cifrado en
   la caja fuerte:
   ```bash
   sudo cat /opt/despacho/despliegue/.env
   ```
   - Sin `SP_CLAVE_CIFRADO` no se pueden leer los IBAN.
   - Sin `CLAVE_COPIAS` no se pueden restaurar las copias.
   - Ninguna de las dos va dentro de las copias de seguridad.
2. **Contraseñas iniciales.** Léalas, repártalas a cada persona y **borre el archivo**. Cada persona cambia la
   suya desde su perfil (arriba a la derecha → Mi perfil → Seguridad). El usuario `admin` es el administrador de
   Odoo.
   ```bash
   sudo cat /opt/despacho/despliegue/credenciales_preproduccion.txt
   ```
   ```bash
   sudo shred -u /opt/despacho/despliegue/credenciales_preproduccion.txt
   ```
3. **Active el cortafuegos** si no lo estaba, después de comprobar que el SSH está permitido:
   ```bash
   sudo ufw status
   ```
   ```bash
   sudo ufw enable
   ```
4. **Copias fuera del servidor.** Las copias se guardan en `/var/backups/odoo-despacho`. Llévelas además a un NAS
   o a un almacenamiento externo en la UE (regla 3-2-1, documento 03 §6). Ya van cifradas.

## 5. Copias y restauración

- Copia manual en cualquier momento:
  ```bash
  sudo bash /opt/despacho/despliegue/copia_seguridad.sh
  ```
- Comprobar una copia, restaurándola en una base aparte (hágalo una vez al trimestre):
  ```bash
  sudo bash /opt/despacho/despliegue/restaurar.sh /var/backups/odoo-despacho/sp_preproduccion_AAAAMMDD_HHMM
  ```
- **Recuperar de verdad** (sustituir la base en uso): restaure en una base nueva, compruébela, pare Odoo, cambie
  `BASE` en `.env` por el nombre de la restaurada y ejecute de nuevo `instalar.sh`. Hágalo con ayuda.

## 6. Actualizar a una versión nueva

```bash
cd /opt/despacho/despliegue && sudo bash actualizar.sh
```

Hace una copia previa, descarga los cambios de GitHub, reconstruye la imagen, actualiza los módulos y reinicia.

## 7. Probar Verifactu con la AEAT (entorno de pruebas)

Odoo ya está en el **entorno de pruebas** de la AEAT, así que no se envía nada a producción.
1. La persona autorizada carga el **certificado** en Odoo (Contabilidad → Configuración → Ajustes →
   Veri*Factu). El certificado **nunca** se envía por correo ni por chat, ni se guarda en el repositorio.
2. Emita una factura de prueba (CIT o EXP) y compruebe en la pestaña Veri*Factu de la factura que la AEAT la acepta.
3. Pruebe también una factura de anticipo y la factura final de un expediente (documento 19 §3.7).
4. Anote el resultado para la gestoría (documento 18, AL-03 y AL-15).

## 8. Activar la conexión directa con el banco (PSD2)

Solo después de que Dirección lo apruebe y de firmar el encargo del tratamiento (documento 18, AL-16).
1. Alta de la empresa en Enable Banking y creación de la aplicación. Dirección de vuelta:
   `https://odoo.midespacho.es/sp_banco_psd2/vuelta`
2. Deje la clave privada en `despliegue/secretos/` (por ejemplo `enablebanking.pem`) y protéjala:
   ```bash
   sudo chown 100:101 secretos/enablebanking.pem && sudo chmod 400 secretos/enablebanking.pem
   ```
3. En `.env`, rellene `SP_EB_APP_ID=<id de la aplicación>` y `SP_EB_CLAVE=/secretos/enablebanking.pem`.
4. Ejecute de nuevo `sudo bash instalar.sh` para aplicar los cambios.
5. En Odoo: Facturación → Banco → Conexión directa (PSD2) → Nuevo → «Autorizar en el banco» (manual del usuario
   §10e).

## 9. Producción (más adelante)

`instalar.sh --entorno produccion` todavía se niega a instalar. Antes falta:
1. Un módulo de configuración real sin datos ficticios: compañías, diarios, cajas, sedes y cuentas de la gestoría.
2. Validar Verifactu con la AEAT (§7) y con la gestoría.
3. Terminar la facturación a clientes (paso 5).
4. Decidir la migración de datos desde MN Program.

Será otra base, `sp_produccion`, limpia, en este servidor o en otro.

## 10. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| El navegador avisa de que el certificado no es válido | El dominio no apunta al servidor o el puerto 80 está cerrado: Let's Encrypt no puede comprobarlo. Revise el DNS y los puertos y ejecute `sudo docker compose --env-file .env restart caddy` |
| «502 Bad Gateway» | Odoo está arrancando (espere un minuto) o ha fallado: `sudo docker compose --env-file .env logs odoo --tail 50` |
| «Falta la clave de cifrado» | `.env` no tiene `SP_CLAVE_CIFRADO` o no es la original: restaure la copia de `.env` (§4) |
| Las copias no se hacen | Consulte `/var/log/odoo-despacho-copias.log` |
