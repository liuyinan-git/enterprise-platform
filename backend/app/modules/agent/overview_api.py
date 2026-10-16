"""首页统计与「系统设置」只读状态。

两条贯穿全文件的约定：
  1. **任何一项探测失败都只降级为 `{ok: false, error}`，绝不让整个接口 500。**
     系统设置页即使 Redis 挂了也必须能打开 —— 那正是它最该被看到的时候。
  2. 系统设置**只读**：间隔的唯一真相是 Celery beat 的 `beat_schedule`，
     各超时来自 `AGENT_*` 环境变量。页面展示它们，不改它们。
"""

import socket
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.timeutil import local_now
from app.modules.agent import containers as container_rules
from app.modules.agent import docker_client
from app.modules.agent.agent_config import agent_settings
from app.modules.agent.endpoint_api import agent_beat_schedule
from app.modules.agent.models import AgentEndpoint, AgentHealthHistory, AgentProjectRule

router = APIRouter(tags=["agent-platform"])


def _mask_proxy_url(url: str) -> str:
    """隐去代理地址的主机名，只留 scheme + 端口。

    系统设置页是给人看的，没必要把内网拓扑画出来（代理本身无鉴权，地址知道得越少越好）。
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "（未配置）"
    host = "***" if parts.hostname else ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}"


def _check_docker() -> dict:
    started = time.perf_counter()
    try:
        containers = docker_client.list_containers()
    except docker_client.DockerUnavailable as exc:
        return {"ok": False, "latency_ms": int((time.perf_counter() - started) * 1000), "error": str(exc)}
    return {
        "ok": True,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": None,
        "detail": f"{len(containers)} 个容器",
    }


def _check_mysql(db: Session) -> dict:
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - 探活失败的原因五花八门，统一降级
        return {"ok": False, "latency_ms": int((time.perf_counter() - started) * 1000), "error": str(exc)[:300]}
    return {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000), "error": None}


def _check_redis() -> dict:
    """裸 socket 探活，**刻意不 import redis 客户端** —— 与全模块零新增依赖一致。"""
    started = time.perf_counter()
    try:
        with socket.create_connection((settings.redis_host, settings.redis_port), timeout=3):
            pass
    except OSError as exc:
        return {"ok": False, "latency_ms": int((time.perf_counter() - started) * 1000), "error": str(exc)[:300]}
    return {
        "ok": True,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": None,
        "detail": f"{settings.redis_host}:{settings.redis_port}/db{settings.redis_db}",
    }


@router.get("/agent/overview")
def get_overview(db: Session = Depends(get_db)):
    """首页统计。

    - 容器类数字来自**实时 Docker**（不可达时归零 + `degraded: true`，绝不 500）
    - 接口类数字来自 `agent_endpoint` 的最近检查快照（仅 enabled）
    """
    containers: list[dict] = []
    degraded = False
    error: str | None = None
    try:
        containers = container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        degraded = True
        error = str(exc)

    rules = container_rules.load_rules(db)
    running = sum(1 for c in containers if c["state"] == "running")
    stopped = sum(1 for c in containers if c["state"] != "running")
    unclassified = sum(1 for c in containers if not c["project_key"])
    projects = {c["project_key"] for c in containers if c["project_key"] and not c["conflict"]}

    endpoint_rows = db.scalars(select(AgentEndpoint).where(AgentEndpoint.enabled.is_(True))).all()
    health_counts = {"healthy": 0, "unhealthy": 0, "timeout": 0, "error": 0, "unknown": 0}
    by_type: dict[str, int] = {}
    for endpoint in endpoint_rows:
        health_counts[endpoint.health_status] = health_counts.get(endpoint.health_status, 0) + 1
        by_type[endpoint.service_type] = by_type.get(endpoint.service_type, 0) + 1

    # 「最近异常接口」：按连续失败次数降序，取前 10 条
    failing = [
        {
            "endpoint_code": e.endpoint_code,
            "name": e.name,
            "service_type": e.service_type,
            "health_status": e.health_status,
            "last_http_status": e.last_http_status,
            "last_error": e.last_error,
            "consecutive_failures": e.consecutive_failures or 0,
            "last_check_at": e.last_check_at.isoformat() if e.last_check_at else None,
        }
        for e in sorted(endpoint_rows, key=lambda x: -(x.consecutive_failures or 0))
        if e.health_status in ("unhealthy", "timeout", "error")
    ][:10]

    return {
        "code": 0,
        "message": "success",
        "data": {
            "project_count": len(projects),
            "rule_count": len(rules),
            "rule_enabled_count": sum(1 for r in rules if r.enabled),
            "container_count": len(containers),
            "running_count": running,
            "stopped_count": stopped,
            "unclassified_count": unclassified,
            "api_total": len(endpoint_rows),
            "api_healthy": health_counts.get("healthy", 0),
            "api_unhealthy": sum(health_counts.get(k, 0) for k in ("unhealthy", "timeout", "error")),
            "api_by_status": health_counts,
            "api_by_type": by_type,
            "failing_endpoints": failing,
            "history_total": db.scalar(select(func.count()).select_from(AgentHealthHistory)) or 0,
            "degraded": degraded,
            "error": error,
            "generated_at": local_now().isoformat(),
        },
    }


@router.get("/agent/system-status")
def get_system_status(db: Session = Depends(get_db)):
    """系统设置页的全部信息：调度 / 超时 / 存储 / 连通性 / 权限。**只读。**"""
    rules_count = db.scalar(select(func.count()).select_from(AgentProjectRule)) or 0
    endpoints_count = db.scalar(select(func.count()).select_from(AgentEndpoint)) or 0
    history_count = db.scalar(select(func.count()).select_from(AgentHealthHistory)) or 0
    history_oldest = db.scalar(select(func.min(AgentHealthHistory.checked_at)))

    return {
        "code": 0,
        "message": "success",
        "data": {
            "schedule": {
                "source": "Celery beat（backend/app/tasks/celery_app.py）",
                "note": "间隔在 beat_schedule 里，改动需重启 scheduler 容器；本页只读。",
                "items": agent_beat_schedule(),
            },
            "timeouts": {
                "docker_request_seconds": {"value": agent_settings.agent_docker_request_timeout_seconds, "env": "AGENT_DOCKER_REQUEST_TIMEOUT_SECONDS"},
                "docker_action_seconds": {"value": agent_settings.agent_docker_action_timeout_seconds, "env": "AGENT_DOCKER_ACTION_TIMEOUT_SECONDS"},
                "docker_stop_grace_seconds": {"value": agent_settings.agent_docker_stop_grace_seconds, "env": "AGENT_DOCKER_STOP_GRACE_SECONDS"},
                "probe_default_seconds": {"value": agent_settings.agent_probe_default_timeout_seconds, "env": "AGENT_PROBE_DEFAULT_TIMEOUT_SECONDS"},
                "probe_max_seconds": {"value": agent_settings.agent_probe_max_timeout_seconds, "env": "AGENT_PROBE_MAX_TIMEOUT_SECONDS"},
                "agent_offline_grace_seconds": {"value": settings.agent_offline_grace_seconds, "env": "AGENT_OFFLINE_GRACE_SECONDS"},
            },
            "storage": {
                "history_retention_days": {"value": agent_settings.agent_history_retention_days, "env": "AGENT_HISTORY_RETENTION_DAYS"},
                "history_total": history_count,
                "history_oldest_at": history_oldest.isoformat() if history_oldest else None,
                "rule_count": rules_count,
                "endpoint_count": endpoints_count,
            },
            "docker": {
                "proxy_url_masked": _mask_proxy_url(agent_settings.agent_docker_proxy_url),
                "protected_project": agent_settings.agent_protected_project,
                "log_tail_default": agent_settings.agent_log_tail_default,
                "log_tail_max": agent_settings.agent_log_tail_max,
                "log_timestamps": agent_settings.agent_log_timestamps,
                **_check_docker(),
            },
            "probe": {
                "verify_tls": agent_settings.agent_probe_verify_tls,
                "max_excerpt_chars": agent_settings.agent_probe_max_excerpt_chars,
            },
            "connections": {
                "mysql": _check_mysql(db),
                "redis": _check_redis(),
            },
            "auth": {
                "oidc_enabled": settings.oidc_enabled,
                # 未开 OIDC 时后端返回匿名 admin —— 与 AGENTS.md 第九条同一个告警
                "anonymous_admin": not settings.oidc_enabled,
                "roles": {
                    "read": ["admin", "viewer", "agent_admin"],
                    "ledger_write": ["admin", "agent_admin"],
                    "container_action": ["admin", "agent_container_admin"],
                },
            },
            "generated_at": local_now().isoformat(),
        },
    }
