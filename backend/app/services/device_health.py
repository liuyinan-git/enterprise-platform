"""设备失联检测：超期未上报的设备生成安全事件与告警，恢复上报后自动关闭。"""

import hashlib
import uuid
from datetime import datetime, timezone
from app.core.timeutil import local_now

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.log_models import AlertRecord, DeviceRegistry, SecurityEvent
from app.services.wecom_config import get_or_create_config, resolve_receiver, should_notify_severity

OFFLINE_GRACE_MULTIPLIER = 2
OFFLINE_MIN_GRACE_SECONDS = 60
OFFLINE_RULE_CODE = "DEVICE_OFFLINE"


def _now() -> datetime:
    return local_now()


def grace_seconds(device: DeviceRegistry) -> int:
    """失联判定宽限：预期上报周期的 OFFLINE_GRACE_MULTIPLIER 倍（至少 60s）。"""
    return max((device.expected_interval_seconds or 900) * OFFLINE_GRACE_MULTIPLIER, OFFLINE_MIN_GRACE_SECONDS)


def _fingerprint(device_id: str) -> str:
    return hashlib.sha256(f"{OFFLINE_RULE_CODE}|{device_id}".encode("utf-8")).hexdigest()


def _gen_no(prefix: str) -> str:
    return f"{prefix}-{_now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"


def _build_markdown(device: DeviceRegistry, event: SecurityEvent, grace: int) -> str:
    return (
        f"# 设备失联告警：{device.device_id}\n\n"
        f"> 告警等级：{event.severity}\n"
        f"> 告警编号：{event.event_no}\n"
        f"> 设备名称：{device.device_name}\n"
        f"> 设备类型：{device.device_type}\n"
        f"> IP 地址：{device.ip_address or '-'}\n"
        f"> 最后上报：{device.last_seen_at}\n"
        f"> 失联阈值：{grace} 秒\n"
    )


def detect_offline_devices(db: Session) -> dict:
    """扫描启用设备：超期未上报的生成/维持「设备失联」事件与告警；恢复上报的自动关闭事件。"""
    now = _now()
    devices = db.scalars(select(DeviceRegistry).where(DeviceRegistry.enabled.is_(True))).all()
    cfg = get_or_create_config(db)

    alerted = 0
    recovered = 0
    for device in devices:
        fp = _fingerprint(device.device_id)
        existing = db.scalar(select(SecurityEvent).where(
            SecurityEvent.fingerprint == fp,
            SecurityEvent.status == "open",
        ))

        is_offline = device.last_seen_at is not None and (now - device.last_seen_at).total_seconds() > grace_seconds(device)

        if is_offline:
            if existing is None:
                grace = grace_seconds(device)
                event = SecurityEvent(
                    event_no=_gen_no("EVT"),
                    fingerprint=fp,
                    rule_code=OFFLINE_RULE_CODE,
                    event_title=f"设备失联：{device.device_id}",
                    severity="high" if device.criticality in ("critical", "high") else "medium",
                    status="open",
                    source_ip=device.ip_address,
                    device_id=device.device_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    occurrence_count=1,
                    summary=f"设备 {device.device_id} 超过 {grace} 秒未上报（预期周期 {device.expected_interval_seconds or 900} 秒）",
                )
                db.add(event)
                db.flush()
                if should_notify_severity(cfg.notify_min_severity, event.severity):
                    db.add(AlertRecord(
                        alert_no=_gen_no("ALT"),
                        security_event_id=event.id,
                        channel="wecom",
                        receiver_key=resolve_receiver(db, device_id=device.device_id),
                        message_content=_build_markdown(device, event, grace),
                        status="pending",
                    ))
                alerted += 1
        else:
            if existing is not None:
                existing.status = "closed"
                existing.resolved_at = now
                existing.resolution_note = "设备恢复上报，自动关闭"
                recovered += 1

    db.commit()
    return {"checked": len(devices), "alerted": alerted, "recovered": recovered}
