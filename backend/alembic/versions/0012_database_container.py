from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0012_database_container"
down_revision = "0011_database_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "database_container_audit",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("container_id", sa.String(64), nullable=False),
        sa.Column("container_name", sa.String(200), server_default="", nullable=False),
        sa.Column("managed_type", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("result", sa.String(24), server_default="success", nullable=False),
        sa.Column("operator", sa.String(100)),
        sa.Column("detail", mysql.JSON()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_db_container_audit_container", "database_container_audit", ["container_id"])
    op.create_index("idx_db_container_audit_created", "database_container_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_db_container_audit_created", table_name="database_container_audit")
    op.drop_index("idx_db_container_audit_container", table_name="database_container_audit")
    op.drop_table("database_container_audit")
