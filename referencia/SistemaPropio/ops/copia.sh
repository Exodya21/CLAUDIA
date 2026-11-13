#!/bin/sh
# Copia de seguridad (AT-29). Se ejecuta DENTRO del contenedor db:
#   docker compose exec -T db sh /ops/copia.sh
# 1) pg_dump en formato personalizado a /copias  2) restauración completa en una base auxiliar
# (<base>_comprobacion) para que la API la verifique  3) empaqueta los justificantes de gasto y los documentos de expedientes, cifrados
# 4) conserva las 14 copias más recientes.
# Imprime en la última línea el nombre del archivo.
set -eu
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="sp_${STAMP}.dump"
RESTORE_DB="${POSTGRES_DB}_comprobacion"
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner -f "/copias/$NAME"
dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB"
createdb -U "$POSTGRES_USER" "$RESTORE_DB"
pg_restore -U "$POSTGRES_USER" --no-owner --exit-on-error -d "$RESTORE_DB" "/copias/$NAME" 1>&2
# Justificantes de gasto (ya cifrados): van en un .tar junto a la copia de la base.
if [ -d /justificantes ]; then
  tar -cf "/copias/sp_${STAMP}_justificantes.tar" -C /justificantes .
fi
# Documentos de expedientes (ya cifrados): pasaportes, certificados, resguardos…
if [ -d /documentos ]; then
  tar -cf "/copias/sp_${STAMP}_documentos.tar" -C /documentos .
fi
ls -1t /copias/sp_*.dump 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t /copias/sp_*_justificantes.tar 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t /copias/sp_*_documentos.tar 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "$NAME"
