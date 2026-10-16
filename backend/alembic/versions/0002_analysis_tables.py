from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0002_analysis_tables"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "log_event",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("raw_log_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("device_id", sa.String(100)),
        sa.Column("hostname", sa.String(255)),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("event_category", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), server_default="info", nullable=False),
        sa.Column("security_label", sa.String(30), server_default="unknown", nullable=False),
        sa.Column("source_ip", sa.String(45)),
        sa.Column("dest_ip", sa.String(45)),
        sa.Column("source_port", mysql.INTEGER(unsigned=True)),
        sa.Column("dest_port", mysql.INTEGER(unsigned=True)),
        sa.Column("username", sa.String(255)),
        sa.Column("process_name", sa.String(255)),
        sa.Column("event_time", mysql.DATETIME(fsp=3)),
        sa.Column("normalized_data", mysql.JSON()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("raw_log_id", name="uk_event_raw"),
        sa.ForeignKeyConstraint(["raw_log_id"], ["log_raw.id"], name="fk_event_raw"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_event_time_severity", "log_event", ["event_time", "severity"])
    op.create_index("idx_event_device_time", "log_event", ["device_id", "event_time"])
    op.create_index("idx_event_type_time", "log_event", ["event_type", "event_time"])
    op.create_index("idx_event_source_time", "log_event", ["source_ip", "event_time"])
    op.create_index("idx_event_category_time", "log_event", ["event_category", "event_time"])

    op.create_table(
        "analysis_rule",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("rule_type", sa.String(40), server_default="threshold", nullable=False),
        sa.Column("device_types", mysql.JSON()),
        sa.Column("rule_config", mysql.JSON(), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("cooldown_seconds", mysql.INTEGER(unsigned=True), server_default="600", nullable=False),
        sa.Column("version", mysql.INTEGER(unsigned=True), server_default="1", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("rule_code", name="uk_rule_code"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rule_enabled", "analysis_rule", ["enabled"])

    op.create_table(
        "security_event",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("event_no", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("rule_code", sa.String(100)),
        sa.Column("event_title", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), server_default="open", nullable=False),
        sa.Column("source_ip", sa.String(45)),
        sa.Column("device_id", sa.String(100)),
        sa.Column("first_seen_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("last_seen_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("occurrence_count", mysql.INTEGER(unsigned=True), server_default="1", nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("ai_analysis", mysql.JSON()),
        sa.Column("assigned_to", sa.String(100)),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("resolved_at", mysql.DATETIME(fsp=3)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("event_no", name="uk_event_no"),
        sa.UniqueConstraint("fingerprint", name="uk_event_fingerprint"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_security_status_severity", "security_event", ["status", "severity"])
    op.create_index("idx_security_last_seen", "security_event", ["last_seen_at"])
    op.create_index("idx_security_rule", "security_event", ["rule_code"])

    op.create_table(
        "security_event_log",
        sa.Column("security_event_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("log_event_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("relation_type", sa.String(40), server_default="evidence", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.PrimaryKeyConstraint("security_event_id", "log_event_id"),
        sa.ForeignKeyConstraint(["security_event_id"], ["security_event.id"], name="fk_relation_event"),
        sa.ForeignKeyConstraint(["log_event_id"], ["log_event.id"], name="fk_relation_log"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_relation_log", "security_event_log", ["log_event_id"])

    op.create_table(
        "alert_record",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("alert_no", sa.String(64), nullable=False),
        sa.Column("security_event_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("channel", sa.String(40), server_default="wecom", nullable=False),
        sa.Column("receiver_key", sa.String(200)),
        sa.Column("message_content", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("attempt_count", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("next_retry_at", mysql.DATETIME(fsp=3)),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("sent_at", mysql.DATETIME(fsp=3)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("alert_no", name="uk_alert_no"),
        sa.ForeignKeyConstraint(["security_event_id"], ["security_event.id"], name="fk_alert_event"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_alert_status_retry", "alert_record", ["status", "next_retry_at"])
    op.create_index("idx_alert_event", "alert_record", ["security_event_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_alert_event", table_name="alert_record")
    op.drop_index("idx_alert_status_retry", table_name="alert_record")
    op.drop_table("alert_record")

    op.drop_index("idx_relation_log", table_name="security_event_log")
    op.drop_table("security_event_log")

    op.drop_index("idx_security_rule", table_name="security_event")
    op.drop_index("idx_security_last_seen", table_name="security_event")
    op.drop_index("idx_security_status_severity", table_name="security_event")
    op.drop_table("security_event")

    op.drop_index("idx_rule_enabled", table_name="analysis_rule")
    op.drop_table("analysis_rule")

    op.drop_index("idx_event_category_time", table_name="log_event")
    op.drop_index("idx_event_source_time", table_name="log_event")
    op.drop_index("idx_event_type_time", table_name="log_event")
    op.drop_index("idx_event_device_time", table_name="log_event")
    op.drop_index("idx_event_time_severity", table_name="log_event")
    op.drop_table("log_event")
