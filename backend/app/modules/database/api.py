from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.core.security import mask_secret
from app.core.timeutil import local_now
from app.modules.database.models import DatabaseBackup, DatabaseHealth, DatabaseInstance
from app.modules.database.schemas import BackupIn, InstanceIn, InstanceUpdate
from app.modules.database.services import probe_instance

router = APIRouter(
    prefix="/api/v1",
    tags=["database"],
    dependencies=[Depends(require_roles("admin", "viewer", "database_admin"))],
)


def _serialize_instance(i: DatabaseInstance) -> dict:
    return {
        "id": i.id,
        "instance_code": i.instance_code,
        "instance_name": i.instance_name,
        "db_type": i.db_type,
        "host": i.host,
        "port": i.port,
        "database_name": i.database_name,
        "username": i.username,
        "password_masked": mask_secret(i.password),
        "environment": i.environment,
        "enabled": i.enabled,
        "attributes": i.attributes,
        "health_status": i.health_status,
        "last_check_at": i.last_check_at.isoformat() if i.last_check_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


@router.get("/database-instances")
def list_instances(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(DatabaseInstance)
    if db_type:
        stmt = stmt.where(DatabaseInstance.db_type == db_type)
    if enabled is not None:
        stmt = stmt.where(DatabaseInstance.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(DatabaseInstance.id).offset((page - 1) * page_size).limit(page_size)).all()
    return paginated([_serialize_instance(i) for i in rows], total, page, page_size)


@router.post("/database-instances", status_code=status.HTTP_201_CREATED)
def create_instance(payload: InstanceIn, db: Session = Depends(get_db)):
    if db.scalar(select(DatabaseInstance.id).where(DatabaseInstance.instance_code == payload.instance_code)):
        raise HTTPException(status_code=409, detail=f"实例 {payload.instance_code} 已存在")
    inst = DatabaseInstance(
        instance_code=payload.instance_code,
        instance_name=payload.instance_name,
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        environment=payload.environment,
        enabled=payload.enabled,
        attributes=payload.attributes,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return created(_serialize_instance(inst))


@router.get("/database-instances/{code}")
def get_instance(code: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == code))
    if inst is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    return ok(_serialize_instance(inst))


@router.put("/database-instances/{code}")
def update_instance(code: str, payload: InstanceUpdate, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == code))
    if inst is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    for field in ("instance_name", "db_type", "host", "port", "database_name", "username", "environment", "enabled", "attributes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(inst, field, value)
    if payload.password and not payload.password.startswith("****"):
        inst.password = payload.password
    db.commit()
    db.refresh(inst)
    return ok(_serialize_instance(inst))


@router.delete("/database-instances/{code}")
def delete_instance(code: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == code))
    if inst is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    db.delete(inst)
    db.commit()
    return ok({"instance_code": code}, message="deleted")


@router.post("/database-instances/{code}/check")
def check_instance(code: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == code))
    if inst is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    ok_flag, latency, message = probe_instance(inst)
    inst.health_status = "healthy" if ok_flag else "unhealthy"
    inst.last_check_at = local_now()
    db.add(DatabaseHealth(
        instance_id=inst.id,
        check_type="connection",
        status=inst.health_status,
        latency_ms=latency,
        detail={"message": message},
        checked_at=inst.last_check_at,
    ))
    db.commit()
    return ok({"instance_code": code, "health_status": inst.health_status, "latency_ms": latency, "detail": message})


@router.get("/database-health")
def list_health(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    instance_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(DatabaseHealth)
    if instance_code:
        stmt = stmt.join(DatabaseInstance, DatabaseInstance.id == DatabaseHealth.instance_id).where(
            DatabaseInstance.instance_code == instance_code
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(DatabaseHealth.checked_at)).offset((page - 1) * page_size).limit(page_size)).all()
    instances = {i.id: i.instance_code for i in db.scalars(select(DatabaseInstance)).all()}
    items = [
        {
            "id": h.id,
            "instance_id": h.instance_id,
            "instance_code": instances.get(h.instance_id),
            "check_type": h.check_type,
            "status": h.status,
            "latency_ms": h.latency_ms,
            "detail": h.detail,
            "checked_at": h.checked_at.isoformat() if h.checked_at else None,
        }
        for h in rows
    ]
    return paginated(items, total, page, page_size)


@router.get("/database-backups")
def list_backups(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    instance_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(DatabaseBackup)
    if instance_code:
        stmt = stmt.join(DatabaseInstance, DatabaseInstance.id == DatabaseBackup.instance_id).where(
            DatabaseInstance.instance_code == instance_code
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(DatabaseBackup.id)).offset((page - 1) * page_size).limit(page_size)).all()
    instances = {i.id: i.instance_code for i in db.scalars(select(DatabaseInstance)).all()}
    items = [
        {
            "id": b.id,
            "instance_id": b.instance_id,
            "instance_code": instances.get(b.instance_id),
            "backup_type": b.backup_type,
            "status": b.status,
            "size": b.size,
            "started_at": b.started_at.isoformat() if b.started_at else None,
            "finished_at": b.finished_at.isoformat() if b.finished_at else None,
            "result": b.result,
        }
        for b in rows
    ]
    return paginated(items, total, page, page_size)


@router.post("/database-backups", status_code=status.HTTP_201_CREATED)
def register_backup(payload: BackupIn, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == payload.instance_code))
    if inst is None:
        raise HTTPException(status_code=404, detail=f"实例 {payload.instance_code} 不存在")
    backup = DatabaseBackup(
        instance_id=inst.id,
        backup_type=payload.backup_type,
        status=payload.status,
        size=payload.size,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        result=payload.result,
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)
    return created({"id": backup.id, "instance_code": payload.instance_code, "status": backup.status})
