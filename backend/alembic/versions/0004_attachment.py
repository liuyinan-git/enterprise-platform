from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0004_attachment"
down_revision = "0003_wecom_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachment",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), server_default="other", nullable=False),
        sa.Column("content_type", sa.String(120), server_default="application/octet-stream", nullable=False),
        sa.Column("size", mysql.BIGINT(unsigned=True), server_default="0", nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_attachment_category", "attachment", ["category"])
    op.create_index("idx_attachment_created", "attachment", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_attachment_created", table_name="attachment")
    op.drop_index("idx_attachment_category", table_name="attachment")
    op.drop_table("attachment")
