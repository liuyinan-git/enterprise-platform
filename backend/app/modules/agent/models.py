from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentRegistry(Base):
    """智能体注册台账：元数据 + 心跳状态。"""
    __tablename__ = "agent_registry"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uk_agent_id"),
        Index("idx_agent_type", "agent_type"),
        Index("idx_agent_last_seen", "last_seen_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str | None] = mapped_column(String(50))
    owner: Mapped[str | None] = mapped_column(String(100))
    environment: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    attributes: Mapped[dict | list | None] = mapped_column(JSON)
    last_seen_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class AgentAudit(Base):
    """智能体操作审计。"""
    __tablename__ = "agent_audit"
    __table_args__ = (
        Index("idx_agent_audit_agent", "agent_id"),
        Index("idx_agent_audit_created", "created_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class AgentProjectRule(Base):
    """Docker 容器的项目分类规则：compose 项目名 / 容器名正则 → 一个项目。

    规则命中逻辑集中在 `containers.classify_container()`，本表只存配置。
    """
    __tablename__ = "agent_project_rule"
    __table_args__ = (
        UniqueConstraint("project_key", name="uk_agent_project_key"),
        Index("idx_agent_project_enabled", "enabled"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(100), nullable=False)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    # 两个都是字符串数组：[...] 。容器名那侧存的是**正则**，按 re.search 匹配。
    compose_project_names: Mapped[list | None] = mapped_column(JSON)
    container_name_patterns: Mapped[list | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(500))
    # 仅在 UI 上作为「冲突时先看哪条」的建议展示；冲突本身不会被自动按优先级指派
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class AgentEndpoint(Base):
    """端点台账：AI 服务接口（OpenClaw / Hermes / Codex / Dify）与 LangGraph 共用一张表。

    用 `service_type` 区分；LangGraph 的附加信息（图名等）放 `attributes`。
    表中的 `health_*` / `last_*` 是**最近一次检查的快照**，明细在 `agent_health_history`。
    """
    __tablename__ = "agent_endpoint"
    __table_args__ = (
        UniqueConstraint("endpoint_code", name="uk_agent_endpoint_code"),
        Index("idx_agent_endpoint_type", "service_type"),
        Index("idx_agent_endpoint_group", "group_name"),
        Index("idx_agent_endpoint_health", "health_status"),
        Index("idx_agent_endpoint_enabled", "enabled"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    endpoint_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 列名加 _name 后缀：`group` 是 SQL 保留字。对外 JSON 里仍叫 "group"。
    group_name: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'GET'"))
    headers: Mapped[dict | None] = mapped_column(JSON)
    request_body: Mapped[dict | list | None] = mapped_column(JSON)
    # 期望状态码列表，如 [200, 401]；为空则按「2xx 为健康」判定
    expected_status: Mapped[list | None] = mapped_column(JSON)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    description: Mapped[str | None] = mapped_column(String(500))
    attributes: Mapped[dict | list | None] = mapped_column(JSON)
    # 最近检查快照
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'unknown'"))
    last_check_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    last_http_status: Mapped[int | None] = mapped_column(Integer)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_ok_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class AgentHealthHistory(Base):
    """端点监控历史（append-only）。

    **刻意不加 FK，并把 endpoint_code / endpoint_name / service_type 冗余进来**：
    这样删掉监控配置后历史仍然可查（「这接口上周一直挂」是有价值的信息），
    历史页也无需 join。对照 database 模块的 `database_health` —— 它带 FK，
    删实例时会被历史行挡住报 IntegrityError。
    """
    __tablename__ = "agent_health_history"
    __table_args__ = (
        # 三条索引对应三种独立筛选路径
        Index("idx_agent_hist_endpoint_time", "endpoint_id", "checked_at"),
        Index("idx_agent_hist_status_time", "status", "checked_at"),
        Index("idx_agent_hist_checked", "checked_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    endpoint_code: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint_name: Mapped[str | None] = mapped_column(String(200))
    service_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(500))
    # scheduled（周期任务）/ manual（页面手点）
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'http'"))
    checked_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class AgentContainerAudit(Base):
    """容器操作审计。被拒绝的操作（refused）同样落库。

    容器清单本身**不落库**，始终实时读 Docker —— 新鲜度正是这个页面的意义。
    """
    __tablename__ = "agent_container_audit"
    __table_args__ = (
        Index("idx_agent_container_audit_container", "container_id"),
        Index("idx_agent_container_audit_created", "created_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    container_id: Mapped[str] = mapped_column(String(64), nullable=False)
    container_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default=text("''"))
    project_key: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'success'"))
    operator: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
