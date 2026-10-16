"""Celery 应用实例与定时调度（beat schedule）。

启动方式（在 backend/ 目录下）：
  celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo   # Windows 需 solo 池
  celery -A app.tasks.celery_app.celery_app beat --loglevel=info
"""

from celery import Celery

from app.core.config import settings
from app.tasks.registry import TASK_MODULES

celery_app = Celery(
    "enterprise_log",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=TASK_MODULES,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    # 调度器：把到期的 Outbox 任务投递给 Worker
    "dispatch-outbox": {
        "task": "dispatch_outbox",
        "schedule": 5.0,
    },
    # 周期运行规则分析、事件聚合与告警
    "run-analysis": {
        "task": "run_analysis",
        "schedule": 30.0,
    },
    # 周期重试发送失败的告警
    "retry-alerts": {
        "task": "retry_alerts",
        "schedule": 30.0,
    },
    # 周期检测设备失联
    "check-device-offline": {
        "task": "check_device_offline",
        "schedule": 60.0,
    },
    # 周期对候选安全事件做 AI 研判
    "run-ai-analysis": {
        "task": "run_ai_analysis",
        "schedule": 30.0,
    },
    # 周期清理超保留期的旧日志
    "cleanup-retention": {
        "task": "cleanup_retention",
        "schedule": 3600.0,
    },
    # 周期基于基线分析生成规则建议
    "rule-suggestions": {
        "task": "generate_rule_suggestions",
        "schedule": 3600.0,
    },
    # 周期检测智能体心跳超时
    "check-agent-offline": {
        "task": "check_agent_offline",
        "schedule": 60.0,
    },
    # 周期探测模型端点健康
    "check-model-endpoints": {
        "task": "check_model_endpoints",
        "schedule": 60.0,
    },
    # 周期拉取 vLLM /metrics，累计模型调用量
    "collect-model-usage": {
        "task": "collect_model_usage",
        "schedule": 60.0,
    },
    # 周期重试发送失败的模型告警（含配置好后补发 pending）
    "retry-model-alerts": {
        "task": "retry_model_alerts",
        "schedule": 30.0,
    },
    # 周期探测数据库实例健康
    "check-database-health": {
        "task": "check_database_health",
        "schedule": 60.0,
    },
}
