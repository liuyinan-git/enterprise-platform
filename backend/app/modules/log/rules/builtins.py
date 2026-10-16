from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.log.models import AnalysisRule

BUILTIN_RULES = [
    {
        "rule_code": "SSH_LOGIN_FAILURE_BURST",
        "rule_name": "SSH登录失败次数异常",
        "rule_type": "threshold",
        "severity": "high",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "login_failure",
            "window_seconds": 300,
            "group_by": ["source_ip", "device_id", "username"],
            "threshold": 10,
        },
    },
    {
        "rule_code": "TRAFFIC_BLOCK_BURST",
        "rule_name": "网络阻断事件激增",
        "rule_type": "threshold",
        "severity": "medium",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "traffic_block",
            "window_seconds": 300,
            "group_by": ["source_ip"],
            "threshold": 5,
        },
    },
    {
        "rule_code": "UPSTREAM_LLM_ERROR_BURST",
        "rule_name": "上游 LLM/B 服务调用失败",
        "rule_type": "threshold",
        "severity": "high",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "upstream_error",
            "window_seconds": 300,
            "group_by": ["device_id"],
            "threshold": 5,
        },
    },
    {
        "rule_code": "KAFKA_CONNECTION_ERROR",
        "rule_name": "Kafka 连接故障",
        "rule_type": "threshold",
        "severity": "high",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "kafka_error",
            "window_seconds": 300,
            "group_by": ["device_id"],
            "threshold": 3,
        },
    },
    {
        "rule_code": "REDIS_CONNECTION_ERROR",
        "rule_name": "Redis 连接失败",
        "rule_type": "threshold",
        "severity": "medium",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "redis_error",
            "window_seconds": 300,
            "group_by": ["device_id"],
            "threshold": 3,
        },
    },
    {
        "rule_code": "ERROR_BURST",
        "rule_name": "通用错误激增（兜底）",
        "rule_type": "threshold",
        "severity": "medium",
        "cooldown_seconds": 600,
        "rule_config": {
            "event_type": "error",
            "window_seconds": 300,
            "group_by": ["device_id"],
            "threshold": 10,
        },
    },
]


def seed_rules(db: Session) -> int:
    """写入内置规则（幂等：已存在则跳过）。返回新增条数。"""
    seeded = 0
    for spec in BUILTIN_RULES:
        exists = db.scalar(select(AnalysisRule.id).where(AnalysisRule.rule_code == spec["rule_code"]))
        if exists:
            continue
        db.add(AnalysisRule(
            rule_code=spec["rule_code"],
            rule_name=spec["rule_name"],
            rule_type=spec["rule_type"],
            severity=spec["severity"],
            cooldown_seconds=spec["cooldown_seconds"],
            enabled=True,
            rule_config=spec["rule_config"],
        ))
        seeded += 1
    if seeded:
        db.commit()
    return seeded
