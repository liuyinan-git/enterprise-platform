from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0008_rule_suggestion"
down_revision = "0007_attachment_uploader"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rule_suggestion",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium", nullable=False),
        sa.Column("threshold", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("window_seconds", mysql.INTEGER(unsigned=True), server_default="3600", nullable=False),
        sa.Column("group_by", mysql.JSON()),
        sa.Column("baseline_stats", mysql.JSON()),
        sa.Column("reason", sa.String(500)),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("event_type", name="uk_suggestion_event"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_suggestion_status", "rule_suggestion", ["status"])


def downgrade() -> None:
    op.drop_index("idx_suggestion_status", table_name="rule_suggestion")
    op.drop_table("rule_suggestion")
