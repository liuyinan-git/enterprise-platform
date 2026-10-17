from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.response import ok
from app.core.security import require_collector_key
from app.core.timeutil import local_now
from app.modules.agent.models import AgentRegistry
from app.modules.agent.services import notify_agent_recovered, record_audit

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

    now = local_now()
    agent.last_seen_at = now

    # 有容器名的智能体由 check_agent_offline 按容器状态判定恢复并清标记；
    # 心跳只负责历史行（没有容器名）的恢复语义，避免两个来源同时补发通知。
    if agent.container_name is None and agent.offline_alerted_at is not None:
        status, error = notify_agent_recovered(db, agent)
        agent.offline_alerted_at = None
        detail = {"recovered_at": now.isoformat(), "notify": "wecom" if status == "sent" else "none"}
        if error:
            detail["notify_error"] = error
        record_audit(db, agent.agent_id, "back_online", detail=detail)

    db.commit()
    return ok({"agent_id": agent_id, "last_seen_at": agent.last_seen_at.isoformat()})
