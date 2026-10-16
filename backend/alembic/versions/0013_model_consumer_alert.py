"""模型模块 Phase 3：调用方台账（model_consumer + model_consumer_rel）+ 告警记录（model_alert）+ 连续失败计数。

Revision ID: 0013_model_consumer_alert
Revises: 0012_model_monitor
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0013_model_consumer_alert"
down_revision = "0012_model_monitor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_registry",
        sa.Column("consecutive_failures", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
    )

    op.create_table(
        "model_consumer",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("consumer_code", sa.String(100), nullable=False),
        sa.Column("consumer_name", sa.String(200), nullable=False),
        sa.Column("identity_type", sa.String(24), server_default="external_ip", nullable=False),
        sa.Column("identifier", sa.String(200), server_default="", nullable=False),
        sa.Column("contact", sa.String(200), server_default="", nullable=False),
        sa.Column("remark", sa.String(500)),
        sa.Column("evidence", sa.String(500)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("consumer_code", name="uk_consumer_code"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_consumer_identifier", "model_consumer", ["identifier"])

    op.create_table(
        "model_consumer_rel",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("consumer_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_consumer.id"), nullable=False),
        sa.Column("model_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("consumer_id", "model_id", name="uk_consumer_model"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rel_model", "model_consumer_rel", ["model_id"])

    op.create_table(
        "model_alert",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("alert_no", sa.String(64), nullable=False),
        sa.Column("model_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("alert_type", sa.String(24), server_default="failure", nullable=False),
        sa.Column("channel", sa.String(24), server_default="wecom", nullable=False),
        sa.Column("receiver_key", sa.String(200), server_default="", nullable=False),
        sa.Column("message_content", sa.String(4000), server_default="", nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("attempt_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("next_retry_at", mysql.DATETIME(fsp=3)),
        sa.Column("sent_at", mysql.DATETIME(fsp=3)),
        sa.Column("resolved_at", mysql.DATETIME(fsp=3)),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("alert_no", name="uk_model_alert_no"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_malert_model", "model_alert", ["model_id", "created_at"])
    op.create_index("idx_malert_status_retry", "model_alert", ["status", "next_retry_at"])


def downgrade() -> None:
    op.drop_index("idx_malert_status_retry", table_name="model_alert")
    op.drop_index("idx_malert_model", table_name="model_alert")
    op.drop_table("model_alert")
    op.drop_index("idx_rel_model", table_name="model_consumer_rel")
    op.drop_table("model_consumer_rel")
    op.drop_index("idx_consumer_identifier", table_name="model_consumer")
    op.drop_table("model_consumer")
    op.drop_column("model_registry", "consecutive_failures")
