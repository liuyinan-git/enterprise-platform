"""Docker Engine API 客户端（经 docker-socket-proxy 白名单代理，零额外依赖）。

刻意**不引入 docker SDK**：与 `core/ai_client.py` 一致，只用标准库 `urllib`，
因此不改 `requirements.txt`。

只用到四个 API：
    GET  /containers/json?all=1
    GET  /containers/{id}/json
    GET  /containers/{id}/logs
    POST /containers/{id}/start | /stop | /restart
"""

import json
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from app.modules.database.container_config import container_settings


class DockerUnavailable(RuntimeError):
    """代理不可达 / 被白名单拒绝 / 上游错误。"""


class ContainerNotFound(RuntimeError):
    """目标容器不存在。"""


def _url(path: str) -> str:
    # 路径刻意不带 API 版本号（不用 /v1.43/...），交由 daemon 自行协商；
    # 写死版本号会在 Docker 版本不一致时报 client version too new。
    return f"{container_settings.container_proxy_url.rstrip('/')}{path}"


def _call(method: str, path: str, *, timeout: int, query: str = "") -> bytes:
    url = _url(path) + (f"?{query}" if query else "")
    req = request.Request(url, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as exc:
        # 304：对已处于目标状态的容器再 start/stop，属幂等成功而非错误
        if exc.code == 304:
            return b""
        body = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code == 404:
            raise ContainerNotFound(body or "容器不存在") from exc
        if exc.code in (401, 403):
            raise DockerUnavailable(f"Docker 代理拒绝该操作（HTTP {exc.code}）：{body}") from exc
        raise DockerUnavailable(f"Docker API HTTP {exc.code}：{body}") from exc
    except (URLError, OSError) as exc:
        raise DockerUnavailable(f"Docker 代理不可达：{exc}") from exc


def _json_call(method: str, path: str, *, timeout: int, query: str = ""):
    raw = _call(method, path, timeout=timeout, query=query)
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise DockerUnavailable(f"Docker API 返回非 JSON：{raw[:200]!r}") from exc


def _demux(raw: bytes) -> str:
    """解 Docker 日志的多路复用帧。

    无 TTY 的容器，`/logs` 返回 `[stream(1)][0,0,0][size(4,大端)] + payload` 的帧序列
    （stdout / stderr 各一路）。不先解帧直接解码，会把 8 字节二进制帧头混进文本里。
    TTY 容器则是裸流，直接解码。
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
    if pos < length:  # 尾帧被截断，剩余字节原样保留，总比丢掉强
        chunks.append(raw[pos:])
    return b"".join(chunks).decode("utf-8", errors="replace")


def list_containers() -> list[dict]:
    """列出全部容器（含已停止）。不可达时抛 DockerUnavailable，由调用方降级。"""
    data = _json_call(
        "GET",
        "/containers/json",
        timeout=container_settings.container_request_timeout_seconds,
        query="all=1",
    )
    return data if isinstance(data, list) else []


def inspect_container(container_id: str) -> dict:
    data = _json_call(
        "GET",
        f"/containers/{quote(container_id, safe='')}/json",
        timeout=container_settings.container_request_timeout_seconds,
    )
    return data if isinstance(data, dict) else {}


def container_logs(container_id: str, tail: int | None = None) -> tuple[str, bool]:
    """取容器日志，返回 (文本, 是否被截断)。

    不加 `timestamps=1`：Docker 给的是 RFC3339 UTC，与平台「全库 naive 北京时」的
    约定不一致，混进来只会误导；日志行本身通常自带时间戳。
    """
    requested = tail if tail and tail > 0 else container_settings.container_log_tail_default
    limit = min(requested, container_settings.container_log_tail_max)
    raw = _call(
        "GET",
        f"/containers/{quote(container_id, safe='')}/logs",
        timeout=container_settings.container_request_timeout_seconds,
        query=f"stdout=1&stderr=1&tail={limit}",
    )
    text = _demux(raw)
    # 按字符数截断（不切原始字节，否则会破坏帧对齐）
    if len(text) > container_settings.container_log_max_chars:
        return text[-container_settings.container_log_max_chars:], True
    return text, False


def start_container(container_id: str) -> None:
    _call(
        "POST",
        f"/containers/{quote(container_id, safe='')}/start",
        timeout=container_settings.container_action_timeout_seconds,
    )


def stop_container(container_id: str, timeout_seconds: int | None = None) -> None:
    grace = container_settings.container_stop_grace_seconds if timeout_seconds is None else timeout_seconds
    _call(
        "POST",
        f"/containers/{quote(container_id, safe='')}/stop",
        timeout=container_settings.container_action_timeout_seconds,
        query=f"t={grace}",
    )


def restart_container(container_id: str, timeout_seconds: int | None = None) -> None:
    grace = container_settings.container_stop_grace_seconds if timeout_seconds is None else timeout_seconds
    _call(
        "POST",
        f"/containers/{quote(container_id, safe='')}/restart",
        timeout=container_settings.container_action_timeout_seconds,
        query=f"t={grace}",
    )
