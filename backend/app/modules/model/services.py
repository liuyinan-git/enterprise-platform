from urllib import request
from urllib.error import URLError

from app.core.config import settings
from app.modules.model.models import ModelProvider


def probe_provider(provider: ModelProvider) -> tuple[bool, str]:
    """探测模型供应商端点：GET {base_url}/models，2xx 视为健康。"""
    if not provider.base_url:
        return False, "未配置 base_url"
    url = f"{provider.base_url.rstrip('/')}/models"
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    req = request.Request(url, method="GET", headers=headers)
    try:
        with request.urlopen(req, timeout=settings.model_check_timeout_seconds) as resp:
            return resp.status < 400, f"HTTP {resp.status}"
    except URLError as exc:
        return False, str(exc.reason)[:200]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]
