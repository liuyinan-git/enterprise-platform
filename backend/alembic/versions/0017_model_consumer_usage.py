"""模型模块：调用方用量统计（model_consumer_usage）+ access log 采集游标。

1. 新表 model_consumer_usage：从模型容器 access log 采集「谁在调哪个模型 + 调用次数 + 状态码」，
   按 (consumer_id, model_id, recorded_day) 唯一聚合。
2. model_registry 新增 last_log_cursor：上次读日志的 epoch 秒，下次只读 since=该值 之后的新日志，
   避免相邻周期重叠窗口重复累加（与 last_metrics_value 的差值思路同构）。

Revision ID: 0017_model_consumer_usage
Revises: 0016_rbac
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0017_model_consumer_usage"
down_revision = "0016_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_registry",
        sa.Column("last_log_cursor", mysql.BIGINT(unsigned=True)),
    )

    op.create_table(
        "model_consumer_usage",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("consumer_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_consumer.id"), nullable=False),
        sa.Column("model_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("recorded_day", sa.String(10), nullable=False),
        sa.Column("call_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("error_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("last_seen_at", mysql.DATETIME(fsp=3)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("consumer_id", "model_id", "recorded_day", name="uk_consumer_model_day"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_cusage_model", "model_consumer_usage", ["model_id"])
    op.create_index("idx_cusage_seen", "model_consumer_usage", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("idx_cusage_seen", table_name="model_consumer_usage")
    op.drop_index("idx_cusage_model", table_name="model_consumer_usage")
    op.drop_table("model_consumer_usage")
    op.drop_column("model_registry", "last_log_cursor")
