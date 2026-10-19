import re
from datetime import datetime, timezone
from app.core.timeutil import local_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.log.models import DeviceRegistry, LogEvent, LogRaw
from app.modules.log.parsers import PARSERS, NormalizedEvent

# 关键词 → (event_category, event_type, severity, security_label)
# 顺序即优先级，首个命中生效；结构化解析已给出 event_type 时不再覆盖。
KEYWORD_RULES: list[tuple[re.Pattern, tuple[str, str, str, str]]] = [
    (re.compile(r"authentication failed|login fail|failed password|login_failure", re.I),
     ("authentication", "login_failure", "warning", "suspicious")),
    (re.compile(r"login success|logon success|accepted password", re.I),
     ("authentication", "login_success", "info", "normal")),
    (re.compile(r"\bdeny\b|\bdrop\b|\bblock\b|denied", re.I),
     ("network", "traffic_block", "warning", "suspicious")),
    (re.compile(r"\baccept\b|allowed", re.I),
     ("network", "traffic_allow", "info", "normal")),
    (re.compile(r"\bssh\b", re.I),
     ("authentication", "ssh_event", "info", "normal")),
    # 基础设施 / 上游服务故障分类（放在通用 error 之前，避免被其吞掉）
    (re.compile(r"KafkaConnectionError|coordinator dead|Unable connect to node|Failed fetch messages|Unable to (?:update|request) metadata|Heartbeat.*(?:fail|expired)", re.I),
     ("infrastructure", "kafka_error", "error", "normal")),
    (re.compile(r"redis\.exceptions|:6380", re.I),
     ("infrastructure", "redis_error", "error", "normal")),
    (re.compile(r"BSideError|platform-llm-service", re.I),
     ("upstream", "upstream_error", "error", "normal")),
    (re.compile(r"fail|error|exception|critical", re.I),
     ("system", "error", "error", "suspicious")),
]


def classify(event: NormalizedEvent, raw_message: str) -> None:
    """规则映射：对未能确定类别/类型的日志做关键词兜底分类。"""
    if event.event_type != "unknown":
        return
    for pattern, (category, etype, severity, label) in KEYWORD_RULES:
        if pattern.search(raw_message):
            event.event_category = category
            event.event_type = etype
            event.severity = severity
            event.security_label = label
            return


# 正文日志级别 → severity 映射（兜底：结构化字段未提供 severity 时按级别前缀补）
_LEVEL_TO_SEVERITY = {
    "DEBUG": "debug", "TRACE": "debug",
    "INFO": "info", "NOTICE": "notice",
    "WARNING": "warning", "WARN": "warning",
    "ERROR": "error", "ERR": "error",
    "CRITICAL": "critical", "CRIT": "critical", "FATAL": "critical",
}

# 典型应用日志头：<可选时间戳> <级别> [<模块名>]
_BODY_HEAD_RE = re.compile(
    r"^\s*(?:(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+)?"
    r"(?P<level>DEBUG|TRACE|INFO|NOTICE|WARNING|WARN|ERROR|ERR|CRITICAL|CRIT|FATAL)\s+"
    r"(?:\[(?P<module>[^\]]+)\]\s*)?",
    re.I,
)

SEVERITY_RANK = {"debug": 0, "info": 1, "notice": 2, "warning": 3, "error": 4, "critical": 5}


def canonical_severity(value: str | None) -> str:
    """把任意级别写法（结构化字段 / 配置阈值）归一到 SEVERITY_RANK 的键。

    ``warn``/``err``/``crit``/``fatal``/``trace`` 等别名经 ``_LEVEL_TO_SEVERITY`` 归一；
    无法识别时回落到 ``info``。
    """
    v = (value or "").strip().lower()
    if v in SEVERITY_RANK:
        return v
    return _LEVEL_TO_SEVERITY.get(v.upper(), "info")


def quick_severity(raw_message: str, payload: dict | None) -> str:
    """轻量级别判断（接入层过滤用，不跑完整解析）。

    优先级：结构化字段 severity/level/log_level → 正文头部级别前缀 → 默认 info。
    """
    if isinstance(payload, dict):
        for key in ("severity", "level", "log_level"):
            v = payload.get(key)
            if v:
                return canonical_severity(str(v))
    m = _BODY_HEAD_RE.match((raw_message or "").strip())
    if m and m.group("level"):
        return _LEVEL_TO_SEVERITY.get(m.group("level").upper(), "info")
    return "info"


def extract_body_fields(event: NormalizedEvent, raw_message: str, payload: dict | None) -> None:
    """从日志正文兜底提取：级别 → severity、[模块] → process_name、正文时间戳存入 normalized_data。

    仅在结构化字段未提供时才覆盖（severity 仍为默认 info、process_name 为空）。
    """
    m = _BODY_HEAD_RE.match((raw_message or "").strip())
    if m:
        level = m.group("level")
        if level and event.severity == "info":
            event.severity = _LEVEL_TO_SEVERITY.get(level.upper(), "info")
        module = m.group("module")
        if module and not event.process_name:
            event.process_name = module
        if m.group("ts"):
            merged = dict(event.normalized_data or {})
            merged["body_timestamp"] = m.group("ts")
            event.normalized_data = merged
            # 直接用正文时间戳作为事件时间（不做时区转换）
            try:
                event.event_time = datetime.fromisoformat(m.group("ts").replace(" ", "T"))
            except ValueError:
                pass
    elif isinstance(payload, dict) and payload.get("source") == "stderr" and event.severity == "info":
        # 无级别前缀时，stderr 输出按 error 兜底
        event.severity = "error"


def normalize_raw(raw_message: str, format_type: str, payload: dict | None) -> NormalizedEvent:
    """把一条原始日志标准化为 NormalizedEvent（解析 → 正文兜底 → 规则映射 → 未知兜底）。"""
    event: NormalizedEvent | None = None
    for parser in PARSERS:
        event = parser.parse(raw_message, payload, format_type)
        if event is not None:
            break
    if event is None:
        event = NormalizedEvent()
    extract_body_fields(event, raw_message, payload)
    classify(event, raw_message)
    return event


def process_pending_logs(db: Session, limit: int = 100, batch_id: str | None = None) -> dict:
    """处理一批 process_status=pending 的原始日志，标准化写入 log_event。可按 batch_id 过滤。"""
    stmt = select(LogRaw).where(LogRaw.process_status == "pending")
    if batch_id:
        stmt = stmt.where(LogRaw.batch_id == batch_id)
    rows = db.scalars(stmt.order_by(LogRaw.id).limit(limit)).all()

    # 设备类型兜底：日志未显式提供 device_type 时，用设备注册表里维护的类型
    device_ids = {r.device_id for r in rows if r.device_id}
    type_map: dict[str, str] = {}
    if device_ids:
        for d in db.scalars(select(DeviceRegistry).where(DeviceRegistry.device_id.in_(device_ids))).all():
            type_map[d.device_id] = d.device_type

    processed = 0
    failed = 0
    for raw in rows:
        # 幂等：该原始日志已生成过标准化事件则跳过
        if db.scalar(select(LogEvent.id).where(LogEvent.raw_log_id == raw.id)):
            raw.process_status = "processed"
            continue

        try:
            event = normalize_raw(raw.raw_message, raw.format_type, raw.raw_payload)
            if event.device_type == "other" and raw.device_id and type_map.get(raw.device_id, "other") != "other":
                event.device_type = type_map[raw.device_id]
            db.add(LogEvent(
                raw_log_id=raw.id,
                device_id=raw.device_id,
                hostname=event.hostname,
                device_type=event.device_type,
                event_category=event.event_category,
                event_type=event.event_type,
                severity=event.severity,
                security_label=event.security_label,
                source_ip=event.source_ip,
                dest_ip=event.dest_ip,
                source_port=event.source_port,
                dest_port=event.dest_port,
                username=event.username,
                process_name=event.process_name,
                event_time=event.event_time if event.event_time is not None else raw.event_time,
                normalized_data=event.normalized_data,
            ))
            raw.process_status = "processed"
            raw.processed_at = local_now()
            processed += 1
        except Exception as exc:  # 解析/落库异常，记录失败与重试次数
            raw.process_status = "failed"
            raw.process_error = str(exc)[:1000]
            raw.retry_count = (raw.retry_count or 0) + 1
            failed += 1

    db.commit()
    return {"processed": processed, "failed": failed}
