from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0010_model_module"
down_revision = "0009_agent_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_provider",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("provider_code", sa.String(100), nullable=False),
        sa.Column("provider_name", sa.String(200), nullable=False),
        sa.Column("provider_type", sa.String(50), server_default="openai", nullable=False),
        sa.Column("base_url", sa.String(500), server_default="", nullable=False),
        sa.Column("api_key", sa.String(500), server_default="", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("provider_code", name="uk_provider_code"),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "model_registry",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("model_code", sa.String(100), nullable=False),
        sa.Column("provider_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_provider.id"), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50)),
        sa.Column("context_window", mysql.INTEGER(unsigned=True)),
        sa.Column("parameters", mysql.JSON()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_check_at", mysql.DATETIME(fsp=3)),
        sa.Column("health_status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("model_code", name="uk_model_code"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_model_provider", "model_registry", ["provider_id"])

    op.create_table(
        "model_usage",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("model_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("call_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("input_tokens", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("output_tokens", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("recorded_day", sa.String(10), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("model_id", "recorded_day", name="uk_model_usage_day"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_model_usage_day", "model_usage", ["recorded_day"])


def downgrade() -> None:
    op.drop_index("idx_model_usage_day", table_name="model_usage")
    op.drop_table("model_usage")
    op.drop_index("idx_model_provider", table_name="model_registry")
    op.drop_table("model_registry")
    op.drop_table("model_provider")
