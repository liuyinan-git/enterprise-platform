from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import local_now
from app.modules.agent import containers as container_rules
from app.modules.agent import docker_client, probes
from app.modules.agent.agent_config import agent_settings
from app.modules.agent.models import AgentAudit, AgentEndpoint, AgentHealthHistory, AgentContainerAudit, AgentRegistry


def load_container_index(db: Session) -> tuple[dict[str, dict], str | None]:
    """一次读取全部 Docker 容器，按容器名索引。

    返回 `({name: 序列化容器}, error)`；Docker 不可达时返回 `({}, error)`，
    由调用方决定降级展示还是跳过告警（绝不能把探测故障当成容器离线）。
    """
    try:
        containers = container_rules.list_serialized_containers(db)
    except docker_client.DockerUnavailable as exc:
        return {}, str(exc)
    return {c["name"]: c for c in containers}, None


def agent_status(agent: AgentRegistry, container: dict | None = None, docker_ok: bool = True) -> str:
    """智能体在线状态。

    - 登记了 `container_name`：以 Docker 容器运行状态为准（running=online）；
      Docker 不可达时返回 `unknown`，避免误报离线。
    - 历史数据没有容器名：仍按最后心跳 + 宽限期判定（向后兼容）。
    """
    if not agent.enabled:
        return "disabled"
    if agent.container_name:
        if not docker_ok:
            return "unknown"
        if container is None:
            return "offline"
        return "online" if container.get("state") == "running" else "offline"
    if agent.last_seen_at is None:
        return "offline"
    grace = settings.agent_offline_grace_seconds
    return "online" if (local_now() - agent.last_seen_at).total_seconds() <= grace else "offline"


def _notify_wecom(db: Session, content: str) -> tuple[str, str | None]:
    """发送一条企业微信通知。返回 `(status, error)`，status 取：

    - `sent`    —— 已发送
    - `skipped` —— 企业微信未配置 / 未启用（不是错误；平台上仍要留下告警记录）
    - `failed`  —— 已配置但发送失败（可重试）

    **通知失败不得影响心跳与周期任务**：这里兜住所有异常，由调用方决定是否重试。

    两个 import 必须在函数内：`notifications.service` 会 import `modules.log.models`，
    后者触发 log 包初始化 → log.api → analyze_ai → 又回到 notifications.service。
    agent 模块在 app 启动期加载，模块级 import 会撞上这个既有环，延迟导入则不会。
    """
    from app.platform.notifications.service import get_or_create_config
    from app.platform.notifications.wecom import send_markdown

    cfg = get_or_create_config(db)
    if not (cfg.enabled and cfg.corpid and cfg.corpsecret and cfg.agentid and cfg.touser):
        return "skipped", "企业微信未配置或未启用"
    try:
        send_markdown(
            cfg.corpid, cfg.corpsecret, cfg.agentid, cfg.touser, content, settings.wecom_timeout_seconds
        )
    except Exception as exc:  # noqa: BLE001 - 第三方网络失败，绝不能让监控任务整体失败
        return "failed", str(exc)[:500]
    return "sent", None


def _container_target(agent: AgentRegistry, container: dict | None) -> str:
    """告警文案里的容器状态一行。"""
    if container is None:
        return f"> 容器：`{agent.container_name}`（未找到该容器）"
    status = container.get("status") or container.get("state") or "unknown"
    return f"> 容器：`{agent.container_name}`（{status}）"


def _offline_markdown(agent: AgentRegistry, grace_seconds: int, container: dict | None = None) -> str:
    if agent.container_name:
        return (
            f"## 智能体容器离线告警\n"
            f"> 智能体：{agent.agent_name} (`{agent.agent_id}`)\n"
            f"> 类型：{agent.agent_type}"
            f"{f' / 环境：{agent.environment}' if agent.environment else ''}\n"
            f"> 负责人：{agent.owner or '未登记'}\n"
            f"{_container_target(agent, container)}\n"
            f"> 检测时间：{local_now()}"
        )
    return (
        f"## 智能体离线告警\n"
        f"> 智能体：{agent.agent_name} (`{agent.agent_id}`)\n"
        f"> 类型：{agent.agent_type}"
        f"{f' / 环境：{agent.environment}' if agent.environment else ''}\n"
        f"> 负责人：{agent.owner or '未登记'}\n"
        f"> 最后心跳：{agent.last_seen_at}\n"
        f"> 离线阈值：{grace_seconds} 秒\n"
        f"> 检测时间：{local_now()}"
    )


def _recovered_markdown(agent: AgentRegistry, container: dict | None = None) -> str:
    if agent.container_name:
        status = (container or {}).get("status") or (container or {}).get("state") or "running"
        return (
            f"## 智能体容器已恢复在线\n"
            f"> 智能体：{agent.agent_name} (`{agent.agent_id}`)\n"
            f"> 类型：{agent.agent_type}"
            f"{f' / 环境：{agent.environment}' if agent.environment else ''}\n"
            f"> 容器：`{agent.container_name}`（{status}）"
        )
    return (
        f"## 智能体已恢复在线\n"
        f"> 智能体：{agent.agent_name} (`{agent.agent_id}`)\n"
        f"> 类型：{agent.agent_type}"
        f"{f' / 环境：{agent.environment}' if agent.environment else ''}\n"
        f"> 恢复心跳：{agent.last_seen_at}"
    )


def detect_offline_agents(db: Session) -> dict:
    """检测启用中智能体的离线状态，**每个离线周期只告警一次**。

    - 登记了 `container_name`：以 Docker 容器状态为准。容器 running 视为在线；
      stopped/exited/created 或容器不存在视为离线。**Docker 不可达时不告警**
      （探测故障不是离线证据），返回 `degraded: true`。
    - 历史数据没有容器名：仍按 `last_seen_at` + 宽限期判定，且「从未心跳过」的
      不告警（多半是还没启动或 agent_id 写错，按故障处理只会制造噪音）。
    - `offline_alerted_at` 是去重标记：容器恢复 running（或历史行心跳恢复）时清空
      并发送「已恢复」通知。
    - **企微未配置时仍然落平台审计**（`notify=none`）并置标记，否则平台上看不到
      任何离线事件；配置了但发送失败（`failed`）则不置标记，下个周期自动重试。
    """
    now = local_now()
    grace = settings.agent_offline_grace_seconds
    index, docker_error = load_container_index(db)
    docker_ok = docker_error is None
    rows = db.scalars(select(AgentRegistry).where(AgentRegistry.enabled.is_(True))).all()
    stats = {
        "checked": len(rows),
        "offline": 0,
        "alerted": 0,
        "recovered": 0,
        "notify_failed": 0,
        "skipped": 0,
        "degraded": not docker_ok,
    }
    if docker_error:
        stats["error"] = docker_error

    for agent in rows:
        container = index.get(agent.container_name) if agent.container_name else None

        # Docker 不可达时无法判定容器归属行，跳过（保留既有去重标记）
        if agent.container_name and not docker_ok:
            stats["skipped"] += 1
            continue

        status = agent_status(agent, container, docker_ok)

        if agent.container_name:
            if status == "online":
                if agent.offline_alerted_at is not None:
                    notify, error = notify_agent_recovered(db, agent, container)
                    agent.offline_alerted_at = None
                    detail = {
                        "container_name": agent.container_name,
                        "container_state": (container or {}).get("state"),
                        "notify": "wecom" if notify == "sent" else "none",
                    }
                    if error:
                        detail["notify_error"] = error
                    record_audit(db, agent.agent_id, "back_online", detail=detail)
                    stats["recovered"] += 1
                continue
            if status != "offline":
                continue
        else:
            if status != "offline":
                continue
            if agent.last_seen_at is None:
                stats["skipped"] += 1
                continue

        stats["offline"] += 1
        if agent.offline_alerted_at is not None:
            stats["skipped"] += 1
            continue

        notify, error = _notify_wecom(db, _offline_markdown(agent, grace, container))
        if notify == "failed":
            # 配置正常但发送失败：不置标记，60s 后随下个周期重试
            stats["notify_failed"] += 1
            continue

        agent.offline_alerted_at = now
        detail = {
            "grace_seconds": grace,
            "notify": "wecom" if notify == "sent" else "none",
        }
        if agent.container_name:
            detail["container_name"] = agent.container_name
            detail["container_state"] = (container or {}).get("state") or "missing"
        elif agent.last_seen_at is not None:
            detail["last_seen_at"] = agent.last_seen_at.isoformat()
        if error:
            detail["notify_error"] = error
        record_audit(db, agent.agent_id, "offline_alert", detail=detail)
        stats["alerted"] += 1

    db.commit()
    return stats


def notify_agent_recovered(
    db: Session, agent: AgentRegistry, container: dict | None = None
) -> tuple[str, str | None]:
    """发送「已恢复」通知。

    - 有容器名的智能体由 `detect_offline_agents` 按容器状态调用；
    - 历史行由心跳接口在离线标记非空时调用（保持原行为）。
    """
    return _notify_wecom(db, _recovered_markdown(agent, container))


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

