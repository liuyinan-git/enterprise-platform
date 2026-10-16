from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0013_agent_platform"
down_revision = "0012_database_container"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 项目分类规则
    op.create_table(
        "agent_project_rule",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("project_key", sa.String(100), nullable=False),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("compose_project_names", mysql.JSON()),
        sa.Column("container_name_patterns", mysql.JSON()),
        sa.Column("description", sa.String(500)),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_unique_constraint("uk_agent_project_key", "agent_project_rule", ["project_key"])
    op.create_index("idx_agent_project_enabled", "agent_project_rule", ["enabled"])

    # 2. 端点台账（AI 服务 + LangGraph 共用）
    op.create_table(
        "agent_endpoint",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("endpoint_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("service_type", sa.String(50), nullable=False),
        sa.Column("group_name", sa.String(100)),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("method", sa.String(10), server_default=sa.text("'GET'"), nullable=False),
        sa.Column("headers", mysql.JSON()),
        sa.Column("request_body", mysql.JSON()),
        sa.Column("expected_status", mysql.JSON()),
        sa.Column("timeout_seconds", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("attributes", mysql.JSON()),
        # 最近检查快照
        sa.Column("health_status", sa.String(24), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("last_check_at", mysql.DATETIME(fsp=3)),
        sa.Column("last_http_status", sa.Integer()),
        sa.Column("last_latency_ms", sa.Integer()),
        sa.Column("last_error", sa.String(500)),
        sa.Column("last_ok_at", mysql.DATETIME(fsp=3)),
        sa.Column("consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_unique_constraint("uk_agent_endpoint_code", "agent_endpoint", ["endpoint_code"])
    op.create_index("idx_agent_endpoint_type", "agent_endpoint", ["service_type"])
    op.create_index("idx_agent_endpoint_group", "agent_endpoint", ["group_name"])
    op.create_index("idx_agent_endpoint_health", "agent_endpoint", ["health_status"])
    op.create_index("idx_agent_endpoint_enabled", "agent_endpoint", ["enabled"])

    # 3. 监控历史（append-only，刻意无 FK，见 models.py 的说明）
    op.create_table(
        "agent_health_history",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("endpoint_id", mysql.BIGINT(unsigned=True)),
        sa.Column("endpoint_code", sa.String(100), nullable=False),
        sa.Column("endpoint_name", sa.String(200)),
        sa.Column("service_type", sa.String(50)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("error", sa.String(500)),
        sa.Column("check_type", sa.String(50), server_default=sa.text("'http'"), nullable=False),
        sa.Column("checked_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_agent_hist_endpoint_time", "agent_health_history", ["endpoint_id", "checked_at"])
    op.create_index("idx_agent_hist_status_time", "agent_health_history", ["status", "checked_at"])
    op.create_index("idx_agent_hist_checked", "agent_health_history", ["checked_at"])

    # 4. 容器操作审计
    op.create_table(
        "agent_container_audit",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("container_id", sa.String(64), nullable=False),
        sa.Column("container_name", sa.String(200), server_default="", nullable=False),
        sa.Column("project_key", sa.String(100)),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("result", sa.String(24), server_default="success", nullable=False),
        sa.Column("operator", sa.String(100)),
        sa.Column("detail", mysql.JSON()),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_agent_container_audit_container", "agent_container_audit", ["container_id"])
    op.create_index("idx_agent_container_audit_created", "agent_container_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_agent_container_audit_created", table_name="agent_container_audit")
    op.drop_index("idx_agent_container_audit_container", table_name="agent_container_audit")
    op.drop_table("agent_container_audit")

    op.drop_index("idx_agent_hist_checked", table_name="agent_health_history")
    op.drop_index("idx_agent_hist_status_time", table_name="agent_health_history")
    op.drop_index("idx_agent_hist_endpoint_time", table_name="agent_health_history")
    op.drop_table("agent_health_history")

    op.drop_index("idx_agent_endpoint_enabled", table_name="agent_endpoint")
    op.drop_index("idx_agent_endpoint_health", table_name="agent_endpoint")
    op.drop_index("idx_agent_endpoint_group", table_name="agent_endpoint")
    op.drop_index("idx_agent_endpoint_type", table_name="agent_endpoint")
    op.drop_constraint("uk_agent_endpoint_code", "agent_endpoint", type_="unique")
    op.drop_table("agent_endpoint")

    op.drop_index("idx_agent_project_enabled", table_name="agent_project_rule")
    op.drop_constraint("uk_agent_project_key", "agent_project_rule", type_="unique")
    op.drop_table("agent_project_rule")
