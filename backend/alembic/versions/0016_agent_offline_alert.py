"""智能体离线告警去重标记

Revision ID: 0016_agent_offline_alert
Revises: 0015_model_consumer_alert

给 agent_registry 加 offline_alerted_at：非空表示「已就本次离线告警过」，
心跳恢复时清空。离线是状态而非事件流水，一个标记即可防止每 60s 重复打扰，
不值得为此单开一张告警表。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0016_agent_offline_alert"
down_revision = "0015_model_consumer_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_registry", sa.Column("offline_alerted_at", mysql.DATETIME(fsp=3), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_registry", "offline_alerted_at")
