"""日志数据清理：手动「还原」清空 + 按保留期定期清理旧数据。"""

from datetime import datetime, timedelta, timezone
from app.core.timeutil import local_now

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.log.models import (
    AlertRecord,
    LogBatch,
    LogEvent,
    LogRaw,
    ProcessingTask,
    SecurityEvent,
    SecurityEventLog,
)

# 单次保留期清理最多处理的标准化日志条数，避免首跑长时间锁表；每小时跑一次逐批追平。
_RETENTION_CHUNK = 5000


def _now() -> datetime:
    return local_now()


def clear_all_logs(db: Session) -> dict:
    """还原：清空日志、安全事件与告警（保留设备/规则/企业微信/附件配置）。

    按外键安全顺序（子→父）删除，返回各表删除计数。
    """
    counts = {
        "security_event_log": db.execute(delete(SecurityEventLog)).rowcount,
        "alert_record": db.execute(delete(AlertRecord)).rowcount,
        "security_event": db.execute(delete(SecurityEvent)).rowcount,
        "log_event": db.execute(delete(LogEvent)).rowcount,
        "log_raw": db.execute(delete(LogRaw)).rowcount,
        "log_batch": db.execute(delete(LogBatch)).rowcount,
        "processing_task": db.execute(delete(ProcessingTask)).rowcount,
    }
    db.commit()
    return counts


def cleanup_retention(db: Session) -> dict:
    """按保留期清理旧日志。

    时间基准用「入库时间」而非日志自身时间戳（event_time 可能上报历史/未来时间），
    原始日志用 received_at，标准化日志用 created_at。
    策略：无事件的原始日志超 raw 保留期即删；有事件的原始日志随其事件超 event 保留期后一并删，
    保证 log_event → log_raw 不产生孤儿行。
    """
    now = _now()
    raw_cutoff = now - timedelta(days=settings.raw_log_retention_days)
    event_cutoff = now - timedelta(days=settings.event_retention_days)

    # 1) 超 raw 保留期且未标准化（无对应事件）的原始日志
    raw_orphan_deleted = db.execute(
        delete(LogRaw)
        .where(
            LogRaw.received_at < raw_cutoff,
            ~exists().where(LogEvent.raw_log_id == LogRaw.id),
        )
    ).rowcount

    # 2) 超 event 保留期的标准化日志：先物化 id（含 raw_log_id），再删关联 join、事件、原始日志
    old_events = db.execute(
        select(LogEvent.id, LogEvent.raw_log_id)
        .where(LogEvent.created_at < event_cutoff)
        .limit(_RETENTION_CHUNK)
    ).all()
    event_ids = [row.id for row in old_events]
    raw_ids = [row.raw_log_id for row in old_events]

    join_deleted = 0
    event_deleted = 0
    raw_with_event_deleted = 0
    if event_ids:
        join_deleted = db.execute(
            delete(SecurityEventLog).where(SecurityEventLog.log_event_id.in_(event_ids))
        ).rowcount
        event_deleted = db.execute(delete(LogEvent).where(LogEvent.id.in_(event_ids))).rowcount
    if raw_ids:
        raw_with_event_deleted = db.execute(
            delete(LogRaw).where(LogRaw.id.in_(raw_ids))
        ).rowcount

    # 3) 超 event 保留期的批次与处理任务元数据（此时其下原始日志已清理，无残留引用）
    batch_deleted = db.execute(delete(LogBatch).where(LogBatch.received_at < event_cutoff)).rowcount
    task_deleted = db.execute(
        delete(ProcessingTask).where(ProcessingTask.created_at < event_cutoff)
    ).rowcount

    db.commit()
    return {
        "raw_orphan_deleted": raw_orphan_deleted,
        "raw_with_event_deleted": raw_with_event_deleted,
        "event_deleted": event_deleted,
        "event_join_deleted": join_deleted,
        "batch_deleted": batch_deleted,
        "task_deleted": task_deleted,
    }
