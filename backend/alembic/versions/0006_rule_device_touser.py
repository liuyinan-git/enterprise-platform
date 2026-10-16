from alembic import op
import sqlalchemy as sa

revision = "0006_rule_device_touser"
down_revision = "0005_wecom_notify_severity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_rule", sa.Column("touser", sa.String(500), nullable=True))
    op.add_column("device_registry", sa.Column("touser", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("device_registry", "touser")
    op.drop_column("analysis_rule", "touser")
