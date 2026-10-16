from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0009_agent_module"
down_revision = "0008_rule_suggestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(50)),
        sa.Column("owner", sa.String(100)),
        sa.Column("environment", sa.String(50)),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("attributes", mysql.JSON()),
        sa.Column("last_seen_at", mysql.DATETIME(fsp=3)),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("agent_id", name="uk_agent_id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_agent_type", "agent_registry", ["agent_type"])
    op.create_index("idx_agent_last_seen", "agent_registry", ["last_seen_at"])

    op.create_table(
        "agent_audit",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(100)),
        sa.Column("detail", mysql.JSON()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_agent_audit_agent", "agent_audit", ["agent_id"])
    op.create_index("idx_agent_audit_created", "agent_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_agent_audit_created", table_name="agent_audit")
    op.drop_index("idx_agent_audit_agent", table_name="agent_audit")
    op.drop_table("agent_audit")
    op.drop_index("idx_agent_last_seen", table_name="agent_registry")
    op.drop_index("idx_agent_type", table_name="agent_registry")
    op.drop_table("agent_registry")
