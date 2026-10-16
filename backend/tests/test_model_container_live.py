"""容器实况单测：快照索引 + 失败标注 + 降级。全部 mock 代理响应，不真连 docker。"""

from app.core.config import settings
from app.modules.model.services import container_live


def _fake_list() -> list[dict]:
    # 对齐 GET /containers/json 真实形状：Names 为数组（首元素带 / 前缀）
    return [
        {"Names": ["/qwen3-embedding-4b"], "State": "running", "Status": "Up 2 hours"},
        {"Names": ["qwen38-27b"], "State": "exited", "Status": "Exited (0) 3 minutes ago"},
    ]


def _enable(monkeypatch):
    monkeypatch.setattr(settings, "model_container_enabled", True)


# ===== 快照 =====


def test_snapshot_indexes_by_name(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(container_live, "_list_containers", lambda: _fake_list())
    snap = container_live.container_snapshot()
    assert snap["qwen3-embedding-4b"]["container_status"] == "running"
    assert snap["qwen3-embedding-4b"]["container_status_text"] == "Up 2 hours"
    assert snap["qwen38-27b"]["container_status"] == "exited"


def test_snapshot_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "model_container_enabled", False)
    assert container_live.container_snapshot() == {}


def test_snapshot_proxy_down_returns_empty(monkeypatch):
    """代理不可达 → 空快照（降级 unknown），不抛异常。"""
    _enable(monkeypatch)
    monkeypatch.setattr(container_live, "_list_containers", lambda: None)
    assert container_live.container_snapshot() == {}


def test_disabled_never_calls_proxy(monkeypatch):
    """未启用时根本不发请求。"""
    monkeypatch.setattr(settings, "model_container_enabled", False)

    def boom(*args, **kwargs):
        raise AssertionError("代理不应被调用")

    monkeypatch.setattr(container_live.urlrequest, "urlopen", boom)
    assert container_live._list_containers() is None


def test_proxy_error_returns_none(monkeypatch):
    """代理连接层异常（URLError/超时/非 JSON）一律降级 None。"""
    _enable(monkeypatch)

    def raise_urlerror(*args, **kwargs):
        from urllib.error import URLError

        raise URLError("refused")

    monkeypatch.setattr(container_live.urlrequest, "urlopen", raise_urlerror)
    assert container_live._list_containers() is None


def test_non_list_response_returns_none(monkeypatch):
    """代理返回 dict（异常响应）→ 视为不可用。"""
    _enable(monkeypatch)

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b'{"error": "forbidden"}'

    monkeypatch.setattr(container_live.urlrequest, "urlopen", lambda *a, **k: FakeResp())
    assert container_live._list_containers() is None


# ===== 失败标注 =====


def test_annotate_exited(monkeypatch):
    """容器已停 → 标注容器状态（一眼分清容器挂了）。"""
    _enable(monkeypatch)
    monkeypatch.setattr(container_live, "_list_containers", lambda: _fake_list())
    snap = container_live.container_snapshot()
    assert container_live.annotate_failure("timeout", "qwen38-27b", snap) == "timeout（容器 exited）"


def test_annotate_running_means_service_stuck(monkeypatch):
    """容器在跑但探测失败 → 服务无响应（区别于容器故障）。"""
    _enable(monkeypatch)
    monkeypatch.setattr(container_live, "_list_containers", lambda: _fake_list())
    snap = container_live.container_snapshot()
    assert (
        container_live.annotate_failure("HTTP 500", "qwen3-embedding-4b", snap)
        == "HTTP 500（容器运行中，服务无响应）"
    )


def test_annotate_unknown_model_unchanged():
    """快照里没有该容器（不在本机/代理关闭）→ 不标注，保持原消息。"""
    assert container_live.annotate_failure("timeout", "not-registered", {}) == "timeout"
