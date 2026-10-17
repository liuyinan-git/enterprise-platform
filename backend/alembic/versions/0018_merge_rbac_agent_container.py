"""合并 RBAC 与智能体容器绑定两条迁移分支

Revision ID: 0018_merge_rbac_agent_container
Revises: 0016_rbac, 0017_agent_container_binding

`0016_rbac`（RBAC 三表）与本地 `0016_agent_offline_alert → 0017_agent_container_binding`
两条分支都从 `0015_model_consumer_alert` 分出，此迁移只负责合并 head，无表结构变更。
"""

revision = "0018_merge_rbac_agent_container"
down_revision = ("0016_rbac", "0017_agent_container_binding")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
