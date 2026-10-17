"""模型告警状态机单测：连续失败触发 / 防重复 / 恢复关闭+通知 / 发送失败退避 / 重试。

企业微信发送与配置均 monkeypatch（外网不可达，且状态机逻辑与真实发送解耦）。
"""

from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import settings
from app.modules.model.models import ModelAlert
from app.modules.model.services import alerting


class FakeWecom:
    """企业微信假配置（SimpleNamespace，绕开 wecom_config 表依赖）。"""

    def __init__(self, enabled=True, notify_min_severity="medium"):
        self.enabled = enabled
        self.corpid = "cid"
        self.corpsecret = "sec"
        self.agentid = 1000001
        self.touser = "ops-team"
        self.notify_min_severity = notify_min_severity


import pytest


@pytest.fixture
def wecom(db, monkeypatch):
    """默认配置完整且开启；测试可改属性再触发。"""
    cfg = FakeWecom()
    monkeypatch.setattr(alerting, "get_or_create_config", lambda session: cfg)
    return cfg


@pytest.fixture
def sender(monkeypatch):
    """记录 send_markdown 调用；可用 .error 切换为抛异常。"""
    box = SimpleNamespace(calls=[], error=None)

    def fake_send(corpid, corpsecret, agentid, touser, content, timeout=5):
        if box.error:
            raise box.error
        box.calls.append({"touser": touser, "content": content})
        return {}

    monkeypatch.setattr(alerting, "send_markdown", fake_send)
    return box


def _count_alerts(db) -> int:
    return len(db.scalars(select(ModelAlert)).all())


# ===== 失败累计与触发 =====


def test_first_failure_no_alert(db, model, wecom, sender):
    assert alerting.process_probe_result(db, model, False, "timeout") == "counted"
    assert model.consecutive_failures == 1
    assert _count_alerts(db) == 0


def test_below_threshold_no_alert(db, model, wecom, sender):
    for _ in range(settings.model_alert_failure_threshold - 1):
        alerting.process_probe_result(db, model, False, "timeout")
    assert _count_alerts(db) == 0


def test_consecutive_failures_fire_alert(db, model, wecom, sender):
    for i in range(settings.model_alert_failure_threshold):
        action = alerting.process_probe_result(db, model, False, "timeout")
    assert action == "alerted"
    alerts = db.scalars(select(ModelAlert)).all()
    assert len(alerts) == 1
    assert alerts[0].alert_type == "failure"
    assert alerts[0].status == "sent"  # sender 成功
    assert alerts[0].receiver_key == "ops-team"
    assert len(sender.calls) == 1
    assert model.model_code in sender.calls[0]["content"]


def test_no_duplicate_while_open(db, model, wecom, sender):
    for _ in range(settings.model_alert_failure_threshold + 2):
        alerting.process_probe_result(db, model, False, "timeout")
    assert _count_alerts(db) == 1  # open 存在（含已 sent）→ 不重复建
    assert model.consecutive_failures == settings.model_alert_failure_threshold + 2


# ===== 恢复逻辑 =====


def test_recovery_closes_and_notifies(db, model, wecom, sender):
    for _ in range(settings.model_alert_failure_threshold):
        alerting.process_probe_result(db, model, False, "timeout")
    action = alerting.process_probe_result(db, model, True, "HTTP 200")
    assert action == "recovered"
    assert model.consecutive_failures == 0
    alerts = db.scalars(select(ModelAlert)).all()
    assert len(alerts) == 2  # failure（已 resolved）+ recovery
    failure = [a for a in alerts if a.alert_type == "failure"][0]
    recovery = [a for a in alerts if a.alert_type == "recovery"][0]
    assert failure.resolved_at is not None
    assert recovery.status == "sent"
    assert "恢复" in recovery.message_content
    assert len(sender.calls) == 2


def test_recovery_resets_without_notify(db, model, wecom, sender):
    """未达阈值的失败 → 恢复：计数清零、不建任何告警。"""
    alerting.process_probe_result(db, model, False, "timeout")
    action = alerting.process_probe_result(db, model, True, "HTTP 200")
    assert action == "none"
    assert model.consecutive_failures == 0
    assert _count_alerts(db) == 0


def test_recovery_only_if_sent(db, model, wecom, sender):
    """故障告警未送达（pending）时恢复：关闭告警但不发恢复通知。"""
    wecom.enabled = False  # 未配置 → failure 告警保持 pending
    for _ in range(settings.model_alert_failure_threshold):
        alerting.process_probe_result(db, model, False, "timeout")
    failure = db.scalars(select(ModelAlert)).one()
    assert failure.status == "pending"
    action = alerting.process_probe_result(db, model, True, "HTTP 200")
    assert action == "recovered"
    assert failure.resolved_at is not None
    assert _count_alerts(db) == 1  # 无 recovery 告警
    assert sender.calls == []


# ===== 配置开关 =====


def test_alert_disabled_by_config(db, model, wecom, sender, monkeypatch):
    monkeypatch.setattr(settings, "model_alert_enabled", False)
    for _ in range(settings.model_alert_failure_threshold + 1):
        action = alerting.process_probe_result(db, model, False, "timeout")
    assert action == "counted"
    assert _count_alerts(db) == 0


def test_alert_filtered_by_severity(db, model, wecom, sender):
    """notify_min_severity=critical 时 high 级故障告警不通知（不建告警记录）。"""
    wecom.notify_min_severity = "critical"
    for _ in range(settings.model_alert_failure_threshold):
        alerting.process_probe_result(db, model, False, "timeout")
    assert _count_alerts(db) == 0


def test_probe_none_skips(db, model, wecom, sender):
    model.probe_method = "none"
    for _ in range(5):
        assert alerting.process_probe_result(db, model, False, "") == "skip"
    assert model.consecutive_failures == 0
    assert _count_alerts(db) == 0


# ===== 发送失败与重试 =====


def test_send_fail_backoff(db, model, wecom, sender):
    sender.error = RuntimeError("network down")
    for _ in range(settings.model_alert_failure_threshold):
        action = alerting.process_probe_result(db, model, False, "timeout")
    assert action == "alerted"
    alert = db.scalars(select(ModelAlert)).one()
    assert alert.status == "failed"
    assert alert.attempt_count == 1
    assert alert.next_retry_at is not None  # 指数退避已排期
    assert "network down" in (alert.last_error or "")


def test_retry_resends_failed(db, model, wecom, sender):
    sender.error = RuntimeError("network down")
    for _ in range(settings.model_alert_failure_threshold):
        alerting.process_probe_result(db, model, False, "timeout")
    alert = db.scalars(select(ModelAlert)).one()
    assert alert.status == "failed"
    sender.error = None  # 网络恢复
    # 退避到期后重试成功
    from datetime import timedelta

    from app.core.timeutil import local_now

    alert.next_retry_at = local_now() - timedelta(seconds=1)
    db.flush()
    count = alerting.retry_model_alerts(db)
    assert count == 1
    assert alert.status == "sent"
    assert len(sender.calls) == 1


def test_retry_skips_not_due(db, model, wecom, sender):
    """next_retry_at 在未来 → 不重试。"""
    sender.error = RuntimeError("network down")
    for _ in range(settings.model_alert_failure_threshold):
        alerting.process_probe_result(db, model, False, "timeout")
    alert = db.scalars(select(ModelAlert)).one()
    assert alert.status == "failed"
    count = alerting.retry_model_alerts(db)  # 退避期内
    assert count == 0
    assert alert.status == "failed"


# ===== Markdown 构造 =====


def test_failure_markdown_content():
    model = SimpleNamespace(
        model_name="Qwen3 Embedding 4B", model_code="qwen3-embedding-4b",
        service_type="embedding", engine="vLLM v0.17.1",
        endpoint_url="http://172.28.110.11:8033",
    )
    text = alerting._build_failure_markdown(model, 3, "timeout")
    assert "模型服务告警" in text
    assert "qwen3-embedding-4b" in text
    assert "连续 **3** 次探测失败" in text
    assert "timeout" in text


def test_recovery_markdown_content():
    model = SimpleNamespace(
        model_name="27B", model_code="qwen38-27b",
        endpoint_url="http://172.28.110.11:9101",
    )
    text = alerting._build_recovery_markdown(model, 42)
    assert "模型服务恢复" in text
    assert "qwen38-27b" in text
    assert "42 分钟" in text
