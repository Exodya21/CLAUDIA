"""Copias de seguridad con restauración comprobada (AT-29).

Una copia solo cuenta como válida si se ha RESTAURADO en una base auxiliar y en ella:
1. existe el esquema (versión de migraciones),
2. la cadena de auditoría se verifica completa, y
3. el último evento restaurado coincide con el mismo evento de la base en uso (la copia no está manipulada).
El resultado queda en `backup_run` (solo inserción) y en la auditoría.

Uso:
  python -m app.ops.backup verificar --archivo sp_20261102T180000Z.dump   (Docker: la copia la hace el contenedor db)
  python -m app.ops.backup completa                                       (local: pg_dump/pg_restore instalados)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .. import audit
from ..config import get_settings
from ..models import AuditEvent
from ..models_security import BackupRun

# Tablas cuyo recuento se guarda como evidencia (sin datos personales).
COUNTED = ["organization", "user_account", "membership", "contact", "case_file", "lead", "task", "audit_event",
           "user_session"]


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_restored(restore_url: str, live: Session) -> dict:
    eng = create_engine(restore_url, connect_args={"options": "-c timezone=UTC"})
    out: dict = {"restore_ok": False, "audit_chain_ok": None, "audit_events": None, "matches_live_chain": None,
                 "schema_version": None, "table_counts": None, "detail": ""}
    try:
        with eng.connect() as conn:
            out["schema_version"] = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            counts = {}
            for t in COUNTED:
                if conn.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar():
                    counts[t] = conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
            out["table_counts"] = counts
        out["restore_ok"] = bool(out["schema_version"])
        rs = sessionmaker(bind=eng)()
        try:
            ok, n, broken = audit.verify_chain(rs)
            out["audit_chain_ok"], out["audit_events"] = ok, n
            if not ok:
                out["detail"] += f"Cadena de auditoría rota en el evento {broken}. "
            last = rs.query(AuditEvent.id, AuditEvent.hash).order_by(AuditEvent.id.desc()).first()
        finally:
            rs.close()
        if last:
            live_hash = live.query(AuditEvent.hash).filter(AuditEvent.id == last[0]).scalar()
            out["matches_live_chain"] = live_hash == last[1]
            if not out["matches_live_chain"]:
                out["detail"] += "El último evento de la copia no coincide con la base en uso. "
        live_version = live.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if out["schema_version"] != live_version:
            out["detail"] += f"Versión de esquema distinta (copia {out['schema_version']}, en uso {live_version}). "
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de restauración se registra como copia no válida
        out["detail"] += f"No se pudo leer la base restaurada: {exc.__class__.__name__}. "
    finally:
        eng.dispose()
    out["detail"] = out["detail"].strip() or "Restauración comprobada: esquema, auditoría íntegra y coincidente."
    return out


FILE_SETS = (  # (tabla, columna con la ruta, sufijo del .tar, etiqueta, clave de resultado)
    ("expense", "receipt_path", "_justificantes.tar", "justificantes", "receipts_ok"),
    ("immig_document", "file_path", "_documentos.tar", "documentos", "documents_ok"),
)


def check_receipts(restore_url: str, dump: Path, result: dict) -> None:
    """Todos los archivos cifrados que la copia de la base menciona (justificantes de gasto y documentos de
    expedientes) deben estar en los .tar que la acompañan."""
    import tarfile

    eng = create_engine(restore_url)
    try:
        for table, col, suffix, label, key in FILE_SETS:
            with eng.connect() as conn:
                if not conn.execute(text(f"SELECT to_regclass('{table}')")).scalar():
                    continue
                needed = set(conn.execute(text(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL")).scalars())
            tar = dump.with_name(dump.stem + suffix)
            have: set[str] = set()
            if tar.exists():
                with tarfile.open(tar) as t:
                    have = {Path(m.name).name for m in t.getmembers() if m.isfile()}
            missing = needed - have
            result["table_counts"] = {**(result["table_counts"] or {}), f"{label}_en_copia": len(have & needed),
                                      f"{label}_que_faltan": len(missing)}
            if missing:
                result[key] = False
                result["detail"] = (result["detail"] + f" Faltan {len(missing)} {label} en la copia.").strip()
    finally:
        eng.dispose()


def is_valid(r: dict) -> bool:
    return bool(r["restore_ok"] and r["audit_chain_ok"] and r["matches_live_chain"] is not False
                and r.get("receipts_ok", True) and r.get("documents_ok", True))


def record_run(live: Session, *, file: Path, result: dict, triggered_by: str) -> BackupRun:
    run = BackupRun(file_name=file.name, size_bytes=file.stat().st_size if file.exists() else None,
                    sha256=sha256_of(file) if file.exists() else None, schema_version=result["schema_version"],
                    restore_ok=result["restore_ok"], audit_chain_ok=result["audit_chain_ok"],
                    audit_events=result["audit_events"], matches_live_chain=result["matches_live_chain"],
                    table_counts=result["table_counts"], detail=result["detail"], triggered_by=triggered_by)
    live.add(run)
    live.flush()
    audit.record(live, actor_id=None, action="backup.verify", resource_type="backup", resource_id=run.id,
                 outcome="ok" if is_valid(result) else "denied", reason=result["detail"][:500],
                 after={"archivo": file.name, "sha256": run.sha256, "eventos_auditoria": result["audit_events"],
                        "valida": is_valid(result)})
    live.commit()
    return run


def local_dump_and_restore(source_url: str, restore_url: str, out_dir: Path) -> Path:
    """Copia con pg_dump y restauración en la base auxiliar (borra y recrea su esquema)."""
    for binary in ("pg_dump", "pg_restore"):
        if not shutil.which(binary):
            raise RuntimeError(f"No se encuentra {binary}. En Docker use COPIA_SEGURIDAD.bat.")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"sp_{stamp}.dump"
    subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(path), libpq_url(source_url)],
                   check=True, capture_output=True)
    eng = create_engine(restore_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    eng.dispose()
    subprocess.run(["pg_restore", "--no-owner", "--exit-on-error", "--dbname", libpq_url(restore_url), str(path)],
                   check=True, capture_output=True)
    import tarfile

    for env, default, suffix in (("RECEIPTS_DIR", get_settings().receipts_dir, "_justificantes.tar"),
                                 ("DOCUMENTS_DIR", get_settings().documents_dir, "_documentos.tar")):
        rdir = Path(os.environ.get(env) or default)
        if rdir.is_dir():
            with tarfile.open(path.with_name(path.stem + suffix), "w") as t:
                for f in rdir.glob("*.bin"):
                    t.add(f, arcname=f.name)
    return path


def _session(url: str) -> Session:
    return sessionmaker(bind=create_engine(url, connect_args={"options": "-c timezone=UTC"}))()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.ops.backup", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verificar", help="Comprueba una copia ya restaurada en RESTORE_DATABASE_URL")
    v.add_argument("--archivo", required=True)
    sub.add_parser("completa", help="Copia + restauración + comprobación con pg_dump local")
    args = ap.parse_args(argv)
    s = get_settings()
    if not s.restore_database_url:
        print("Falta RESTORE_DATABASE_URL (base auxiliar para comprobar la restauración).", file=sys.stderr)
        return 2
    if s.restore_database_url.rsplit("/", 1)[-1] == s.database_url.rsplit("/", 1)[-1]:
        print("RESTORE_DATABASE_URL no puede ser la base en uso.", file=sys.stderr)
        return 2
    backup_dir = Path(os.environ.get("BACKUP_DIR", s.backup_dir))
    live = _session(s.database_url)
    try:
        if args.cmd == "completa":
            try:
                file = local_dump_and_restore(s.database_url, s.restore_database_url, backup_dir)
            except subprocess.CalledProcessError as exc:
                print("Fallo al copiar o restaurar:", (exc.stderr or b"").decode()[-400:], file=sys.stderr)
                return 1
        else:
            file = backup_dir / Path(args.archivo).name
            if not file.exists():
                print(f"No existe {file}", file=sys.stderr)
                return 2
        result = verify_restored(s.restore_database_url, live)
        check_receipts(s.restore_database_url, file, result)
        run = record_run(live, file=file, result=result, triggered_by="script")
        estado = "VÁLIDA" if is_valid(result) else "NO VÁLIDA"
        print(f"Copia {estado}: {file.name} · {run.size_bytes or 0:,} bytes · sha256 {run.sha256}")
        print(f"  Esquema {result['schema_version']} · auditoría {result['audit_events']} eventos · {result['detail']}")
        return 0 if is_valid(result) else 1
    finally:
        live.close()


if __name__ == "__main__":
    sys.exit(main())
