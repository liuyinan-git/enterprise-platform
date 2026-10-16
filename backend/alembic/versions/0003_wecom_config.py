from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0003_wecom_config"
down_revision = "0002_analysis_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wecom_config",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("corpid", sa.String(200), server_default="", nullable=False),
        sa.Column("corpsecret", sa.String(200), server_default="", nullable=False),
        sa.Column("agentid", mysql.INTEGER(unsigned=True), server_default="0", nullable=False),
        sa.Column("touser", sa.String(500), server_default="", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("wecom_config")
