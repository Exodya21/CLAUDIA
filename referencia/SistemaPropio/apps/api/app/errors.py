"""Formato de error único: {"error": {"code", "message", "details", "request_id"}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .validation import ValidationFailure

log = logging.getLogger("sistema_propio")

_DEFAULT_CODES = {
    400: "peticion_incorrecta", 401: "no_autenticado", 403: "prohibido", 404: "no_encontrado",
    405: "metodo_no_permitido", 409: "conflicto", 422: "validacion", 429: "demasiadas_peticiones",
}


def api_error(status: int, code: str, message: str, details: Any = None,
              headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message, "details": details}, headers=headers)


def _body(request: Request, status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details,
                           "request_id": getattr(request.state, "request_id", None)}},
    )


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        d = exc.detail
        if isinstance(d, dict):
            resp = _body(request, exc.status_code, d.get("code", "error"), d.get("message", ""), d.get("details"))
        else:
            resp = _body(request, exc.status_code, _DEFAULT_CODES.get(exc.status_code, "error"), str(d))
        for k, v in (getattr(exc, "headers", None) or {}).items():
            resp.headers[k] = v
        return resp

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
        ]
        return _body(request, 422, "validacion", "Revise los datos marcados.", details)

    @app.exception_handler(ValidationFailure)
    async def _vf(request: Request, exc: ValidationFailure) -> JSONResponse:
        return _body(request, 422, "validacion", exc.message, [{"field": exc.field, "message": exc.message}])

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Nunca devolvemos trazas ni datos internos al cliente.
        log.exception("Error no controlado request_id=%s", getattr(request.state, "request_id", None))
        return _body(request, 500, "error_interno", "Se ha producido un error. Se ha registrado para revisión.")
