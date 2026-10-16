from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DatabaseInstance(Base):
    """数据库实例台账（MySQL / PostgreSQL / Redis 等外部资产）。"""
    __tablename__ = "database_instance"
    __table_args__ = (
        UniqueConstraint("instance_code", name="uk_instance_code"),
        Index("idx_db_instance_type", "db_type"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    instance_code: Mapped[str] = mapped_column(String(100), nullable=False)
    instance_name: Mapped[str] = mapped_column(String(200), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    database_name: Mapped[str | None] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    environment: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    attributes: Mapped[dict | list | None] = mapped_column(JSON)
    last_check_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class DatabaseHealth(Base):
    """数据库健康检查记录（连接 / 慢查询 / 容量）。"""
    __tablename__ = "database_health"
    __table_args__ = (
        Index("idx_db_health_instance", "instance_id"),
        Index("idx_db_health_checked", "checked_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("database_instance.id"), nullable=False)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="connection")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    latency_ms: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    detail: Mapped[dict | list | None] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class DatabaseBackup(Base):
    """数据库备份记录（平台自运维）。"""
    __tablename__ = "database_backup"
    __table_args__ = (
        Index("idx_db_backup_instance", "instance_id"),
        Index("idx_db_backup_started", "started_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("database_instance.id"), nullable=False)
    backup_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="full")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="success")
    size: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class DatabaseContainerAudit(Base):
    """容器操作审计：启停 / 重启的留痕（含被拒的操作）。

    容器清单**实时读 Docker、不落库**（陈旧数据正是这个功能要避免的失败模式），
    但「改变宿主状态的操作」必须留痕，与 `agent_audit` 的做法一致。
    """
    __tablename__ = "database_container_audit"
    __table_args__ = (
        Index("idx_db_container_audit_container", "container_id"),
        Index("idx_db_container_audit_created", "created_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    container_id: Mapped[str] = mapped_column(String(64), nullable=False)
    container_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    managed_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False, server_default="success")
    operator: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
