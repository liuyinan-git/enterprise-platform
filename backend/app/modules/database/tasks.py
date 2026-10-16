"""数据库模块周期任务：实例健康探测。"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.timeutil import local_now
from app.modules.database.models import DatabaseHealth, DatabaseInstance
from app.modules.database.services import probe_instance
from app.tasks.celery_app import celery_app


@celery_app.task(name="check_database_health")
def check_database_health_task() -> dict:
    """周期探测启用中的数据库实例，更新 health_status 并写入健康记录。"""
    db = SessionLocal()
    healthy = 0
    unhealthy = 0
    try:
        instances = db.scalars(select(DatabaseInstance).where(DatabaseInstance.enabled.is_(True))).all()
        now = local_now()
        for inst in instances:
            ok_flag, latency, message = probe_instance(inst)
            inst.health_status = "healthy" if ok_flag else "unhealthy"
            inst.last_check_at = now
            db.add(DatabaseHealth(
                instance_id=inst.id,
                check_type="connection",
                status="healthy" if ok_flag else "unhealthy",
                latency_ms=latency,
                detail={"message": message},
                checked_at=now,
            ))
            if ok_flag:
                healthy += 1
            else:
                unhealthy += 1
        db.commit()
        return {"healthy": healthy, "unhealthy": unhealthy}
    finally:
        db.close()
