from datetime import datetime, timedelta, timezone
from app.core.timeutil import local_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.log_models import AnalysisRule, LogEvent


def _now() -> datetime:
    return local_now()


def evaluate_threshold_rule(db: Session, rule: AnalysisRule) -> list[dict]:
    """时间窗口统计规则：统计窗口内某 event_type 的条数，按 group_by 分组，超阈值产出发现。"""
    config = rule.rule_config or {}
    event_type = config.get("event_type")
    if not event_type:
        return []

    window_seconds = int(config.get("window_seconds", 300))
    threshold = int(config.get("threshold", 10))
    group_by = config.get("group_by") or []

    window_start = _now() - timedelta(seconds=window_seconds)
    rows = db.scalars(
        select(LogEvent).where(
            LogEvent.event_type == event_type,
            LogEvent.event_time >= window_start,
        )
    ).all()

    groups: dict[tuple, list[LogEvent]] = {}
    for row in rows:
        key = tuple(
            "" if getattr(row, field, None) is None else str(getattr(row, field))
            for field in group_by
        )
        groups.setdefault(key, []).append(row)

    findings = []
    for key, group in groups.items():
        if len(group) >= threshold:
            first = group[0]
            findings.append({
                "rule_code": rule.rule_code,
                "group_key": "|".join(key),
                "count": len(group),
                "severity": rule.severity,
                "event_ids": [g.id for g in group],
                "source_ip": first.source_ip,
                "device_id": first.device_id,
            })
    return findings


def evaluate_rule(db: Session, rule: AnalysisRule) -> list[dict]:
    """按规则类型分发。首版仅实现 threshold。"""
    if rule.rule_type == "threshold":
        return evaluate_threshold_rule(db, rule)
    return []
