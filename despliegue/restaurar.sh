#!/usr/bin/env bash
# Restaura una copia en una base NUEVA (no toca la que está en uso), para comprobar las copias o recuperar datos:
#   sudo bash restaurar.sh /var/backups/odoo-despacho/sp_preproduccion_20261116_0230 [nombre_base_nueva]
# Para sustituir la base en uso por la restaurada, ver LEEME.md §5 (se hace a mano y con Odoo parado).
source "$(dirname "$0")/comun.sh"
cargar_env
P="${1:?Indique la copia (ruta sin .base.enc)}"; NUEVA="${2:-${BASE}_restaurada_$(date +%Y%m%d%H%M)}"
( cd "$(dirname "$P")" && sha256sum -c "$(basename "$P").sha256" )
descifrar() { openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:CLAVE_COPIAS; }
dc exec -T db createdb -U odoo "$NUEVA"
descifrar < "$P.base.enc" | dc exec -T db pg_restore -U odoo -d "$NUEVA" --no-owner
descifrar < "$P.archivos.enc" | dc exec -T odoo sh -c "mkdir -p /var/lib/odoo/filestore && cd /var/lib/odoo/filestore && tar -xzf - && rm -rf '$NUEVA' && mv '$BASE' '$NUEVA'"
N=$(dc exec -T db psql -U odoo -d "$NUEVA" -tAc "select count(*) from account_move")
echo "Restaurada en la base $NUEVA ($N asientos). Compruébela y bórrela después con:"
echo "  docker compose --env-file .env exec db dropdb -U odoo $NUEVA"
