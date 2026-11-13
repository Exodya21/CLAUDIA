"""Cliente OIDC (código de autorización + PKCE) para el proveedor corporativo (T-01).

Verifica firma (JWKS), emisor, audiencia, caducidad, nonce y — si OIDC_REQUIRE_MFA — que el
proveedor declare un segundo factor en `amr`. No crea usuarios: solo enlaza cuentas dadas de alta
por Dirección (por correo la primera vez; después por emisor+sub).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from ..config import get_settings

# Las pruebas sustituyen el transporte por un proveedor simulado (httpx.MockTransport).
_transport: httpx.BaseTransport | None = None
_cache: dict[str, tuple[float, Any]] = {}
_TTL = 3600


class OidcError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _client() -> httpx.Client:
    return httpx.Client(transport=_transport, timeout=10.0, follow_redirects=False)


def _get_json(url: str) -> Any:
    hit = _cache.get(url)
    if hit and hit[0] > time.time():
        return hit[1]
    with _client() as c:
        r = c.get(url)
    if r.status_code != 200:
        raise OidcError("oidc_proveedor", f"El proveedor de identidad no responde ({r.status_code}).")
    data = r.json()
    _cache[url] = (time.time() + _TTL, data)
    return data


def discovery() -> dict:
    s = get_settings()
    return _get_json(s.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration")


def redirect_uri() -> str:
    s = get_settings()
    return s.oidc_redirect_uri or s.web_origin.rstrip("/") + "/api/v1/auth/oidc/callback"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def begin() -> tuple[str, dict]:
    """URL de autorización y el estado a guardar en una cookie firmada de corta duración."""
    s = get_settings()
    meta = discovery()
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    params = {"response_type": "code", "client_id": s.oidc_client_id, "redirect_uri": redirect_uri(),
              "scope": s.oidc_scopes, "state": state, "nonce": nonce, "code_challenge": challenge,
              "code_challenge_method": "S256"}
    return meta["authorization_endpoint"] + "?" + urlencode(params), {"state": state, "nonce": nonce, "verifier": verifier}


def _jwk_for(kid: str | None) -> jwt.PyJWK:
    meta = discovery()
    for _attempt in range(2):
        jwks = _get_json(meta["jwks_uri"])
        for k in jwks.get("keys", []):
            if kid is None or k.get("kid") == kid:
                return jwt.PyJWK(k)
        _cache.pop(meta["jwks_uri"], None)  # rotación de claves: recargar una vez
    raise OidcError("oidc_token", "Firma del proveedor no reconocida.")


def finish(code: str, saved: dict) -> dict:
    """Canjea el código y devuelve las afirmaciones validadas del id_token."""
    s = get_settings()
    meta = discovery()
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
            "client_id": s.oidc_client_id, "code_verifier": saved["verifier"]}
    if s.oidc_client_secret:
        form["client_secret"] = s.oidc_client_secret
    with _client() as c:
        r = c.post(meta["token_endpoint"], data=form, headers={"Accept": "application/json"})
    if r.status_code != 200:
        raise OidcError("oidc_token", "El proveedor rechazó el código de acceso.")
    id_token = r.json().get("id_token")
    if not id_token:
        raise OidcError("oidc_token", "El proveedor no devolvió identidad.")
    try:
        header = jwt.get_unverified_header(id_token)
        key = _jwk_for(header.get("kid"))
        claims = jwt.decode(id_token, key.key, algorithms=["RS256", "ES256", "PS256"], audience=s.oidc_client_id,
                            issuer=meta.get("issuer", s.oidc_issuer), options={"require": ["exp", "iat", "sub"]},
                            leeway=60)
    except jwt.PyJWTError as exc:
        raise OidcError("oidc_token", f"Identidad no válida: {exc.__class__.__name__}.") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), saved["nonce"]):
        raise OidcError("oidc_token", "La respuesta no corresponde a esta solicitud (nonce).")
    if s.oidc_require_mfa:
        accepted = {a.strip() for a in s.oidc_mfa_amr.split(",") if a.strip()}
        amr = claims.get("amr") or []
        if isinstance(amr, str):
            amr = [amr]
        if not accepted.intersection(amr):
            raise OidcError("oidc_sin_mfa", "Su proveedor no confirmó la doble verificación (MFA). Acceso denegado.")
    return claims


def subject(claims: dict) -> str:
    return f"{claims['iss']}|{claims['sub']}"[:255]


def dumps(saved: dict) -> str:
    return json.dumps(saved)
