"""Configuración por variables de entorno. Ningún secreto vive en el código."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AUTH_METHODS = ("demo", "local", "oidc")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    # Métodos de acceso habilitados, separados por comas: demo (solo desarrollo/tests),
    # local (usuario + contraseña + código TOTP obligatorio) y oidc (proveedor corporativo con MFA).
    auth_mode: str = "local"
    database_url: str = Field(..., description="postgresql+psycopg://usuario:clave@host:5432/bd")
    session_secret: str = Field(..., min_length=32, description="Clave HMAC de sesión (>=32 caracteres)")
    session_ttl_minutes: int = 480       # duración máxima de una sesión
    session_idle_minutes: int = 60       # cierre por inactividad
    cookie_secure: bool = True
    web_origin: str = "http://localhost:3000"
    # CIF/NIF propios del despacho (separados por comas) para que la lectura de facturas recibidas no los confunda
    # con el del proveedor. Se ponen en el .env de cada instalación, nunca en el código.
    own_tax_ids: str = ""
    # Detrás del proxy de la web (Next.js) la IP real llega en X-Forwarded-For.
    trust_proxy: bool = False
    # Clave para cifrar secretos TOTP en la base de datos (Fernet, base64 de 32 bytes).
    # Obligatoria fuera de development/test; en desarrollo se deriva de SESSION_SECRET.
    field_encryption_key: str | None = None
    # Límite de intentos de acceso
    login_max_failures_user: int = 5
    login_max_failures_ip: int = 30
    login_window_minutes: int = 15
    # OIDC (T-01: proveedor pendiente de elegir). Vacío = acceso corporativo no disponible.
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None   # por defecto WEB_ORIGIN/api/v1/auth/oidc/callback
    oidc_scopes: str = "openid email profile"
    oidc_email_claim: str = "email"
    oidc_require_mfa: bool = True
    oidc_mfa_amr: str = "mfa,otp,hwk,swk,fido,sms,mca"
    # Copias de seguridad (AT-29): base auxiliar donde se restaura cada copia para comprobarla.
    restore_database_url: str | None = None
    backup_dir: str = "/copias"
    # Justificantes de gasto (cifrados). En Docker es un volumen propio incluido en las copias.
    receipts_dir: str = "/datos/justificantes"
    # Documentos de expedientes (cifrados). Volumen propio, incluido en las copias.
    documents_dir: str = "/datos/documentos"
    # F2.3 portal del cliente y comunicaciones. Correo saliente por SMTP (proveedor con contrato de encargo en la UE).
    # Sin SMTP_HOST el correo queda «no configurado»: en desarrollo/pruebas el código de acceso se muestra en pantalla.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Despacho <no-responder@despacho.invalid>"
    smtp_starttls: bool = True
    portal_session_minutes: int = 480       # duración máxima de la sesión del cliente
    portal_idle_minutes: int = 30           # cierre por inactividad del cliente
    portal_code_minutes: int = 10           # validez del código de acceso

    @property
    def auth_methods(self) -> set[str]:
        return {m.strip() for m in self.auth_mode.split(",") if m.strip()}

    @property
    def oidc_enabled(self) -> bool:
        return "oidc" in self.auth_methods and bool(self.oidc_issuer and self.oidc_client_id)

    @model_validator(mode="after")
    def _guard(self) -> Settings:
        unknown = self.auth_methods - set(AUTH_METHODS)
        if unknown or not self.auth_methods:
            raise ValueError(f"AUTH_MODE no válido: {self.auth_mode!r}. Use una lista de {', '.join(AUTH_METHODS)}.")
        shared = self.app_env not in ("development", "test")
        # Regla F0: el modo DEMO solo existe en desarrollo y tests.
        if "demo" in self.auth_methods and shared:
            raise ValueError(
                f"AUTH_MODE=demo está prohibido con APP_ENV={self.app_env}. "
                "Use acceso local con doble verificación u OIDC con MFA."
            )
        if shared and "local" in self.auth_methods and not self.field_encryption_key:
            raise ValueError("FIELD_ENCRYPTION_KEY es obligatoria con acceso local fuera de desarrollo.")
        if shared and "oidc" in self.auth_methods and not self.oidc_require_mfa:
            raise ValueError("OIDC sin MFA obligatorio está prohibido fuera de desarrollo.")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE debe ser true en producción.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
