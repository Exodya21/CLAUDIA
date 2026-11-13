from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..config import get_settings


@dataclass
class ReqCtx:
    ip: str | None
    request_id: str | None
    user_agent: str | None = None


def client_ip(request: Request) -> str | None:
    if get_settings().trust_proxy:
        # La web (Next.js) añade la IP que ve al final de X-Forwarded-For; las entradas
        # anteriores las puede escribir el propio cliente, así que no se usan.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[-1].strip()[:64] or None
    return request.client.host if request.client else None


def req_ctx(request: Request) -> ReqCtx:
    return ReqCtx(ip=client_ip(request), request_id=getattr(request.state, "request_id", None),
                  user_agent=request.headers.get("user-agent"))
