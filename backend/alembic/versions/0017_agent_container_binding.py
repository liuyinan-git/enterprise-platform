"""智能体绑定容器 + 端点归属智能体

Revision ID: 0017_agent_container_binding
Revises: 0016_agent_offline_alert

- `agent_registry.container_name`：智能体以容器运行时的关联键，容器名手动录入。
  唯一索引允许多个 NULL，历史行（没有容器名）不受影响。
- `agent_endpoint.agent_id`：端点归属的智能体业务码；不做 FK，删除智能体由
  接口层显式拦截，避免历史数据被外键牵连（与本模块既有立场一致）。
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_agent_container_binding"
down_revision = "0016_agent_offline_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_registry", sa.Column("container_name", sa.String(length=200), nullable=True))
    op.create_unique_constraint("uk_agent_container_name", "agent_registry", ["container_name"])
    op.add_column("agent_endpoint", sa.Column("agent_id", sa.String(length=100), nullable=True))
    op.create_index("idx_agent_endpoint_agent", "agent_endpoint", ["agent_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_endpoint_agent", table_name="agent_endpoint")
    op.drop_column("agent_endpoint", "agent_id")
    op.drop_constraint("uk_agent_container_name", "agent_registry", type_="unique")
    op.drop_column("agent_registry", "container_name")
