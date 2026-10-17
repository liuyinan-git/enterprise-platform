"""RBAC：角色 / 权限 / 角色-权限关联，并写入默认角色与权限种子。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0016_rbac"
down_revision = "0015_model_consumer_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rbac_role",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("role_code", sa.String(64), nullable=False),
        sa.Column("role_name", sa.String(100), nullable=False),
        sa.Column("external_role_id", sa.String(64)),
        sa.Column("description", sa.String(500)),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=sa.text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), nullable=False),
        sa.UniqueConstraint("role_code", name="uk_rbac_role_code"),
        sa.UniqueConstraint("external_role_id", name="uk_rbac_external_role_id"),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "rbac_permission",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("permission_code", sa.String(64), nullable=False),
        sa.Column("permission_name", sa.String(100), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("permission_code", name="uk_rbac_permission_code"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rbac_permission_module", "rbac_permission", ["module"])

    op.create_table(
        "rbac_role_permission",
        sa.Column("role_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("rbac_role.id"), primary_key=True),
        sa.Column("permission_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("rbac_permission.id"), primary_key=True),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rbac_role_perm_role", "rbac_role_permission", ["role_id"])

    # ---- 种子：角色 ----
    role_tbl = sa.table(
        "rbac_role",
        sa.column("id", sa.Integer),
        sa.column("role_code", sa.String),
        sa.column("role_name", sa.String),
        sa.column("external_role_id", sa.String),
        sa.column("description", sa.String),
        sa.column("enabled", sa.Boolean),
    )
    roles = [
        {"id": 1, "role_code": "admin", "role_name": "超级管理员", "description": "全部权限"},
        {"id": 2, "role_code": "viewer", "role_name": "只读用户", "description": "所有模块只读"},
        {"id": 3, "role_code": "log_admin", "role_name": "日志管理员", "description": "日志模块"},
        {"id": 4, "role_code": "agent_admin", "role_name": "智能体管理员", "description": "智能体模块"},
        {"id": 5, "role_code": "model_admin", "role_name": "模型管理员", "description": "模型模块"},
        {"id": 6, "role_code": "database_admin", "role_name": "数据库管理员", "description": "数据库模块"},
        {"id": 7, "role_code": "gateway_admin", "role_name": "网关管理员", "description": "网关模块"},
        {"id": 8, "role_code": "agent_container_admin", "role_name": "智能体容器操作员", "description": "启停智能体容器"},
        {"id": 9, "role_code": "database_container_admin", "role_name": "数据库容器操作员", "description": "启停数据库容器"},
    ]
    for r in roles:
        r.setdefault("external_role_id", None)
        r.setdefault("enabled", True)
    op.bulk_insert(role_tbl, roles)

    # ---- 种子：权限 ----
    perm_tbl = sa.table(
        "rbac_permission",
        sa.column("id", sa.Integer),
        sa.column("permission_code", sa.String),
        sa.column("permission_name", sa.String),
        sa.column("module", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    perms = [
        {"id": 1, "permission_code": "log:view", "permission_name": "查看日志", "module": "log", "sort_order": 1},
        {"id": 2, "permission_code": "log:manage", "permission_name": "管理日志", "module": "log", "sort_order": 2},
        {"id": 3, "permission_code": "agent:view", "permission_name": "查看智能体", "module": "agent", "sort_order": 1},
        {"id": 4, "permission_code": "agent:manage", "permission_name": "管理智能体", "module": "agent", "sort_order": 2},
        {"id": 5, "permission_code": "agent:container", "permission_name": "启停智能体容器", "module": "agent", "sort_order": 3},
        {"id": 6, "permission_code": "model:view", "permission_name": "查看模型", "module": "model", "sort_order": 1},
        {"id": 7, "permission_code": "model:manage", "permission_name": "管理模型", "module": "model", "sort_order": 2},
        {"id": 8, "permission_code": "database:view", "permission_name": "查看数据库", "module": "database", "sort_order": 1},
        {"id": 9, "permission_code": "database:manage", "permission_name": "管理数据库", "module": "database", "sort_order": 2},
        {"id": 10, "permission_code": "database:container", "permission_name": "启停数据库容器", "module": "database", "sort_order": 3},
        {"id": 11, "permission_code": "gateway:view", "permission_name": "查看网关", "module": "gateway", "sort_order": 1},
        {"id": 12, "permission_code": "gateway:manage", "permission_name": "管理网关", "module": "gateway", "sort_order": 2},
        {"id": 13, "permission_code": "platform:wecom", "permission_name": "企业微信配置", "module": "platform", "sort_order": 1},
        {"id": 14, "permission_code": "platform:files", "permission_name": "附件管理", "module": "platform", "sort_order": 2},
        {"id": 15, "permission_code": "platform:system", "permission_name": "系统监控", "module": "platform", "sort_order": 3},
        {"id": 16, "permission_code": "platform:rbac", "permission_name": "权限管理", "module": "platform", "sort_order": 4},
    ]
    op.bulk_insert(perm_tbl, perms)

    # ---- 种子：角色-权限 ----
    rp_tbl = sa.table(
        "rbac_role_permission",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    # admin -> 全部
    admin_pairs = [{"role_id": 1, "permission_id": i} for i in range(1, 17)]
    mapping = {
        2: [1, 3, 6, 8, 11, 15],                    # viewer
        3: [1, 2],                                   # log_admin
        4: [3, 4],                                   # agent_admin
        5: [6, 7],                                   # model_admin
        6: [8, 9],                                   # database_admin
        7: [11, 12],                                 # gateway_admin
        8: [3, 5],                                   # agent_container_admin
        9: [8, 10],                                  # database_container_admin
    }
    pairs = admin_pairs + [{"role_id": rid, "permission_id": pid} for rid, pids in mapping.items() for pid in pids]
    op.bulk_insert(rp_tbl, pairs)


def downgrade() -> None:
    op.drop_index("idx_rbac_role_perm_role", table_name="rbac_role_permission")
    op.drop_table("rbac_role_permission")
    op.drop_index("idx_rbac_permission_module", table_name="rbac_permission")
    op.drop_table("rbac_permission")
    op.drop_table("rbac_role")
