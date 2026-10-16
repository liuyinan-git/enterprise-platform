from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.core.security import mask_secret
from app.core.timeutil import local_now
from app.modules.model.models import ModelProvider, ModelRegistry, ModelUsage
from app.modules.model.schemas import ModelIn, ModelUpdate, ProviderIn, ProviderUpdate, UsageIn
from app.modules.model.services import probe_provider

router = APIRouter(prefix="/api/v1", tags=["model"])


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
        "version": m.version,
        "context_window": m.context_window,
        "parameters": m.parameters,
        "enabled": m.enabled,
        "health_status": m.health_status,
        "last_check_at": m.last_check_at.isoformat() if m.last_check_at else None,
    }


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


@router.post("/model-providers", status_code=status.HTTP_201_CREATED)
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


@router.put("/model-providers/{code}")
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


@router.delete("/model-providers/{code}")
def delete_provider(code: str, db: Session = Depends(get_db)):
    provider = db.scalar(select(ModelProvider).where(ModelProvider.provider_code == code))
    if provider is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
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
    return paginated(items, total, page, page_size)


@router.post("/models", status_code=status.HTTP_201_CREATED)
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
        version=payload.version,
        context_window=payload.context_window,
        parameters=payload.parameters,
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
    return ok(_serialize_model(model, provider.provider_code if provider else None, provider.provider_name if provider else None))


@router.put("/models/{code}")
def update_model(code: str, payload: ModelUpdate, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    for field in ("model_name", "version", "context_window", "parameters", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(model, field, value)
    db.commit()
    db.refresh(model)
    provider = db.get(ModelProvider, model.provider_id)
    return ok(_serialize_model(model, provider.provider_code if provider else None, provider.provider_name if provider else None))


@router.delete("/models/{code}")
def delete_model(code: str, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    db.delete(model)
    db.commit()
    return ok({"model_code": code}, message="deleted")


@router.post("/models/{code}/check")
def check_model(code: str, db: Session = Depends(get_db)):
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_code == code))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    provider = db.get(ModelProvider, model.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="关联供应商不存在")
    ok_flag, message = probe_provider(provider)
    model.health_status = "healthy" if ok_flag else "unhealthy"
    model.last_check_at = local_now()
    db.commit()
    return ok({"model_code": code, "health_status": model.health_status, "detail": message})


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


@router.post("/model-usages", status_code=status.HTTP_201_CREATED)
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
