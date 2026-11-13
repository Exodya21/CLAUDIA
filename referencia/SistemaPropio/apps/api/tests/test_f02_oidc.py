"""F0.2 — Acceso corporativo OIDC (código + PKCE) contra un proveedor SIMULADO en memoria (sin red).

Comprueba firma, nonce, estado, MFA exigido y que no se crean cuentas automáticamente.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

ISSUER = "https://idp.ficticio.invalid"
CLIENT = "sistema-propio-pruebas"


class FakeIdP:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "clave-ficticia-1"
        self.codes: dict[str, dict] = {}
        self.next_claims: dict = {}

    def jwk(self) -> dict:
        return {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key())), "kid": self.kid,
                "use": "sig", "alg": "RS256"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize",
                                             "token_endpoint": f"{ISSUER}/token", "jwks_uri": f"{ISSUER}/jwks"})
        if url.endswith("/jwks"):
            return httpx.Response(200, json={"keys": [self.jwk()]})
        if url.endswith("/token"):
            form = parse_qs(request.content.decode())
            code = form["code"][0]
            data = self.codes.pop(code, None)
            if data is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            # PKCE: el verificador debe corresponder al desafío enviado al autorizar
            challenge = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"][0].encode()).digest()
                                                 ).rstrip(b"=").decode()
            if challenge != data["challenge"]:
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "pkce"})
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": CLIENT, "iat": now, "exp": now + 300, "nonce": data["nonce"],
                      **self.next_claims}
            token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": self.kid})
            return httpx.Response(200, json={"id_token": token, "access_token": "x", "token_type": "Bearer"})
        return httpx.Response(404)

    def authorize(self, location: str) -> str:
        """Simula que la persona se autentica en el proveedor: devuelve la URL de vuelta a la app."""
        q = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
        assert q["code_challenge_method"] == "S256" and q["client_id"] == CLIENT
        code = uuid.uuid4().hex
        self.codes[code] = {"nonce": q["nonce"], "challenge": q["code_challenge"]}
        return f"/api/v1/auth/oidc/callback?code={code}&state={q['state']}"


@pytest.fixture
def idp(monkeypatch):
    from app.security import oidc

    fake = FakeIdP()
    monkeypatch.setattr(oidc, "_transport", httpx.MockTransport(fake.handler))
    oidc._cache.clear()
    yield fake
    oidc._cache.clear()


def _flow(app, idp: FakeIdP, claims: dict, tamper=None) -> tuple[TestClient, httpx.Response]:
    c = TestClient(app, follow_redirects=False)
    r = c.get("/api/v1/auth/oidc/login")
    assert r.status_code == 302 and r.headers["location"].startswith(f"{ISSUER}/authorize")
    back = idp.authorize(r.headers["location"])
    if tamper:
        back = tamper(back)
    idp.next_claims = claims
    return c, c.get(back)


def _target(resp: httpx.Response) -> str:
    return resp.text.split('url=')[1].split('"')[0]


def _user_with_email(login, ids) -> tuple[str, str]:
    admin = login("direccion.demo")
    username = "oidc." + uuid.uuid4().hex[:6]
    email = f"{username}@corporativo.invalid"
    r = admin.post("/api/v1/admin/users", json={
        "username": username, "full_name": "Persona Corporativa Ficticia", "email": email,
        "membership": {"organization_id": str(ids["es"]), "role_code": "atc"}, "reason": "alta para OIDC"})
    assert r.status_code == 201
    return r.json()["user"]["id"], email


def test_oidc_con_mfa_entra_y_enlaza_la_cuenta(app, idp, login, ids, db):
    uid, email = _user_with_email(login, ids)
    sub = uuid.uuid4().hex
    c, r = _flow(app, idp, {"sub": sub, "email": email, "amr": ["pwd", "mfa"]})
    assert r.status_code == 200 and _target(r) == "/"
    me = c.get("/api/v1/me").json()
    assert me["id"] == uid and me["auth_mode"] == "oidc"
    from app.models import UserAccount

    db.rollback()
    assert db.get(UserAccount, uid).external_subject == f"{ISSUER}|{sub}"
    # Segunda vez: entra por el identificador del proveedor aunque cambie el correo
    c2, r2 = _flow(app, idp, {"sub": sub, "email": "otro@corporativo.invalid", "amr": ["mfa"]})
    assert c2.get("/api/v1/me").json()["id"] == uid


def test_oidc_sin_mfa_denegado(app, idp, login, ids):
    _, email = _user_with_email(login, ids)
    c, r = _flow(app, idp, {"sub": uuid.uuid4().hex, "email": email, "amr": ["pwd"]})
    assert _target(r) == "/login?error=oidc_sin_mfa"
    assert c.get("/api/v1/me").status_code == 401


def test_oidc_sin_cuenta_no_crea_usuario(app, idp, db):
    from app.models import UserAccount

    db.rollback()
    before = db.query(UserAccount).count()
    c, r = _flow(app, idp, {"sub": uuid.uuid4().hex, "email": "desconocido@corporativo.invalid", "amr": ["mfa"]})
    assert _target(r) == "/login?error=oidc_sin_cuenta"
    db.rollback()
    assert db.query(UserAccount).count() == before


def test_oidc_estado_manipulado(app, idp, login, ids):
    _, email = _user_with_email(login, ids)
    c, r = _flow(app, idp, {"sub": "x", "email": email, "amr": ["mfa"]},
                 tamper=lambda u: u.split("&state=")[0] + "&state=falso")
    assert _target(r) == "/login?error=oidc_estado"


def test_oidc_firma_ajena_rechazada(app, idp, login, ids, monkeypatch):
    _, email = _user_with_email(login, ids)
    impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    real = idp.key
    original = idp.handler

    def handler(request):
        if str(request.url).endswith("/token"):
            idp.key = impostor  # firma con otra clave que no está en el JWKS publicado
            try:
                return original(request)
            finally:
                idp.key = real
        return original(request)

    from app.security import oidc

    monkeypatch.setattr(oidc, "_transport", httpx.MockTransport(handler))
    c, r = _flow(app, idp, {"sub": "y", "email": email, "amr": ["mfa"]})
    assert _target(r) == "/login?error=oidc_token"
    assert c.get("/api/v1/me").status_code == 401


def test_oidc_usuario_desactivado(app, idp, login, ids):
    uid, email = _user_with_email(login, ids)
    login("direccion.demo").post(f"/api/v1/admin/users/{uid}/deactivate", json={"reason": "baja ficticia"})
    c, r = _flow(app, idp, {"sub": uuid.uuid4().hex, "email": email, "amr": ["mfa"]})
    assert _target(r) == "/login?error=oidc_sin_cuenta"
