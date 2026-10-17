"""网关统一认证：从 APISIX 注入的请求头读取用户，并经 RBAC 解析角色与权限。

APISIX 的 openid-connect 插件完成认证后，经 forward-auth 插件注入：
  x-user-id       —— 用户 ID
  x-user-num      —— 工号/编号
  x-user-roles    —— 角色 ID（逗号/空格分隔或 JSON 数组）
  x-user-role-ids —— 角色 ID（同上）
后端把角色 ID 映射成平台角色码（rbac_role.external_role_id → role_code），
再求得权限集（rbac_role_permission）。gateway_auth_enabled=False 时降级为匿名 admin。
"""

import json
import logging
from dataclasses import dataclass, field
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.modules.rbac.services import get_permissions, resolve_roles

logger = logging.getLogger("enterprise_platform")


@dataclass
class CurrentUser:
    user_id: str
    username: str
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)


def _default_user() -> CurrentUser:
    return CurrentUser(user_id="anonymous", username="anonymous", roles={"admin"})


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    value = raw.strip()
    if value.startswith("["):
        try:
            data = json.loads(unquote(value))
            if isinstance(data, list):
                return [str(r) for r in data if str(r).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
    return [p for p in value.replace(",", " ").split() if p]


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="x-user-id"),
    x_user_num: str | None = Header(default=None, alias="x-user-num"),
    x_user_roles: str | None = Header(default=None, alias="x-user-roles"),
    x_user_role_ids: str | None = Header(default=None, alias="x-user-role-ids"),
) -> CurrentUser:
    """从 APISIX 注入的头解析用户，并经 RBAC 解析角色/权限。"""
    if not settings.gateway_auth_enabled:
        return _default_user()
    if not x_user_id:
        raise HTTPException(status_code=401, detail="未登录或缺少用户信息")

    role_ids = _parse_list(x_user_role_ids or x_user_roles)
    role_codes = resolve_roles(db, role_ids)
    permissions = get_permissions(db, role_codes)
    logger.info(
        "[auth] id=%s role_ids=%s roles=%s perms=%s",
        x_user_id, role_ids, sorted(role_codes), sorted(permissions),
    )
    return CurrentUser(
        user_id=x_user_id.strip(),
        username=(x_user_num or x_user_id).strip(),
        roles=role_codes,
        permissions=permissions,
    )


def require_permission(*perms: str):
    """依赖工厂：当前用户需命中任一权限（或拥有 admin 角色），否则 403。"""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "admin" in user.roles or user.permissions.intersection(perms):
            return user
        raise HTTPException(status_code=403, detail="无权访问该资源")

    return dependency


def require_roles(*allowed: str):
    """依赖工厂（过渡兼容）：按角色码校验。"""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "admin" in user.roles or user.roles.intersection(allowed):
            return user
        raise HTTPException(status_code=403, detail="无权访问该资源")

    return dependency


def get_auth_config() -> dict:
    """返回认证开关，供前端判断是否启用菜单过滤。"""
    return {"enabled": settings.gateway_auth_enabled}
