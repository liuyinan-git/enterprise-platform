from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.modules.agent.models import AgentAudit, AgentRegistry
from app.modules.agent.schemas import AgentIn, AgentUpdate
from app.modules.agent.services import agent_status, record_audit

router = APIRouter(
    prefix="/api/v1",
    tags=["agent"],
    dependencies=[Depends(require_roles("admin", "viewer", "agent_admin"))],
)


def _serialize(a: AgentRegistry) -> dict:
    return {
        "id": a.id,
        "agent_id": a.agent_id,
        "agent_name": a.agent_name,
        "agent_type": a.agent_type,
        "version": a.version,
        "owner": a.owner,
        "environment": a.environment,
        "enabled": a.enabled,
        "attributes": a.attributes,
        "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
        "status": agent_status(a),
    }


@router.get("/agents")
def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    agent_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentRegistry)
    if agent_type:
        stmt = stmt.where(AgentRegistry.agent_type == agent_type)
    if enabled is not None:
        stmt = stmt.where(AgentRegistry.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(AgentRegistry.updated_at)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginated([_serialize(a) for a in rows], total, page, page_size)


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentIn, db: Session = Depends(get_db)):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == payload.agent_id))
    is_new = agent is None
    if agent is None:
        agent = AgentRegistry(agent_id=payload.agent_id, agent_name=payload.agent_name, agent_type=payload.agent_type)
        db.add(agent)
    agent.agent_name = payload.agent_name
    agent.agent_type = payload.agent_type
    agent.version = payload.version
    agent.owner = payload.owner
    agent.environment = payload.environment
    agent.enabled = payload.enabled
    if payload.attributes is not None:
        agent.attributes = payload.attributes
    record_audit(db, payload.agent_id, "register" if is_new else "upsert")
    db.commit()
    db.refresh(agent)
    return created(_serialize(agent), message="created" if is_new else "updated")


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return ok(_serialize(agent))


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: str, payload: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    for field in ("agent_name", "agent_type", "version", "owner", "environment", "enabled", "attributes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(agent, field, value)
    record_audit(db, agent_id, "update")
    db.commit()
    db.refresh(agent)
    return ok(_serialize(agent))


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    db.delete(agent)
    record_audit(db, agent_id, "delete")
    db.commit()
    return ok({"agent_id": agent_id}, message="deleted")


@router.get("/agent-audits")
def list_agent_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    agent_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentAudit)
    if agent_id:
        stmt = stmt.where(AgentAudit.agent_id == agent_id)
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
