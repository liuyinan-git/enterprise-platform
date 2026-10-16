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
    """模型注册台账：关联供应商，含健康状态。"""
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
    version: Mapped[str | None] = mapped_column(String(50))
    context_window: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    parameters: Mapped[dict | list | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    last_check_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


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
