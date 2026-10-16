"""模型模块周期任务：端点健康探测。"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.timeutil import local_now
from app.modules.model.models import ModelProvider, ModelRegistry
from app.modules.model.services import probe_provider
from app.tasks.celery_app import celery_app


@celery_app.task(name="check_model_endpoints")
def check_model_endpoints_task() -> dict:
    """周期探测启用中的模型端点，更新 health_status。"""
    db = SessionLocal()
    healthy = 0
    unhealthy = 0
    try:
        providers = {p.id: p for p in db.scalars(select(ModelProvider)).all()}
        models = db.scalars(select(ModelRegistry).where(ModelRegistry.enabled.is_(True))).all()
        for model in models:
            provider = providers.get(model.provider_id)
            if provider is None:
                continue
            ok_flag, message = probe_provider(provider)
            model.health_status = "healthy" if ok_flag else "unhealthy"
            model.last_check_at = local_now()
            if ok_flag:
                healthy += 1
            else:
                unhealthy += 1
        db.commit()
        return {"healthy": healthy, "unhealthy": unhealthy}
    finally:
        db.close()
