"""Almacén cifrado de documentos de expedientes (Fernet con FIELD_ENCRYPTION_KEY). Mismo esquema que los
justificantes de gasto, en su propia carpeta (DOCUMENTS_DIR). En BD solo se guarda la ruta y el hash."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from ..config import get_settings
from ..security.credentials import _fernet

ALLOWED = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG"}
MAX_BYTES = 20 * 1024 * 1024


class VaultError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def sniff(data: bytes) -> str:
    if not data:
        raise VaultError("El archivo está vacío.")
    if len(data) > MAX_BYTES:
        raise VaultError("El archivo supera 20 MB.")
    for mime, magic in ALLOWED.items():
        if data.startswith(magic):
            return mime
    raise VaultError("Formato no admitido. Use PDF, JPG o PNG.")


def documents_dir() -> Path:
    d = Path(os.environ.get("DOCUMENTS_DIR") or get_settings().documents_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def store(data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    name = f"{uuid.uuid4().hex}.bin"
    (documents_dir() / name).write_bytes(_fernet().encrypt(data))
    return name, sha


def load(path: str) -> bytes:
    return _fernet().decrypt((documents_dir() / Path(path).name).read_bytes())
