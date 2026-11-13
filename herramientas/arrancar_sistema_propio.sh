#!/usr/bin/env bash
# Arranca la versión de referencia de Sistema Propio (referencia/SistemaPropio) con DATOS FICTICIOS, sin Docker,
# en Linux (p. ej. el entorno de Claude en la nube). Necesita PostgreSQL 16, Python 3.12+ y Node 22.
#
#   bash herramientas/arrancar_sistema_propio.sh [carpeta_de_trabajo]
#
# Copia el código a la carpeta de trabajo (por defecto /tmp/sistema_propio_run) para no ensuciar el repositorio,
# crea las bases de datos, aplica las migraciones, carga la semilla ficticia y arranca:
#   API  → http://localhost:8000   ·   Web → http://localhost:3000
# Usuarios de demostración: en la pantalla de acceso (modo demo), p. ej. contabilidad.demo o direccion.demo.
# En Windows use INICIAR.bat de referencia/SistemaPropio (con Docker Desktop).
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
R="${1:-/tmp/sistema_propio_run}"
PGPASS="sp_demo_$(openssl rand -hex 8)"

rm -rf "$R" && mkdir -p "$R"
cp -a "$RAIZ/referencia/SistemaPropio/apps" "$R/"
mkdir -p "$R/datos/justificantes" "$R/datos/documentos" "$R/copias"

# Base de datos (rol y bases nuevas en cada arranque)
pg_ctlcluster 16 main start >/dev/null 2>&1 || true
su postgres -c "psql -q -c \"DROP DATABASE IF EXISTS sistema_propio\" -c \"DROP DATABASE IF EXISTS sistema_propio_comprobacion\" -c \"DROP DATABASE IF EXISTS sistema_propio_test\" -c \"DROP ROLE IF EXISTS sistema\" -c \"CREATE ROLE sistema LOGIN CREATEDB PASSWORD '$PGPASS'\""
su postgres -c "createdb -O sistema sistema_propio && createdb -O sistema sistema_propio_comprobacion"

# API
cd "$R/apps/api"
python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]"
cat > "$R/api.env" <<EOF
export APP_ENV=development
export AUTH_MODE=demo,local
export DATABASE_URL=postgresql+psycopg://sistema:$PGPASS@localhost:5432/sistema_propio
export RESTORE_DATABASE_URL=postgresql+psycopg://sistema:$PGPASS@localhost:5432/sistema_propio_comprobacion
export SESSION_SECRET=$(openssl rand -hex 32)
export FIELD_ENCRYPTION_KEY=$(.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export COOKIE_SECURE=false
export WEB_ORIGIN=http://localhost:3000
export TRUST_PROXY=true
export RECEIPTS_DIR=$R/datos/justificantes
export DOCUMENTS_DIR=$R/datos/documentos
export BACKUP_DIR=$R/copias
EOF
. "$R/api.env"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.security.catalog_sync
.venv/bin/python -m app.seed
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$R/api.log" 2>&1 &

# Web
cd "$R/apps/web"
npm ci --no-audit --no-fund
NEXT_TELEMETRY_DISABLED=1 API_URL=http://127.0.0.1:8000 npm run build
API_URL=http://127.0.0.1:8000 nohup npm start > "$R/web.log" 2>&1 &

sleep 8
curl -s --noproxy '*' http://localhost:3000/api/v1/health && echo
echo "Sistema Propio (datos ficticios) en http://localhost:3000 · registros en $R/api.log y $R/web.log"
