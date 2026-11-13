"""AT-29 — Copia de seguridad restaurada en una base auxiliar y comprobada (esquema + auditoría íntegra).

Usa pg_dump/pg_restore del sistema y la base RESTORE_DATABASE_URL (nombre terminado en _test).
"""

from __future__ import annotations

import shutil

import pytest
from sqlalchemy import create_engine, select, text

pytestmark = pytest.mark.skipif(not shutil.which("pg_dump"), reason="pg_dump no instalado")


def test_at29_copia_restaurada_y_verificada(tmp_path, db, login):
    from app.config import get_settings
    from app.models_security import BackupRun
    from app.ops import backup

    s = get_settings()
    assert s.restore_database_url.endswith("_test")
    login("recepcion.bcn")  # genera actividad auditada antes de la copia
    file = backup.local_dump_and_restore(s.database_url, s.restore_database_url, tmp_path)
    assert file.exists() and file.stat().st_size > 10_000
    result = backup.verify_restored(s.restore_database_url, db)
    assert result["restore_ok"] and result["audit_chain_ok"] and result["matches_live_chain"], result
    assert result["schema_version"] == db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert result["table_counts"]["contact"] > 0 and result["audit_events"] > 0
    run = backup.record_run(db, file=file, result=result, triggered_by="pruebas")
    assert len(run.sha256) == 64 and run.size_bytes == file.stat().st_size
    # Registro solo de inserción
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE backup_run SET restore_ok = false WHERE id = :i"), {"i": run.id})
        db.flush()
    db.rollback()
    assert db.execute(select(BackupRun).where(BackupRun.id == run.id)).scalar_one().restore_ok is True


def test_at29_copia_manipulada_se_detecta(tmp_path, db):
    from app.config import get_settings
    from app.ops import backup

    s = get_settings()
    backup.local_dump_and_restore(s.database_url, s.restore_database_url, tmp_path)
    eng = create_engine(s.restore_database_url)
    with eng.begin() as conn:
        # Alguien con acceso a la copia altera un evento (desactivando la protección de la tabla)
        conn.execute(text("ALTER TABLE audit_event DISABLE TRIGGER USER"))
        conn.execute(text("UPDATE audit_event SET reason = 'alterado' WHERE id = (SELECT min(id) FROM audit_event)"))
    eng.dispose()
    result = backup.verify_restored(s.restore_database_url, db)
    assert result["audit_chain_ok"] is False and not backup.is_valid(result)
    assert "rota" in result["detail"]


def test_at29_cli_y_listado_para_direccion(tmp_path, monkeypatch, login, db):
    from app.ops import backup

    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    assert backup.main(["completa"]) == 0
    rows = login("direccion.demo").get("/api/v1/admin/backups").json()
    assert rows[0]["restore_ok"] and rows[0]["audit_chain_ok"] and rows[0]["triggered_by"] == "script"
    assert rows[0]["file_name"].startswith("sp_") and rows[0]["file_name"].endswith(".dump")
    # Verificar un archivo inexistente no registra nada válido
    assert backup.main(["verificar", "--archivo", "no_existe.dump"]) == 2


def test_at29_copia_incluye_justificantes_de_gasto(tmp_path, monkeypatch, db):
    """Una copia sin los justificantes que la base menciona no es válida."""
    from app.config import get_settings
    from app.ops import backup

    rdir = tmp_path / "just"
    rdir.mkdir()
    monkeypatch.setenv("RECEIPTS_DIR", str(rdir))
    s = get_settings()
    db.rollback()
    from app.models import Branch
    from app.models_economy import Expense

    u = db.execute(text("SELECT id FROM user_account WHERE username = 'asesor.laboral.bcn'")).scalar()
    b = db.query(Branch).filter(Branch.name == "Barcelona", Branch.kind == "sede").first()
    db.add(Expense(organization_id=b.organization_id, employee_id=u, branch_id=b.id, currency="EUR",
                   receipt_path="copia-prueba-ficticia.bin", receipt_mime="image/jpeg"))
    db.commit()
    paths = list(db.execute(text("SELECT receipt_path FROM expense WHERE receipt_path IS NOT NULL")).scalars())
    for pth in paths:
        (rdir / pth).write_bytes(b"cifrado-ficticio")
    file = backup.local_dump_and_restore(s.database_url, s.restore_database_url, tmp_path / "copias")
    r = backup.verify_restored(s.restore_database_url, db)
    backup.check_receipts(s.restore_database_url, file, r)
    assert backup.is_valid(r) and r["table_counts"]["justificantes_que_faltan"] == 0
    assert paths
    if paths:
        (file.with_name(file.stem + "_justificantes.tar")).unlink()
        r = backup.verify_restored(s.restore_database_url, db)
        backup.check_receipts(s.restore_database_url, file, r)
        assert not backup.is_valid(r) and "Faltan" in r["detail"]


def test_at29_copia_incluye_documentos_de_expedientes(db, tmp_path):
    """F4.1: los documentos cifrados de extranjería van en su propio .tar y la verificación exige que estén."""
    from app.config import get_settings
    from app.ops import backup

    s = get_settings()
    n = db.execute(text("SELECT count(*) FROM immig_document")).scalar_one()
    assert n > 0  # la semilla crea pasaportes y certificados ficticios
    file = backup.local_dump_and_restore(s.database_url, s.restore_database_url, tmp_path / "copias")
    r = backup.verify_restored(s.restore_database_url, db)
    backup.check_receipts(s.restore_database_url, file, r)
    assert r["table_counts"]["documentos_que_faltan"] == 0 and r["table_counts"]["documentos_en_copia"] >= n
    file.with_name(file.stem + "_documentos.tar").unlink()
    r = backup.verify_restored(s.restore_database_url, db)
    backup.check_receipts(s.restore_database_url, file, r)
    assert not backup.is_valid(r) and "documentos" in r["detail"]
