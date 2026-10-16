"""智能体模块周期任务：心跳超时检测（骨架）。"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.agent.models import AgentRegistry
from app.modules.agent.services import agent_status
from app.tasks.celery_app import celery_app


@celery_app.task(name="check_agent_offline")
def check_agent_offline_task() -> int:
    """周期检测启用中的智能体心跳是否超时，返回离线数量。"""
    db = SessionLocal()
    try:
        rows = db.scalars(select(AgentRegistry).where(AgentRegistry.enabled.is_(True))).all()
        return sum(1 for a in rows if agent_status(a) == "offline")
    finally:
        db.close()
