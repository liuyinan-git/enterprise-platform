"""网关模块 ORM 模型：Squid（squid_log 库）与 APISIX（apisix_monitor 库）。

说明：access_log（Squid 与 APISIX 各一张）无 DDL、仅做聚合查询，故不建 ORM 模型，
后续在 services 里用原生 SQL 读取。users 表随登录体系一起废弃。
"""

from datetime import datetime

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, JSON, MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.gateway.db import ApisixMonitorBase, SquidBase


# ---------------------------------------------------------------------------
# Squid（squid_log 库）
# ---------------------------------------------------------------------------

class SquidConfHistory(SquidBase):
    __tablename__ = "squid_conf_history"
    __table_args__ = (
        Index("idx_changed_at", "changed_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    username: Mapped[str | None] = mapped_column(String(64))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    conf_path: Mapped[str | None] = mapped_column(String(512))
    backup_path: Mapped[str | None] = mapped_column(String(512))
    lines_before: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    lines_after: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    size_before: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    size_after: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    diff: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    changed_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SquidDetailsFile(SquidBase):
    __tablename__ = "squid_details_files"
    __table_args__ = (
        UniqueConstraint("filename", name="uk_filename"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(191), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    lines: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    mtime: Mapped[datetime | None] = mapped_column(DATETIME)
    created_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class SquidDetailsHistory(SquidBase):
    __tablename__ = "squid_details_history"
    __table_args__ = (
        Index("idx_changed_at", "changed_at"),
        Index("idx_username", "username"),
        Index("idx_filename", "filename"),
        Index("idx_action", "action"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    username: Mapped[str | None] = mapped_column(String(64))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(191), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, server_default="update")
    backup_path: Mapped[str | None] = mapped_column(String(512))
    lines_before: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    lines_after: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    size_before: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    size_after: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    diff: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    changed_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SquidFileChangeAlert(SquidBase):
    __tablename__ = "squid_file_change_alert"
    __table_args__ = (
        Index("idx_detected_at", "detected_at"),
        Index("idx_is_read", "is_read"),
        Index("idx_file_type", "file_type"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    size_before: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    size_after: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    mtime_before: Mapped[datetime | None] = mapped_column(DATETIME)
    mtime_after: Mapped[datetime | None] = mapped_column(DATETIME)
    md5_before: Mapped[str | None] = mapped_column(String(32))
    md5_after: Mapped[str | None] = mapped_column(String(32))
    diff: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    detected_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))


class SquidWhitelistExpiry(SquidBase):
    __tablename__ = "squid_whitelist_expiries"
    __table_args__ = (
        UniqueConstraint("kind", "file_key", "domain", name="uk_kind_file_domain"),
        Index("idx_file_key", "file_key"),
        Index("idx_expire_at", "expire_at"),
        Index("idx_is_deleted", "is_deleted"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="domain")
    file_key: Mapped[str] = mapped_column(String(191), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False)
    synced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME)
    updated_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class SquidWhitelistChangelog(SquidBase):
    __tablename__ = "squid_whitelist_changelog"
    __table_args__ = (
        Index("idx_kind_changed_at", "kind", "changed_at"),
        Index("idx_file_key", "file_key"),
        Index("idx_action", "action"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="domain")
    user_id: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    username: Mapped[str | None] = mapped_column(String(64))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    file_key: Mapped[str | None] = mapped_column(String(191))
    file_name: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | list | None] = mapped_column(JSON)
    changed_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SquidWhitelistDomainHistory(SquidBase):
    __tablename__ = "squid_whitelist_domain_history"
    __table_args__ = (
        Index("idx_kind_file_domain", "kind", "file_key", "domain"),
        Index("idx_created_at", "created_at"),
        Index("idx_action", "action"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="domain")
    file_key: Mapped[str] = mapped_column(String(191), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    expire_at: Mapped[datetime | None] = mapped_column(DATETIME)
    prev_expire_at: Mapped[datetime | None] = mapped_column(DATETIME)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    user_id: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    username: Mapped[str | None] = mapped_column(String(64))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


# ---------------------------------------------------------------------------
# APISIX（apisix_monitor 库）
# ---------------------------------------------------------------------------

class ApisixRoute(ApisixMonitorBase):
    __tablename__ = "apisix_routes"
    __table_args__ = (
        Index("idx_route_name", "name"),
        Index("idx_route_service", "service_id"),
        Index("idx_route_upstream", "upstream_id"),
        Index("idx_route_sync", "sync_time"),
        {"mysql_engine": "InnoDB"},
    )
    source_node: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    uri: Mapped[str | None] = mapped_column(String(1024))
    uris: Mapped[str | None] = mapped_column(Text)
    methods: Mapped[str | None] = mapped_column(String(255))
    host: Mapped[str | None] = mapped_column(String(1024))
    hosts: Mapped[str | None] = mapped_column(Text)
    service_id: Mapped[str | None] = mapped_column(String(128))
    upstream_id: Mapped[str | None] = mapped_column(String(128))
    plugin_config_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default="1")
    plugins: Mapped[dict | list | None] = mapped_column(JSON)
    upstream: Mapped[dict | list | None] = mapped_column(JSON)
    vars: Mapped[dict | list | None] = mapped_column(JSON)
    labels: Mapped[dict | list | None] = mapped_column(JSON)
    priority: Mapped[int | None] = mapped_column(INTEGER)
    created_index: Mapped[int | None] = mapped_column(BIGINT)
    modified_index: Mapped[int | None] = mapped_column(BIGINT)
    raw: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    sync_time: Mapped[datetime] = mapped_column(DATETIME, nullable=False)


class ApisixService(ApisixMonitorBase):
    __tablename__ = "apisix_services"
    __table_args__ = (
        Index("idx_service_name", "name"),
        Index("idx_service_upstream", "upstream_id"),
        Index("idx_service_sync", "sync_time"),
        {"mysql_engine": "InnoDB"},
    )
    source_node: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    upstream_id: Mapped[str | None] = mapped_column(String(128))
    plugins: Mapped[dict | list | None] = mapped_column(JSON)
    upstream: Mapped[dict | list | None] = mapped_column(JSON)
    labels: Mapped[dict | list | None] = mapped_column(JSON)
    enable_websocket: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default="1")
    raw: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    sync_time: Mapped[datetime] = mapped_column(DATETIME, nullable=False)


class ApisixUpstream(ApisixMonitorBase):
    __tablename__ = "apisix_upstreams"
    __table_args__ = (
        Index("idx_upstream_name", "name"),
        Index("idx_upstream_sync", "sync_time"),
        {"mysql_engine": "InnoDB"},
    )
    source_node: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(64))
    scheme: Mapped[str | None] = mapped_column(String(32))
    nodes: Mapped[dict | list | None] = mapped_column(JSON)
    hash_on: Mapped[str | None] = mapped_column(String(64))
    hash_key: Mapped[str | None] = mapped_column(String(255))
    checks: Mapped[dict | list | None] = mapped_column(JSON)
    retries: Mapped[int | None] = mapped_column(INTEGER)
    timeout: Mapped[dict | list | None] = mapped_column(JSON)
    pass_host: Mapped[str | None] = mapped_column(String(64))
    raw: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    sync_time: Mapped[datetime] = mapped_column(DATETIME, nullable=False)


class ApisixSyncLog(ApisixMonitorBase):
    __tablename__ = "apisix_sync_log"
    __table_args__ = (
        Index("idx_log_node_time", "source_node", "started_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    source_node: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(32), nullable=False)
    fetched: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")
    saved: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1024))
    started_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False)
