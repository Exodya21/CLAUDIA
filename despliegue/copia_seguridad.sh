#!/usr/bin/env bash
# Copia diaria CIFRADA de la base de datos y de los archivos de Odoo. Conserva 14 días, las de los domingos 8 semanas y
# las del día 1, 12 meses. La clave de cifrado de los IBAN (SP_CLAVE_CIFRADO) y la de las copias (CLAVE_COPIAS) NO van
# en la copia: se guardan aparte (ver LEEME.md §4).
source "$(dirname "$0")/comun.sh"
cargar_env
umask 077
mkdir -p "$COPIAS" && chmod 700 "$COPIAS"
F="$COPIAS/${BASE}_$(date +%Y%m%d_%H%M)"
cifrar() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:CLAVE_COPIAS; }
dc exec -T db pg_dump -U odoo -Fc "$BASE" | cifrar > "$F.base.enc"
dc exec -T odoo sh -c "tar -C /var/lib/odoo/filestore -czf - '$BASE'" | cifrar > "$F.archivos.enc"
sha256sum "$F.base.enc" "$F.archivos.enc" > "$F.sha256"
[ -s "$F.base.enc" ] && [ -s "$F.archivos.enc" ] || { echo "$(date) ERROR: copia vacía"; exit 1; }
# Rotación
find "$COPIAS" -name "${BASE}_*" -mtime +14 | while read -r f; do
  d=$(basename "$f" | sed -E "s/^${BASE}_([0-9]{8}).*/\1/")
  dia=$(date -d "$d" +%d 2>/dev/null || echo 00); sem=$(date -d "$d" +%u 2>/dev/null || echo 0)
  edad=$(( ( $(date +%s) - $(date -d "$d" +%s) ) / 86400 ))
  if [ "$dia" = 01 ] && [ "$edad" -le 366 ]; then continue; fi
  if [ "$sem" = 7 ] && [ "$edad" -le 56 ]; then continue; fi
  rm -f "$f"
done
echo "$(date) Copia correcta: $F"
