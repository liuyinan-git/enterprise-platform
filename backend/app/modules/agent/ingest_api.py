from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.response import ok
from app.core.security import require_collector_key
from app.core.timeutil import local_now
from app.modules.agent.models import AgentRegistry

ingest_router = APIRouter(prefix="/api/v1", tags=["agent-ingestion"])


@ingest_router.post("/agents/{agent_id}/heartbeat")
def agent_heartbeat(
    agent_id: str,
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    agent = db.scalar(select(AgentRegistry).where(AgentRegistry.agent_id == agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    agent.last_seen_at = local_now()
    db.commit()
    return ok({"agent_id": agent_id, "last_seen_at": agent.last_seen_at.isoformat()})
