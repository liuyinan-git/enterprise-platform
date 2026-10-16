from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import local_now
from app.modules.agent.models import AgentAudit, AgentRegistry


def agent_status(agent: AgentRegistry) -> str:
    """按最后心跳时间判定在线/离线（宽限阈值见配置 agent_offline_grace_seconds）。"""
    if not agent.enabled:
        return "disabled"
    if agent.last_seen_at is None:
        return "offline"
    grace = settings.agent_offline_grace_seconds
    return "online" if (local_now() - agent.last_seen_at).total_seconds() <= grace else "offline"


def record_audit(
    db: Session,
    agent_id: str,
    action: str,
    operator: str | None = None,
    detail: dict | list | None = None,
) -> None:
    """写入一条智能体操作审计记录。"""
    db.add(AgentAudit(agent_id=agent_id, action=action, operator=operator, detail=detail))
