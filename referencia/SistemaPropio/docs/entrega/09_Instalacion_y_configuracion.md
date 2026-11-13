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
