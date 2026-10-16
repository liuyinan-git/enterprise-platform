import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from app.core.timeutil import local_now

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.log.models import AlertRecord, AnalysisRule, SecurityEvent, SecurityEventLog
from app.platform.notifications.wecom import send_markdown
from app.modules.log.rules.engine import evaluate_rule
from app.platform.notifications.service import get_or_create_config, resolve_receiver, should_notify_severity


def _now() -> datetime:
    return local_now()


def _fingerprint(rule_code: str, group_key: str) -> str:
    return hashlib.sha256(f"{rule_code}|{group_key}".encode("utf-8")).hexdigest()


def _gen_no(prefix: str) -> str:
    return f"{prefix}-{_now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"


def _link_evidence(db: Session, security_event_id: int, event_ids: list[int]) -> None:
    existing = set(db.scalars(
        select(SecurityEventLog.log_event_id).where(SecurityEventLog.security_event_id == security_event_id)
    ).all())
    for eid in event_ids:
        if eid not in existing:
            db.add(SecurityEventLog(security_event_id=security_event_id, log_event_id=eid, relation_type="evidence"))


def _build_markdown(event: SecurityEvent, rule: AnalysisRule) -> str:
    return (
        f"# 企业安全告警：{event.event_title}\n\n"
        f"> 告警等级：{event.severity}\n"
        f"> 告警编号：{event.event_no}\n"
        f"> 最近发生：{event.last_seen_at}\n\n"
        f"**触发规则：** {rule.rule_code}\n"
        f"**涉及设备：** {event.device_id or '-'}\n"
        f"**来源 IP：** {event.source_ip or '-'}\n"
        f"**累计次数：** {event.occurrence_count}\n"
    )


def _evidence_count(db: Session, security_event_id: int) -> int:
    """该安全事件去重后关联的证据日志数。"""
    return db.scalar(
        select(func.count(SecurityEventLog.log_event_id)).where(
            SecurityEventLog.security_event_id == security_event_id
        )
    ) or 0


def aggregate_finding(db: Session, rule: AnalysisRule, finding: dict) -> tuple[SecurityEvent, bool]:
    """事件聚合：用指纹匹配未关闭事件，命中则更新，否则新建。返回 (事件, 是否新建)。"""
    fp = _fingerprint(rule.rule_code, finding["group_key"])
    existing = db.scalar(
        select(SecurityEvent).where(SecurityEvent.fingerprint == fp, SecurityEvent.status == "open")
    )
    if existing:
        existing.last_seen_at = _now()
        _link_evidence(db, existing.id, finding["event_ids"])
        existing.occurrence_count = _evidence_count(db, existing.id)
        return existing, False

    event = SecurityEvent(
        event_no=_gen_no("EVT"),
        fingerprint=fp,
        rule_code=rule.rule_code,
        event_title=rule.rule_name,
        severity=finding["severity"],
        status="open",
        source_ip=finding["source_ip"],
        device_id=finding["device_id"],
        first_seen_at=_now(),
        last_seen_at=_now(),
        occurrence_count=0,
    )
    db.add(event)
    db.flush()
    _link_evidence(db, event.id, finding["event_ids"])
    event.occurrence_count = _evidence_count(db, event.id)
    return event, True


def _send_alert(db: Session, alert: AlertRecord) -> None:
    """尝试发送企业微信；未配置或未启用则保持 pending，交由后续通知 worker。"""
    cfg = get_or_create_config(db)
    if not cfg.enabled or not cfg.corpid or not cfg.corpsecret or not cfg.agentid or not cfg.touser:
        return
    try:
        send_markdown(cfg.corpid, cfg.corpsecret, cfg.agentid, cfg.touser, alert.message_content, settings.wecom_timeout_seconds)
        alert.status = "sent"
        alert.sent_at = _now()
        alert.next_retry_at = None
        alert.last_error = None
    except Exception as exc:
        alert.status = "failed"
        alert.last_error = str(exc)[:1000]
        alert.attempt_count = (alert.attempt_count or 0) + 1
        backoff = min(60 * (2 ** min(alert.attempt_count, 6)), 3600)
        alert.next_retry_at = _now() + timedelta(seconds=backoff)


def analyze(db: Session) -> dict:
    """规则分析：评估启用规则 → 聚合安全事件 → 新建告警并尝试发送。"""
    rules = db.scalars(select(AnalysisRule).where(AnalysisRule.enabled.is_(True))).all()
    cfg = get_or_create_config(db)
    stats = {"rules": len(rules), "events": 0, "alerts": 0}
    for rule in rules:
        for finding in evaluate_rule(db, rule):
            event, created = aggregate_finding(db, rule, finding)
            stats["events"] += 1
            if created and should_notify_severity(cfg.notify_min_severity, event.severity):
                alert = AlertRecord(
                    alert_no=_gen_no("ALT"),
                    security_event_id=event.id,
                    channel="wecom",
                    receiver_key=resolve_receiver(db, rule_touser=rule.touser, device_id=finding["device_id"]),
                    message_content=_build_markdown(event, rule),
                    status="pending",
                )
                db.add(alert)
                db.flush()
                _send_alert(db, alert)
                stats["alerts"] += 1
    db.commit()
    return stats
