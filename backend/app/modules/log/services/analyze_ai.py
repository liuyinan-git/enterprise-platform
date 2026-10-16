"""AI 研判：筛选候选事件 → 调用大模型 → 结构化校验 → 写回事件。"""

import time
import uuid
from datetime import datetime, timezone
from app.core.timeutil import local_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai_client import chat_completion
from app.modules.log.ai.prompts import build_messages
from app.modules.log.ai.schemas import parse_response
from app.core.config import settings
from app.modules.log.models import AlertRecord, DeviceRegistry, LogEvent, SecurityEvent, SecurityEventLog
from app.platform.notifications.service import get_or_create_config, resolve_receiver, should_notify_severity


def _now() -> datetime:
    return local_now()


def _gen_no(prefix: str) -> str:
    return f"{prefix}-{_now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"


_RISK_LABEL = {"malicious": "恶意", "suspicious": "可疑", "normal": "正常"}
_RISK_LEVEL = {"normal": 0, "suspicious": 1, "malicious": 2}


def _should_notify(analysis: dict) -> bool:
    """风险等级达到 ai_wecom_min_risk 才补发企业微信 AI 研判消息（留空则关闭）。"""
    min_risk = (settings.ai_wecom_min_risk or "").strip()
    if not min_risk:
        return False
    threshold = _RISK_LEVEL.get(min_risk, 0)
    level = _RISK_LEVEL.get(analysis.get("risk_assessment"), 0)
    return level >= threshold


def _build_ai_markdown(event: SecurityEvent, analysis: dict) -> str:
    """把 AI 研判结果组织成企业微信 Markdown。"""
    risk = _RISK_LABEL.get(analysis.get("risk_assessment"), analysis.get("risk_assessment") or "-")
    conf = analysis.get("confidence") or 0
    recs = (analysis.get("recommendations") or [])[:5]
    needs = "是" if analysis.get("needs_human_review") else "否"
    lines = [
        f"# AI 研判：{event.event_title}",
        "",
        f"> 事件编号：{event.event_no}",
        f"> 风险研判：{risk}（置信度 {conf:.0%}）",
        f"> 摘要：{analysis.get('summary') or '-'}",
        f"> 需人工复核：{needs}",
    ]
    if recs:
        lines.append("")
        lines.append("**核查建议：**")
        lines.extend(f"- {r}" for r in recs)
    return "\n".join(lines)


def _build_input(db: Session, event: SecurityEvent) -> dict:
    """组装分析输入：规则发现 + 资产信息 + 证据日志（不传全量原始数据）。"""
    evidence_rows = db.scalars(
        select(LogEvent)
        .join(SecurityEventLog, SecurityEventLog.log_event_id == LogEvent.id)
        .where(SecurityEventLog.security_event_id == event.id)
        .order_by(LogEvent.event_time)
        .limit(50)
    ).all()

    device = None
    if event.device_id:
        device = db.scalar(select(DeviceRegistry).where(DeviceRegistry.device_id == event.device_id))

    return {
        "task_type": "security_event_analysis",
        "rule_findings": [
            {
                "rule_code": event.rule_code or "UNKNOWN",
                "count": event.occurrence_count,
                "severity": event.severity,
            }
        ],
        "asset": {
            "device_id": event.device_id,
            "device_type": device.device_type if device else None,
            "hostname": device.hostname if device else None,
            "criticality": device.criticality if device else None,
        },
        "evidence": [
            {
                "event_type": e.event_type,
                "source_ip": e.source_ip,
                "username": e.username,
                "event_time": e.event_time.isoformat() if e.event_time else None,
            }
            for e in evidence_rows
        ],
    }


def analyze_event_ai(db: Session, event: SecurityEvent) -> dict:
    """对单个安全事件做 AI 研判，结果写入 event.ai_analysis。"""
    messages = build_messages(_build_input(db, event))
    last_error = None
    for attempt in range(settings.ai_max_retries + 1):
        try:
            content = chat_completion(
                messages,
                base_url=settings.ai_base_url,
                model=settings.ai_model,
                api_key=settings.ai_api_key,
                timeout=settings.ai_timeout_seconds,
            )
            parsed = parse_response(content)
            result = parsed.model_dump()
            result["model"] = settings.ai_model
            result["analyzed_at"] = _now().isoformat()
            event.ai_analysis = result
            event.summary = parsed.summary
            cfg = get_or_create_config(db)
            # 风险达到阈值且事件级别达到通知阈值才补发「AI 研判」消息
            if _should_notify(result) and should_notify_severity(cfg.notify_min_severity, event.severity):
                db.add(AlertRecord(
                    alert_no=_gen_no("ALT"),
                    security_event_id=event.id,
                    channel="wecom",
                    receiver_key=resolve_receiver(db, rule_code=event.rule_code, device_id=event.device_id),
                    message_content=_build_ai_markdown(event, result),
                    status="pending",
                ))
            db.commit()
            return {"status": "done", "model": settings.ai_model}
        except Exception as exc:  # 暂时性故障，有限次重试
            last_error = str(exc)[:500]
            if attempt < settings.ai_max_retries:
                time.sleep(2 * (attempt + 1))

    event.ai_analysis = {"status": "failed", "error": last_error, "analyzed_at": _now().isoformat()}
    db.commit()
    return {"status": "failed", "error": last_error}


def run_ai_analysis(db: Session, limit: int = 3) -> dict:
    """筛选待研判的未关闭高危/中危事件并逐个分析。返回统计。"""
    if not settings.ai_enabled or not settings.ai_model:
        return {"total": 0, "analyzed": 0, "failed": 0, "skipped": "AI 未启用"}

    candidates = db.scalars(
        select(SecurityEvent)
        .where(
            SecurityEvent.status == "open",
            SecurityEvent.severity.in_(["high", "medium"]),
            SecurityEvent.ai_analysis.is_(None),
        )
        .order_by(SecurityEvent.last_seen_at.desc())
        .limit(limit)
    ).all()

    analyzed = failed = 0
    for event in candidates:
        result = analyze_event_ai(db, event)
        if result["status"] == "done":
            analyzed += 1
        else:
            failed += 1
    return {"total": len(candidates), "analyzed": analyzed, "failed": failed}
