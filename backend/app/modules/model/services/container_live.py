"""模型容器实况：经 docker-socket-proxy 只读读取模型服务容器状态。

设计要点（与 database 模块 docker_client.py 同模式，但刻意不跨模块 import ——
模块边界规则禁止 model 依赖 database，此处保留只读精简子集）：
- 纯标准库 urllib，不引入 docker SDK，不改 requirements.txt
- model 模块只读不启停（启停管控是 database 模块职责）
- 每个探测周期只调一次 GET /containers/json?all=1，按容器名（=model_code）匹配，
  不做逐个 inspect —— 容器名在宿主机上唯一，精确匹配已足够
- 代理未启用/不可达 → 空快照，容器状态显示 unknown，探测管线完全不受影响
  （不为容器编排层故障发告警 —— 模块边界约定）
"""

import json
from urllib import request as urlrequest
from urllib.error import URLError

from app.core.config import settings


def _list_containers() -> list[dict] | None:
    """GET /containers/json?all=1。未启用/不可达/响应异常一律返回 None（调用方降级）。"""
    if not settings.model_container_enabled:
        return None
    url = f"{settings.model_container_proxy_url.rstrip('/')}/containers/json?all=1"
    req = urlrequest.Request(url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=settings.model_container_timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except TimeoutError:  # 读超时不是 URLError 子类，须单独兜住
        return None
    except (URLError, OSError, ValueError):
        return None
    return data if isinstance(data, list) else None


def container_snapshot() -> dict[str, dict]:
    """按容器名索引的实况快照：{容器名: {container_status, container_status_text}}。

    list 接口的 State 为 running/exited/paused/restarting/created/dead；
    Status 为人类可读描述（"Up 2 hours" / "Exited (0) 3 minutes ago"）。
    """
    raw = _list_containers()
    if raw is None:
        return {}
    snap: dict[str, dict] = {}
    for item in raw:
        # GET /containers/json 的键是 Names（数组，首元素带 / 前缀），取第一个名字
        names = item.get("Names") or []
        name = (names[0] if names else "").lstrip("/")
        if not name:
            continue
        snap[name] = {
            "container_status": item.get("State") or "unknown",
            "container_status_text": item.get("Status") or "",
        }
    return snap


def annotate_failure(message: str, model_code: str, snap: dict[str, dict]) -> str:
    """探测失败时标注容器状态：一眼分清「容器挂了」还是「容器在跑但服务无响应」。

    快照里没有该容器（代理未启用/容器不在本机）时不标注，保持原消息。
    """
    info = snap.get(model_code)
    if not info:
        return message
    status = info.get("container_status") or ""
    if not status:
        return message
    if status == "running":
        return f"{message}（容器运行中，服务无响应）"
    return f"{message}（容器 {status}）"
