"""F5.4b Contabilidad: rutina de trabajo con comprobación automática e informes semanales, quincenales y mensuales.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09 13:05:00
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

TABLES = ("accounting_routine_owner", "accounting_routine_item", "accounting_report")


def upgrade() -> None:
    op.create_table(
        "accounting_routine_owner",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("updated_by", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "step"),
    )
    op.create_table(
        "accounting_routine_item",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("cadence", sa.String(10), nullable=False),
        sa.Column("period", sa.String(12), nullable=False),
        sa.Column("period_label", sa.String(60), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("task.id")),
        sa.Column("evidence", sa.String(500)),
        sa.Column("done_at", sa.DateTime(timezone=True)),
        sa.Column("on_time", sa.Boolean()),
        sa.Column("na_by", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("na_reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "step", "period"),
        sa.CheckConstraint("status IN ('pendiente','hecho','no_aplica')", name="ck_routine_status"),
        sa.CheckConstraint("cadence IN ('diaria','semanal','quincenal','mensual')", name="ck_routine_cadence"),
        sa.CheckConstraint("status <> 'no_aplica' OR (na_by IS NOT NULL AND length(na_reason) >= 10)",
                           name="ck_routine_na_reason"),
    )
    op.create_index("ix_routine_item_org_due", "accounting_routine_item", ["organization_id", "due_date"])
    op.create_table(
        "accounting_report",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("figures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("figures_sha256", sa.String(64), nullable=False),
        sa.Column("generated_by", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.String(1000)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "kind", "period_from", "version"),
        sa.CheckConstraint("kind IN ('semanal','quincenal','mensual')", name="ck_report_kind"),
        sa.CheckConstraint("period_to >= period_from", name="ck_report_period"),
    )
    for t in TABLES:
        op.execute(f"CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION sp_forbid_change()")
    # Un paso hecho o «no aplica» no vuelve atrás; el periodo, la fecha y la evidencia no se reescriben.
    op.execute("""
    CREATE OR REPLACE FUNCTION sp_routine_item_guard() RETURNS trigger AS $$
    BEGIN
      IF NEW.organization_id <> OLD.organization_id OR NEW.step <> OLD.step OR NEW.period <> OLD.period
         OR NEW.due_date <> OLD.due_date THEN
        RAISE EXCEPTION 'El paso de la rutina no cambia de periodo ni de fecha';
      END IF;
      IF OLD.status <> 'pendiente' AND (NEW.status <> OLD.status OR NEW.done_at IS DISTINCT FROM OLD.done_at
         OR NEW.evidence IS DISTINCT FROM OLD.evidence OR NEW.na_reason IS DISTINCT FROM OLD.na_reason) THEN
        RAISE EXCEPTION 'Un paso de la rutina cerrado no se modifica';
      END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """)
    op.execute("CREATE TRIGGER accounting_routine_item_guard BEFORE UPDATE ON accounting_routine_item "
               "FOR EACH ROW EXECUTE FUNCTION sp_routine_item_guard()")
    # Un informe es una foto: solo se puede anotar UNA vez que se ha revisado.
    op.execute("""
    CREATE OR REPLACE FUNCTION sp_report_guard() RETURNS trigger AS $$
    BEGIN
      IF NEW.figures IS DISTINCT FROM OLD.figures OR NEW.figures_sha256 <> OLD.figures_sha256 OR NEW.kind <> OLD.kind
         OR NEW.period_from <> OLD.period_from OR NEW.period_to <> OLD.period_to OR NEW.version <> OLD.version
         OR NEW.generated_at <> OLD.generated_at OR NEW.generated_by IS DISTINCT FROM OLD.generated_by
         OR NEW.organization_id <> OLD.organization_id THEN
        RAISE EXCEPTION 'Un informe generado no se modifica';
      END IF;
      IF OLD.reviewed_by IS NOT NULL THEN
        RAISE EXCEPTION 'El informe ya está revisado';
      END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """)
    op.execute("CREATE TRIGGER accounting_report_guard BEFORE UPDATE ON accounting_report "
               "FOR EACH ROW EXECUTE FUNCTION sp_report_guard()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS accounting_report_guard ON accounting_report")
    op.execute("DROP TRIGGER IF EXISTS accounting_routine_item_guard ON accounting_routine_item")
    for t in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {t}_no_delete ON {t}")
    op.execute("DROP FUNCTION IF EXISTS sp_report_guard() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS sp_routine_item_guard() CASCADE")
    op.drop_table("accounting_report")
    op.drop_index("ix_routine_item_org_due", table_name="accounting_routine_item")
    op.drop_table("accounting_routine_item")
    op.drop_table("accounting_routine_owner")
