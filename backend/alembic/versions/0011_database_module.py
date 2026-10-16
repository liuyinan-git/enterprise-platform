from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0011_database_module"
down_revision = "0010_model_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "database_instance",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("instance_code", sa.String(100), nullable=False),
        sa.Column("instance_name", sa.String(200), nullable=False),
        sa.Column("db_type", sa.String(50), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("database_name", sa.String(100)),
        sa.Column("username", sa.String(100)),
        sa.Column("password", sa.String(500), server_default="", nullable=False),
        sa.Column("environment", sa.String(50)),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("attributes", mysql.JSON()),
        sa.Column("last_check_at", mysql.DATETIME(fsp=3)),
        sa.Column("health_status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("instance_code", name="uk_instance_code"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_db_instance_type", "database_instance", ["db_type"])

    op.create_table(
        "database_health",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("instance_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("database_instance.id"), nullable=False),
        sa.Column("check_type", sa.String(50), server_default="connection", nullable=False),
        sa.Column("status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("latency_ms", mysql.INTEGER(unsigned=True)),
        sa.Column("detail", mysql.JSON()),
        sa.Column("checked_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_db_health_instance", "database_health", ["instance_id"])
    op.create_index("idx_db_health_checked", "database_health", ["checked_at"])

    op.create_table(
        "database_backup",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("instance_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("database_instance.id"), nullable=False),
        sa.Column("backup_type", sa.String(50), server_default="full", nullable=False),
        sa.Column("status", sa.String(24), server_default="success", nullable=False),
        sa.Column("size", mysql.BIGINT(unsigned=True), server_default="0", nullable=False),
        sa.Column("started_at", mysql.DATETIME(fsp=3)),
        sa.Column("finished_at", mysql.DATETIME(fsp=3)),
        sa.Column("result", sa.Text()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_db_backup_instance", "database_backup", ["instance_id"])
    op.create_index("idx_db_backup_started", "database_backup", ["started_at"])


def downgrade() -> None:
    op.drop_index("idx_db_backup_started", table_name="database_backup")
    op.drop_index("idx_db_backup_instance", table_name="database_backup")
    op.drop_table("database_backup")
    op.drop_index("idx_db_health_checked", table_name="database_health")
    op.drop_index("idx_db_health_instance", table_name="database_health")
    op.drop_table("database_health")
    op.drop_index("idx_db_instance_type", table_name="database_instance")
    op.drop_table("database_instance")
