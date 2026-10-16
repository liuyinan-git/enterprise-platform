import socket
import time

from app.core.config import settings
from app.modules.database.models import DatabaseInstance


def probe_instance(instance: DatabaseInstance) -> tuple[bool, int | None, str]:
    """探测数据库实例：TCP 连接 host:port 是否可达，返回 (是否健康, 延迟 ms, 说明)。"""
    if not instance.host or not instance.port:
        return False, None, "未配置 host/port"
    start = time.time()
    try:
        with socket.create_connection((instance.host, instance.port), timeout=settings.database_check_timeout_seconds):
            latency = int((time.time() - start) * 1000)
            return True, latency, "connected"
    except OSError as exc:
        return False, None, str(exc)[:200]
