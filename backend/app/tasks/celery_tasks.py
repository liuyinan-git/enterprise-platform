"""Celery 任务实现：Outbox 调度、批次标准化、规则分析、告警重试。"""

from datetime import datetime, timedelta, timezone
from app.core.timeutil import local_now

from sqlalchemy import or_, select, update

from app.db.session import SessionLocal
from app.models.log_models import AlertRecord, LogBatch, ProcessingTask
from app.services.analyze import _send_alert, analyze
from app.services.analyze_ai import run_ai_analysis
from app.services.cleanup import cleanup_retention
from app.services.device_health import detect_offline_devices
from app.services.normalize import process_pending_logs
from app.services.rule_suggest import generate_rule_suggestions
from app.tasks.celery_app import celery_app

MAX_BATCH_ATTEMPTS = 5


def _now() -> datetime:
    return local_now()


@celery_app.task(name="dispatch_outbox")
def dispatch_outbox() -> int:
    """把到期的待处理任务（Outbox）投递给 Worker 消费。返回本次投递条数。"""
    db = SessionLocal()
    dispatched = 0
    try:
        rows = db.scalars(
            select(ProcessingTask)
            .where(
                ProcessingTask.status == "pending",
                ProcessingTask.available_at <= _now(),
            )
            .order_by(ProcessingTask.id)
            .limit(50)
        ).all()
        for task in rows:
            claimed = db.execute(
                update(ProcessingTask)
                .where(ProcessingTask.id == task.id, ProcessingTask.status == "pending")
                .values(status="running", locked_at=_now())
            )
            if claimed.rowcount:
                db.commit()
                if task.task_type == "process_batch":
                    process_batch_task.delay(task.id)
                dispatched += 1
    finally:
        db.close()
    return dispatched


@celery_app.task(name="process_batch")
def process_batch_task(task_id: int) -> dict:
    """处理单个批次：标准化该批次的原始日志，并回写任务状态。"""
    db = SessionLocal()
    try:
        task = db.get(ProcessingTask, task_id)
        if task is None:
            return {"task": task_id, "status": "missing"}
        if task.task_type != "process_batch":
            task.status = "done"
            db.commit()
            return {"task": task_id, "status": "skipped"}

        batch = db.get(LogBatch, int(task.business_key)) if str(task.business_key).isdigit() else None
        if batch is None:
            task.status = "done"
            task.last_error = f"批次 {task.business_key} 不存在"
            db.commit()
            return {"task": task_id, "status": "missing_batch"}

        result = process_pending_logs(db, limit=100000, batch_id=batch.batch_id)
        if result["failed"] == 0:
            task.status = "done"
            task.last_error = None
        else:
            task.status = "failed"
            task.last_error = f"{result['failed']} 条解析失败"
        db.commit()
        return {"task": task_id, "batch": batch.batch_id, **result}
    except Exception as exc:
        db.rollback()
        task = db.get(ProcessingTask, task_id)
        if task is not None:
            task.attempt_count = (task.attempt_count or 0) + 1
            task.last_error = str(exc)[:1000]
            if task.attempt_count >= MAX_BATCH_ATTEMPTS:
                task.status = "failed"
            else:
                task.status = "pending"
                task.available_at = _now() + timedelta(seconds=min(30 * (2 ** task.attempt_count), 3600))
            db.commit()
        return {"task": task_id, "status": "error", "error": str(exc)[:200]}
    finally:
        db.close()


@celery_app.task(name="run_analysis")
def run_analysis() -> dict:
    """周期运行规则分析、事件聚合与告警。"""
    db = SessionLocal()
    try:
        return analyze(db)
    finally:
        db.close()


@celery_app.task(name="retry_alerts")
def retry_alerts() -> int:
    """重试到期仍未发送成功的告警。返回本次尝试条数。"""
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(AlertRecord)
            .where(
                AlertRecord.status.in_(["pending", "failed"]),
                or_(
                    AlertRecord.next_retry_at.is_(None),
                    AlertRecord.next_retry_at <= _now(),
                ),
            )
            .order_by(AlertRecord.id)
            .limit(50)
        ).all()
        for alert in rows:
            _send_alert(db, alert)
        db.commit()
        return len(rows)
    finally:
        db.close()


@celery_app.task(name="check_device_offline")
def check_device_offline_task() -> dict:
    """周期检测设备失联：生成/关闭「设备失联」事件与告警。"""
    db = SessionLocal()
    try:
        return detect_offline_devices(db)
    finally:
        db.close()


@celery_app.task(name="run_ai_analysis")
def run_ai_analysis_task() -> dict:
    """周期对候选安全事件做 AI 研判。"""
    db = SessionLocal()
    try:
        return run_ai_analysis(db)
    finally:
        db.close()


@celery_app.task(name="cleanup_retention")
def cleanup_retention_task() -> dict:
    """周期清理超保留期的旧日志。"""
    db = SessionLocal()
    try:
        return cleanup_retention(db)
    finally:
        db.close()


@celery_app.task(name="generate_rule_suggestions")
def generate_rule_suggestions_task() -> int:
    """周期基于日志基线分析生成规则建议。"""
    db = SessionLocal()
    try:
        return generate_rule_suggestions(db)
    finally:
        db.close()
