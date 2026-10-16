"""OIDC 鉴权：JWT 验签 + 角色校验依赖。

`oidc_enabled=False` 时优雅降级为「匿名 admin 全放行」，保持内网开放现状；
置为 True 且配置好 IDP 后，按 token 中的角色做前端菜单 / 后端接口双重控制。
"""

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException

from app.core.config import settings


@dataclass
class CurrentUser:
    user_id: str
    username: str
    roles: set[str]


def _default_user() -> CurrentUser:
    return CurrentUser(user_id="anonymous", username="anonymous", roles={"admin"})


def _decode_token(token: str) -> dict[str, Any]:
    """用 IDP 的 JWKS 验签并校验 exp（可选 aud）。"""
    jwks_client = jwt.PyJWKClient(settings.oidc_jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    options: dict[str, Any] = {}
    audience: str | None = settings.oidc_audience or None
    if not audience:
        options["verify_aud"] = False
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        options=options,
    )


def _extract_roles(payload: dict[str, Any]) -> set[str]:
    claim = settings.oidc_roles_claim or "roles"
    value = payload.get(claim, [])
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(v) for v in value}
    return set()


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """解析并校验 Bearer token；未启用 OIDC 时返回默认 admin 用户。"""
    if not settings.oidc_enabled:
        return _default_user()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录或缺少凭证")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = _decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"凭证无效：{exc}") from exc

    sub = str(payload.get("sub") or payload.get("preferred_username") or "unknown")
    username = str(payload.get("preferred_username") or payload.get("name") or sub)
    return CurrentUser(user_id=sub, username=username, roles=_extract_roles(payload))


def require_roles(*allowed: str):
    """依赖工厂：当前用户需命中任一允许角色（或拥有 admin），否则 403。"""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "admin" in user.roles or user.roles.intersection(allowed):
            return user
        raise HTTPException(status_code=403, detail="无权访问该资源")

    return dependency


def get_oidc_config() -> dict[str, Any]:
    """返回前端登录所需的公开配置（不含 client_secret）。"""
    return {
        "enabled": settings.oidc_enabled,
        "issuer": settings.oidc_issuer,
        "authorize_url": settings.oidc_authorize_url,
        "token_url": settings.oidc_token_url,
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scopes": settings.oidc_scopes,
    }
