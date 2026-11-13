#!/usr/bin/env bash
# Entorno de desarrollo de Odoo 20 en Linux (p. ej. el entorno de Claude en la nube), con Docker.
# Arranca Docker si hace falta, levanta odoo/docker-compose.yml y, si no existe la base «sp_contable», la crea con
# los módulos base y monta la base contable. Uso:  bash herramientas/odoo_dev.sh [módulos_extra_separados_por_comas]
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"; cd "$RAIZ/odoo"
if ! docker info >/dev/null 2>&1; then (nohup dockerd >/tmp/dockerd.log 2>&1 &); for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done; fi
# Imagen propia (odoo/Dockerfile): se construye si falta, pasando el proxy del entorno si lo hay.
if ! docker image inspect despacho/odoo:20 >/dev/null 2>&1; then
  docker compose build --build-arg HTTP_PROXY="${HTTP_PROXY:-}" --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
    --build-arg http_proxy="${HTTP_PROXY:-}" --build-arg https_proxy="${HTTPS_PROXY:-}" odoo
fi
docker compose up -d >/dev/null
for i in $(seq 1 60); do docker compose exec -T db pg_isready -U odoo >/dev/null 2>&1 && break; sleep 1; done
ODOO="docker compose exec -T odoo odoo --db_host=db -r odoo -w odoo"
if ! docker compose exec -T db psql -U odoo -lqt | cut -d'|' -f1 | grep -qw sp_contable; then
  echo "Creando la base sp_contable y montando todo (igual que MONTAR_ODOO.bat)…"
  $ODOO -d sp_contable -i account,l10n_es,l10n_co,l10n_es_edi_verifactu --load-language=es_ES --stop-after-init --no-http --log-level=warn
  $ODOO shell -d sp_contable --no-http --log-level=error < configuracion/base_contable.py | tail -1
  docker compose restart odoo >/dev/null
  $ODOO -d sp_contable -i sp_recepcion,sp_contabilidad,sp_gastos --stop-after-init --no-http --log-level=warn
  $ODOO shell -d sp_contable --no-http --log-level=error < configuracion/recepcion.py | tail -1
  $ODOO shell -d sp_contable --no-http --log-level=error < configuracion/gastos.py | tail -1
fi
if [ -n "${1:-}" ]; then
  $ODOO -d sp_contable -i "$1" -u "$1" --stop-after-init --log-level=warn
fi
docker compose restart odoo >/dev/null
echo "Odoo 20 en http://localhost:8069 (admin/admin) · base sp_contable"
