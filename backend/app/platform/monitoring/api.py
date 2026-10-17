from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user, require_permission, require_roles
from app.core.db import get_db
from app.core.timeutil import local_now
from app.modules.log.models import (
    AlertRecord,
    DeviceRegistry,
    LogBatch,
    LogEvent,
    LogRaw,
    ProcessingTask,
    SecurityEvent,
)
from app.modules.log.services.cleanup import clear_all_logs
from app.modules.agent import docker_client
from app.modules.agent.models import AgentEndpoint, AgentProjectRule
from app.modules.database.models import DatabaseBackup, DatabaseInstance
from app.modules.model.models import ModelAlert, ModelConsumer, ModelProvider, ModelRegistry

router = APIRouter(prefix="/api/v1", tags=["monitoring"])


@router.get("/system/overview")
def system_overview(
    _: CurrentUser = Depends(require_permission("platform:system")),
    db: Session = Depends(get_db),
):
    """管理端：系统运行监控统计（队列积压、解析失败、Worker 状态等）。"""
    raw_pending = db.scalar(select(func.count(LogRaw.id)).where(LogRaw.process_status == "pending")) or 0
    raw_failed = db.scalar(select(func.count(LogRaw.id)).where(LogRaw.process_status == "failed")) or 0
    task_pending = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "pending")) or 0
    task_running = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "running")) or 0
    task_failed = db.scalar(select(func.count(ProcessingTask.id)).where(ProcessingTask.status == "failed")) or 0
    return {
        "code": 0,
        "message": "success",
        "data": {
            "raw_total": db.scalar(select(func.count(LogRaw.id))) or 0,
            "raw_pending": raw_pending,
            "raw_failed": raw_failed,
            "event_total": db.scalar(select(func.count(LogEvent.id))) or 0,
            "batch_total": db.scalar(select(func.count(LogBatch.id))) or 0,
            "device_total": db.scalar(select(func.count(DeviceRegistry.id))) or 0,
            "security_event_total": db.scalar(select(func.count(SecurityEvent.id))) or 0,
            "alert_total": db.scalar(select(func.count(AlertRecord.id))) or 0,
            "task_pending": task_pending,
            "task_running": task_running,
            "task_failed": task_failed,
        },
    }


@router.post("/system/reset")
def reset_system(
    _: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """管理端：还原——清空日志、事件与告警（保留设备/规则/企业微信/附件）。"""
    return {"code": 0, "message": "success", "data": clear_all_logs(db)}


@router.get("/overview")
def platform_overview(
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """平台总览：聚合四大模块关键指标（Docker 不可达时容器数字降级为 None）。"""
    now = local_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        cnt = db.scalar(
            select(func.count(LogEvent.id)).where(
                LogEvent.event_time >= day,
                LogEvent.event_time < next_day,
            )
        ) or 0
        trend.append({"date": day.strftime("%m-%d"), "count": cnt})

    container_count = None
    running_count = None
    try:
        containers = docker_client.list_containers()
        container_count = len(containers)
        running_count = sum(1 for c in containers if c.get("State") == "running")
    except docker_client.DockerUnavailable:
        pass

    return {
        "code": 0,
        "message": "success",
        "data": {
            "log": {
                "device_total": db.scalar(select(func.count(DeviceRegistry.id))) or 0,
                "event_today": db.scalar(select(func.count(LogEvent.id)).where(LogEvent.event_time >= today_start)) or 0,
                "open_events": db.scalar(select(func.count(SecurityEvent.id)).where(SecurityEvent.status == "open")) or 0,
                "pending_alerts": db.scalar(select(func.count(AlertRecord.id)).where(AlertRecord.status == "pending")) or 0,
                "trend": trend,
            },
            "agent": {
                "project_count": db.scalar(select(func.count(AgentProjectRule.id))) or 0,
                "api_total": db.scalar(select(func.count(AgentEndpoint.id))) or 0,
                "api_healthy": db.scalar(select(func.count(AgentEndpoint.id)).where(AgentEndpoint.health_status == "healthy")) or 0,
                "container_count": container_count,
                "running_count": running_count,
            },
            "model": {
                "provider_count": db.scalar(select(func.count(ModelProvider.id))) or 0,
                "model_count": db.scalar(select(func.count(ModelRegistry.id))) or 0,
                "consumer_count": db.scalar(select(func.count(ModelConsumer.id))) or 0,
                "alert_count": db.scalar(select(func.count(ModelAlert.id))) or 0,
            },
            "database": {
                "instance_count": db.scalar(select(func.count(DatabaseInstance.id))) or 0,
                "backup_count": db.scalar(select(func.count(DatabaseBackup.id))) or 0,
                "container_count": container_count,
            },
        },
    }


@router.get("/dashboard/overview")
def dashboard_overview(
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理端：首页态势统计 + 近 7 日日志趋势。"""
    now = local_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        cnt = db.scalar(
            select(func.count(LogEvent.id)).where(
                LogEvent.event_time >= day,
                LogEvent.event_time < next_day,
            )
        ) or 0
        trend.append({"date": day.strftime("%m-%d"), "count": cnt})

    return {
        "code": 0,
        "message": "success",
        "data": {
            "device_total": db.scalar(select(func.count(DeviceRegistry.id))) or 0,
            "log_total": db.scalar(select(func.count(LogEvent.id))) or 0,
            "event_today": db.scalar(select(func.count(LogEvent.id)).where(LogEvent.event_time >= today_start)) or 0,
            "security_event_total": db.scalar(select(func.count(SecurityEvent.id))) or 0,
            "open_events": db.scalar(select(func.count(SecurityEvent.id)).where(SecurityEvent.status == "open")) or 0,
            "alert_total": db.scalar(select(func.count(AlertRecord.id))) or 0,
            "pending_alerts": db.scalar(select(func.count(AlertRecord.id)).where(AlertRecord.status == "pending")) or 0,
            "trend": trend,
        },
    }
