"""合并模型监控 head（0018_model_node_proxy）与智能体 / RBAC head（0018_merge_rbac_agent_container）。

两条分支并行开发后各自到达 head，此处做空合并，保证 `alembic upgrade head` 只有一个 head。

Revision ID: 0019_merge_model_agent
Revises: 0018_model_node_proxy, 0018_merge_rbac_agent_container
"""

revision = "0019_merge_model_agent"
down_revision = ("0018_model_node_proxy", "0018_merge_rbac_agent_container")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
