"""企业微信配置读写：单行 id=1，环境变量作为初始值，运行期以库内配置为准。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.log.models import AnalysisRule, DeviceRegistry
from app.platform.notifications.models import WecomConfig

SEVERITY_LEVEL = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def get_or_create_config(db: Session) -> WecomConfig:
    """读取配置行；不存在则以环境变量为初始值创建（flush 不提交，由调用方 commit）。"""
    row = db.get(WecomConfig, 1)
    if row is None:
        row = WecomConfig(
            id=1,
            corpid=settings.wecom_corpid,
            corpsecret=settings.wecom_corpsecret,
            agentid=settings.wecom_agentid,
            touser=settings.wecom_touser,
            enabled=settings.wecom_enabled,
            notify_min_severity=settings.wecom_notify_min_severity,
        )
        db.add(row)
        db.flush()
    return row


def should_notify_severity(min_severity: str, severity: str) -> bool:
    """事件级别是否达到「通知最低级别」（默认 medium）。"""
    threshold = SEVERITY_LEVEL.get(min_severity, 1)
    level = SEVERITY_LEVEL.get(severity, 0)
    return level >= threshold


def resolve_receiver(
    db: Session,
    *,
    rule_touser: str | None = None,
    rule_code: str | None = None,
    device_id: str | None = None,
) -> str:
    """按「规则 > 设备 > 全局」解析告警接收人。"""
    if rule_touser:
        return rule_touser
    if rule_code:
        rule = db.scalar(select(AnalysisRule).where(AnalysisRule.rule_code == rule_code))
        if rule and rule.touser:
            return rule.touser
    if device_id:
        device = db.scalar(select(DeviceRegistry).where(DeviceRegistry.device_id == device_id))
        if device and device.touser:
            return device.touser
    return get_or_create_config(db).touser
