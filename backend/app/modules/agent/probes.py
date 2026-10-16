"""HTTP 端点健康探测（标准库 urllib，零额外依赖）。

纯函数：不碰 ORM、不碰 Docker、不读全局状态，可单测。
"""

import json
import socket
import ssl
import time
from dataclasses import dataclass
from urllib import request
from urllib.error import HTTPError, URLError

from app.modules.agent.agent_config import agent_settings

# 结果四态
HEALTHY = "healthy"
UNHEALTHY = "unhealthy"
TIMEOUT = "timeout"
ERROR = "error"

# 探测成功时用过的 HTTP 方法白名单（避免被拿去做任意方法转发）
ALLOWED_METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


@dataclass(frozen=True)
class ProbeResult:
    status: str
    http_status: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    body_excerpt: str | None = None


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError))


def _truncate(value: str, limit: int) -> str:
    text = (value or "").strip()
    return text[:limit]


def probe_http(
    url: str,
    *,
    method: str = "GET",
    timeout: int = 5,
    headers: dict | None = None,
    body: dict | list | None = None,
    expected_status: list[int] | None = None,
    verify_tls: bool | None = None,
    max_excerpt_chars: int | None = None,
) -> ProbeResult:
    """探测一个 HTTP 端点。

    **状态码策略**：`expected_status` 有值 → 健康当且仅当状态码在其中；
    无值 → 2xx 为健康。响应收到了但不符合预期 → `unhealthy`，**绝不归为 error**。

    **`HTTPError` 必须先于 `URLError` 捕获** —— urllib 对 4xx/5xx 抛 `HTTPError`，
    它带 `.code`，且**是 `URLError` 的子类**。先捕 URLError 会把 404 报成
    `str(exc.reason)` 并丢掉状态码（`modules/model/services.py` 的 `probe_provider`
    正是这样写的）。这里必须先拿 `.code` 再判策略。
    """
    limit = agent_settings.agent_probe_max_excerpt_chars if max_excerpt_chars is None else max_excerpt_chars
    verify = agent_settings.agent_probe_verify_tls if verify_tls is None else verify_tls
    method = (method or "GET").upper()
    if method not in ALLOWED_METHODS:
        return ProbeResult(status=ERROR, error=f"不支持的 HTTP 方法：{method}")

    # 关 TLS 校验时**只给本次 urlopen 传 context**，绝不改全局默认 context
    context = None if verify else ssl._create_unverified_context()

    data = None
    if body is not None and method in ("POST", "PUT", "PATCH", "DELETE"):
        data = json.dumps(body).encode("utf-8")

    started = time.perf_counter()
    try:
        # URL 非法（缺 scheme 等）时，Request() 构造本身就会抛 ValueError，
        # 所以构造必须放在 try 内，否则会漏成 500。
        req = request.Request(url, data=data, method=method)
        req.add_header("User-Agent", "enterprise-platform-agent-probe/1.0")
        req.add_header("Accept", "application/json, text/plain, */*")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            if str(key).lower() in ("host", "content-length"):
                # 交给 urllib 自己算，手工覆盖只会造出非法请求
                continue
            req.add_header(str(key), str(value))

        with request.urlopen(req, timeout=timeout, context=context) as resp:
            http_status = getattr(resp, "status", None) or resp.getcode()
            snippet = resp.read(limit * 4).decode("utf-8", errors="replace")
    except HTTPError as exc:
        elapsed = _elapsed(started)
        http_status = exc.code
        try:
            snippet = exc.read(limit * 4).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 读 body 失败不影响状态码判定
            snippet = ""
        healthy = http_status in expected_status if expected_status else 200 <= http_status < 300
        if healthy:
            return ProbeResult(HEALTHY, http_status, elapsed)
        return ProbeResult(UNHEALTHY, http_status, elapsed, f"HTTP {http_status}",
                           _truncate(snippet, limit))
    except (URLError, OSError) as exc:
        elapsed = _elapsed(started)
        if _is_timeout(exc):
            return ProbeResult(TIMEOUT, None, elapsed, f"请求超时（{timeout}s）")
        if isinstance(getattr(exc, "reason", None), ssl.SSLError):
            return ProbeResult(ERROR, None, elapsed,
                               f"TLS 校验失败：{exc.reason}（内网自签证书可设 AGENT_PROBE_VERIFY_TLS=false）")
        reason = getattr(exc, "reason", None) or exc
        return ProbeResult(ERROR, None, elapsed, _truncate(str(reason), 400))
    except ValueError as exc:
        # URL 非法（缺 scheme 等）
        return ProbeResult(ERROR, None, _elapsed(started), _truncate(str(exc), 400))

    elapsed = _elapsed(started)
    healthy = http_status in expected_status if expected_status else 200 <= http_status < 300
    if healthy:
        # 成功的历史行保持干净，不带响应体
        return ProbeResult(HEALTHY, http_status, elapsed)
    return ProbeResult(UNHEALTHY, http_status, elapsed, f"HTTP {http_status}",
                       _truncate(snippet, limit))


def _elapsed(started: float) -> int:
    """耗时（毫秒）。失败时同样记录 —— 失败得快和失败得慢是两种故障。"""
    return int((time.perf_counter() - started) * 1000)
