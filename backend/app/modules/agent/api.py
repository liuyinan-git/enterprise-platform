from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, require_permission
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.modules.agent.container_api import router as container_router
from app.modules.agent.endpoint_api import router as endpoint_router
from app.modules.agent.models import AgentAudit, AgentEndpoint, AgentRegistry
from app.modules.agent.overview_api import router as overview_router
from app.modules.agent.project_api import router as project_router
from app.modules.agent.schemas import AgentIn, AgentUpdate
from app.modules.agent.services import agent_status, load_container_index, record_audit

router = APIRouter(
    prefix="/api/v1",
    tags=["agent"],
    dependencies=[Depends(require_permission("agent:view"))],
)

# AI Agent 平台的四个子 router 并入本 router：因此改 main.py 的事情一件都不用做。
# 读权限由本 router 的 require_permission("agent:view") 覆盖；写接口再逐路由加严。
# 路径写成 "/agent/...", 叠加本 router 的 "/api/v1" 前缀后即 "/api/v1/agent/..."。
router.include_router(container_router)
router.include_router(project_router)
router.include_router(endpoint_router)
router.include_router(overview_router)


def _identity(user: CurrentUser) -> dict:
    """审计里保存身份快照：user_id 稳定、roles/permissions 记录当时的授权。"""
    return {
        "user_id": user.user_id,
        "roles": sorted(user.roles),
        "permissions": sorted(user.permissions),
    }


def _serialize(a: AgentRegistry, container: dict | None = None, docker_ok: bool = True) -> dict:
    """智能体台账 + 绑定的容器实况（Docker 不可达时容器字段为空、状态 unknown）。"""
    return {
        "id": a.id,
        "agent_id": a.agent_id,
        "agent_name": a.agent_name,
        "agent_type": a.agent_type,
        "container_name": a.container_name,
        "container_id": (container or {}).get("container_id"),
        "container_state": (container or {}).get("state"),
        "container_status": (container or {}).get("status"),
        "container_image": (container or {}).get("image"),
        "container_ports": (container or {}).get("ports") or [],
        "container_created_at": (container or {}).get("created_at"),
        "project_key": (container or {}).get("project_key"),
        "project_name": (container or {}).get("project_name"),
        "container_found": container is not None,
        "container_protected": bool((container or {}).get("protected")),
        "container_protected_reason": (container or {}).get("protected_reason"),
        "version": a.version,
        "owner": a.owner,
        "environment": a.environment,
        "enabled": a.enabled,
        "attributes": a.attributes,
        "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
        "offline_alerted_at": a.offline_alerted_at.isoformat() if a.offline_alerted_at else None,
        "status": agent_status(a, container, docker_ok),
    }


def _serialize_one(db: Session, agent: AgentRegistry) -> dict:
    index, error = load_container_index(db)
    container = index.get(agent.container_name) if agent.container_name else None
    return _serialize(agent, container, docker_ok=error is None)


def _assert_container_free(db: Session, container_name: str | None, agent_id: str) -> None:
    """容器名全局唯一：一个容器只能绑定一个智能体（库里还有唯一索引兜并发）。"""
    if not container_name:
        return
    other = db.scalar(
        select(AgentRegistry).where(
            AgentRegistry.container_name == container_name,
            AgentRegistry.agent_id != agent_id,
        )
    )
    if other is not None:
        raise HTTPException(
            status_code=409,
            detail=f"容器 {container_name} 已绑定智能体「{other.agent_name}」({other.agent_id})",
        )


@router.get("/agents")
def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    agent_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="按 agent_id / 名称 / 容器名模糊搜索"),
    db: Session = Depends(get_db),
):
    stmt = select(AgentRegistry)
    if agent_type:
        stmt = stmt.where(AgentRegistry.agent_type == agent_type)
    if enabled is not None:
        stmt = stmt.where(AgentRegistry.enabled.is_(enabled))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                AgentRegistry.agent_id.like(like),
                AgentRegistry.agent_name.like(like),
                AgentRegistry.container_name.like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(AgentRegistry.updated_at)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    index, error = load_container_index(db)
    items = [
        _serialize(a, index.get(a.container_name) if a.container_name else None, docker_ok=error is None)
        for a in rows
    ]
    return paginated(items, total, page, page_size, extra={"degraded": error is not None, "error": error})


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def register_agent(
    payload: AgentIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("agent:manage")),
):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == payload.agent_id))
    is_new = agent is None
    _assert_container_free(db, payload.container_name, payload.agent_id)
    if agent is None:
        agent = AgentRegistry(agent_id=payload.agent_id, agent_name=payload.agent_name, agent_type=payload.agent_type)
        db.add(agent)
    agent.agent_name = payload.agent_name
    agent.agent_type = payload.agent_type
    agent.container_name = payload.container_name
    agent.version = payload.version
    agent.owner = payload.owner
    agent.environment = payload.environment
    agent.enabled = payload.enabled
    if payload.attributes is not None:
        agent.attributes = payload.attributes
    record_audit(
        db,
        payload.agent_id,
        "register" if is_new else "upsert",
        operator=user.username,
        detail={
            **_identity(user),
            "is_new": is_new,
            "container_name": payload.container_name,
        },
    )
    try:
        db.commit()
    except IntegrityError:
        # 唯一索引兜住并发登记同名容器；预检查只负责给出友好提示
        db.rollback()
        raise HTTPException(status_code=409, detail="容器名已被其他智能体绑定")
    db.refresh(agent)
    return created(_serialize_one(db, agent), message="created" if is_new else "updated")


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return ok(_serialize_one(db, agent))


@router.patch("/agents/{agent_id}")
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("agent:manage")),
):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    changed: list[str] = []
    for field in ("agent_name", "agent_type", "version", "owner", "environment", "enabled", "attributes"):
        value = getattr(payload, field)
        if value is not None:
            if getattr(agent, field) != value:
                changed.append(field)
            setattr(agent, field, value)
    # container_name 支持显式清空：只有请求里带了该字段才处理，空串已在 schema 归一为 None
    if "container_name" in payload.model_fields_set:
        _assert_container_free(db, payload.container_name, agent_id)
        if agent.container_name != payload.container_name:
            changed.append("container_name")
        agent.container_name = payload.container_name
    record_audit(
        db,
        agent_id,
        "update",
        operator=user.username,
        detail={**_identity(user), "changed": changed},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="容器名已被其他智能体绑定")
    db.refresh(agent)
    return ok(_serialize_one(db, agent))


@router.delete("/agents/{agent_id}")
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("agent:manage")),
):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    # 端点不做 FK，删智能体前必须显式处理绑定关系，避免留下悬挂的 agent_id
    bound = db.scalar(
        select(func.count()).select_from(AgentEndpoint).where(AgentEndpoint.agent_id == agent_id)
    ) or 0
    if bound:
        raise HTTPException(
            status_code=409,
            detail=f"该智能体仍绑定 {bound} 个接口监控端点，请先删除或改绑端点后再删除智能体",
        )
    agent_name = agent.agent_name
    db.delete(agent)
    record_audit(
        db,
        agent_id,
        "delete",
        operator=user.username,
        detail={**_identity(user), "agent_name": agent_name},
    )
    db.commit()
    return ok({"agent_id": agent_id}, message="deleted")


@router.get("/agent-audits")
def list_agent_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    agent_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentAudit)
    if agent_id:
        stmt = stmt.where(AgentAudit.agent_id == agent_id)
    if operator:
        stmt = stmt.where(AgentAudit.operator == operator)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(AgentAudit.id)).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "action": r.action,
            "operator": r.operator,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return paginated(items, total, page, page_size)
