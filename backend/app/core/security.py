import secrets

from fastapi import Header, HTTPException

from app.core.config import settings


def require_collector_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """采集端接入鉴权：校验 X-API-Key，比较使用 compare_digest 防时序攻击。"""
    configured = settings.collector_api_key
    if not configured or configured.startswith("CHANGE_ME"):
        raise HTTPException(status_code=503, detail="Collector API key is not configured.")
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def mask_secret(secret: str) -> str:
    """凭据脱敏展示：仅保留后 4 位。"""
    if not secret:
        return ""
    if len(secret) <= 4:
        return "****"
    return "****" + secret[-4:]

