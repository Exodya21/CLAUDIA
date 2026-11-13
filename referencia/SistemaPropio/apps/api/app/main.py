"""SISTEMA PROPIO — API F0.1 (núcleo de seguridad + directorio de clientes)."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import errors
from .config import get_settings
from .db import get_engine
from .routers import (
    accounting,
    admin,
    audit_log,
    auth,
    bank,
    cases,
    comm,
    contacts,
    economy,
    expenses,
    grants,
    hr,
    immigration,
    immigration_forms,
    leads,
    me,
    portal,
    reception,
    tasks,
)
from .routers import agents as agents_router

API_PREFIX = "/api/v1"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "sistema-propio"


def create_app() -> FastAPI:
    settings = get_settings()  # valida configuración: DEMO en producción aborta aquí
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title="SISTEMA PROPIO API",
        version="0.7.0",
        description="F0.1 núcleo y clientes · F0.2 acceso seguro, sesiones, administración y copias · F5.0 control económico y gastos (sin facturación fiscal) · F1.2 CRM · F2.1 expedientes · F2.2 tareas y agenda · F4.1–F4.3 extranjería (lectura de documentos y relleno de Mercurio, sin presentación automática) · F2.3 portal del cliente y conversaciones por expediente (sin WhatsApp). Datos ficticios.",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    errors.install(app)

    @app.middleware("http")
    async def security_mw(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        # Defensa CSRF: toda petición que modifica exige una cabecera propia (no enviable
        # entre sitios sin preflight CORS) además de la cookie SameSite=Strict.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith(API_PREFIX):
            if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
                return JSONResponse(status_code=403, content={"error": {
                    "code": "csrf", "message": "Falta la cabecera de seguridad de la aplicación.",
                    "details": None, "request_id": request.state.request_id}})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    for r in (auth.router, me.router, contacts.router, cases.router, grants.router, audit_log.router,
              leads.router, tasks.router, admin.router, economy.router, expenses.router,
              immigration.router, immigration_forms.router, comm.router, portal.router, bank.router,
              agents_router.router, reception.router, hr.router, accounting.router):
        app.include_router(r, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/health", tags=["sistema"])
    def health() -> dict:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "environment": settings.app_env, "auth_mode": ",".join(sorted(settings.auth_methods))}

    return app


app = create_app()
