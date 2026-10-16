from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import local_now
from app.modules.agent import probes
from app.modules.agent.agent_config import agent_settings
from app.modules.agent.models import AgentAudit, AgentEndpoint, AgentHealthHistory, AgentContainerAudit, AgentRegistry


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


def record_container_audit(
    db: Session,
    *,
    container_id: str,
    container_name: str,
    project_key: str | None,
    action: str,
    result: str,
    operator: str | None = None,
    detail: dict | list | None = None,
) -> None:
    """写入一条容器操作审计（被拒绝的 refused 同样落库）。

    只 add、不 commit —— 由调用方决定提交时机（与 `record_audit` 一致）。
    """
    db.add(AgentContainerAudit(
        container_id=container_id,
        container_name=container_name,
        project_key=project_key,
        action=action,
        result=result,
        operator=operator,
        detail=detail,
    ))


def probe_endpoint(endpoint: AgentEndpoint) -> probes.ProbeResult:
    """对端点台账的一行做一次 HTTP 探测（纯探测，不写库）。"""
    timeout = endpoint.timeout_seconds or agent_settings.agent_probe_default_timeout_seconds
    timeout = min(timeout, agent_settings.agent_probe_max_timeout_seconds)

    # expected_status 为空 → 不传，交给 probes 走「2xx 为健康」的默认策略
    expected: list[int] = []
    if isinstance(endpoint.expected_status, list):
        expected = [int(x) for x in endpoint.expected_status
                    if isinstance(x, (int, str)) and str(x).strip().isdigit()]

    return probes.probe_http(
        endpoint.url,
        method=endpoint.method or "GET",
        timeout=timeout,
        headers=endpoint.headers if isinstance(endpoint.headers, dict) else None,
        body=endpoint.request_body,
        expected_status=expected or None,
    )


def check_endpoint(db: Session, endpoint: AgentEndpoint, check_type: str = "manual") -> dict:
    """探测一个端点：写快照 + 落一行历史。**不 commit**，由调用方统一提交。

    快照字段：
      - `health_status` / `last_check_at` / `last_http_status` / `last_latency_ms` / `last_error`
      - `last_ok_at` —— 最近一次健康的时刻（不随失败清空，用于回答「上次好的时候是什么时候」）
      - `consecutive_failures` —— 连续失败次数，健康时清零
    """
    result = probe_endpoint(endpoint)
    now = local_now()

    endpoint.health_status = result.status
    endpoint.last_check_at = now
    endpoint.last_http_status = result.http_status
    endpoint.last_latency_ms = result.latency_ms
    endpoint.last_error = result.error
    if result.status == probes.HEALTHY:
        endpoint.last_ok_at = now
        endpoint.consecutive_failures = 0
    else:
        endpoint.consecutive_failures = (endpoint.consecutive_failures or 0) + 1

    db.add(AgentHealthHistory(
        endpoint_id=endpoint.id,
        endpoint_code=endpoint.endpoint_code,
        endpoint_name=endpoint.name,
        service_type=endpoint.service_type,
        status=result.status,
        http_status=result.http_status,
        latency_ms=result.latency_ms,
        error=result.error,
        check_type=check_type,
        checked_at=now,
    ))
    return {
        "endpoint_code": endpoint.endpoint_code,
        "name": endpoint.name,
        "status": result.status,
        "http_status": result.http_status,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "body_excerpt": result.body_excerpt,
        "consecutive_failures": endpoint.consecutive_failures,
        "checked_at": now.isoformat(),
    }

