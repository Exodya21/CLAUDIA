# 09 · Documentación de instalación y configuración

Sistema Propio · versión F5.6 · 12/11/2026

## 1. Requisitos
| Instalación | Requisitos |
|---|---|
| Windows (demo o real provisional) | Windows 10/11, Docker Desktop, 8 GB de RAM, 20 GB libres, BitLocker activo para la real |
| Servidor Linux (Docker) | Docker Engine + Compose v2, 4 núcleos, 16 GB, SSD |
| Desarrollo local sin Docker | Python 3.12, Node 22, PostgreSQL 16, Tesseract (`tesseract-ocr-spa`) y `poppler-utils` |

## 2. Windows con doble clic
### 2.1 Demostración (datos ficticios)
1. Descomprima el paquete, por ejemplo en `C:\SistemaPropio`.
2. Abra Docker Desktop y espere a que indique «Engine running».
3. Doble clic en `INICIAR.bat`.
   - La primera vez crea `.env` con claves aleatorias, construye las imágenes (unos minutos) y siembra datos
     ficticios.
4. Abra `http://localhost:3000` y entre con un usuario de la lista de demostración.
5. Para parar: `DETENER.bat`. Para volver a empezar los datos ficticios: `REINICIAR_DATOS_DEMO.bat`.

### 2.2 Real provisional (datos del despacho)
1. Doble clic en `INICIAR_REAL.bat`.
   - Si no existe la base real, se considera primer arranque.
   - Crea o comprueba `.env.real` con `ops\crear_env_real.ps1` (si PowerShell falla, usa un contenedor `alpine` de
     respaldo).
   - Comprueba que `SESSION_SECRET`, `POSTGRES_PASSWORD` y `FIELD_ENCRYPTION_KEY` existen y no están vacías.
   - Arranca el proyecto `sistemapropio_real` con `APP_ENV=production`, `AUTH_MODE=local` y `COOKIE_SECURE=true`.
2. El script pide la sociedad, las sedes (`Barcelona,Madrid,…`) y el usuario, nombre y correo de la primera persona
   de Dirección. Muestra **una sola vez** la contraseña provisional.
3. Primer acceso en `http://localhost:3000`:
   1. Cambie la contraseña.
   2. Active el TOTP. Si la aplicación del móvil no lee el QR, use «Introducir clave de configuración»: cuenta
      `Sistema Propio`, la clave que aparece debajo del QR, tipo «Basado en tiempo».
4. Escriba el CIF del despacho en `OWN_TAX_IDS=` dentro de `.env.real` y vuelva a ejecutar `INICIAR_REAL.bat`.
5. Copias: `COPIA_SEGURIDAD_REAL.bat` (carpeta `copias_real`). Guarde **también** `.env.real` fuera del equipo y por
   separado.

Las dos instalaciones usan el puerto 3000: al arrancar una, se para la otra. Nunca comparten volúmenes.

## 3. Servidor Linux con Docker Compose
```bash
git clone <repositorio> /opt/sistemapropio && cd /opt/sistemapropio
cp .env.example .env            # rellenar: ver la tabla del apartado 5
chmod 600 .env
docker compose up -d --build    # migra, sincroniza roles y arranca
docker compose exec api python -m app.ops.primer_admin --crear-entidad \
  --entidad "Razón social" --sedes "Sede 1,Sede 2" \
  --usuario nombre.apellido --nombre "Nombre Apellidos" --correo persona@dominio.es
```
Delante, un proxy inverso con TLS: los puertos 3000 y 8000 solo escuchan en 127.0.0.1. Configuración mínima de Nginx:
```nginx
server {
  listen 443 ssl http2;  server_name sistema.dominio.es;
  ssl_certificate /etc/letsencrypt/live/sistema.dominio.es/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/sistema.dominio.es/privkey.pem;
  add_header Strict-Transport-Security "max-age=31536000" always;
  client_max_body_size 30m;
  location / { proxy_pass http://127.0.0.1:3000; proxy_set_header Host $host;
               proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header X-Forwarded-Proto https; }
}
```
Con proxy: `TRUST_PROXY=true` y `WEB_ORIGIN=https://sistema.dominio.es`.

## 4. Desarrollo local sin Docker
```bash
createdb sistema_propio && createdb sistema_propio_test
cd apps/api && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env            # APP_ENV=development, AUTH_MODE=demo,local
alembic upgrade head && python -m app.security.catalog_sync && python -m app.seed
uvicorn app.main:app --reload --port 8000
cd ../web && npm ci && npm run dev   # http://localhost:3000
```

## 5. Variables de configuración (API)
Generada desde `apps/api/app/config.py`. Los nombres van en mayúsculas en `.env`. Docker Compose usa además
`POSTGRES_USER`, `POSTGRES_PASSWORD` (obligatoria), `POSTGRES_DB`, `COPIAS_DIR` y `API_URL`. Construye `DATABASE_URL` y
`RESTORE_DATABASE_URL` a partir de ellas.

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `APP_ENV` | development · test · staging · production | Entorno. En producción: cookie segura obligatoria, sin modo demo y sin semilla de datos |
| `AUTH_MODE` | local, oidc, demo (lista) | Métodos de acceso habilitados. `demo` solo en development/test |
| `DATABASE_URL` | obligatoria | Conexión a PostgreSQL (`postgresql+psycopg://…`) |
| `SESSION_SECRET` | obligatoria, ≥ 32 caracteres | Clave HMAC de las cookies de sesión. Secreta |
| `SESSION_TTL_MINUTES` | 480 | Duración máxima de la sesión del equipo |
| `SESSION_IDLE_MINUTES` | 60 | Cierre por inactividad |
| `COOKIE_SECURE` | true | Cookie solo por HTTPS. Obligatoria en producción |
| `WEB_ORIGIN` | http://localhost:3000 | Origen permitido de la web (CORS y enlaces de correo). En el servidor: `https://dominio` |
| `OWN_TAX_IDS` | vacío | CIF/NIF propios (separados por comas) para que la lectura de facturas no los confunda con el proveedor. No subir al repositorio |
| `TRUST_PROXY` | false | Confiar en `X-Forwarded-For` (poner `true` detrás del proxy inverso) para el límite de intentos por IP |
| `FIELD_ENCRYPTION_KEY` | obligatoria con `local` | Clave Fernet del cifrado de columna y archivos. **Si se pierde, los datos cifrados no se recuperan** |
| `LOGIN_MAX_FAILURES_USER` | 5 | Fallos de acceso por usuario en la ventana |
| `LOGIN_MAX_FAILURES_IP` | 30 | Fallos por IP en la ventana |
| `LOGIN_WINDOW_MINUTES` | 15 | Ventana del límite de intentos |
| `OIDC_ISSUER` | vacío | Emisor OIDC (T-01). Vacío = acceso corporativo no disponible |
| `OIDC_CLIENT_ID` | vacío | Cliente OIDC |
| `OIDC_CLIENT_SECRET` | vacío | Secreto OIDC. Secreto |
| `OIDC_REDIRECT_URI` | WEB_ORIGIN/api/v1/auth/oidc/callback | Retorno OIDC |
| `OIDC_SCOPES` | openid email profile | Ámbitos OIDC |
| `OIDC_EMAIL_CLAIM` | email | Claim con el correo |
| `OIDC_REQUIRE_MFA` | true | Exigir MFA al proveedor (no se puede desactivar fuera de desarrollo) |
| `OIDC_MFA_AMR` | mfa,otp,hwk,… | Valores de `amr` que cuentan como MFA |
| `RESTORE_DATABASE_URL` | vacío | Base auxiliar donde se restaura cada copia para comprobarla (AT-29) |
| `BACKUP_DIR` | /copias | Carpeta de copias dentro del contenedor (volumen `COPIAS_DIR`) |
| `RECEIPTS_DIR` | /datos/justificantes | Justificantes de gastos y cobros, cifrados |
| `DOCUMENTS_DIR` | /datos/documentos | Documentos de expedientes, RRHH, extractos y facturas, cifrados |
| `SMTP_HOST` | vacío | Servidor de correo saliente. Vacío = correo «no configurado» |
| `SMTP_PORT` | 587 | Puerto SMTP |
| `SMTP_USER` | vacío | Usuario SMTP |
| `SMTP_PASSWORD` | vacío | Contraseña SMTP. Secreta |
| `SMTP_FROM` | Despacho <no-responder@despacho.invalid> | Remitente |
| `SMTP_STARTTLS` | true | STARTTLS |
| `PORTAL_SESSION_MINUTES` | 480 | Sesión máxima del cliente en el portal |
| `PORTAL_IDLE_MINUTES` | 30 | Inactividad del cliente |
| `PORTAL_CODE_MINUTES` | 10 | Validez del código de acceso del cliente |

**La configuración se niega a arrancar si:**
- `AUTH_MODE` incluye `demo` fuera de development/test;
- falta `FIELD_ENCRYPTION_KEY` con acceso `local` en staging o producción;
- `COOKIE_SECURE=false` en producción;
- se desactiva la MFA de OIDC fuera de desarrollo.

**Generar claves:**
```bash
python -c "import secrets;print(secrets.token_hex(32))"                                       # SESSION_SECRET
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"      # FIELD_ENCRYPTION_KEY
```

## 6. Configuración inicial desde la aplicación
1. **Administración → Usuarios:** alta del equipo con rol, entidad, sede y departamento. Cada persona recibe una
   contraseña provisional y activa su TOTP al entrar.
2. **Contabilidad → Banco:** alta de las cuentas con su IBAN completo.
3. **Contabilidad → Rutina → Responsables:** Dirección asigna una persona a cada paso.
4. **Administración → Agentes:** activar o desactivar cada agente y el modo automático de mensajes (T-47).
5. **Correo:** `SMTP_*` en `.env`. Sin ellos, los avisos quedan en cola como «no configurado».

## 7. Instalación en Odoo Community (guía para el equipo)
1. Instale Odoo 17.0 o 18.0 Community (imagen Docker oficial o paquete) con PostgreSQL 16 en la red interna.
2. Clone los repositorios de la OCA necesarios **en la misma rama** (ver 02 · Arquitectura, 8.1), por ejemplo
   `server-tools`, `server-ux`, `bank-statement-import`, `account-reconcile`, `bank-payment`, `l10n-spain`, `dms`,
   `account-financial-reporting`, `mis-builder` y `queue`.
3. Configure `odoo.conf`:
   ```ini
   addons_path = /opt/odoo/addons,/opt/oca/...,/opt/sp_addons
   proxy_mode = True
   list_db = False
   admin_passwd = <secreto del gestor>
   workers = 6
   max_cron_threads = 2
   limit_memory_soft = 2147483648
   db_filter = ^sistemapropio$
   ```
4. Cree la base de producción con idioma español y país España. Instale `l10n_es` y después los módulos `sp_*`.
5. Active la multicompañía (España y Colombia), cree los grupos por rol y obligue el TOTP.
6. Configure el correo saliente, la tarea programada de copias y la supervisión (ver 13).

## Anexo · Odoo 20 Community de pruebas en un ordenador con Windows
Para probar Odoo en local con **datos ficticios**. No sirve para producción: no tiene copias de seguridad ni
accesos controlados.

1. **Docker Desktop:** descárguelo de docker.com (Download for Windows, AMD64) e instálelo con la opción
   «Use WSL 2». Reinicie el ordenador.
2. Si aparece «WSL not installed», abra PowerShell **como administrador**, ejecute `wsl --install --no-distribution`
   y reinicie (ver INC-50).
3. Compruebe que funciona: `docker run hello-world` debe mostrar «Hello from Docker!».
4. Arranque Odoo 20 en PowerShell, con un comando cada vez:
   ```
   docker network create odoo-net
   docker run -d --name odoo-db --network odoo-net --restart unless-stopped -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres -v odoo-db-data:/var/lib/postgresql/data postgres:16
   docker run -d --name odoo --network odoo-net --restart unless-stopped -p 8069:8069 -e HOST=odoo-db -e USER=odoo -e PASSWORD=odoo -v odoo-data:/var/lib/odoo odoo:20
   ```
5. Abra http://localhost:8069 y cree la base de datos con el idioma Español, el país España y, si se quiere,
   datos de demostración. Anote la contraseña maestra en un gestor de contraseñas.
6. En Aplicaciones, active **Facturación**. Al elegir el país España se instala sola la localización (`l10n_es`).
7. Para parar Odoo: `docker stop odoo odoo-db`. Para arrancarlo: `docker start odoo-db odoo`.

Monedas: la moneda principal (EUR) solo se cambia antes de que haya asientos. Para facturar en otra moneda, actívela
en Facturación → Configuración → Ajustes → Monedas e introduzca el tipo de cambio **a mano**, porque la
actualización automática es Enterprise.

## Anexo B · Versión de referencia de Sistema Propio (datos ficticios)
El código completo de la versión F5.6c está en `referencia/SistemaPropio/`. Se usa como **referencia** para
implantar en Odoo 20 lo que ya está construido y probado (ver 19). Para arrancarla:
- **Windows:** dentro de `referencia/SistemaPropio`, `INICIAR.bat` (con Docker Desktop). Ver su `README.md`.
- **Linux sin Docker** (p. ej. el entorno de Claude): `bash herramientas/arrancar_sistema_propio.sh`. Crea las bases
  de datos, aplica las migraciones, carga los datos ficticios y abre la API en el puerto 8000 y la web en el 3000.
  En la pantalla de acceso se elige un usuario de demostración (p. ej. `contabilidad.demo` o `direccion.demo`).

Nunca se cargan datos reales en esta instalación.

## Anexo C · Odoo 20 con la base contable del despacho (datos ficticios)
Para montar Odoo 20 Community **con la base contable ya configurada** (compañías, plan contable, diarios CIT y EXP,
bancos, cajas, analítica, cuentas propias provisionales y Verifactu en el entorno de pruebas), siga
[`odoo/LEEME.md`](../../odoo/LEEME.md). Resumen:
- Usa `odoo/docker-compose.yml` (Odoo 20 + PostgreSQL 16). Odoo solo se abre desde el propio ordenador
  (http://localhost:8069). No hace falta crear la red ni los contenedores a mano como en el primer anexo.
- **Imagen propia `despacho/odoo:20`** (desde el 13/11/2026; 11 · DOC-13): es la oficial `odoo:20` más
  `poppler-utils` (`pdftotext`, `pdftoppm`) y Tesseract con español (`tesseract-ocr`, `tesseract-ocr-spa`), que
  `sp_contabilidad` usa para leer facturas en el propio servidor. Se define en `odoo/Dockerfile` y el compose la
  construye (`build: .`). Por eso el primer paso es `docker compose up -d --build`: la primera vez y cada vez que
  cambie el `Dockerfile` (12 · INC-76).
- Son cinco pasos en PowerShell, dentro de la carpeta `odoo`: arrancar (con `--build`), crear la base `sp_contable` con los módulos,
  ejecutar `configuracion/base_contable.py`, pasar (opcional) `pruebas/prueba_base_contable.py` y entrar.
- Cambie la contraseña de `admin` al entrar. Para empezar de cero: `docker compose down -v`.
- **Nunca** se carga aquí un certificado real ni datos reales. Qué monta exactamente y qué resultado dio la prueba:
  11 · DOC-5 y 19 §6.
- **Linux o entorno en la nube:** `bash herramientas/odoo_dev.sh [módulos]` arranca Docker si hace falta, levanta los
  contenedores, crea y configura la base `sp_contable` si no existe y, si se indican módulos, los instala o
  actualiza (p. ej. `bash herramientas/odoo_dev.sh sp_recepcion`). Si falta la imagen `despacho/odoo:20`, la
  construye antes, pasando el proxy del entorno como argumento de construcción. Recepción y cajas: `odoo/LEEME.md`,
  apartado «Recepción y cajas» (11 · DOC-8).
- **Facturas de proveedores** (`sp_contabilidad`): `odoo/LEEME.md`, pasos 10 (instalar y pasar las pruebas) y 11
  (escenario con una factura ficticia) (11 · DOC-13). Si al instalar con `-i` salen «0 tests», páselas con
  `-u sp_contabilidad` (12 · INC-80).
