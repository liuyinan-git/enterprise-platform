"""网关统一认证：从 APISIX 注入的请求头读取用户与角色。

APISIX 的 openid-connect 插件完成认证后，再经 forward-auth 插件调用 enrich 服务
补全用户信息，最终后端从以下头读取（由 forward-auth 的 upstream_headers 注入）：
  x-user-id    —— 用户 ID
  x-user-num   —— 工号（作为用户名展示）
  x-user-roles —— 角色（逗号/空格分隔，或 JSON 数组）
`gateway_auth_enabled=False` 时降级为匿名 admin 全放行，保持内网开放现状。
"""

import json
from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


@dataclass
class CurrentUser:
    user_id: str
    username: str
    roles: set[str]


def _default_user() -> CurrentUser:
    return CurrentUser(user_id="anonymous", username="anonymous", roles={"admin"})


def _parse_roles(raw: str | None) -> set[str]:
    if not raw:
        return set()
    value = raw.strip()
    if value.startswith("["):
        try:
            data = json.loads(unquote(value))
            if isinstance(data, list):
                return {str(r) for r in data if str(r).strip()}
        except (json.JSONDecodeError, ValueError):
            pass
    # 兼容逗号或空白分隔
    return {p for p in value.replace(",", " ").split() if p}


def get_current_user(
    x_user_id: str | None = Header(default=None, alias="x-user-id"),
    x_user_num: str | None = Header(default=None, alias="x-user-num"),
    x_user_roles: str | None = Header(default=None, alias="x-user-roles"),
) -> CurrentUser:
    """从 APISIX 注入的头解析当前用户；未启用网关认证时返回匿名 admin。"""
    if not settings.gateway_auth_enabled:
        return _default_user()
    if not x_user_id:
        raise HTTPException(status_code=401, detail="未登录或缺少用户信息")
    return CurrentUser(
        user_id=x_user_id.strip(),
        username=(x_user_num or x_user_id).strip(),
        roles=_parse_roles(x_user_roles),
    )


def require_roles(*allowed: str):
    """依赖工厂：当前用户需命中任一允许角色（或拥有 admin），否则 403。"""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "admin" in user.roles or user.roles.intersection(allowed):
            return user
        raise HTTPException(status_code=403, detail="无权访问该资源")

    return dependency


def get_auth_config() -> dict:
    """返回认证开关，供前端判断是否启用菜单过滤。"""
    return {"enabled": settings.gateway_auth_enabled}
