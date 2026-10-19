"""log_event 加 (event_time, id) 复合索引，支撑日志检索的 ORDER BY event_time DESC, id DESC。"""

from alembic import op

revision = "0020_log_event_index"
down_revision = "0019_merge_model_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_event_time_id", "log_event", ["event_time", "id"])


def downgrade() -> None:
    op.drop_index("idx_event_time_id", table_name="log_event")
