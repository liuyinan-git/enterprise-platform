"""模型模块服务层单测：分层探测 + Prometheus 指标解析 + 差值计算。

外网开发期无真实 vLLM 服务，用标准库 mock 覆盖探测全部分支，
内网验收时以真实环境回归为准。
"""

import socket
from urllib.error import HTTPError, URLError

from app.modules.model.models import ModelRegistry
from app.modules.model.services import probing as services  # monkeypatch 必须打到真实定义模块

# 绕过登录鉴权等外部依赖：直接测试服务函数


def _model(**kwargs) -> ModelRegistry:
    """构造离线 ModelRegistry（不落库，仅探测用）。"""
    defaults = {
        "model_code": "test-svc",
        "service_type": "chat",
        "endpoint_url": "http://172.28.110.11:8033",
        "probe_method": "openai",
    }
    defaults.update(kwargs)
    return ModelRegistry(**defaults)


# ===== probe_model：openai 分支 =====


def test_probe_openai_healthy(monkeypatch):
    monkeypatch.setattr(services, "_http_get", lambda url, timeout, api_key="": (200, 0.05))
    ok_flag, latency, msg = services.probe_model(_model(), None)
    assert ok_flag is True
    assert latency == 50
    assert msg == "HTTP 200"


def test_probe_openai_extracts_url_with_v1(monkeypatch):
    """openai 探测必须拼 /v1/models（endpoint 为服务根地址，不含 /v1）。"""
    seen = {}

    def fake_get(url, timeout, api_key=""):
        seen["url"] = url
        return 200, 0.01

    monkeypatch.setattr(services, "_http_get", fake_get)
    services.probe_model(_model(), None)
    assert seen["url"] == "http://172.28.110.11:8033/v1/models"


def test_probe_openai_500_unhealthy(monkeypatch):
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(HTTPError(url, 500, "err", None, None)),
    )
    ok_flag, latency, msg = services.probe_model(_model(), None)
    assert ok_flag is False
    assert msg == "HTTP 500"


def test_probe_openai_conn_refused(monkeypatch):
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(URLError(socket.gaierror())),
    )
    ok_flag, latency, msg = services.probe_model(_model(), None)
    assert ok_flag is False


def test_probe_no_endpoint():
    ok_flag, latency, msg = services.probe_model(_model(endpoint_url=""), None)
    assert ok_flag is False
    assert "未配置" in msg


# ===== probe_model：tcp 分支 =====


def test_probe_tcp_healthy(monkeypatch):
    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(services.socket, "create_connection", lambda addr, timeout: FakeConn())
    ok_flag, latency, msg = services.probe_model(_model(probe_method="tcp", endpoint_url="http://172.28.110.11:5014"), None)
    assert ok_flag is True
    assert msg == "connected"


def test_probe_tcp_refused(monkeypatch):
    def boom(addr, timeout):
        raise ConnectionRefusedError()

    monkeypatch.setattr(services.socket, "create_connection", boom)
    ok_flag, _, _ = services.probe_model(_model(probe_method="tcp"), None)
    assert ok_flag is False


# ===== probe_model：http 分支 =====


def test_probe_http_root_404_still_alive(monkeypatch):
    """http 探测：404 也是存活（服务在响应），连接失败才是不健康。"""
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(HTTPError(url, 404, "nope", None, None)),
    )
    ok_flag, _, msg = services.probe_model(_model(probe_method="http"), None)
    assert ok_flag is True
    assert msg == "HTTP 404"


def test_probe_http_root_200(monkeypatch):
    monkeypatch.setattr(services, "_http_get", lambda url, timeout, api_key="": (200, 0.02))
    ok_flag, latency, _ = services.probe_model(_model(probe_method="http"), None)
    assert ok_flag is True
    assert latency == 20


def test_probe_http_root_conn_failed(monkeypatch):
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(URLError(OSError("refused"))),
    )
    ok_flag, _, _ = services.probe_model(_model(probe_method="http"), None)
    assert ok_flag is False


def test_probe_http_root_timeout(monkeypatch):
    """外网探测内网 IP 被防火墙 drop：读超时抛 TimeoutError（非 URLError 子类），必须兜住。"""
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(TimeoutError()),
    )
    ok_flag, _, msg = services.probe_model(_model(probe_method="http"), None)
    assert ok_flag is False
    assert msg == "timeout"


def test_probe_openai_timeout(monkeypatch):
    monkeypatch.setattr(
        services, "_http_get",
        lambda url, timeout, api_key="": (_ for _ in ()).throw(TimeoutError()),
    )
    ok_flag, _, _ = services.probe_model(_model(probe_method="openai"), None)
    assert ok_flag is False


# ===== probe_model：none 分支 =====


def test_probe_none_skips():
    ok_flag, latency, msg = services.probe_model(_model(probe_method="none"), None)
    assert ok_flag is True
    assert msg == "skip"


# ===== Prometheus 指标解析 =====


PROM_TEXT = """# HELP vllm:request_success_total Number of requests successfully processed.
# TYPE vllm:request_success_total counter
vllm:request_success_total{model_name="qwen3-embedding-4b"} 163019.0
vllm:request_success_total{model_name="bge-m3"} 6182.0
vllm:num_requests_running 3
# TYPE vllm:prompt_tokens_total counter
vllm:prompt_tokens_total 1024.0
"""


def test_parse_counter_sums_samples():
    """多标签样本求和：两个模型共 169201。"""
    assert services.parse_prometheus_counter(PROM_TEXT, "vllm:request_success_total") == 169201


def test_parse_counter_missing_metric():
    assert services.parse_prometheus_counter(PROM_TEXT, "vllm:not_exist") is None


def test_parse_counter_float_values():
    text = "vllm:request_success_total 42.7\n"
    assert services.parse_prometheus_counter(text, "vllm:request_success_total") == 42


# ===== 差值计算 =====


def test_delta_first_collection_is_zero():
    """首次采集只记基线，不计增量。"""
    assert services.compute_delta(None, 1000) == 0


def test_delta_normal():
    assert services.compute_delta(1000, 1030) == 30


def test_delta_counter_reset_on_restart():
    """服务重启计数器回退：按当前值计（重启后的调用数）。"""
    assert services.compute_delta(1000, 5) == 5
