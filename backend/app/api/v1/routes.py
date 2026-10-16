import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from app.core.timeutil import local_now
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.log_models import (
    AlertRecord,
    AnalysisRule,
    Attachment,
    DeviceRegistry,
    LogBatch,
    LogEvent,
    LogRaw,
    ProcessingTask,
    RuleSuggestion,
    SecurityEvent,
    SecurityEventLog,
)
from app.notifications.wecom import send_markdown
from app.schemas.logs import LogBatchIn
from app.schemas.management import DeviceIn, EventPatch, RuleIn, RuleUpdate, WecomConfigIn, WecomTestIn
from app.services.ingest import ingest_batch, ingest_fluentbit, parse_fluentbit_body, parse_msgpack_body
from app.services.analyze_ai import analyze_event_ai
from app.services.cleanup import clear_all_logs
from app.services.device_health import grace_seconds
from app.services.wecom_config import get_or_create_config, mask_secret

router = APIRouter(prefix="/api/v1", tags=["log-ingestion"])


def require_collector_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configured = settings.collector_api_key
    if not configured or configured.startswith("CHANGE_ME"):
        raise HTTPException(status_code=503, detail="Collector API key is not configured.")
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@router.post("/logs/batch", status_code=status.HTTP_202_ACCEPTED)
def receive_log_batch(
    payload: LogBatchIn,
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    try:
        data = ingest_batch(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "accepted", "data": data}


@router.post("/ingest/fluentbit")
async def ingest_fluentbit_endpoint(
    request: Request,
    x_source_id: str | None = Header(default=None, alias="X-Source-Id"),
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    """接收 Fluent Bit HTTP output 上报的日志（JSON 数组 / 单对象 / NDJSON / msgpack）。"""
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "msgpack" in content_type.lower():
        records = parse_msgpack_body(body)
    else:
        records = parse_fluentbit_body(body)
    source_id = x_source_id or "fluentbit"
    try:
        data = ingest_fluentbit(db, records, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "accepted", "data": data}


@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: str,
    source_id: str = Query(min_length=1, max_length=100),
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    batch = db.scalar(select(LogBatch).where(
        LogBatch.batch_id == batch_id,
        LogBatch.source_id == source_id,
    ))
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "code": 0,
        "message": "success",
        "data": {
            "batch_id": batch.batch_id,
            "source_id": batch.source_id,
            "received": batch.received_count,
            "accepted": batch.accepted_count,
            "rejected": batch.rejected_count,
            "status": batch.status,
            "received_at": batch.received_at.isoformat() if batch.received_at else None,
        },
    }


@router.get("/batches")
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """管理端：批次列表（按接收时间倒序，分页）。"""
    total = db.scalar(select(func.count(LogBatch.id))) or 0
    rows = db.scalars(
        select(LogBatch)
        .order_by(desc(LogBatch.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "batch_id": b.batch_id,
            "source_id": b.source_id,
            "received": b.received_count,
            "accepted": b.accepted_count,
            "rejected": b.rejected_count,
            "status": b.status,
            "received_at": b.received_at.isoformat() if b.received_at else None,
        }
        for b in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/collectors")
def list_collectors(
    offline_after_seconds: int = Query(900, ge=1, le=86400),
    db: Session = Depends(get_db),
):
    """管理端：采集端列表（按 source_id 聚合批次与日志统计，状态依据最近上报时间判定）。"""
    batch_rows = db.execute(
        select(
            LogBatch.source_id,
            func.count(LogBatch.id),
            func.coalesce(func.sum(LogBatch.received_count), 0),
            func.coalesce(func.sum(LogBatch.accepted_count), 0),
            func.coalesce(func.sum(LogBatch.rejected_count), 0),
            func.max(LogBatch.received_at),
        ).group_by(LogBatch.source_id)
    ).all()

    raw_rows = db.execute(
        select(
            LogRaw.source_id,
            func.count(LogRaw.id),
            func.count(func.distinct(LogRaw.device_id)),
        ).group_by(LogRaw.source_id)
    ).all()
    raw_map = {r.source_id: r for r in raw_rows}

    now = local_now()
    items = []
    for row in batch_rows:
        source_id, batch_count, received, accepted, rejected, last_seen = row
        raw = raw_map.get(source_id)
        online = last_seen is not None and (now - last_seen).total_seconds() <= offline_after_seconds
        items.append({
            "source_id": source_id,
            "batch_count": batch_count,
            "log_count": int(raw[1]) if raw else 0,
            "device_count": int(raw[2]) if raw else 0,
            "received": int(received),
            "accepted": int(accepted),
            "rejected": int(rejected),
            "last_seen_at": last_seen.isoformat() if last_seen else None,
            "status": "online" if online else "offline",
        })
    items.sort(key=lambda x: x["last_seen_at"] or "", reverse=True)
    return {"code": 0, "message": "success", "data": {"items": items, "total": len(items)}}


@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    device_type: str | None = Query(default=None),
    event_category: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    source_ip: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：标准化日志列表（分页 + 可选筛选）。"""
    stmt = select(LogEvent)
    if device_type:
        stmt = stmt.where(LogEvent.device_type == device_type)
    if event_category:
        stmt = stmt.where(LogEvent.event_category == event_category)
    if event_type:
        stmt = stmt.where(LogEvent.event_type == event_type)
    if severity:
        stmt = stmt.where(LogEvent.severity == severity)
    if source_ip:
        stmt = stmt.where(LogEvent.source_ip == source_ip)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(
            LogEvent.event_type.like(like),
            LogEvent.event_category.like(like),
            LogEvent.username.like(like),
            LogEvent.hostname.like(like),
        ))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(LogEvent.event_time), desc(LogEvent.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": e.id,
            "device_type": e.device_type,
            "device_id": e.device_id,
            "hostname": e.hostname,
            "event_category": e.event_category,
            "event_type": e.event_type,
            "severity": e.severity,
            "security_label": e.security_label,
            "source_ip": e.source_ip,
            "dest_ip": e.dest_ip,
            "username": e.username,
            "process_name": e.process_name,
            "event_time": e.event_time.isoformat() if e.event_time else None,
        }
        for e in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/logs/{log_id}")
def get_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
):
    """管理端：标准化日志详情（含关联的原始报文）。"""
    event = db.get(LogEvent, log_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Log event not found")
    raw = db.get(LogRaw, event.raw_log_id) if event.raw_log_id else None
    return {
        "code": 0,
        "message": "success",
        "data": {
            "id": event.id,
            "device_type": event.device_type,
            "device_id": event.device_id,
            "hostname": event.hostname,
            "event_category": event.event_category,
            "event_type": event.event_type,
            "severity": event.severity,
            "security_label": event.security_label,
            "source_ip": event.source_ip,
            "dest_ip": event.dest_ip,
            "source_port": event.source_port,
            "dest_port": event.dest_port,
            "username": event.username,
            "process_name": event.process_name,
            "event_time": event.event_time.isoformat() if event.event_time else None,
            "normalized_data": event.normalized_data,
            "raw": {
                "raw_message": raw.raw_message if raw else None,
                "raw_payload": raw.raw_payload if raw else None,
                "format_type": raw.format_type if raw else None,
                "source_id": raw.source_id if raw else None,
                "batch_id": raw.batch_id if raw else None,
                "received_at": raw.received_at.isoformat() if raw and raw.received_at else None,
            } if raw else None,
        },
    }


@router.get("/raw-logs")
def list_raw_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    source_id: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    process_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：原始日志列表（分页 + 可选筛选）。"""
    stmt = select(LogRaw)
    if source_id:
        stmt = stmt.where(LogRaw.source_id == source_id)
    if device_id:
        stmt = stmt.where(LogRaw.device_id == device_id)
    if process_status:
        stmt = stmt.where(LogRaw.process_status == process_status)
    if keyword:
        stmt = stmt.where(LogRaw.raw_message.like(f"%{keyword}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(LogRaw.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "batch_id": r.batch_id,
            "source_id": r.source_id,
            "event_id": r.event_id,
            "device_id": r.device_id,
            "event_time": r.event_time.isoformat() if r.event_time else None,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "format_type": r.format_type,
            "raw_message": r.raw_message,
            "process_status": r.process_status,
        }
        for r in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# ---------------------------------------------------------------------------
# 安全事件
# ---------------------------------------------------------------------------

def _serialize_event(e: SecurityEvent) -> dict:
    return {
        "id": e.id,
        "event_no": e.event_no,
        "rule_code": e.rule_code,
        "event_title": e.event_title,
        "severity": e.severity,
        "status": e.status,
        "source_ip": e.source_ip,
        "device_id": e.device_id,
        "occurrence_count": e.occurrence_count,
        "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
        "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
        "assigned_to": e.assigned_to,
        "resolution_note": e.resolution_note,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "summary": e.summary,
    }


@router.get("/events")
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：安全事件列表（分页 + 按状态/级别筛选）。"""
    stmt = select(SecurityEvent)
    if status:
        stmt = stmt.where(SecurityEvent.status == status)
    if severity:
        stmt = stmt.where(SecurityEvent.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(SecurityEvent.last_seen_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"code": 0, "message": "success", "data": {"items": [_serialize_event(e) for e in rows], "total": total, "page": page, "page_size": page_size}}


@router.get("/events/{event_no}")
def get_event(
    event_no: str,
    db: Session = Depends(get_db),
):
    """管理端：安全事件详情，含关联证据日志与告警记录。"""
    event = db.scalar(select(SecurityEvent).where(SecurityEvent.event_no == event_no))
    if event is None:
        raise HTTPException(status_code=404, detail="Security event not found")

    evidence = db.scalars(
        select(LogEvent)
        .join(SecurityEventLog, SecurityEventLog.log_event_id == LogEvent.id)
        .where(SecurityEventLog.security_event_id == event.id)
        .order_by(desc(LogEvent.event_time), desc(LogEvent.id))
        .limit(200)
    ).all()
    evidence_items = [
        {
            "id": e.id,
            "event_time": e.event_time.isoformat() if e.event_time else None,
            "device_type": e.device_type,
            "device_id": e.device_id,
            "event_category": e.event_category,
            "event_type": e.event_type,
            "severity": e.severity,
            "source_ip": e.source_ip,
            "username": e.username,
        }
        for e in evidence
    ]

    alerts = db.scalars(
        select(AlertRecord).where(AlertRecord.security_event_id == event.id).order_by(desc(AlertRecord.created_at))
    ).all()
    alert_items = [
        {
            "alert_no": a.alert_no,
            "channel": a.channel,
            "status": a.status,
            "attempt_count": a.attempt_count,
            "last_error": a.last_error,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]

    data = _serialize_event(event)
    data["evidence"] = evidence_items
    data["alerts"] = alert_items
    data["ai_analysis"] = event.ai_analysis
    return {"code": 0, "message": "success", "data": data}


@router.patch("/events/{event_no}")
def patch_event(
    event_no: str,
    payload: EventPatch,
    db: Session = Depends(get_db),
):
    """管理端：确认、分派或关闭安全事件。"""
    event = db.scalar(select(SecurityEvent).where(SecurityEvent.event_no == event_no))
    if event is None:
        raise HTTPException(status_code=404, detail="Security event not found")

    if payload.status is not None:
        event.status = payload.status
        if payload.status == "closed" and event.resolved_at is None:
            event.resolved_at = local_now()
        elif payload.status in ("open", "confirmed") and event.resolved_at is not None:
            event.resolved_at = None
    if payload.assigned_to is not None:
        event.assigned_to = payload.assigned_to
    if payload.resolution_note is not None:
        event.resolution_note = payload.resolution_note
    db.commit()
    return {"code": 0, "message": "success", "data": _serialize_event(event)}


@router.post("/events/{event_no}/ai-analyze")
def ai_analyze_event(event_no: str, db: Session = Depends(get_db)):
    """管理端：手动触发单个安全事件的 AI 研判。"""
    if not settings.ai_enabled or not settings.ai_model:
        raise HTTPException(status_code=400, detail="AI 研判未启用或未配置模型")
    event = db.scalar(select(SecurityEvent).where(SecurityEvent.event_no == event_no))
    if event is None:
        raise HTTPException(status_code=404, detail="Security event not found")
    result = analyze_event_ai(db, event)
    return {"code": 0, "message": "success", "data": {"status": result["status"], "ai_analysis": event.ai_analysis}}


# ---------------------------------------------------------------------------
# 告警记录
# ---------------------------------------------------------------------------

@router.get("/alerts")
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：告警发送记录列表。"""
    stmt = select(AlertRecord)
    if status:
        stmt = stmt.where(AlertRecord.status == status)
    if channel:
        stmt = stmt.where(AlertRecord.channel == channel)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(AlertRecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": a.id,
            "alert_no": a.alert_no,
            "security_event_id": a.security_event_id,
            "channel": a.channel,
            "receiver_key": a.receiver_key,
            "status": a.status,
            "attempt_count": a.attempt_count,
            "last_error": a.last_error,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/alerts/{alert_no}/retry")
def retry_alert(
    alert_no: str,
    db: Session = Depends(get_db),
):
    """管理端：手动重试告警发送。"""
    alert = db.scalar(select(AlertRecord).where(AlertRecord.alert_no == alert_no))
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    cfg = get_or_create_config(db)
    if not cfg.enabled or not cfg.corpid or not cfg.corpsecret or not cfg.agentid or not cfg.touser:
        raise HTTPException(status_code=400, detail="企业微信未配置或未启用，无法发送")

    try:
        send_markdown(cfg.corpid, cfg.corpsecret, cfg.agentid, cfg.touser, alert.message_content, settings.wecom_timeout_seconds)
        alert.status = "sent"
        alert.sent_at = local_now()
        alert.last_error = None
        alert.next_retry_at = None
    except Exception as exc:
        alert.status = "failed"
        alert.last_error = str(exc)[:1000]
        alert.attempt_count = (alert.attempt_count or 0) + 1
    db.commit()
    return {
        "code": 0,
        "message": "success",
        "data": {
            "alert_no": alert.alert_no,
            "status": alert.status,
            "attempt_count": alert.attempt_count,
            "last_error": alert.last_error,
            "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
        },
    }


# ---------------------------------------------------------------------------
# 分析规则
# ---------------------------------------------------------------------------

def _serialize_rule(r: AnalysisRule) -> dict:
    return {
        "id": r.id,
        "rule_code": r.rule_code,
        "rule_name": r.rule_name,
        "description": r.description,
        "rule_type": r.rule_type,
        "severity": r.severity,
        "enabled": r.enabled,
        "cooldown_seconds": r.cooldown_seconds,
        "touser": r.touser,
        "rule_config": r.rule_config,
        "version": r.version,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    """管理端：分析规则列表。"""
    rows = db.scalars(select(AnalysisRule).order_by(AnalysisRule.id)).all()
    return {"code": 0, "message": "success", "data": {"items": [_serialize_rule(r) for r in rows], "total": len(rows)}}


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleIn,
    db: Session = Depends(get_db),
):
    """管理端：新增分析规则。"""
    exists = db.scalar(select(AnalysisRule.id).where(AnalysisRule.rule_code == payload.rule_code))
    if exists:
        raise HTTPException(status_code=409, detail=f"Rule code {payload.rule_code} already exists")
    rule = AnalysisRule(
        rule_code=payload.rule_code,
        rule_name=payload.rule_name,
        description=payload.description,
        rule_type=payload.rule_type,
        severity=payload.severity,
        enabled=payload.enabled,
        cooldown_seconds=payload.cooldown_seconds,
        touser=payload.touser,
        rule_config=payload.rule_config,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"code": 0, "message": "created", "data": _serialize_rule(rule)}


@router.put("/rules/{rule_code}")
def update_rule(
    rule_code: str,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
):
    """管理端：修改分析规则（启停、阈值、级别等）。"""
    rule = db.scalar(select(AnalysisRule).where(AnalysisRule.rule_code == rule_code))
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    if payload.rule_name is not None:
        rule.rule_name = payload.rule_name
    if payload.description is not None:
        rule.description = payload.description
    if payload.severity is not None:
        rule.severity = payload.severity
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.cooldown_seconds is not None:
        rule.cooldown_seconds = payload.cooldown_seconds
    if payload.touser is not None:
        rule.touser = payload.touser
    if payload.rule_config is not None:
        rule.rule_config = payload.rule_config
        rule.version = (rule.version or 1) + 1
    db.commit()
    db.refresh(rule)
    return {"code": 0, "message": "success", "data": _serialize_rule(rule)}


# ---------------------------------------------------------------------------
# 规则建议
# ---------------------------------------------------------------------------

def _serialize_suggestion(s: RuleSuggestion) -> dict:
    return {
        "id": s.id,
        "event_type": s.event_type,
        "rule_name": s.rule_name,
        "severity": s.severity,
        "threshold": s.threshold,
        "window_seconds": s.window_seconds,
        "group_by": s.group_by,
        "baseline_stats": s.baseline_stats,
        "reason": s.reason,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/rule-suggestions")
def list_rule_suggestions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：自动规则建议列表。"""
    stmt = select(RuleSuggestion).order_by(desc(RuleSuggestion.id))
    if status:
        stmt = stmt.where(RuleSuggestion.status == status)
    rows = db.scalars(stmt).all()
    return {"code": 0, "message": "success", "data": {"items": [_serialize_suggestion(s) for s in rows], "total": len(rows)}}


@router.post("/rule-suggestions/{suggestion_id}/accept")
def accept_rule_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """管理端：采纳建议 → 生成一条启用规则，并标记建议为 accepted。"""
    s = db.get(RuleSuggestion, suggestion_id)
    if s is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if s.status == "accepted":
        raise HTTPException(status_code=409, detail="该建议已采纳")

    base = f"AUTO_{s.event_type.upper()}"
    code = base
    n = 1
    while db.scalar(select(AnalysisRule.id).where(AnalysisRule.rule_code == code)):
        n += 1
        code = f"{base}_{n}"

    rule = AnalysisRule(
        rule_code=code,
        rule_name=s.rule_name,
        rule_type="threshold",
        severity=s.severity,
        enabled=True,
        cooldown_seconds=600,
        rule_config={
            "event_type": s.event_type,
            "window_seconds": s.window_seconds,
            "threshold": s.threshold,
            "group_by": s.group_by or [],
        },
    )
    db.add(rule)
    s.status = "accepted"
    db.commit()
    db.refresh(rule)
    return {"code": 0, "message": "accepted", "data": {"rule_code": rule.rule_code}}


@router.post("/rule-suggestions/{suggestion_id}/ignore")
def ignore_rule_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """管理端：忽略建议。"""
    s = db.get(RuleSuggestion, suggestion_id)
    if s is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    s.status = "ignored"
    db.commit()
    return {"code": 0, "message": "ignored", "data": {"id": s.id}}


# ---------------------------------------------------------------------------
# 设备登记
# ---------------------------------------------------------------------------

def _device_status(device: DeviceRegistry, now: datetime) -> str:
    """按最后上报时间与预期上报周期判定在线/离线（宽限见 services/device_health.py）。"""
    if device.last_seen_at is None:
        return "offline"
    return "online" if (now - device.last_seen_at).total_seconds() <= grace_seconds(device) else "offline"


@router.get("/devices")
def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    device_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """管理端：设备登记列表。"""
    stmt = select(DeviceRegistry)
    if device_type:
        stmt = stmt.where(DeviceRegistry.device_type == device_type)
    if enabled is not None:
        stmt = stmt.where(DeviceRegistry.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(DeviceRegistry.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    now = local_now()
    items = [
        {
            "id": d.id,
            "device_id": d.device_id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "hostname": d.hostname,
            "ip_address": d.ip_address,
            "environment": d.environment,
            "criticality": d.criticality,
            "expected_interval_seconds": d.expected_interval_seconds,
            "touser": d.touser,
            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
            "status": _device_status(d, now),
            "enabled": d.enabled,
            "attributes": d.attributes,
        }
        for d in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def register_device(
    payload: DeviceIn,
    db: Session = Depends(get_db),
):
    """管理端：登记设备（按 device_id 幂等 upsert）。"""
    device = db.scalar(select(DeviceRegistry).where(DeviceRegistry.device_id == payload.device_id))
    created = device is None
    old_type = device.device_type if device is not None else None
    if device is None:
        device = DeviceRegistry(
            device_id=payload.device_id,
            device_name=payload.device_name,
            device_type=payload.device_type,
        )
        db.add(device)
    device.device_name = payload.device_name
    device.device_type = payload.device_type
    device.hostname = payload.hostname
    device.ip_address = payload.ip_address
    device.environment = payload.environment
    device.criticality = payload.criticality
    device.expected_interval_seconds = payload.expected_interval_seconds
    device.touser = payload.touser
    device.enabled = payload.enabled
    if payload.attributes is not None:
        device.attributes = payload.attributes
    if old_type is not None and old_type != payload.device_type:
        # 设备类型变更时，同步更新该设备历史日志的设备类型
        db.execute(
            update(LogEvent).where(LogEvent.device_id == payload.device_id).values(device_type=payload.device_type)
        )
    db.commit()
    db.refresh(device)
    return {
        "code": 0,
        "message": "created" if created else "updated",
        "data": {
            "id": device.id,
            "device_id": device.device_id,
            "device_name": device.device_name,
            "device_type": device.device_type,
        },
    }


@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db)):
    """管理端：删除设备（仅删注册表记录，不影响其历史日志/事件）。"""
    device = db.scalar(select(DeviceRegistry).where(DeviceRegistry.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    db.delete(device)
    db.commit()
    return {"code": 0, "message": "deleted", "data": {"device_id": device_id}}


# ---------------------------------------------------------------------------
# 系统运行监控
# ---------------------------------------------------------------------------

@router.get("/system/overview")
def system_overview(db: Session = Depends(get_db)):
    """管理端：系统运行监控统计（队列积压、解析失败、Worker 状态等）。"""
    raw_pending = db.scalar(select(func.count(LogRaw.id)).where(LogRaw.process_status == "pending")) or 0
    raw_failed = db.scalar(select(func.count(LogRaw.id)).where(LogRaw.process_status == "failed")) or 0
    task_pending = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "pending")) or 0
    task_running = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "running")) or 0
    task_failed = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "failed")) or 0
    return {
        "code": 0,
        "message": "success",
        "data": {
            "raw_total": db.scalar(select(func.count(LogRaw.id))) or 0,
            "raw_pending": raw_pending,
            "raw_failed": raw_failed,
            "event_total": db.scalar(select(func.count(LogEvent.id))) or 0,
            "batch_total": db.scalar(select(func.count(LogBatch.id))) or 0,
            "device_total": db.scalar(select(func.count(DeviceRegistry.id))) or 0,
            "security_event_total": db.scalar(select(func.count(SecurityEvent.id))) or 0,
            "alert_total": db.scalar(select(func.count(AlertRecord.id))) or 0,
            "task_pending": task_pending,
            "task_running": task_running,
            "task_failed": task_failed,
        },
    }


@router.post("/system/reset")
def reset_system(db: Session = Depends(get_db)):
    """管理端：还原——清空日志、事件与告警（保留设备/规则/企业微信/附件）。"""
    return {"code": 0, "message": "success", "data": clear_all_logs(db)}


@router.get("/dashboard/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    """管理端：首页态势统计 + 近 7 日日志趋势。"""
    now = local_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        cnt = db.scalar(
            select(func.count(LogEvent.id)).where(
                LogEvent.event_time >= day,
                LogEvent.event_time < next_day,
            )
        ) or 0
        trend.append({"date": day.strftime("%m-%d"), "count": cnt})

    return {
        "code": 0,
        "message": "success",
        "data": {
            "device_total": db.scalar(select(func.count(DeviceRegistry.id))) or 0,
            "log_total": db.scalar(select(func.count(LogEvent.id))) or 0,
            "event_today": db.scalar(select(func.count(LogEvent.id)).where(LogEvent.event_time >= today_start)) or 0,
            "security_event_total": db.scalar(select(func.count(SecurityEvent.id))) or 0,
            "open_events": db.scalar(select(func.count(SecurityEvent.id)).where(SecurityEvent.status == "open")) or 0,
            "alert_total": db.scalar(select(func.count(AlertRecord.id))) or 0,
            "pending_alerts": db.scalar(select(func.count(AlertRecord.id)).where(AlertRecord.status == "pending")) or 0,
            "trend": trend,
        },
    }


# ---------------------------------------------------------------------------
# 企业微信消息发送管理
# ---------------------------------------------------------------------------

def _wecom_config_dict(cfg) -> dict:
    return {
        "corpid": cfg.corpid,
        "corpsecret_masked": mask_secret(cfg.corpsecret),
        "agentid": cfg.agentid,
        "touser": cfg.touser,
        "enabled": cfg.enabled,
        "notify_min_severity": cfg.notify_min_severity,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/wecom/config")
def get_wecom_config(db: Session = Depends(get_db)):
    """管理端：读取企业微信配置（密钥脱敏）。"""
    cfg = get_or_create_config(db)
    db.commit()
    return {"code": 0, "message": "success", "data": _wecom_config_dict(cfg)}


@router.put("/wecom/config")
def update_wecom_config(payload: WecomConfigIn, db: Session = Depends(get_db)):
    """管理端：保存企业微信配置（corpsecret 留空或 **** 开头则不修改）。"""
    cfg = get_or_create_config(db)
    cfg.corpid = payload.corpid
    if payload.corpsecret and not payload.corpsecret.startswith("****"):
        cfg.corpsecret = payload.corpsecret
    cfg.agentid = payload.agentid
    cfg.touser = payload.touser
    cfg.enabled = payload.enabled
    cfg.notify_min_severity = payload.notify_min_severity
    db.commit()
    db.refresh(cfg)
    return {"code": 0, "message": "success", "data": _wecom_config_dict(cfg)}


@router.post("/wecom/test")
def test_wecom(payload: WecomTestIn, db: Session = Depends(get_db)):
    """管理端：发送测试消息（touser 留空则用已配置的默认接收人）。"""
    cfg = get_or_create_config(db)
    db.commit()
    if not cfg.corpid or not cfg.corpsecret or not cfg.agentid:
        raise HTTPException(status_code=400, detail="企业微信未配置完整（corpid/corpsecret/agentid）")
    touser = payload.touser or cfg.touser
    if not touser:
        raise HTTPException(status_code=400, detail="未配置接收人 touser")
    content = payload.content or "这是一条测试消息"
    try:
        result = send_markdown(cfg.corpid, cfg.corpsecret, cfg.agentid, touser, content, settings.wecom_timeout_seconds)
        return {"code": 0, "message": "success", "data": {"errcode": result.get("errcode"), "errmsg": result.get("errmsg")}}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"发送失败：{exc}") from exc


# ---------------------------------------------------------------------------
# 附件管理
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "document": {".txt", ".md", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".rtf", ".log", ".json", ".xml", ".conf", ".yaml", ".yml", ".ini", ".cfg", ".toml"},
    "spreadsheet": {".xls", ".xlsx", ".csv"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"},
}


def _classify_file(filename: str) -> str | None:
    ext = os.path.splitext(filename)[1].lower()
    for category, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return category
    return None


def _serialize_attachment(a: Attachment) -> dict:
    return {
        "id": a.id,
        "filename": a.filename,
        "stored_name": a.stored_name,
        "uploader": a.uploader,
        "category": a.category,
        "content_type": a.content_type,
        "size": a.size,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.post("/files", status_code=status.HTTP_201_CREATED)
def upload_file(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """上传附件：保存到专属目录，库内记录文件地址与上传人。"""
    filename = file.filename or "unnamed"
    category = _classify_file(filename)
    if category is None:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{os.path.splitext(filename)[1] or '未知'}")

    ext = os.path.splitext(filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / stored_name
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("file too large")
                out.write(chunk)
    except ValueError:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=413, detail=f"文件超过 {settings.max_upload_size_mb}MB 限制")
    finally:
        file.file.close()

    att = Attachment(
        filename=filename,
        stored_name=stored_name,
        uploader=(uploader or "").strip() or None,
        category=category,
        content_type=file.content_type or "application/octet-stream",
        size=size,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"code": 0, "message": "success", "data": _serialize_attachment(att)}


@router.get("/files")
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """附件目录：分页列表 + 按类别筛选。"""
    stmt = select(Attachment)
    if category:
        stmt = stmt.where(Attachment.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(Attachment.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [_serialize_attachment(a) for a in rows]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


def _file_response(a: Attachment, inline: bool) -> FileResponse:
    path = Path(settings.upload_dir) / a.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path,
        filename=a.filename,
        media_type=a.content_type or "application/octet-stream",
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/files/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db)):
    """下载附件（Content-Disposition: attachment）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    return _file_response(a, inline=False)


@router.get("/files/{file_id}/preview")
def preview_file(file_id: int, db: Session = Depends(get_db)):
    """预览附件（inline，图片/PDF 可在浏览器直接查看）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    return _file_response(a, inline=True)


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """删除附件（删除磁盘文件 + 库内记录）。"""
    a = db.get(Attachment, file_id)
    if a is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    path = Path(settings.upload_dir) / a.stored_name
    if path.exists():
        path.unlink()
    db.delete(a)
    db.commit()
    return {"code": 0, "message": "deleted", "data": {"id": file_id}}
