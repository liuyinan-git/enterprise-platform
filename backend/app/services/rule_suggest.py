"""自动规则建议：基于日志基线分析生成候选规则（默认停用，待人工采纳）。"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import local_now
from app.models.log_models import LogEvent, RuleSuggestion

# 不为其生成建议的事件类型（未知类型范围太泛，无告警价值）
EXCLUDE_EVENT_TYPES = ["unknown"]

# 各 event_type 的默认建议风险等级
DEFAULT_SEVERITY = {
    "kafka_error": "high",
    "upstream_error": "high",
    "login_failure": "high",
    "traffic_block": "high",
    "redis_error": "medium",
    "error": "medium",
    "ssh_event": "medium",
}

BASELINE_DAYS = 7       # 统计最近多少天
WINDOW_SECONDS = 3600   # 建议规则的时间窗口（1 小时）
THRESHOLD_FACTOR = 1.5  # 阈值 = 每小时峰值次数 * 系数
THRESHOLD_FLOOR = 3     # 阈值下限
MIN_TOTAL = 10          # 窗口内总次数低于此不生成建议


def _hourly_counts(db: Session, since) -> dict[str, list[int]]:
    """按 event_type 统计每小时条数。返回 {event_type: [每小时计数...]}。"""
    rows = db.execute(
        select(
            LogEvent.event_type,
            func.date_format(LogEvent.event_time, "%Y-%m-%d %H"),
            func.count(LogEvent.id),
        )
        .where(LogEvent.event_time >= since, LogEvent.event_type.notin_(EXCLUDE_EVENT_TYPES))
        .group_by(LogEvent.event_type, func.date_format(LogEvent.event_time, "%Y-%m-%d %H"))
    ).all()
    data: dict[str, list[int]] = {}
    for event_type, _hour, cnt in rows:
        data.setdefault(event_type, []).append(int(cnt))
    return data


def generate_rule_suggestions(db: Session, baseline_days: int = BASELINE_DAYS) -> int:
    """扫描基线，为每个有意义的 event_type 生成/更新一条规则建议。返回本次更新的建议条数。"""
    since = local_now() - timedelta(days=baseline_days)
    per_type = _hourly_counts(db, since)

    updated = 0
    for event_type, hourly in per_type.items():
        total = sum(hourly)
        if total < MIN_TOTAL:
            continue
        peak = max(hourly)
        threshold = max(int(peak * THRESHOLD_FACTOR) + 1, THRESHOLD_FLOOR)

        existing = db.scalar(select(RuleSuggestion).where(RuleSuggestion.event_type == event_type))
        if existing is None:
            existing = RuleSuggestion(event_type=event_type)
            db.add(existing)
        # 已人工采纳/忽略的建议不再覆盖
        if existing.status in ("accepted", "ignored"):
            continue

        existing.rule_name = f"{event_type} 频率异常（自动建议）"
        existing.severity = DEFAULT_SEVERITY.get(event_type, "medium")
        existing.threshold = threshold
        existing.window_seconds = WINDOW_SECONDS
        existing.group_by = ["device_id"]
        existing.baseline_stats = {
            "days": baseline_days,
            "total": total,
            "hours_active": len(hourly),
            "peak_per_hour": peak,
            "avg_per_hour": round(total / len(hourly), 2) if hourly else 0,
        }
        existing.reason = (
            f"近 {baseline_days} 天出现 {total} 次（峰值每小时 {peak} 次）；"
            f"建议窗口 {WINDOW_SECONDS}s、阈值 {threshold}"
        )
        existing.status = "pending"
        updated += 1

    if updated:
        db.commit()
    return updated
