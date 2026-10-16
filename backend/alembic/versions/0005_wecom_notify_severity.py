from alembic import op
import sqlalchemy as sa

revision = "0005_wecom_notify_severity"
down_revision = "0004_attachment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wecom_config",
        sa.Column("notify_min_severity", sa.String(20), server_default="medium", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("wecom_config", "notify_min_severity")
