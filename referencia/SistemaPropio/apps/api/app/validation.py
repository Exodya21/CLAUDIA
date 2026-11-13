"""Normalización y validación de documentos, teléfonos y nombres."""

from __future__ import annotations

import re
import unicodedata

import phonenumbers

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_DNI_RE = re.compile(r"^(\d{8})([A-Z])$")
_NIE_RE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_PASSPORT_RE = re.compile(r"^[A-Z0-9]{5,20}$")
_OTHER_RE = re.compile(r"^[A-Z0-9\-]{3,40}$")


class ValidationFailure(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_doc(raw: str) -> str:
    return re.sub(r"[\s.\-]", "", raw or "").upper()


def validate_identifier(kind: str, number: str, country: str) -> str:
    """Devuelve el número normalizado o lanza ValidationFailure.

    DNI y NIE comprueban la letra de control (algoritmo público módulo 23).
    """
    n = normalize_doc(number)
    if kind == "DNI":
        m = _DNI_RE.match(n)
        if not m:
            raise ValidationFailure("number", "El DNI debe tener 8 dígitos y una letra.")
        if DNI_LETTERS[int(m.group(1)) % 23] != m.group(2):
            raise ValidationFailure("number", "La letra de control del DNI no es correcta.")
        if country != "ES":
            raise ValidationFailure("country", "Un DNI siempre es de país ES.")
        return n
    if kind == "NIE":
        m = _NIE_RE.match(n)
        if not m:
            raise ValidationFailure("number", "El NIE debe tener el formato X/Y/Z + 7 dígitos + letra.")
        digits = str("XYZ".index(m.group(1))) + m.group(2)
        if DNI_LETTERS[int(digits) % 23] != m.group(3):
            raise ValidationFailure("number", "La letra de control del NIE no es correcta.")
        if country != "ES":
            raise ValidationFailure("country", "Un NIE siempre es de país ES.")
        return n
    if kind == "PASAPORTE":
        if not _PASSPORT_RE.match(n):
            raise ValidationFailure("number", "El pasaporte debe tener entre 5 y 20 caracteres alfanuméricos.")
        return n
    if kind == "OTRO":
        if not _OTHER_RE.match(n):
            raise ValidationFailure("number", "Identificador no válido.")
        return n
    raise ValidationFailure("kind", "Tipo de documento no admitido.")


def normalize_phone(raw: str, default_region: str = "ES") -> str:
    """Devuelve el teléfono en formato E.164 o lanza ValidationFailure."""
    try:
        p = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException as exc:
        raise ValidationFailure("phone", "Teléfono no reconocible.") from exc
    if not phonenumbers.is_possible_number(p) or not phonenumbers.is_valid_number(p):
        raise ValidationFailure("phone", "El teléfono no es válido para su país.")
    return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)


def phone_search_digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def fold(text: str) -> str:
    """Minúsculas sin tildes para búsquedas ('Núñez' -> 'nunez')."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"\s+", " ", "".join(c for c in nfkd if not unicodedata.combining(c))).strip().lower()


def mask_identifier(number: str) -> str:
    return "•" * max(len(number) - 4, 2) + number[-4:]


def mask_phone(e164: str) -> str:
    return e164[:3] + " ••• ••• " + e164[-3:] if len(e164) > 6 else "•••"


def mask_email(email: str) -> str:
    user, _, dom = email.partition("@")
    return (user[:1] + "•••@" + dom) if dom else "•••"
