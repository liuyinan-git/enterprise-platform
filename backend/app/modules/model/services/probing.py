"""模型模块服务层：分层健康探测 + vLLM /metrics 用量采集。

探测方式（probe_method）：
- openai: GET {endpoint_url}/v1/models，2xx 视为健康（vLLM 全系 OpenAI 兼容服务）
- tcp:    socket 探活 host:port（whisper / voiceprint / stablediffusion 等非 HTTP 标准协议服务）
- http:   GET {endpoint_url}/，任意 HTTP 响应（含 4xx/5xx）视为存活，连接层失败才是不健康
- none:   跳过探测

踩坑约定（来自内网盘点实践，2026-10-16）：
- endpoint_url 一律填服务根地址（不含 /v1），openai 探测自动拼 /v1/models
- 非 vLLM 容器 /metrics 拉不到属正常（no_data），不算健康事件
- vLLM 用量口径：/metrics 的 vllm:request_success_total 计数器做差值
"""

import re
import socket
import time
from urllib import parse, request
from urllib.error import URLError

from app.core.config import settings
from app.modules.model.models import ModelProvider, ModelRegistry

VALID_PROBE_METHODS = {"openai", "tcp", "http", "none"}
# 支撑用量采集的服务类型（vLLM 起的推理服务才有 /metrics）
METRICS_SERVICE_TYPES = {"chat", "embedding", "rerank"}


def _model_endpoint(model: ModelRegistry, provider: ModelProvider | None) -> str:
    """模型服务根地址：endpoint_url 优先，为空回退 provider.base_url（去尾部斜杠）。"""
    base = model.endpoint_url or (provider.base_url if provider else "") or ""
    return base.rstrip("/")


def _http_get(url: str, timeout: int, api_key: str = "") -> tuple[int, float]:
    """GET 请求，返回 (状态码, 耗时秒)。异常向上抛。"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(url, method="GET", headers=headers)
    start = time.time()
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.status, time.time() - start


def probe_provider(provider: ModelProvider) -> tuple[bool, str]:
    """探测模型供应商端点：GET {base_url}/models，2xx 视为健康。"""
    if not provider.base_url:
        return False, "未配置 base_url"
    url = f"{provider.base_url.rstrip('/')}/models"
    try:
        status, _ = _http_get(url, settings.model_check_timeout_seconds, provider.api_key)
        return status < 400, f"HTTP {status}"
    except URLError as exc:
        return False, str(exc.reason)[:200]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def probe_model(model: ModelRegistry, provider: ModelProvider | None) -> tuple[bool, int | None, str]:
    """分层探测模型服务，返回 (是否健康, 延迟 ms, 说明)。"""
    method = model.probe_method or "openai"
    if method == "none":
        return True, None, "skip"

    endpoint = _model_endpoint(model, provider)
    if not endpoint:
        return False, None, "未配置 endpoint_url"

    if method == "tcp":
        return _probe_tcp(endpoint)
    if method == "http":
        return _probe_http_root(endpoint)
    return _probe_openai(endpoint, provider.api_key if provider else "")


def _probe_tcp(endpoint: str) -> tuple[bool, int | None, str]:
    """socket 探活：从 endpoint 解析 host:port（注意精确解析，避免端口数字误匹配）。"""
    parsed = parse.urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False, None, f"endpoint 无法解析 host: {endpoint}"
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=settings.model_check_timeout_seconds):
            return True, int((time.time() - start) * 1000), "connected"
    except OSError as exc:
        return False, None, str(exc)[:200]


def _probe_http_root(endpoint: str) -> tuple[bool, int | None, str]:
    """GET 服务根路径：任意 HTTP 响应（含 4xx/5xx）视为存活；连接失败才是不健康。"""
    try:
        status, elapsed = _http_get(endpoint, settings.model_check_timeout_seconds)
        return True, int(elapsed * 1000), f"HTTP {status}"
    except request.HTTPError as exc:  # type: ignore[attr-defined]  # 4xx/5xx 也证明服务在响应
        return True, None, f"HTTP {exc.code}"
    except URLError as exc:
        return False, None, str(exc.reason)[:200]
    except TimeoutError:  # 外网探测内网被防火墙 drop 的典型表现
        return False, None, "timeout"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)[:200]


def _probe_openai(endpoint: str, api_key: str) -> tuple[bool, int | None, str]:
    """OpenAI 兼容探测：GET {endpoint}/v1/models，2xx 视为健康。"""
    url = f"{endpoint}/v1/models"
    try:
        status, elapsed = _http_get(url, settings.model_check_timeout_seconds, api_key)
        return status < 400, int(elapsed * 1000), f"HTTP {status}"
    except request.HTTPError as exc:  # type: ignore[attr-defined]  # 必须先于 URLError 捕获（子类）
        return False, None, f"HTTP {exc.code}"
    except URLError as exc:
        return False, None, str(exc.reason)[:200]
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)[:200]


# ===== /metrics 用量采集 =====

# Prometheus 文本行：<metric_name>{labels} <value> [timestamp]
_PROM_LINE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([0-9.eE+-]+)")


def parse_prometheus_counter(text: str, metric_name: str) -> int | None:
    """解析 Prometheus 文本，返回指定指标所有样本值之和（无该指标返回 None）。"""
    total = 0
    found = False
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        match = _PROM_LINE.match(line.strip())
        if match and match.group(1) == metric_name:
            found = True
            total += int(float(match.group(3)))
    return total if found else None


def compute_delta(last: int | None, current: int) -> int:
    """计数器差值：首次采集只记基线（0）；计数器回退（服务重启）按当前值计。"""
    if last is None:
        return 0
    return current - last if current >= last else current
