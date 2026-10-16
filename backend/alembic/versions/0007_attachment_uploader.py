from alembic import op
import sqlalchemy as sa

revision = "0007_attachment_uploader"
down_revision = "0006_rule_device_touser"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attachment", sa.Column("uploader", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("attachment", "uploader")
