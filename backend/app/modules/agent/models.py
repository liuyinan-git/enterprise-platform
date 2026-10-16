from datetime import datetime

from sqlalchemy import Boolean, Index, String, UniqueConstraint, text
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
