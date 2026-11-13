"""Sincroniza el catálogo de trámites del código con la BD, creando una versión nueva cuando cambia."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_immigration import ImmigProcedure
from .catalog import PROCEDURES


def _hash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sync_procedures(db: Session) -> int:
    changed = 0
    for p in PROCEDURES:
        h = _hash(p)
        latest = db.execute(select(ImmigProcedure).where(ImmigProcedure.code == p["code"])
                            .order_by(ImmigProcedure.version.desc()).limit(1)).scalar_one_or_none()
        if latest is not None and latest.content_hash == h:
            continue
        if latest is not None:
            latest.status = "sustituido"
        db.add(ImmigProcedure(code=p["code"], version=(latest.version + 1) if latest else 1, content_hash=h,
                              name=p["name"], family=p["family"], materia=p["materia"], data=p,
                              status="pendiente_validacion"))
        changed += 1
    db.flush()
    return changed


def current(db: Session, code: str) -> ImmigProcedure | None:
    return db.execute(select(ImmigProcedure).where(ImmigProcedure.code == code, ImmigProcedure.status != "sustituido")
                      .order_by(ImmigProcedure.version.desc()).limit(1)).scalar_one_or_none()
