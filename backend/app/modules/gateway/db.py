"""网关模块独立数据库连接：3 套库分布在不同服务器，各建 engine + session + Base。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class SquidBase(DeclarativeBase):
    """squid_log 库（Squid 代理日志/配置/白名单）。"""
    pass


class ApisixLogsBase(DeclarativeBase):
    """apisix_logs 库（APISIX 访问日志）。"""
    pass


class ApisixMonitorBase(DeclarativeBase):
    """apisix_monitor 库（APISIX 路由/服务/上游同步）。"""
    pass


def _make_engine(url: str):
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


squid_engine = _make_engine(settings.gateway_squid_db_url)
apisix_logs_engine = _make_engine(settings.gateway_apisix_logs_db_url)
apisix_monitor_engine = _make_engine(settings.gateway_apisix_monitor_db_url)

SquidSessionLocal = sessionmaker(bind=squid_engine, autoflush=False, autocommit=False, expire_on_commit=False)
ApisixLogsSessionLocal = sessionmaker(bind=apisix_logs_engine, autoflush=False, autocommit=False, expire_on_commit=False)
ApisixMonitorSessionLocal = sessionmaker(bind=apisix_monitor_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_squid_db():
    db = SquidSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_apisix_logs_db():
    db = ApisixLogsSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_apisix_monitor_db():
    db = ApisixMonitorSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """建缺失表（对应原 ensure_* 逻辑；已存在的表跳过）。"""
    SquidBase.metadata.create_all(squid_engine, checkfirst=True)
    ApisixLogsBase.metadata.create_all(apisix_logs_engine, checkfirst=True)
    ApisixMonitorBase.metadata.create_all(apisix_monitor_engine, checkfirst=True)
