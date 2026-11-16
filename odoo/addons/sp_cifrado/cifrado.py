"""Claves y primitivas de cifrado del despacho. La clave maestra NUNCA se guarda en la base de datos."""
import base64
import os
import re

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from odoo.tools import config

MARCA = "sp1:"  # prefijo de los valores cifrados en columna (permite convivir con valores antiguos en claro)
FALTA_CLAVE = "[cifrado: falta la clave]"
_AD = [b"sp-campo"]


class SinClave(Exception):
    pass


def generar_clave():
    """Clave maestra nueva (64 bytes aleatorios en base64). Se guarda fuera de Odoo y con copia de seguridad aparte."""
    return base64.urlsafe_b64encode(os.urandom(64)).decode()


def _maestra():
    valor = os.environ.get("SP_CLAVE_CIFRADO") or config.get("sp_clave_cifrado")
    if not valor:
        raise SinClave("Falta la clave de cifrado (variable SP_CLAVE_CIFRADO). Sin ella no se guardan IBAN ni "
                       "documentos cifrados. Avise a quien administra el servidor.")
    clave = base64.urlsafe_b64decode(valor.encode())
    if len(clave) < 32:
        raise SinClave("La clave de cifrado es demasiado corta (mínimo 32 bytes).")
    return clave


def _derivar(info, largo):
    return HKDF(algorithm=hashes.SHA256(), length=largo, salt=b"despacho-sp", info=info).derive(_maestra())


_cache = {}


def _siv():
    k = os.environ.get("SP_CLAVE_CIFRADO") or config.get("sp_clave_cifrado")
    if ("siv", k) not in _cache:
        _cache.clear()
        _cache[("siv", k)] = AESSIV(_derivar(b"sp-campos", 64))
    return _cache[("siv", k)]


def _fernet():
    k = os.environ.get("SP_CLAVE_CIFRADO") or config.get("sp_clave_cifrado")
    if ("fernet", k) not in _cache:
        _cache[("fernet", k)] = Fernet(base64.urlsafe_b64encode(_derivar(b"sp-archivos", 32)))
    return _cache[("fernet", k)]


def hay_clave():
    try:
        _maestra()
        return True
    except SinClave:
        return False


def cifrar_valor(texto):
    """Determinista: el mismo texto da siempre el mismo cifrado (permite buscar por igualdad y evitar duplicados)."""
    if not texto or texto.startswith(MARCA):
        return texto
    return MARCA + base64.urlsafe_b64encode(_siv().encrypt(texto.encode("utf-8"), _AD)).decode()


def descifrar_valor(valor):
    if not valor or not isinstance(valor, str) or not valor.startswith(MARCA):
        return valor  # vacío o valor antiguo en claro
    try:
        return _siv().decrypt(base64.urlsafe_b64decode(valor[len(MARCA):].encode()), _AD).decode("utf-8")
    except SinClave:
        return FALTA_CLAVE
    except Exception:  # clave equivocada o valor alterado
        return "[cifrado: no se puede leer]"


def cifrar_archivo(datos: bytes) -> bytes:
    return _fernet().encrypt(datos)


def descifrar_archivo(datos: bytes) -> bytes:
    try:
        return _fernet().decrypt(datos)
    except InvalidToken as e:
        raise SinClave("El archivo no se puede descifrar con la clave actual.") from e


def enmascarar(iban):
    """ES12 **** 1234: lo justo para reconocer la cuenta sin exponerla."""
    s = re.sub(r"\W+", "", iban or "").upper()
    if len(s) <= 8:
        return "****" if s else ""
    return f"{s[:4]} **** {s[-4:]}"
