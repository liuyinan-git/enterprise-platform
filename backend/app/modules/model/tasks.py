"""模型模块周期任务：端点健康探测（含告警状态机）+ vLLM 用量采集 + 告警重试。"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.timeutil import local_now
from app.modules.model.models import (
    ModelConsumer,
    ModelConsumerUsage,
    ModelHealth,
    ModelProvider,
    ModelRegistry,
    ModelUsage,
)
from app.modules.model.services import (
    METRICS_SERVICE_TYPES,
    _model_endpoint,
    compute_delta,
    probe_model,
)
from app.modules.model.services.access_log import parse_access_lines
from app.modules.model.services.alerting import process_probe_result, retry_model_alerts
from app.modules.model.services.container_live import (
    annotate_failure,
    container_ip_map,
    container_logs,
    container_snapshot,
)
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
        # 多节点：每个节点一个 proxy，按模型所属节点分别快照（缓存去重，同节点只读一次）
        snap_cache: dict[str, dict] = {}

        def _snap_for(provider: ModelProvider | None) -> dict:
            key = (provider.container_proxy_url or "") if provider else ""
            if key not in snap_cache:
                snap_cache[key] = container_snapshot(provider.container_proxy_url if provider else None)
            return snap_cache[key]

        for model in models:
            provider = providers.get(model.provider_id)
            ok_flag, latency_ms, message = probe_model(model, provider)
            if not ok_flag:  # 失败时标注容器状态（容器挂了 vs 服务无响应），告警内容同步受益
                message = annotate_failure(message or "", model.model_code, _snap_for(provider))
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


@celery_app.task(name="collect_model_callers")
def collect_model_callers_task() -> dict:
    """周期读各模型容器 access log，按 source_ip 聚合「谁在调哪个模型」调用量。

    数据源是模型容器（vLLM/uvicorn）打到 stdout 的 access log，经 docker-socket-proxy
    读取后解析 source_ip + 状态码，反查调用方台账（容器名 / external_ip）后 upsert 到
    model_consumer_usage。匹配不到调用方的归入 unknown_ips 统计（不自动建台账）。

    仅处理 enabled 且 service_type in METRICS_SERVICE_TYPES 的模型（vLLM 类才有
    标准 access log）；stdout 空日志的模型标 no_log 跳过，不误报。
    """
    from app.core.config import settings
    import time

    db = SessionLocal()
    scanned = 0
    no_log = 0
    with_calls = 0
    unknown_ips: dict[str, int] = {}
    rows_written = 0
    try:
        consumers = db.scalars(select(ModelConsumer)).all()
        consumer_by_container = {c.identifier: c.id for c in consumers if c.identity_type == "container"}
        consumer_by_ip = {c.identifier: c.id for c in consumers if c.identity_type == "external_ip"}
        providers = {p.id: p for p in db.scalars(select(ModelProvider)).all()}
        # 多节点：ip→容器名 反查表按节点 proxy 分别取（缓存去重，同节点只读一次）
        ip_map_cache: dict[str, dict[str, str]] = {}

        def _ip_map_for(provider: ModelProvider | None) -> dict[str, str]:
            key = (provider.container_proxy_url or "") if provider else ""
            if key not in ip_map_cache:
                ip_map_cache[key] = container_ip_map(provider.container_proxy_url if provider else None)
            return ip_map_cache[key]

        models = db.scalars(
            select(ModelRegistry).where(
                ModelRegistry.enabled.is_(True),
                ModelRegistry.service_type.in_(METRICS_SERVICE_TYPES),
            )
        ).all()
        day = local_now().strftime("%Y-%m-%d")
        # (consumer_id, model_id) → [call_count, error_count]
        aggregated: dict[tuple[int, int], list[int]] = {}
        for model in models:
            scanned += 1
            provider = providers.get(model.provider_id)
            ip_to_container = _ip_map_for(provider)
            # 无重叠增量：只读 last_log_cursor 之后的新日志；游标用「读取开始时刻」，
            # 这样本周期读到的行下一周期不会重复，写与读之间的新行也不会漏。
            read_start = int(time.time())
            cursor = model.last_log_cursor or 0
            text = container_logs(model.model_code, settings.model_access_log_tail, since=cursor,
                                  proxy_url=provider.container_proxy_url if provider else None)
            if text is None:  # 代理未启用/不可达/容器不在 → 不推进游标，下周期重试
                no_log += 1
                continue
            model.last_log_cursor = read_start  # 读取成功，推进游标
            if not text:
                continue
            hits = parse_access_lines(text)
            if not hits:
                continue
            with_calls += 1
            for line in hits:
                consumer_id = None
                container_name = ip_to_container.get(line.source_ip)
                if container_name and container_name in consumer_by_container:
                    consumer_id = consumer_by_container[container_name]
                elif line.source_ip in consumer_by_ip:
                    consumer_id = consumer_by_ip[line.source_ip]
                if consumer_id is None:
                    unknown_ips[line.source_ip] = unknown_ips.get(line.source_ip, 0) + 1
                    continue
                key = (consumer_id, model.id)
                bucket = aggregated.setdefault(key, [0, 0])
                bucket[0] += 1
                if line.status >= 400:
                    bucket[1] += 1
        for (consumer_id, model_id), (calls, errors) in aggregated.items():
            row = db.scalar(
                select(ModelConsumerUsage).where(
                    ModelConsumerUsage.consumer_id == consumer_id,
                    ModelConsumerUsage.model_id == model_id,
                    ModelConsumerUsage.recorded_day == day,
                )
            )
            if row is None:
                # 显式初始化计数：DB 的 server_default 只作用于 INSERT，内存属性仍是 None
                row = ModelConsumerUsage(
                    consumer_id=consumer_id, model_id=model_id, recorded_day=day,
                    call_count=0, error_count=0,
                )
                db.add(row)
            row.call_count += calls
            row.error_count += errors
            row.last_seen_at = local_now()
            rows_written += 1
        db.commit()
        return {
            "scanned": scanned,
            "no_log": no_log,
            "with_calls": with_calls,
            "unknown_ips": len(unknown_ips),
            "rows_written": rows_written,
        }
    finally:
        db.close()
