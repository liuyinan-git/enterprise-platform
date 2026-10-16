"""模型服务告警：连续探测失败 → 企业微信告警，恢复 → 恢复通知。

状态机（防重复核心）：
- 失败：consecutive_failures 累加；达到阈值且无未恢复的 failure 告警 → 新建告警并发送
  （open 告警已存在——含发送失败——则不新建，交给 retry 任务防重复）
- 恢复：关闭 open 告警（resolved_at）；仅当故障告警已送达（sent）且恢复通知开启时发恢复通知；
  计数清零
- 发送失败：置 failed + 指数退避（60s·2^n，上限 1h），由 retry_model_alerts 周期重试

模块边界：只依赖 platform/notifications 的 get_or_create_config + wecom.send_markdown；
不使用 resolve_receiver（其内部依赖 log 模块表），接收人直接取全局配置 touser。
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import local_now
from app.modules.model.models import ModelAlert, ModelRegistry
from app.platform.notifications.service import get_or_create_config, should_notify_severity
from app.platform.notifications.wecom import send_markdown

# 故障告警级别（wecom_config.notify_min_severity 过滤，默认 medium 则 high 会通知）
FAILURE_SEVERITY = "high"


def _gen_no(prefix: str = "MALT") -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def _build_failure_markdown(model: ModelRegistry, consecutive: int, detail: str) -> str:
    return (
        f"**模型服务告警**\n"
        f"> 服务：**{model.model_name}**（{model.model_code}）\n"
        f"> 类型：{model.service_type} | 引擎：{model.engine or '-'}\n"
        f"> 端点：{model.endpoint_url}\n"
        f"> 状态：连续 **{consecutive}** 次探测失败\n"
        f"> 详情：{detail or '无响应'}\n"
        f"> 时间：{local_now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def _build_recovery_markdown(model: ModelRegistry, downtime_minutes: int | None) -> str:
    duration = f"（持续约 {downtime_minutes} 分钟）" if downtime_minutes is not None else ""
    return (
        f"**模型服务恢复**\n"
        f"> 服务：**{model.model_name}**（{model.model_code}）\n"
        f"> 端点：{model.endpoint_url}\n"
        f"> 状态：探测恢复健康{duration}\n"
        f"> 时间：{local_now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def _send_model_alert(db: Session, alert: ModelAlert) -> None:
    """尝试发送告警（企业微信）。未配置保持 pending；成功 sent；失败 failed + 退避。

    注意：不 commit，由调用方统一提交。
    """
    cfg = get_or_create_config(db)
    if not cfg.enabled or not cfg.corpid or not cfg.corpsecret or not cfg.agentid:
        return  # 未配置：保持 pending，待配置后 retry 任务补发
    touser = cfg.touser or "@all"
    alert.receiver_key = touser
    try:
        send_markdown(cfg.corpid, cfg.corpsecret, cfg.agentid, touser, alert.message_content)
        alert.status = "sent"
        alert.sent_at = local_now()
        alert.last_error = None
    except Exception as exc:  # noqa: BLE001
        alert.attempt_count += 1
        alert.status = "failed"
        backoff = min(60 * (2 ** min(alert.attempt_count, 6)), 3600)
        alert.next_retry_at = local_now() + timedelta(seconds=backoff)
        alert.last_error = str(exc)[:1000]
    db.flush()  # 状态变更即时可见（同 session 后续 SELECT / retry 查询）


def _get_open_failure_alert(db: Session, model_id: int) -> ModelAlert | None:
    return db.scalar(
        select(ModelAlert).where(
            ModelAlert.model_id == model_id,
            ModelAlert.alert_type == "failure",
            ModelAlert.resolved_at.is_(None),
        ).order_by(ModelAlert.id.desc()).limit(1)
    )


def process_probe_result(db: Session, model: ModelRegistry, ok_flag: bool, detail: str = "") -> str:
    """探测结果驱动告警状态机。返回动作：none / counted / alerted / recovered / skip。

    不 commit，由调用方统一提交。
    """
    if model.probe_method == "none":
        model.consecutive_failures = 0
        return "skip"

    if ok_flag:
        had_alert = False
        open_alert = _get_open_failure_alert(db, model.id)
        if open_alert is not None:
            open_alert.resolved_at = local_now()
            had_alert = True
            # 恢复通知：仅故障告警确实送达过的人才需要知道恢复了
            if settings.model_alert_recovery_enabled and open_alert.status == "sent":
                downtime = None
                if open_alert.created_at:
                    downtime = max(0, int((local_now() - open_alert.created_at).total_seconds() // 60))
                recovery = ModelAlert(
                    alert_no=_gen_no(),
                    model_id=model.id,
                    alert_type="recovery",
                    receiver_key=open_alert.receiver_key,
                    message_content=_build_recovery_markdown(model, downtime),
                )
                db.add(recovery)
                db.flush()
                _send_model_alert(db, recovery)
        model.consecutive_failures = 0
        return "recovered" if had_alert else "none"

    # 探测失败
    model.consecutive_failures = (model.consecutive_failures or 0) + 1
    open_alert = _get_open_failure_alert(db, model.id)
    if open_alert is not None:
        return "counted"  # 已有未恢复告警（含发送失败），不重复建

    cfg = get_or_create_config(db)
    if (
        settings.model_alert_enabled
        and model.consecutive_failures >= settings.model_alert_failure_threshold
        and should_notify_severity(cfg.notify_min_severity, FAILURE_SEVERITY)
    ):
        # 注意：cfg.enabled / 配置完整性不影响建告警——未配置时建为 pending，
        # 待配置好后由 retry 任务补发（企业微信停用也留痕可查）。
        alert = ModelAlert(
            alert_no=_gen_no(),
            model_id=model.id,
            alert_type="failure",
            message_content=_build_failure_markdown(model, model.consecutive_failures, detail),
        )
        db.add(alert)
        db.flush()
        _send_model_alert(db, alert)
        return "alerted"
    return "counted"


def retry_model_alerts(db: Session, limit: int = 50) -> int:
    """重试 pending/failed 且到期的告警，返回处理条数。不 commit。"""
    now = local_now()
    stmt = (
        select(ModelAlert)
        .where(
            ModelAlert.status.in_(("pending", "failed")),
            (ModelAlert.next_retry_at.is_(None)) | (ModelAlert.next_retry_at <= now),
        )
        .order_by(ModelAlert.id)
        .limit(limit)
    )
    count = 0
    for alert in db.scalars(stmt).all():
        _send_model_alert(db, alert)
        count += 1
    return count
