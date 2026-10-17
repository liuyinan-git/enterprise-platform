"""模型模块：部署节点（model_provider）新增容器代理地址，支撑跨服务器读容器实况/日志。

给 model_provider 加 container_proxy_url（可空）：该节点所在服务器的 docker-socket-proxy 地址。
空/NULL 回退全局 MODEL_CONTAINER_PROXY_URL；跨机场景每个节点填自己的 proxy 即可，无需改代码。

Revision ID: 0018_model_node_proxy
Revises: 0017_model_consumer_usage
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_model_node_proxy"
down_revision = "0017_model_consumer_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_provider", sa.Column("container_proxy_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("model_provider", "container_proxy_url")
