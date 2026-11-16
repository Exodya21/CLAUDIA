"""Cliente mínimo de la API de Enable Banking (agregador PSD2 autorizado).

Verificado con la muestra oficial github.com/enablebanking/enablebanking-api-samples (python_example/
account_information.py, 30/03/2026): JWT RS256 con «kid» = id de la aplicación, iss «enablebanking.com», aud
«api.enablebanking.com», validez 1 h; GET /aspsps, POST /auth, POST /sessions, GET/DELETE /sessions/{id},
GET /accounts/{uid}/balances y /transactions con «continuation_key».

Las credenciales viven FUERA de la base de datos: SP_EB_APP_ID (id de la aplicación) y SP_EB_CLAVE (ruta del .pem con
la clave privada en el servidor). También se aceptan sp_eb_app_id / sp_eb_clave en el archivo de configuración.
"""
import base64
import hashlib
import json
import os
import time
from datetime import date
from decimal import Decimal

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from odoo.tools import config

API = "https://api.enablebanking.com"
TIMEOUT = 30
MAX_DIAS_CONSENTIMIENTO = 179  # PSD2: la autenticación reforzada para leer cuentas se renueva cada 180 días


class ErrorProveedor(Exception):
    def __init__(self, mensaje, estado=None, limite=False):
        super().__init__(mensaje)
        self.mensaje, self.estado, self.limite = mensaje, estado, limite


def _opcion(env_var, conf):
    return os.environ.get(env_var) or config.get(conf) or ""


def configurado():
    return bool(_opcion("SP_EB_APP_ID", "sp_eb_app_id") and _opcion("SP_EB_CLAVE", "sp_eb_clave"))


def _b64(d):
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode()


def token(ahora=None):
    app_id, ruta = _opcion("SP_EB_APP_ID", "sp_eb_app_id"), _opcion("SP_EB_CLAVE", "sp_eb_clave")
    if not app_id or not ruta:
        raise ErrorProveedor("La conexión con el banco no está configurada en el servidor (SP_EB_APP_ID y "
                             "SP_EB_CLAVE). La configura quien administra el servidor; nunca se envía por correo o chat.")
    try:
        with open(ruta, "rb") as f:
            clave = serialization.load_pem_private_key(f.read(), password=None)
    except OSError as e:
        raise ErrorProveedor(f"No se puede leer la clave de la aplicación ({e.strerror}).") from e
    iat = int(ahora or time.time())
    cabecera = {"typ": "JWT", "alg": "RS256", "kid": app_id}
    cuerpo = {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": iat, "exp": iat + 3600}
    firmar = f"{_b64(json.dumps(cabecera, separators=(',', ':')).encode())}." \
             f"{_b64(json.dumps(cuerpo, separators=(',', ':')).encode())}"
    firma = clave.sign(firmar.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{firmar}.{_b64(firma)}"


def _http(metodo, ruta, **kw):
    """Única salida a la red (las pruebas la sustituyen)."""
    base = os.environ.get("SP_EB_API") or config.get("sp_eb_api") or API
    return requests.request(metodo, base + ruta, timeout=TIMEOUT,
                            headers={"Authorization": f"Bearer {token()}"}, **kw)


def _llamar(metodo, ruta, **kw):
    try:
        r = _http(metodo, ruta, **kw)
    except requests.RequestException as e:
        raise ErrorProveedor(f"No se puede contactar con el agregador: {e.__class__.__name__}.") from e
    if r.status_code == 429:
        raise ErrorProveedor("El banco limita el número de consultas diarias: se reintentará más tarde.", 429, True)
    if r.status_code in (401, 403, 410) and ruta.startswith(("/accounts", "/sessions")):
        raise ErrorProveedor("El consentimiento ya no es válido (caducado o revocado): hay que volver a autorizar.",
                             r.status_code)
    if r.status_code >= 400:
        # El cuerpo puede traer datos del banco: no se guarda entero, solo el código de error.
        try:
            codigo = r.json().get("error") or r.json().get("code") or ""
        except ValueError:
            codigo = ""
        raise ErrorProveedor(f"El agregador ha respondido {r.status_code} {codigo}".strip(), r.status_code)
    return r.json() if r.content else {}


def bancos(pais="ES"):
    return _llamar("GET", "/aspsps", params={"country": pais}).get("aspsps", [])


def iniciar_autorizacion(banco, pais, valido_hasta, url_vuelta, estado, tipo="business"):
    datos = _llamar("POST", "/auth", json={
        "access": {"valid_until": valido_hasta.isoformat()}, "aspsp": {"name": banco, "country": pais},
        "state": estado, "redirect_url": url_vuelta, "psu_type": tipo})
    return datos["url"]


def crear_sesion(codigo):
    return _llamar("POST", "/sessions", json={"code": codigo})


def borrar_sesion(sesion_id):
    return _llamar("DELETE", f"/sessions/{sesion_id}")


def movimientos(uid, desde, hasta=None):
    """Todos los movimientos de la cuenta desde la fecha (paginando con continuation_key)."""
    params = {"date_from": desde.isoformat()}
    if hasta:
        params["date_to"] = hasta.isoformat()
    todos = []
    for _vuelta in range(200):
        datos = _llamar("GET", f"/accounts/{uid}/transactions", params=params)
        todos += datos.get("transactions") or []
        if not datos.get("continuation_key"):
            return todos
        params["continuation_key"] = datos["continuation_key"]
    raise ErrorProveedor("Demasiadas páginas de movimientos: revise el periodo.")


def _cents(cantidad):
    return int((Decimal(str(cantidad)) * 100).quantize(Decimal(1)))


def a_lineas(transacciones, iban_propio):
    """Convierte los movimientos del agregador en líneas del importador (solo los contabilizados)."""
    from odoo.addons.sp_banco.lectura.extractos import Line, _clean
    lineas, vistos = [], {}
    for t in transacciones:
        if (t.get("status") or "BOOK").upper() not in ("BOOK", "BOOKED"):
            continue  # pendientes: llegarán como contabilizados (con otros datos) en una vuelta posterior
        importe = (t.get("transaction_amount") or {}).get("amount")
        if importe is None or not t.get("booking_date"):
            continue
        cent = abs(_cents(importe))
        entra = (t.get("credit_debit_indicator") or "").upper() == "CRDT"
        cent = cent if entra else -cent
        remesa = t.get("remittance_information") or []
        texto = _clean(" ".join(remesa) if isinstance(remesa, list) else str(remesa))
        parte = (t.get("debtor") if entra else t.get("creditor")) or {}
        cuenta = (t.get("debtor_account") if entra else t.get("creditor_account")) or {}
        codigo = (t.get("bank_transaction_code") or {}).get("description")
        reservado = t.get("entry_reference") or t.get("transaction_id") or ""
        # entry_reference no es único en todos los bancos: la huella combina varios datos (y un contador).
        base = "|".join([iban_propio or "", reservado, t["booking_date"], t.get("value_date") or "", str(cent),
                         texto[:80], parte.get("name") or "", cuenta.get("iban") or ""])
        h = hashlib.sha256(base.encode()).hexdigest()[:40]
        vistos[h] = vistos.get(h, 0) + 1
        lineas.append(Line(
            booking_date=date.fromisoformat(t["booking_date"]),
            value_date=date.fromisoformat(t["value_date"]) if t.get("value_date") else None,
            amount_cents=cent, description=texto or _clean(codigo) or "/",
            reference=_clean(t.get("reference_number") or reservado, 80) or None,
            counterparty=_clean(parte.get("name"), 120) or None, counterparty_iban=cuenta.get("iban") or None,
            ext_id=f"eb:{h}:{vistos[h]}"))
    return lineas
