from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.core.security import mask_secret
from app.core.timeutil import local_now
from app.modules.database import containers as container_rules
from app.modules.database import docker_client
from app.modules.database.container_api import router as container_router
from app.modules.database.models import DatabaseBackup, DatabaseHealth, DatabaseInstance
from app.modules.database.schemas import BackupIn, InstanceIn, InstanceUpdate
from app.modules.database.services import probe_instance

router = APIRouter(
    prefix="/api/v1",
    tags=["database"],
    dependencies=[Depends(require_permission("database:view"))],
)

# 容器实况接口并入本 router：因此改 main.py 的事情一件都不用做。
# container_api 的路径写成 "/database-containers"，叠加本 router 的 "/api/v1" 前缀后
# 对外即 "/api/v1/database-containers"。
router.include_router(container_router)


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


@router.get("/database-overview")
def database_overview(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    include_protected: bool = Query(default=False),
    unregistered_scope: str = Query(default="managed", pattern="^(managed|all)$"),
    unregistered_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """台账 + 容器实况的合并视图（「数据库实例」页用）。

    `unregistered_scope`：`managed`（默认）只列受管类型——宿主机上跑的应用容器
    （kafka、后端、前端……）不是本平台的纳管对象，全列出来只会把真正要纳管的
    数据库淹掉；`all` 则连未分类的一起列。

    Docker 不可达时**不报错**：返回 200 + `degraded`，由页面显示告警条，
    而不是整页红屏。
    """
    stmt = select(DatabaseInstance)
    if db_type:
        stmt = stmt.where(DatabaseInstance.db_type == db_type)
    if enabled is not None:
        stmt = stmt.where(DatabaseInstance.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(DatabaseInstance.id).offset((page - 1) * page_size).limit(page_size)).all()

    degraded, error = False, None
    try:
        live = [container_rules.serialize_container(c) for c in docker_client.list_containers()]
    except docker_client.DockerUnavailable as exc:
        live, degraded, error = [], True, str(exc)
    index = container_rules.build_container_index(live)

    # 「未登记」必须覆盖**全部**台账行而不只是当前页，否则第 2 页才关联上的容器
    # 会被误报为未登记。
    linked_ids: set[str] = set()
    for code, attributes in db.execute(select(DatabaseInstance.instance_code, DatabaseInstance.attributes)).all():
        hit, _ = container_rules.resolve_instance_container(code, attributes, index)
        if hit:
            linked_ids.add(hit["full_id"])
    unregistered = [
        c for c in live
        if c["full_id"] not in linked_ids and (include_protected or not c["protected"])
    ]
    # 默认只留受管类型。被滤掉的数量一并返回，前端据此显示「另有 N 个未分类容器」，
    # 让隐藏是**可见的**——静默省略会让人误以为宿主机上只有这几个容器。
    hidden_unknown = 0
    if unregistered_scope == "managed":
        hidden_unknown = sum(1 for c in unregistered if c["managed_type"] == "unknown")
        unregistered = [c for c in unregistered if c["managed_type"] != "unknown"]
    if unregistered_type:
        unregistered = [c for c in unregistered if c["managed_type"] == unregistered_type]

    items = []
    for inst in rows:
        payload = _serialize_instance(inst)
        hit, source = container_rules.resolve_instance_container(inst.instance_code, inst.attributes, index)
        payload["container"] = hit
        payload["container_link"] = source
        payload["refusal_reason"] = container_rules.refusal_reason(hit) if hit else "未找到对应容器"
        items.append(payload)

    return ok({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "unregistered": unregistered,
        "unregistered_total": len(unregistered),
        "containers_total": len(live),
        "degraded": degraded,
        "error": error,
        "generated_at": local_now().isoformat(),
    })


@router.post("/database-instances", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("database:manage"))])
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


@router.put("/database-instances/{code}", dependencies=[Depends(require_permission("database:manage"))])
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


@router.delete("/database-instances/{code}", dependencies=[Depends(require_permission("database:manage"))])
def delete_instance(code: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(DatabaseInstance).where(DatabaseInstance.instance_code == code))
    if inst is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    db.delete(inst)
    db.commit()
    return ok({"instance_code": code}, message="deleted")


@router.post("/database-instances/{code}/check", dependencies=[Depends(require_permission("database:manage"))])
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


@router.post("/database-backups", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("database:manage"))])
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
