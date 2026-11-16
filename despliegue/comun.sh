# Variables y funciones comunes de los scripts de despliegue (se carga con «source»).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
MODULOS_BASE="account,l10n_es,l10n_co,l10n_es_edi_verifactu"
MODULOS_SP="sp_recepcion,sp_contabilidad,sp_gastos,sp_cifrado,sp_banco,sp_banco_psd2,sp_expediente,sp_facturacion"
COPIAS="${COPIAS:-/var/backups/odoo-despacho}"
dc() { docker compose --env-file "$DIR/.env" -f "$DIR/docker-compose.yml" "$@"; }
cargar_env() {
  [ -f "$DIR/.env" ] || { echo "Falta $DIR/.env: ejecute primero instalar.sh"; exit 1; }
  set -a; . "$DIR/.env"; set +a
}
odoo_cmd() { dc run --rm -T --no-deps odoo odoo -c /etc/odoo/odoo.conf -d "$BASE" --no-http "$@"; }
odoo_shell() { dc run --rm -T --no-deps odoo odoo shell -c /etc/odoo/odoo.conf -d "$BASE" --no-http --log-level=error; }
aleatorio() { python3 -c "import secrets;print(secrets.token_urlsafe(${1:-32}))"; }
