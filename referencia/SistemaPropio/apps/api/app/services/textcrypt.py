"""Cifrado de textos en reposo (mensajes del portal, cuerpos de la cola de envíos). Misma clave que el almacén."""

from __future__ import annotations

from ..security.credentials import _fernet


def enc(text: str) -> str:
    return _fernet().encrypt((text or "").encode("utf-8")).decode("ascii")


def dec(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
