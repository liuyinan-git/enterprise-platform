from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_registry",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(100), nullable=False),
        sa.Column("device_name", sa.String(200), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("hostname", sa.String(255)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("environment", sa.String(50)),
        sa.Column("criticality", sa.String(20), server_default="normal", nullable=False),
        sa.Column("expected_interval_seconds", mysql.INTEGER(unsigned=True), server_default="900", nullable=False),
        sa.Column("last_seen_at", mysql.DATETIME(fsp=3)),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("attributes", mysql.JSON()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("device_id", name="uk_device_id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_device_type", "device_registry", ["device_type"])
    op.create_index("idx_device_last_seen", "device_registry", ["last_seen_at"])

    op.create_table(
        "log_batch",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("received_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("accepted_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("rejected_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("status", sa.String(24), server_default="accepted", nullable=False),
        sa.Column("error_summary", mysql.JSON()),
        sa.Column("received_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("processing_started_at", mysql.DATETIME(fsp=3)),
        sa.Column("processing_finished_at", mysql.DATETIME(fsp=3)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("source_id", "batch_id", name="uk_batch_source"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_batch_received", "log_batch", ["received_at"])
    op.create_index("idx_batch_status", "log_batch", ["status"])

    op.create_table(
        "log_raw",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(200)),
        sa.Column("device_id", sa.String(100)),
        sa.Column("event_time", mysql.DATETIME(fsp=3)),
        sa.Column("received_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("format_type", sa.String(40), server_default="text", nullable=False),
        sa.Column("raw_message", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("raw_payload", mysql.JSON()),
        sa.Column("process_status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("process_error", sa.String(1000)),
        sa.Column("retry_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("processed_at", mysql.DATETIME(fsp=3)),
        mysql_engine="InnoDB",
    )
    op.create_index("uk_source_event", "log_raw", ["source_id", "event_id"], unique=True)
    op.create_index("idx_raw_batch", "log_raw", ["batch_id"])
    op.create_index("idx_raw_device_time", "log_raw", ["device_id", "event_time"])
    op.create_index("idx_raw_received", "log_raw", ["received_at"])
    op.create_index("idx_raw_status", "log_raw", ["process_status"])

    op.create_table(
        "processing_task",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("business_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("attempt_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("available_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("locked_at", mysql.DATETIME(fsp=3)),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("task_type", "business_key", name="uk_task_business"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_task_dispatch", "processing_task", ["status", "available_at"])


def downgrade() -> None:
    op.drop_index("idx_task_dispatch", table_name="processing_task")
    op.drop_table("processing_task")
    op.drop_index("idx_raw_status", table_name="log_raw")
    op.drop_index("idx_raw_received", table_name="log_raw")
    op.drop_index("idx_raw_device_time", table_name="log_raw")
    op.drop_index("idx_raw_batch", table_name="log_raw")
    op.drop_index("uk_source_event", table_name="log_raw")
    op.drop_table("log_raw")
    op.drop_index("idx_batch_status", table_name="log_batch")
    op.drop_index("idx_batch_received", table_name="log_batch")
    op.drop_table("log_batch")
    op.drop_index("idx_device_last_seen", table_name="device_registry")
    op.drop_index("idx_device_type", table_name="device_registry")
    op.drop_table("device_registry")
