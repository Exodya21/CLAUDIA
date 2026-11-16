#!/usr/bin/env bash
# Instala Odoo 20 del despacho en un servidor Ubuntu 22.04/24.04 (ver LEEME.md). Se ejecuta con sudo desde la carpeta
# despliegue del repositorio:
#   sudo bash instalar.sh --dominio odoo.midespacho.es --correo sistemas@midespacho.es
# Opciones: --entorno preproduccion (por defecto; datos FICTICIOS y Verifactu en pruebas) · --sin-docker (no instala
# Docker) · --sin-cortafuegos (no toca ufw) · --sin-copias (no programa la copia diaria) · --con-ejemplos (carga
# los escenarios de demostración con datos ficticios para practicar).
# Es seguro repetirlo: nunca cambia las claves ya creadas ni borra datos.
source "$(dirname "$0")/comun.sh"
ENTORNO=preproduccion; DOMINIO=""; CORREO=""; DOCKER=1; UFW=1; CRON=1; EJEMPLOS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dominio) DOMINIO="$2"; shift 2;; --correo) CORREO="$2"; shift 2;; --entorno) ENTORNO="$2"; shift 2;;
    --sin-docker) DOCKER=0; shift;; --con-ejemplos) EJEMPLOS=1; shift;; --sin-cortafuegos) UFW=0; shift;; --sin-copias) CRON=0; shift;;
    *) echo "Opción desconocida: $1"; exit 1;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "Ejecute con sudo."; exit 1; }
if [ "$ENTORNO" = produccion ]; then
  echo "La instalación de PRODUCCIÓN aún no está disponible: falta el módulo de configuración real (sin datos"
  echo "ficticios) y validar Verifactu con la AEAT y la gestoría. Instale la preproducción (ver LEEME.md §1)."; exit 1
fi
[ "$ENTORNO" = preproduccion ] || { echo "Entorno no válido: $ENTORNO"; exit 1; }

echo "== 1/7 Docker"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  [ "$DOCKER" = 1 ] || { echo "Falta Docker con «docker compose»."; exit 1; }
  apt-get update -q && apt-get install -yq docker.io docker-compose-v2 openssl python3
  systemctl enable --now docker
fi

echo "== 2/7 Claves del servidor (.env, solo aquí; NUNCA en el repositorio)"
if [ ! -f .env ]; then
  [ -n "$DOMINIO" ] && [ -n "$CORREO" ] || { echo "Indique --dominio y --correo (avisos del certificado HTTPS)."; exit 1; }
  umask 077
  cat > .env <<FIN
ENTORNO=$ENTORNO
BASE=sp_$ENTORNO
DOMINIO=$DOMINIO
CORREO_TLS=$CORREO
POSTGRES_PASSWORD=$(aleatorio 32)
ADMIN_PASSWD=$(aleatorio 32)
SP_CLAVE_CIFRADO=$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(64)).decode())')
CLAVE_COPIAS=$(aleatorio 32)
SP_EB_APP_ID=
SP_EB_CLAVE=
FIN
  echo "   Creado .env. GUARDE UNA COPIA en un lugar seguro y separado del servidor: sin SP_CLAVE_CIFRADO no se leen"
  echo "   los IBAN y sin CLAVE_COPIAS no se pueden restaurar las copias."
else
  echo "   .env ya existe: se conservan sus claves."
fi
cargar_env
mkdir -p secretos && chmod 700 secretos

echo "== 3/7 Configuración de Odoo (odoo.conf)"
NUCLEOS=$(nproc); WORKERS=$(( NUCLEOS * 2 + 1 )); [ "$WORKERS" -gt 9 ] && WORKERS=9
sed -e "s|@POSTGRES_PASSWORD@|$POSTGRES_PASSWORD|" -e "s|@ADMIN_PASSWD@|$ADMIN_PASSWD|" -e "s|@BASE@|$BASE|g" \
    -e "s|@WORKERS@|$WORKERS|" odoo.conf.plantilla > odoo.conf
chown 100:101 odoo.conf secretos 2>/dev/null || true   # usuario «odoo» del contenedor
chmod 600 odoo.conf

echo "== 4/7 Imagen y base de datos"
dc build odoo
dc up -d db
for i in $(seq 1 60); do dc exec -T db pg_isready -U odoo >/dev/null 2>&1 && break; sleep 2; done
if dc exec -T db psql -U odoo -lqt | cut -d'|' -f1 | grep -qw "$BASE"; then
  echo "   La base $BASE ya existe: se actualizan los módulos."
  odoo_cmd -i "$MODULOS_SP" -u "$MODULOS_SP" --stop-after-init
else
  echo "   Creando $BASE (contabilidad, España, Colombia, Verifactu)… unos minutos."
  odoo_cmd -i "$MODULOS_BASE" --load-language=es_ES --stop-after-init
  odoo_shell < ../odoo/configuracion/base_contable.py | tail -3
  odoo_cmd -i "$MODULOS_SP" --stop-after-init
  for s in recepcion gastos banco facturacion; do odoo_shell < "../odoo/configuracion/$s.py" | tail -1; done
  if [ "$EJEMPLOS" = 1 ]; then
    echo "   Cargando los escenarios de demostración (datos ficticios)…"
    for p in prueba_recepcion prueba_devoluciones prueba_facturas_proveedor prueba_gastos prueba_banco prueba_expediente; do
      odoo_shell < "../odoo/pruebas/$p.py" | tail -1
    done
  fi
fi

echo "== 5/7 Dirección pública y contraseñas"
umask 077
odoo_shell <<PY | { grep '^CRED ' || true; } | sed 's/^CRED //' > credenciales.nuevas
import secrets
P = env["ir.config_parameter"].sudo()
P.set_str("web.base.url", "https://$DOMINIO")
P.set_bool("web.base.url.freeze", True)
# Ningún usuario conserva una contraseña conocida (admin/admin o la de demostración = usuario): una nueva y aleatoria
# para cada uno, solo la primera vez. Después cada persona la cambia desde su perfil.
if not P.get_bool("sp_despliegue.claves_iniciales"):
    for u in env["res.users"].search([("share", "=", False), ("login", "not in", ("__system__", "public"))]):
        clave = secrets.token_urlsafe(12)
        u.password = clave
        print(f"CRED {u.login}: {clave}")
    P.set_bool("sp_despliegue.claves_iniciales", True)
env.cr.commit()
PY
if [ -s credenciales.nuevas ]; then
  mv credenciales.nuevas "credenciales_${ENTORNO}.txt"
  echo "   Contraseñas iniciales en $DIR/credenciales_${ENTORNO}.txt (léalas, repártalas y BORRE el archivo)."
else
  rm -f credenciales.nuevas; echo "   Las contraseñas ya se generaron en la primera instalación (no se cambian)."
fi

echo "== 6/7 Arranque con HTTPS"
dc up -d
if [ "$UFW" = 1 ] && command -v ufw >/dev/null; then
  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw status | grep -q "Status: active" || echo "   Aviso: el cortafuegos (ufw) está desactivado. Actívelo con «sudo ufw enable» tras comprobar SSH."
fi

echo "== 7/7 Copias de seguridad diarias"
if [ "$CRON" = 1 ]; then
  echo "30 2 * * * root bash $DIR/copia_seguridad.sh >> /var/log/odoo-despacho-copias.log 2>&1" > /etc/cron.d/odoo-despacho-copias
  echo "   Programada cada día a las 02:30 en $COPIAS (cifrada). Cópiela también fuera del servidor (NAS, UE)."
fi
echo
echo "Listo: https://$DOMINIO  (base $BASE · $ENTORNO · DATOS FICTICIOS · Verifactu en PRUEBAS)"
