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
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.timeutil import local_now
from app.modules.agent import docker_client
from app.modules.agent.agent_config import agent_settings
from app.modules.agent.endpoint_api import agent_beat_schedule
from app.modules.agent.models import AgentEndpoint, AgentHealthHistory, AgentProjectRule, AgentRegistry
from app.modules.agent.services import agent_status, load_container_index

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


def _service_runtime(service: str) -> dict:
    """按平台自身 compose 服务检测 worker / scheduler 是否在跑。

    这是「调度配置」表最容易被误读的地方：表里列的是 beat_schedule 的**配置**，
    即使 scheduler 没启动也照样列出来。这里补上运行态，避免把配置当现状。

    本地直接 `celery ... worker/beat`（不经 Docker）时会是 `not_found`，属正常；
    页面据此提示「本地运行或未启动」，而不是断言一定是故障。
    """
    try:
        containers = docker_client.list_containers()
    except docker_client.DockerUnavailable as exc:
        return {"ok": False, "state": "unknown", "error": str(exc)}

    project = agent_settings.agent_protected_project
    for container in containers:
        labels = container.get("Labels") or {}
        if (
            labels.get("com.docker.compose.project") == project
            and labels.get("com.docker.compose.service") == service
        ):
            state = str(container.get("State") or "").lower() or "unknown"
            return {
                "ok": state == "running",
                "state": state,
                "container_id": (container.get("Id") or "")[:12],
                "status": container.get("Status"),
            }
    return {"ok": False, "state": "not_found", "error": f"未找到 compose 服务：{service}"}


@router.get("/agent/overview")
def get_overview(db: Session = Depends(get_db)):
    """首页统计：**只围绕「智能体管理」里已登记的智能体**。

    - 不再统计全宿主机的容器 / 项目 / 分类规则（那些是容器页的旧口径）；
    - 智能体状态以其绑定容器的运行状态为准（Docker 不可达时 `unknown` + 降级，
      绝不 500、也不误报离线）；
    - 接口类数字来自 `agent_endpoint` 的最近检查快照（仅 enabled）。
    """
    index, error = load_container_index(db)
    degraded = error is not None

    agents = db.scalars(
        select(AgentRegistry)
        .where(AgentRegistry.enabled.is_(True))
        .order_by(AgentRegistry.agent_name)
    ).all()

    # 每个智能体的接口数 / 异常接口数：一次 group by，避免 N+1
    count_rows = db.execute(
        select(
            AgentEndpoint.agent_id,
            func.count().label("total"),
            func.sum(
                case(
                    (AgentEndpoint.health_status.in_(("unhealthy", "timeout", "error")), 1),
                    else_=0,
                )
            ).label("unhealthy"),
        )
        .where(AgentEndpoint.enabled.is_(True), AgentEndpoint.agent_id.is_not(None))
        .group_by(AgentEndpoint.agent_id)
    ).all()
    endpoint_counts = {row.agent_id: (row.total, int(row.unhealthy or 0)) for row in count_rows}

    agent_items: list[dict] = []
    status_counts = {"online": 0, "offline": 0, "unknown": 0, "disabled": 0}
    unbound = 0
    for agent in agents:
        container = index.get(agent.container_name) if agent.container_name else None
        status = agent_status(agent, container, docker_ok=not degraded)
        status_counts[status] = status_counts.get(status, 0) + 1
        if not agent.container_name:
            unbound += 1
        total, unhealthy = endpoint_counts.get(agent.agent_id, (0, 0))
        agent_items.append({
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "agent_type": agent.agent_type,
            "container_name": agent.container_name,
            "container_id": (container or {}).get("container_id"),
            "container_state": (container or {}).get("state"),
            "container_status": (container or {}).get("status"),
            "container_image": (container or {}).get("image"),
            "container_found": container is not None,
            "project_key": (container or {}).get("project_key"),
            "project_name": (container or {}).get("project_name"),
            "status": status,
            "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
            "endpoint_total": total,
            "endpoint_unhealthy": unhealthy,
        })

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
            "agent_id": e.agent_id,
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
            "agent_total": len(agents),
            "agent_online": status_counts.get("online", 0),
            "agent_offline": status_counts.get("offline", 0),
            "agent_unknown": status_counts.get("unknown", 0),
            "agent_unbound": unbound,
            "agents": agent_items,
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
def get_system_status(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """系统设置页的全部信息：调度 / 超时 / 存储 / 连通性 / 权限。**只读。**

    `auth.current_user` 是**本次请求**解析出来的用户与角色（网关认证关闭时是匿名
    admin），供前端动态展示「我是谁、我能做什么」，而不是只抄一份静态角色策略。
    """
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
            # 配置（上面的 schedule）≠ 运行（这里）。两者都要展示，缺一会误导。
            "runtime": {
                "worker": _service_runtime("worker"),
                "scheduler": _service_runtime("scheduler"),
            },
            "auth": {
                "gateway_auth_enabled": settings.gateway_auth_enabled,
                # 未开网关认证时后端返回匿名 admin —— 与 AGENTS.md 第九条同一个告警
                "anonymous_admin": not settings.gateway_auth_enabled,
                # 动态：本次请求的身份、角色与权限（来自 APISIX 注入的 x-user-*，或匿名 admin）
                "current_user": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "roles": sorted(user.roles),
                    "permissions": sorted(user.permissions),
                },
                # 静态策略：各能力要求的权限码（admin 角色恒放行，不在此处重复列）
                "permissions": {
                    "read": ["agent:view"],
                    "ledger_write": ["agent:manage"],
                    "container_action": ["agent:container"],
                },
            },
            "generated_at": local_now().isoformat(),
        },
    }
