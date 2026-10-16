from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ModelProvider(Base):
    """模型供应商台账（DeepSeek / Ollama / OpenAI 兼容等）。"""
    __tablename__ = "model_provider"
    __table_args__ = (
        UniqueConstraint("provider_code", name="uk_provider_code"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="openai")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    api_key: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class ModelRegistry(Base):
    """模型注册台账：关联供应商，含健康状态。

    面向自建模型服务（vLLM 等）：
    - model_code 建议用容器名（内网盘点唯一标识）
    - endpoint_url 为服务根地址（如 http://172.28.110.11:8033，不含 /v1）
    - probe_method 决定探测方式：openai=GET /v1/models / tcp=socket 探活 / http=GET /（任意响应即存活）/ none=跳过
    """
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_code", name="uk_model_code"),
        Index("idx_model_provider", "provider_id"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    model_code: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_provider.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="chat")
    endpoint_url: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    probe_method: Mapped[str] = mapped_column(String(24), nullable=False, server_default="openai")
    engine: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[str | None] = mapped_column(String(50))
    context_window: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    parameters: Mapped[dict | list | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    last_check_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    # /metrics 用量采集：上次计数器值（差值计算）；metrics_metric 可按模型覆盖全局默认指标名
    last_metrics_value: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    metrics_metric: Mapped[str | None] = mapped_column(String(200))
    # 告警状态机：连续探测失败计数（恢复清零），达到阈值触发企业微信告警
    consecutive_failures: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class ModelHealth(Base):
    """模型服务健康检查记录（对齐 database_health 模式，支撑趋势与状态灯）。"""
    __tablename__ = "model_health"
    __table_args__ = (
        Index("idx_model_health_model", "model_id"),
        Index("idx_model_health_checked", "checked_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_registry.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    latency_ms: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    message: Mapped[str | None] = mapped_column(String(500))
    checked_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class ModelUsage(Base):
    """模型调用用量统计（按模型 + 天聚合）。"""
    __tablename__ = "model_usage"
    __table_args__ = (
        UniqueConstraint("model_id", "recorded_day", name="uk_model_usage_day"),
        Index("idx_model_usage_day", "recorded_day"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_registry.id"), nullable=False)
    call_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    recorded_day: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class ModelConsumer(Base):
    """模型调用方台账：谁在调哪些模型（支撑下线影响面分析）。

    - identity_type: external_ip（外部服务器）/ container（本机容器）/ external_system（外部系统）
    - identifier: IP 或容器名（可索引）；MCP 网关多节点各登记一条，备注注明归属
    """
    __tablename__ = "model_consumer"
    __table_args__ = (
        UniqueConstraint("consumer_code", name="uk_consumer_code"),
        Index("idx_consumer_identifier", "identifier"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    consumer_code: Mapped[str] = mapped_column(String(100), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="external_ip")
    identifier: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    contact: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    remark: Mapped[str | None] = mapped_column(String(500))
    evidence: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class ModelConsumerRel(Base):
    """调用方-模型多对多关联（中间表，支撑按模型反查调用方）。"""
    __tablename__ = "model_consumer_rel"
    __table_args__ = (
        UniqueConstraint("consumer_id", "model_id", name="uk_consumer_model"),
        Index("idx_rel_model", "model_id"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    consumer_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_consumer.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_registry.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class ModelAlert(Base):
    """模型服务告警记录（对齐 log 模块 AlertRecord 模式的模块内轻量版）。

    - alert_type: failure（连续探测失败）/ recovery（恢复通知）
    - status: pending（待发送/未配置）/ sent / failed（可重试，指数退避）
    - resolved_at 非空表示故障已恢复（仅 failure 类型使用）
    """
    __tablename__ = "model_alert"
    __table_args__ = (
        UniqueConstraint("alert_no", name="uk_model_alert_no"),
        Index("idx_malert_model", "model_id", "created_at"),
        Index("idx_malert_status_retry", "status", "next_retry_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    alert_no: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("model_registry.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="failure")
    channel: Mapped[str] = mapped_column(String(24), nullable=False, server_default="wecom")
    receiver_key: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    message_content: Mapped[str] = mapped_column(String(4000), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))
