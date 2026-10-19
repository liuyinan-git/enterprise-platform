from datetime import datetime
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, JSON, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class DeviceRegistry(Base):
    __tablename__ = "device_registry"
    __table_args__ = (
        UniqueConstraint("device_id", name="uk_device_id"),
        Index("idx_device_type", "device_type"),
        Index("idx_device_last_seen", "last_seen_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    environment: Mapped[str | None] = mapped_column(String(50))
    criticality: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    expected_interval_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="900")
    touser: Mapped[str | None] = mapped_column(String(500))
    last_seen_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    attributes: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class LogBatch(Base):
    __tablename__ = "log_batch"
    __table_args__ = (
        UniqueConstraint("source_id", "batch_id", name="uk_batch_source"),
        Index("idx_batch_received", "received_at"),
        Index("idx_batch_status", "status"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    received_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    accepted_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    rejected_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="accepted")
    error_summary: Mapped[dict | list | None] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    processing_started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    processing_finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class LogRaw(Base):
    __tablename__ = "log_raw"
    __table_args__ = (
        UniqueConstraint("source_id", "event_id", name="uk_source_event"),
        Index("idx_raw_batch", "batch_id"),
        Index("idx_raw_device_time", "device_id", "event_time"),
        Index("idx_raw_received", "received_at"),
        Index("idx_raw_status", "process_status"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(200))
    device_id: Mapped[str | None] = mapped_column(String(100))
    event_time: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    received_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    format_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="text")
    raw_message: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    raw_payload: Mapped[dict | list | None] = mapped_column(JSON)
    process_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    process_error: Mapped[str | None] = mapped_column(String(1000))
    retry_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    processed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))


class ProcessingTask(Base):
    __tablename__ = "processing_task"
    __table_args__ = (
        UniqueConstraint("task_type", "business_key", name="uk_task_business"),
        Index("idx_task_dispatch", "status", "available_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    business_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    locked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class LogEvent(Base):
    __tablename__ = "log_event"
    __table_args__ = (
        UniqueConstraint("raw_log_id", name="uk_event_raw"),
        Index("idx_event_time_severity", "event_time", "severity"),
        Index("idx_event_time_id", "event_time", "id"),
        Index("idx_event_device_time", "device_id", "event_time"),
        Index("idx_event_type_time", "event_type", "event_time"),
        Index("idx_event_source_time", "source_ip", "event_time"),
        Index("idx_event_category_time", "event_category", "event_time"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    raw_log_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("log_raw.id"), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(100))
    hostname: Mapped[str | None] = mapped_column(String(255))
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_category: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="info")
    security_label: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unknown")
    source_ip: Mapped[str | None] = mapped_column(String(45))
    dest_ip: Mapped[str | None] = mapped_column(String(45))
    source_port: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    dest_port: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    username: Mapped[str | None] = mapped_column(String(255))
    process_name: Mapped[str | None] = mapped_column(String(255))
    event_time: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    normalized_data: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class AnalysisRule(Base):
    __tablename__ = "analysis_rule"
    __table_args__ = (
        UniqueConstraint("rule_code", name="uk_rule_code"),
        Index("idx_rule_enabled", "enabled"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="threshold")
    device_types: Mapped[dict | list | None] = mapped_column(JSON)
    rule_config: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    cooldown_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="600")
    touser: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class SecurityEvent(Base):
    __tablename__ = "security_event"
    __table_args__ = (
        UniqueConstraint("event_no", name="uk_event_no"),
        UniqueConstraint("fingerprint", name="uk_event_fingerprint"),
        Index("idx_security_status_severity", "status", "severity"),
        Index("idx_security_last_seen", "last_seen_at"),
        Index("idx_security_rule", "rule_code"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    event_no: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_code: Mapped[str | None] = mapped_column(String(100))
    event_title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="open")
    source_ip: Mapped[str | None] = mapped_column(String(45))
    device_id: Mapped[str | None] = mapped_column(String(100))
    first_seen_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="1")
    summary: Mapped[str | None] = mapped_column(Text)
    ai_analysis: Mapped[dict | list | None] = mapped_column(JSON)
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class SecurityEventLog(Base):
    __tablename__ = "security_event_log"
    __table_args__ = (
        Index("idx_relation_log", "log_event_id"),
        {"mysql_engine": "InnoDB"},
    )
    security_event_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("security_event.id"), primary_key=True)
    log_event_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("log_event.id"), primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="evidence")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))


class AlertRecord(Base):
    __tablename__ = "alert_record"
    __table_args__ = (
        UniqueConstraint("alert_no", name="uk_alert_no"),
        Index("idx_alert_status_retry", "status", "next_retry_at"),
        Index("idx_alert_event", "security_event_id", "created_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    alert_no: Mapped[str] = mapped_column(String(64), nullable=False)
    security_event_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("security_event.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, server_default="wecom")
    receiver_key: Mapped[str | None] = mapped_column(String(200))
    message_content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class RuleSuggestion(Base):
    """自动规则建议：基线分析产出的候选规则（默认停用，待人工采纳）。"""
    __tablename__ = "rule_suggestion"
    __table_args__ = (
        UniqueConstraint("event_type", name="uk_suggestion_event"),
        Index("idx_suggestion_status", "status"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    threshold: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="3600")
    group_by: Mapped[dict | list | None] = mapped_column(JSON)
    baseline_stats: Mapped[dict | list | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))
