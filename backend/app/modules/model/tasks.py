"""模型模块周期任务：端点健康探测（含告警状态机）+ vLLM 用量采集 + 告警重试。"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.timeutil import local_now
from app.modules.model.models import ModelHealth, ModelProvider, ModelRegistry, ModelUsage
from app.modules.model.services import (
    METRICS_SERVICE_TYPES,
    _model_endpoint,
    compute_delta,
    probe_model,
)
from app.modules.model.services.alerting import process_probe_result, retry_model_alerts
from app.modules.model.services.container_live import annotate_failure, container_snapshot
from app.tasks.celery_app import celery_app


def _upsert_usage(db, model_id: int, day: str, delta: int) -> None:
    usage = db.scalar(
        select(ModelUsage).where(ModelUsage.model_id == model_id, ModelUsage.recorded_day == day)
    )
    if usage is None:
        usage = ModelUsage(model_id=model_id, recorded_day=day, call_count=0)
        db.add(usage)
    usage.call_count += delta


@celery_app.task(name="check_model_endpoints")
def check_model_endpoints_task() -> dict:
    """周期探测启用中的模型服务（按 probe_method 分层），更新 health_status 并落历史；驱动告警状态机。"""
    db = SessionLocal()
    healthy = 0
    unhealthy = 0
    skipped = 0
    alerted = 0
    recovered = 0
    try:
        providers = {p.id: p for p in db.scalars(select(ModelProvider)).all()}
        models = db.scalars(select(ModelRegistry).where(ModelRegistry.enabled.is_(True))).all()
        snap = container_snapshot()  # 每周期一次快照，12 个模型按容器名匹配
        for model in models:
            ok_flag, latency_ms, message = probe_model(model, providers.get(model.provider_id))
            if not ok_flag:  # 失败时标注容器状态（容器挂了 vs 服务无响应），告警内容同步受益
                message = annotate_failure(message or "", model.model_code, snap)
            action = process_probe_result(db, model, ok_flag, message or "")
            if model.probe_method == "none":
                model.health_status = "unknown"
                skipped += 1
            else:
                model.health_status = "healthy" if ok_flag else "unhealthy"
                if ok_flag:
                    healthy += 1
                else:
                    unhealthy += 1
            if action == "alerted":
                alerted += 1
            elif action == "recovered":
                recovered += 1
            model.last_check_at = local_now()
            db.add(
                ModelHealth(
                    model_id=model.id,
                    status=model.health_status,
                    latency_ms=latency_ms,
                    message=(message or "")[:500] or None,
                )
            )
        db.commit()
        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "skipped": skipped,
            "alerted": alerted,
            "recovered": recovered,
        }
    finally:
        db.close()


@celery_app.task(name="retry_model_alerts")
def retry_model_alerts_task() -> dict:
    """周期重试 pending/failed 且到期的模型告警（含企业微信配置好后补发 pending）。"""
    db = SessionLocal()
    try:
        count = retry_model_alerts(db)
        db.commit()
        return {"retried": count}
    finally:
        db.close()


@celery_app.task(name="collect_model_usage")
def collect_model_usage_task() -> dict:
    """周期拉取 vLLM /metrics，按计数器差值累计当日调用量。

    非 vLLM 服务（拉不到 /metrics 或无指标）静默跳过，用量页显示为无数据（no_data）。
    """
    import urllib.request

    from app.core.config import settings
    from app.modules.model.services import parse_prometheus_counter

    db = SessionLocal()
    collected = 0
    skipped = 0
    failed = 0
    try:
        providers = {p.id: p for p in db.scalars(select(ModelProvider)).all()}
        models = db.scalars(select(ModelRegistry).where(ModelRegistry.enabled.is_(True))).all()
        day = local_now().strftime("%Y-%m-%d")
        for model in models:
            if model.service_type not in METRICS_SERVICE_TYPES or not model.endpoint_url:
                skipped += 1
                continue
            endpoint = _model_endpoint(model, providers.get(model.provider_id))
            url = f"{endpoint}/metrics"
            metric_name = model.metrics_metric or settings.model_usage_metric
            try:
                with urllib.request.urlopen(url, timeout=settings.model_metrics_timeout_seconds) as resp:
                    if resp.status >= 400:
                        failed += 1
                        continue
                    text = resp.read().decode("utf-8", errors="replace")
                current = parse_prometheus_counter(text, metric_name)
                if current is None:
                    failed += 1
                    continue
                delta = compute_delta(model.last_metrics_value, current)
                model.last_metrics_value = current
                if delta > 0:
                    _upsert_usage(db, model.id, day, delta)
                collected += 1
            except Exception:  # noqa: BLE001  # 非 vLLM 服务无 /metrics 属正常
                failed += 1
        db.commit()
        return {"collected": collected, "skipped": skipped, "failed": failed}
    finally:
        db.close()
