"""模型管控增强：model_registry 扩展服务化字段 + model_health 探测历史表。

Revision ID: 0014_model_monitor
Revises: 0013_agent_platform
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0014_model_monitor"
down_revision = "0013_agent_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_registry", sa.Column("service_type", sa.String(24), server_default="chat", nullable=False))
    op.add_column("model_registry", sa.Column("endpoint_url", sa.String(500), server_default="", nullable=False))
    op.add_column("model_registry", sa.Column("probe_method", sa.String(24), server_default="openai", nullable=False))
    op.add_column("model_registry", sa.Column("engine", sa.String(100)))
    op.add_column("model_registry", sa.Column("last_metrics_value", mysql.BIGINT(unsigned=True)))
    op.add_column("model_registry", sa.Column("metrics_metric", sa.String(200)))

    op.create_table(
        "model_health",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("model_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("latency_ms", mysql.INTEGER(unsigned=True)),
        sa.Column("message", sa.String(500)),
        sa.Column("checked_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_model_health_model", "model_health", ["model_id"])
    op.create_index("idx_model_health_checked", "model_health", ["checked_at"])


def downgrade() -> None:
    op.drop_index("idx_model_health_checked", table_name="model_health")
    op.drop_index("idx_model_health_model", table_name="model_health")
    op.drop_table("model_health")
    op.drop_column("model_registry", "metrics_metric")
    op.drop_column("model_registry", "last_metrics_value")
    op.drop_column("model_registry", "engine")
    op.drop_column("model_registry", "probe_method")
    op.drop_column("model_registry", "endpoint_url")
    op.drop_column("model_registry", "service_type")
