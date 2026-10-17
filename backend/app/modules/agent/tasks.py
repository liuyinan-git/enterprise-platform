"""智能体模块周期任务：心跳超时检测、端点健康探测、监控历史清理。"""

from datetime import timedelta

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.timeutil import local_now
from app.modules.agent.agent_config import agent_settings
from app.modules.agent.models import AgentEndpoint, AgentHealthHistory
from app.modules.agent.services import check_endpoint, detect_offline_agents
from app.tasks.celery_app import celery_app


@celery_app.task(name="check_agent_offline")
def check_agent_offline_task() -> dict:
    """周期检测心跳超时并告警（每个离线周期只发一次）。

    返回 `checked/offline/alerted/notify_failed/skipped`，通知失败会在下个周期
    自动重试，所以 `notify_failed > 0` 不是丢告警，只是本轮没发出去。
    """
    db = SessionLocal()
    try:
        return detect_offline_agents(db)
    finally:
        db.close()


@celery_app.task(name="check_agent_endpoints")
def check_agent_endpoints_task() -> dict:
    """周期探测全部启用中的端点，更新快照并写入监控历史。

    串行探测：端点数量在内网是几十个量级，串行比并发更容易定位问题，
    也不会在 Docker / 目标服务已经吃紧时再叠一层并发压力。
    """
    db = SessionLocal()
    summary = {"healthy": 0, "unhealthy": 0, "timeout": 0, "error": 0}
    try:
        endpoints = db.scalars(
            select(AgentEndpoint).where(AgentEndpoint.enabled.is_(True)).order_by(AgentEndpoint.endpoint_code)
        ).all()
        for endpoint in endpoints:
            result = check_endpoint(db, endpoint, check_type="scheduled")
            summary[result["status"]] = summary.get(result["status"], 0) + 1
        db.commit()
        return {"total": len(endpoints), **summary}
    finally:
        db.close()


@celery_app.task(name="cleanup_agent_history")
def cleanup_agent_history_task() -> int:
    """按 AGENT_HISTORY_RETENTION_DAYS 清理过期的监控历史，返回删除行数。

    配了保留天数就必须有人清理，否则这个配置项是在撒谎（与 log 模块的
    `cleanup_retention` 同构）。
    """
    days = max(1, agent_settings.agent_history_retention_days)
    cutoff = local_now() - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(delete(AgentHealthHistory).where(AgentHealthHistory.checked_at < cutoff))
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()
