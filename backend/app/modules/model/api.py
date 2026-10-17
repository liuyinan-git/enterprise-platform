from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.core.security import mask_secret
from app.core.timeutil import local_now
from app.modules.model.models import (
    ModelAlert,
    ModelConsumer,
    ModelConsumerRel,
    ModelHealth,
    ModelProvider,
    ModelRegistry,
    ModelUsage,
)
from app.modules.model.schemas import (
    ConsumerIn,
    ConsumerUpdate,
    ModelIn,
    ModelUpdate,
    ProviderIn,
    ProviderUpdate,
    UsageIn,
)
from app.modules.model.services import probe_model
from app.modules.model.services.alerting import _send_model_alert, process_probe_result
from app.modules.model.services.container_live import annotate_failure, container_snapshot

router = APIRouter(
    prefix="/api/v1",
    tags=["model"],
    dependencies=[Depends(require_permission("model:view"))],
)


def _serialize_provider(p: ModelProvider) -> dict:
    return {
        "id": p.id,
        "provider_code": p.provider_code,
        "provider_name": p.provider_name,
        "provider_type": p.provider_type,
        "base_url": p.base_url,
        "api_key_masked": mask_secret(p.api_key),
        "enabled": p.enabled,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_model(m: ModelRegistry, provider_code: str | None = None, provider_name: str | None = None) -> dict:
    return {
        "id": m.id,
        "model_code": m.model_code,
        "provider_id": m.provider_id,
        "provider_code": provider_code,
        "provider_name": provider_name,
        "model_name": m.model_name,
        "service_type": m.service_type,
        "endpoint_url": m.endpoint_url,
        "probe_method": m.probe_method,
        "engine": m.engine,
        "version": m.version,
        "context_window": m.context_window,
        "parameters": m.parameters,
        "enabled": m.enabled,
        "health_status": m.health_status,
        "last_check_at": m.last_check_at.isoformat() if m.last_check_at else None,
        "metrics_metric": m.metrics_metric,
        "consecutive_failures": m.consecutive_failures,
    }


def _attach_container_status(items: list[dict]) -> None:
    """就地合并容器实况字段（一次快照；代理未启用/不可达时全为 None → 前端显示 unknown）。"""
    snap = container_snapshot()
    for item in items:
        info = snap.get(item.get("model_code") or "")
        item["container_status"] = info.get("container_status") if info else None
        item["container_status_text"] = info.get("container_status_text") if info else None


@router.get("/model-providers")
def list_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    provider_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(ModelProvider)
    if provider_type:
        stmt = stmt.where(ModelProvider.provider_type == provider_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ModelProvider.id).offset((page - 1) * page_size).limit(page_size)).all()
    return paginated([_serialize_provider(p) for p in rows], total, page, page_size)


@router.post("/model-providers", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("model:manage"))])
def create_provider(payload: ProviderIn, db: Session = Depends(get_db)):
    if db.scalar(select(ModelProvider.id).where(ModelProvider.provider_code == payload.provider_code)):
        raise HTTPException(status_code=409, detail=f"供应商 {payload.provider_code} 已存在")
    provider = ModelProvider(
        provider_code=payload.provider_code,
        provider_name=payload.provider_name,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        enabled=payload.enabled,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return created(_serialize_provider(provider))


@router.get("/model-providers/{code}")
def get_provider(code: str, db: Session = Depends(get_db)):
    provider = db.scalar(select(ModelProvider).where(ModelProvider.provider_code == code))
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return ok(_serialize_provider(provider))


@router.put("/model-providers/{code}", dependencies=[Depends(require_permission("model:manage"))])
def update_provider(code: str, payload: ProviderUpdate, db: Session = Depends(get_db)):
    provider = db.scalar(select(ModelProvider).where(ModelProvider.provider_code == code))
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    for field in ("provider_name", "provider_type", "base_url", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(provider, field, value)
    if payload.api_key and not payload.api_key.startswith("****"):
        provider.api_key = payload.api_key
    db.commit()
    db.refresh(provider)
    return ok(_serialize_provider(provider))


@router.delete("/model-providers/{code}", dependencies=[Depends(require_permission("model:manage"))])
def delete_provider(code: str, db: Session = Depends(get_db)):
    provider = db.scalar(select(ModelProvider).where(ModelProvider.provider_code == code))
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    model_count = db.scalar(
        select(func.count()).select_from(ModelRegistry).where(ModelRegistry.provider_id == provider.id)
    ) or 0
    if model_count:
        raise HTTPException(status_code=409, detail=f"供应商下仍有 {model_count} 个模型，请先删除或迁移这些模型")
    db.delete(provider)
    db.commit()
    return ok({"provider_code": code}, message="deleted")


@router.get("/models")
def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    provider_code: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(ModelRegistry)
    if provider_code:
        stmt = stmt.join(ModelProvider, ModelProvider.id == ModelRegistry.provider_id).where(
            ModelProvider.provider_code == provider_code
        )
    if enabled is not None:
        stmt = stmt.where(ModelRegistry.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ModelRegistry.id).offset((page - 1) * page_size).limit(page_size)).all()
    providers = {p.id: p for p in db.scalars(select(ModelProvider)).all()}
    items = [_serialize_model(m, providers[m.provider_id].provider_code if m.provider_id in providers else None,
                              providers[m.provider_id].provider_name if m.provider_id in providers else None) for m in rows]
    _attach_container_status(items)
    return paginated(items, total, page, page_size)


@router.post("/models", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("model:manage"))])
def create_model(payload: ModelIn, db: Session = Depends(get_db)):
    if db.scalar(select(ModelRegistry.id).where(ModelRegistry.model_code == payload.model_code)):
        raise HTTPException(status_code=409, detail=f"模型 {payload.model_code} 已存在")
    provider = db.scalar(select(ModelProvider).where(ModelProvider.provider_code == payload.provider_code))
    if provider is None:
        raise HTTPException(status_code=404, detail=f"供应商 {payload.provider_code} 不存在")
    model = ModelRegistry(
        model_code=payload.model_code,
        provider_id=provider.id,
        model_name=payload.model_name,
        service_type=payload.service_type,
        endpoint_url=payload.endpoint_url,
        probe_method=payload.probe_method,
        engine=payload.engine,
        version=payload.version,
        context_window=payload.context_window,
        parameters=payload.parameters,
        metrics_metric=payload.metrics_metric,
        enabled=payload.enabled,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return created(_serialize_model(model, provider.provider_code, provider.provider_name))


@router.get("/models/{code}")
def get_model(code: str, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    provider = db.get(ModelProvider, model.provider_id)
    item = _serialize_model(model, provider.provider_code if provider else None, provider.provider_name if provider else None)
    _attach_container_status([item])
    return ok(item)


@router.put("/models/{code}", dependencies=[Depends(require_permission("model:manage"))])
def update_model(code: str, payload: ModelUpdate, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    for field in (
        "model_name", "service_type", "endpoint_url", "probe_method", "engine",
        "version", "context_window", "parameters", "metrics_metric", "enabled",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(model, field, value)
    db.commit()
    db.refresh(model)
    provider = db.get(ModelProvider, model.provider_id)
    return ok(_serialize_model(model, provider.provider_code if provider else None, provider.provider_name if provider else None))


@router.delete("/models/{code}", dependencies=[Depends(require_permission("model:manage"))])
def delete_model(code: str, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    # 先清子表引用（health/usage/consumer_rel/alert 均有 FK，直接删主行会被外键约束拒绝）
    for child in (ModelHealth, ModelUsage, ModelConsumerRel, ModelAlert):
        db.query(child).filter(child.model_id == model.id).delete()
    db.delete(model)
    db.commit()
    return ok({"model_code": code}, message="deleted")


@router.post("/models/{code}/check", dependencies=[Depends(require_permission("model:manage"))])
def check_model(code: str, db: Session = Depends(get_db)):
    """手动探测单个模型服务（按 probe_method 分层），并落健康历史；同步驱动告警状态机。"""
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    provider = db.get(ModelProvider, model.provider_id)
    ok_flag, latency_ms, message = probe_model(model, provider)
    if not ok_flag:  # 失败时标注容器状态（容器挂了 vs 服务无响应），告警内容同步受益
        message = annotate_failure(message or "", model.model_code, container_snapshot())
    action = process_probe_result(db, model, ok_flag, message or "")
    if model.probe_method == "none":
        model.health_status = "unknown"
    else:
        model.health_status = "healthy" if ok_flag else "unhealthy"
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
    return ok(
        {
            "model_code": code,
            "health_status": model.health_status,
            "latency_ms": latency_ms,
            "detail": message,
            "alert_action": action,
        }
    )


@router.get("/model-health")
def list_model_health(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """模型服务健康检查历史（趋势 / 状态灯依据）。"""
    stmt = select(ModelHealth)
    if model_code:
        stmt = stmt.join(ModelRegistry, ModelRegistry.id == ModelHealth.model_id).where(
            ModelRegistry.model_code == model_code
        )
    if status:
        stmt = stmt.where(ModelHealth.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(ModelHealth.checked_at)).offset((page - 1) * page_size).limit(page_size)).all()
    models = {m.id: m.model_code for m in db.scalars(select(ModelRegistry)).all()}
    items = [
        {
            "id": h.id,
            "model_id": h.model_id,
            "model_code": models.get(h.model_id),
            "status": h.status,
            "latency_ms": h.latency_ms,
            "message": h.message,
            "checked_at": h.checked_at.isoformat() if h.checked_at else None,
        }
        for h in rows
    ]
    return paginated(items, total, page, page_size)


@router.get("/model-usages")
def list_usages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(ModelUsage)
    if model_code:
        stmt = stmt.join(ModelRegistry, ModelRegistry.id == ModelUsage.model_id).where(ModelRegistry.model_code == model_code)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(ModelUsage.recorded_day)).offset((page - 1) * page_size).limit(page_size)).all()
    models = {m.id: m.model_code for m in db.scalars(select(ModelRegistry)).all()}
    items = [
        {
            "id": u.id,
            "model_id": u.model_id,
            "model_code": models.get(u.model_id),
            "call_count": u.call_count,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "recorded_day": u.recorded_day,
        }
        for u in rows
    ]
    return paginated(items, total, page, page_size)


@router.post("/model-usages", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("model:manage"))])
def record_usage(payload: UsageIn, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == payload.model_code))
    if model is None:
        raise HTTPException(status_code=404, detail=f"模型 {payload.model_code} 不存在")
    usage = db.scalar(
        select(ModelUsage).where(ModelUsage.model_id == model.id, ModelUsage.recorded_day == payload.recorded_day)
    )
    if usage is None:
        usage = ModelUsage(model_id=model.id, recorded_day=payload.recorded_day)
        db.add(usage)
    usage.call_count += payload.call_count
    usage.input_tokens += payload.input_tokens
    usage.output_tokens += payload.output_tokens
    db.commit()
    db.refresh(usage)
    return created({"id": usage.id, "model_code": payload.model_code, "recorded_day": usage.recorded_day})


# ===== 调用方台账 =====


def _consumer_model_codes(db: Session, consumer_id: int) -> list[str]:
    rows = db.scalars(
        select(ModelRegistry.model_code)
        .join(ModelConsumerRel, ModelConsumerRel.model_id == ModelRegistry.id)
        .where(ModelConsumerRel.consumer_id == consumer_id)
        .order_by(ModelRegistry.model_code)
    ).all()
    return list(rows)


def _serialize_consumer(db: Session, c: ModelConsumer) -> dict:
    return {
        "id": c.id,
        "consumer_code": c.consumer_code,
        "consumer_name": c.consumer_name,
        "identity_type": c.identity_type,
        "identifier": c.identifier,
        "contact": c.contact,
        "remark": c.remark,
        "evidence": c.evidence,
        "model_codes": _consumer_model_codes(db, c.id),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _replace_consumer_models(db: Session, consumer_id: int, model_codes: list[str]) -> None:
    """全删全插中间表；model_code 不存在直接 404。"""
    models = []
    for code in dict.fromkeys(model_codes):
        model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
        if model is None:
            raise HTTPException(status_code=404, detail=f"模型 {code} 不存在")
        models.append(model)
    db.query(ModelConsumerRel).filter(ModelConsumerRel.consumer_id == consumer_id).delete()
    for model in models:
        db.add(ModelConsumerRel(consumer_id=consumer_id, model_id=model.id))


@router.get("/model-consumers")
def list_consumers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model_code: str | None = Query(default=None, description="按模型反查调用方（影响面分析）"),
    identity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(ModelConsumer)
    if identity_type:
        stmt = stmt.where(ModelConsumer.identity_type == identity_type)
    if model_code:
        stmt = (
            stmt.join(ModelConsumerRel, ModelConsumerRel.consumer_id == ModelConsumer.id)
            .join(ModelRegistry, ModelRegistry.id == ModelConsumerRel.model_id)
            .where(ModelRegistry.model_code == model_code)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ModelConsumer.id).offset((page - 1) * page_size).limit(page_size)).all()
    return paginated([_serialize_consumer(db, c) for c in rows], total, page, page_size)


@router.post("/model-consumers", status_code=status.HTTP_201_CREATED)
def create_consumer(payload: ConsumerIn, db: Session = Depends(get_db)):
    if db.scalar(select(ModelConsumer.id).where(ModelConsumer.consumer_code == payload.consumer_code)):
        raise HTTPException(status_code=409, detail=f"调用方 {payload.consumer_code} 已存在")
    consumer = ModelConsumer(
        consumer_code=payload.consumer_code,
        consumer_name=payload.consumer_name,
        identity_type=payload.identity_type,
        identifier=payload.identifier,
        contact=payload.contact,
        remark=payload.remark,
        evidence=payload.evidence,
    )
    db.add(consumer)
    db.flush()
    _replace_consumer_models(db, consumer.id, payload.model_codes)
    db.commit()
    db.refresh(consumer)
    return created(_serialize_consumer(db, consumer))


@router.get("/model-consumers/{code}")
def get_consumer(code: str, db: Session = Depends(get_db)):
    consumer = db.scalar(select(ModelConsumer).where(ModelConsumer.consumer_code == code))
    if consumer is None:
        raise HTTPException(status_code=404, detail="调用方不存在")
    return ok(_serialize_consumer(db, consumer))


@router.put("/model-consumers/{code}")
def update_consumer(code: str, payload: ConsumerUpdate, db: Session = Depends(get_db)):
    consumer = db.scalar(select(ModelConsumer).where(ModelConsumer.consumer_code == code))
    if consumer is None:
        raise HTTPException(status_code=404, detail="调用方不存在")
    for field in ("consumer_name", "identity_type", "identifier", "contact", "remark", "evidence"):
        value = getattr(payload, field)
        if value is not None:
            setattr(consumer, field, value)
    if payload.model_codes is not None:
        _replace_consumer_models(db, consumer.id, payload.model_codes)
    db.commit()
    db.refresh(consumer)
    return ok(_serialize_consumer(db, consumer))


@router.delete("/model-consumers/{code}")
def delete_consumer(code: str, db: Session = Depends(get_db)):
    consumer = db.scalar(select(ModelConsumer).where(ModelConsumer.consumer_code == code))
    if consumer is None:
        raise HTTPException(status_code=404, detail="调用方不存在")
    db.query(ModelConsumerRel).filter(ModelConsumerRel.consumer_id == consumer.id).delete()
    db.delete(consumer)
    db.commit()
    return ok({"consumer_code": code}, message="deleted")


# ===== 模型告警 =====


@router.get("/model-alerts")
def list_model_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model_code: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    alert_status: str | None = Query(default=None, description="pending/sent/failed"),
    db: Session = Depends(get_db),
):
    stmt = select(ModelAlert)
    if model_code:
        stmt = stmt.join(ModelRegistry, ModelRegistry.id == ModelAlert.model_id).where(
            ModelRegistry.model_code == model_code
        )
    if alert_type:
        stmt = stmt.where(ModelAlert.alert_type == alert_type)
    if alert_status:
        stmt = stmt.where(ModelAlert.status == alert_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(ModelAlert.id)).offset((page - 1) * page_size).limit(page_size)).all()
    models = {m.id: m.model_code for m in db.scalars(select(ModelRegistry)).all()}
    items = [
        {
            "id": a.id,
            "alert_no": a.alert_no,
            "model_id": a.model_id,
            "model_code": models.get(a.model_id),
            "alert_type": a.alert_type,
            "channel": a.channel,
            "receiver_key": a.receiver_key,
            "message_content": a.message_content,
            "status": a.status,
            "attempt_count": a.attempt_count,
            "next_retry_at": a.next_retry_at.isoformat() if a.next_retry_at else None,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "last_error": a.last_error,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
    return paginated(items, total, page, page_size)


@router.post("/model-alerts/{alert_no}/retry")
def retry_model_alert(alert_no: str, db: Session = Depends(get_db)):
    """手动重试单条告警（对齐 log 模块 retry_alert 模式）。"""
    alert = db.scalar(select(ModelAlert).where(ModelAlert.alert_no == alert_no))
    if alert is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alert.status == "sent":
        raise HTTPException(status_code=400, detail="告警已送达，无需重试")
    _send_model_alert(db, alert)
    db.commit()
    db.refresh(alert)
    return ok(
        {
            "alert_no": alert.alert_no,
            "status": alert.status,
            "attempt_count": alert.attempt_count,
            "last_error": alert.last_error,
        }
    )
