"""pytest 公共夹具：sqlite 内存库承载 MySQL 方言 ORM（外网无法连内网 MySQL）。

ORM 模型用 mysql 方言类型（DATETIME(3)/BIGINT UNSIGNED/ON UPDATE...），sqlite create_all 直接炸；
改为 CreateTable 编译到 sqlite 方言后正则改写 DDL，仅建 model 模块 7 张表。
"""

import re

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from app.modules.model.models import (
    ModelAlert,
    ModelConsumer,
    ModelConsumerRel,
    ModelHealth,
    ModelProvider,
    ModelRegistry,
    ModelUsage,
)

TABLES = [
    ModelProvider,
    ModelRegistry,
    ModelHealth,
    ModelUsage,
    ModelConsumer,
    ModelConsumerRel,
    ModelAlert,
]


def make_sqlite_ddl(table) -> str:
    """MySQL 方言 DDL → sqlite 兼容 DDL。"""
    ddl = str(CreateTable(table).compile(dialect=sqlite_dialect.dialect()))
    # sqlite 不认 ON UPDATE CURRENT_TIMESTAMP(n) 与 CURRENT_TIMESTAMP(n)
    ddl = re.sub(r" ON UPDATE CURRENT_TIMESTAMP\(\d+\)", "", ddl)
    ddl = re.sub(r"CURRENT_TIMESTAMP\(\d+\)", "CURRENT_TIMESTAMP", ddl)
    # sqlite 仅 INTEGER PRIMARY KEY 支持自增（rowid 别名）
    ddl = re.sub(r"\bid BIGINT NOT NULL,?", "id INTEGER NOT NULL PRIMARY KEY,", ddl)
    ddl = re.sub(r",\s*PRIMARY KEY \(id\)", "", ddl)
    return ddl


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(make_sqlite_ddl(table.__table__)))
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def provider(db):
    row = ModelProvider(provider_code="node1", provider_name="node1", base_url="http://172.28.110.11")
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def model(db, provider):
    row = ModelRegistry(
        model_code="qwen3-embedding-4b",
        provider_id=provider.id,
        model_name="Qwen3 Embedding 4B",
        service_type="embedding",
        endpoint_url="http://172.28.110.11:8033",
        probe_method="openai",
    )
    db.add(row)
    db.commit()
    return row
