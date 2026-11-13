"""Credenciales locales: contraseña Argon2id, segundo factor TOTP (RFC 6238) y cifrado del secreto.

- La contraseña nunca se guarda ni se registra en claro; solo su hash Argon2id.
- El secreto TOTP se guarda cifrado (Fernet) con FIELD_ENCRYPTION_KEY.
- Un código TOTP no puede reutilizarse: se guarda el último paso de tiempo aceptado.
"""

from __future__ import annotations

import base64
import hashlib
import io
import secrets
import string
import time

import pyotp
import segno
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings

_ph = PasswordHasher()  # parámetros recomendados por argon2-cffi (Argon2id)
ISSUER = "SISTEMA PROPIO"
MIN_PASSWORD = 12
# Lista mínima de contraseñas habituales; se amplía en producción con una lista de filtraciones.
_COMMON = {"contraseña123", "password1234", "123456789012", "qwertyuiopas", "despacho2024", "despacho2025",
           "despacho2026", "abogado12345", "administrador"}


# ------------------------------------------------------------------ contraseñas
def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(stored: str | None, raw: str) -> bool:
    if not stored:
        # Igualar tiempos aunque el usuario no tenga contraseña.
        _ph.hash(raw)
        return False
    try:
        return _ph.verify(stored, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_problems(raw: str, username: str) -> list[str]:
    errs = []
    if len(raw) < MIN_PASSWORD:
        errs.append(f"Debe tener al menos {MIN_PASSWORD} caracteres.")
    if len(raw) > 128:
        errs.append("No puede superar 128 caracteres.")
    low = raw.lower()
    if username and username.lower() in low:
        errs.append("No puede contener su nombre de usuario.")
    if low in _COMMON or len(set(raw)) < 5:
        errs.append("Es demasiado común o repetitiva.")
    return errs


def temporary_password() -> str:
    """Contraseña provisional legible (sin caracteres ambiguos). Se muestra una sola vez."""
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0OoIl1")
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(groups)


# ------------------------------------------------------------------ cifrado de campos
def _fernet() -> Fernet:
    s = get_settings()
    if s.field_encryption_key:
        return Fernet(s.field_encryption_key.encode())
    # Solo desarrollo/tests (la configuración lo impide en otros entornos).
    digest = hashlib.sha256(b"sp-field-key|" + s.session_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


# ------------------------------------------------------------------ TOTP
def new_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning(secret: str, username: str) -> tuple[str, str]:
    """URI otpauth:// y su código QR en SVG (generado en el servidor, sin servicios externos)."""
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, dark="#111", light="#fff", xmldecl=False)
    return uri, buf.getvalue().decode()


def verify_totp(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Devuelve el paso aceptado o None. Tolera ±1 paso (30 s) de desfase y rechaza reutilizaciones."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return None
    totp = pyotp.TOTP(secret)
    t = time.time() if now is None else now
    current = int(t // totp.interval)
    for step in (current, current - 1, current + 1):
        if secrets.compare_digest(totp.at(step * totp.interval), code):
            if last_step is not None and step <= last_step:
                return None
            return step
    return None
