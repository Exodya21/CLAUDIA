#!/usr/bin/env bash
# Actualiza el servidor a la última versión del repositorio: copia previa, descarga, imagen y módulos.
#   sudo bash actualizar.sh
source "$(dirname "$0")/comun.sh"
cargar_env
echo "== Copia de seguridad previa"; bash "$DIR/copia_seguridad.sh"
echo "== Descargando la versión nueva"; git -C "$DIR/.." pull --ff-only
echo "== Imagen y módulos"; dc build odoo
dc stop odoo
odoo_cmd -i "$MODULOS_SP" -u "$MODULOS_SP" --stop-after-init
dc up -d
echo "Actualizado. Si algo falla, la copia previa está en $COPIAS (restaurar.sh)."
