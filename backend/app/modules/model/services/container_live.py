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
from urllib.parse import quote

from app.core.config import settings


def _resolve_proxy(proxy_url: str | None) -> str:
    """节点级 proxy 覆盖：有值用节点自己的，空回退全局 MODEL_CONTAINER_PROXY_URL。"""
    if proxy_url and proxy_url.strip():
        return proxy_url.strip()
    return settings.model_container_proxy_url


def _list_containers(proxy_url: str | None = None) -> list[dict] | None:
    """GET /containers/json?all=1。未启用/不可达/响应异常一律返回 None（调用方降级）。

    proxy_url 非空时指向该节点自己的 docker-socket-proxy（跨服务器场景），否则用全局默认。
    """
    if not settings.model_container_enabled:
        return None
    url = f"{_resolve_proxy(proxy_url).rstrip('/')}/containers/json?all=1"
    req = urlrequest.Request(url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=settings.model_container_timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except TimeoutError:  # 读超时不是 URLError 子类，须单独兜住
        return None
    except (URLError, OSError, ValueError):
        return None
    return data if isinstance(data, list) else None


def container_snapshot(proxy_url: str | None = None) -> dict[str, dict]:
    """按容器名索引的实况快照：{容器名: {container_status, container_status_text}}。

    list 接口的 State 为 running/exited/paused/restarting/created/dead；
    Status 为人类可读描述（"Up 2 hours" / "Exited (0) 3 minutes ago"）。
    proxy_url 非空时读该节点自己的 proxy（跨服务器场景）。
    """
    raw = _list_containers(proxy_url)
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


def _demux(raw: bytes) -> str:
    """解 Docker 日志多路复用帧（复制自 agent/docker_client.py，模块边界约定禁止跨模块 import）。

    无 TTY 容器 `/logs` 返回 `[stream(1)][0,0,0][size(4,大端)] + payload` 帧序列，
    不解帧会把 8 字节二进制帧头混进文本。TTY 容器是裸流，直接解码。
    """
    if not raw:
        return ""
    if raw[0] not in (0, 1, 2) or raw[1:4] != b"\x00\x00\x00":
        return raw.decode("utf-8", errors="replace")
    chunks: list[bytes] = []
    pos, length = 0, len(raw)
    while pos + 8 <= length:
        size = int.from_bytes(raw[pos + 4:pos + 8], "big")
        chunks.append(raw[pos + 8:pos + 8 + size])
        pos += 8 + size
    if pos < length:  # 尾帧被截断，剩余字节原样保留
        chunks.append(raw[pos:])
    return b"".join(chunks).decode("utf-8", errors="replace")


def container_logs(container_name: str, tail: int | None = None, since: int | None = None, proxy_url: str | None = None) -> str | None:
    """读取容器日志文本（用于 access log 采集）。

    - 容器名或 ID 均可直接作路径段（Docker 接受两者）。
    - since（epoch 秒）：只读该时间点之后新写入的日志，配合 model_registry.last_log_cursor
      做无重叠增量采集，避免相邻周期重复累加。
    - 未启用代理 / 不可达 / 404（容器已不在）→ None，调用方降级为 no_data，不抛异常。
    - 返回文本按 model_access_log_max_chars 截断（保留末尾 = 最近的日志）。
    """
    if not settings.model_container_enabled:
        return None
    limit = tail if tail and tail > 0 else settings.model_access_log_tail
    query = f"stdout=1&stderr=1&tail={limit}"
    if since and since > 0:
        query += f"&since={int(since)}"
    url = (
        f"{_resolve_proxy(proxy_url).rstrip('/')}"
        f"/containers/{quote(container_name, safe='')}/logs"
        f"?{query}"
    )
    req = urlrequest.Request(url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=settings.model_container_timeout_seconds) as resp:
            raw = resp.read()
    except TimeoutError:
        return None
    except (URLError, OSError):
        return None
    text = _demux(raw)
    if len(text) > settings.model_access_log_max_chars:
        return text[-settings.model_access_log_max_chars:]
    return text


def container_ip_map(proxy_url: str | None = None) -> dict[str, str]:
    """容器 IP → 容器名 反查表（从 /containers/json 的 NetworkSettings 抽取）。

    模型 access log 里看到的 source_ip 是调用方容器 IP（bridge 网络直连），
    需要反查成容器名才能与调用方台账的 identifier 对上。
    proxy_url 非空时读该节点自己的 proxy（跨服务器场景）。
    """
    raw = _list_containers(proxy_url)
    if raw is None:
        return {}
    mapping: dict[str, str] = {}
    for item in raw:
        names = item.get("Names") or []
        name = (names[0] if names else "").lstrip("/")
        if not name:
            continue
        networks = (item.get("NetworkSettings") or {}).get("Networks") or {}
        for net in networks.values():
            ip = net.get("IPAddress")
            if ip:
                mapping[ip] = name
    return mapping


_MODEL_HINT_TOKENS = (
    # 推理引擎 / 部署框架（镜像名常见）
    "vllm", "sglang", "tgi", "triton", "xinference", "lmdeploy", "ollama", "fastchat",
    "llama.cpp", "llamacpp", "text-generation-inference", "tensorrt",
    # 模型家族 / 服务类型（容器名常见）
    "qwen", "llama", "bge", "glm", "deepseek", "baichuan", "mistral", "mixtral", "yi-",
    "whisper", "embedding", "rerank", "stable-diffusion", "paddleocr", "ocr",
)


def _looks_like_model(name: str, image: str) -> bool:
    """轻量启发式：容器名/镜像名含模型服务引擎关键词 → 标记为「疑似模型」。

    只作前端高亮建议，不作自动纳管依据；真实模型镜像多样，最终由人工确认。
    """
    hay = f"{name} {image}".lower()
    return any(tok in hay for tok in _MODEL_HINT_TOKENS)


def discover_containers(proxy_url: str | None = None) -> list[dict] | None:
    """列出节点上的容器（供「发现模型」）：name/image/state/status/ports + suggested 标记。

    未启用代理/不可达返回 None（调用方降级为 degraded）。含已停止容器（模型可能挂了）。
    """
    raw = _list_containers(proxy_url)
    if raw is None:
        return None
    out: list[dict] = []
    for item in raw:
        names = item.get("Names") or []
        name = (names[0] if names else "").lstrip("/")
        if not name:
            continue
        ports = [
            {"private": p.get("PrivatePort"), "public": p.get("PublicPort"), "type": p.get("Type")}
            for p in (item.get("Ports") or [])
        ]
        out.append({
            "name": name,
            "image": item.get("Image") or "",
            "state": item.get("State") or "unknown",
            "status": item.get("Status") or "",
            "ports": ports,
            "suggested": _looks_like_model(name, item.get("Image") or ""),
        })
    return out
