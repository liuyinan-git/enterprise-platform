"""RBAC 查询：网关注入的角色 ID → 角色码 → 权限集，带简单内存缓存。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.rbac.models import RbacPermission, RbacRole, RbacRolePermission

# 简单内存缓存：外部角色ID -> role_code；role_code -> 权限集
_id_to_code_cache: dict[str, str] | None = None
_code_to_perms_cache: dict[str, set[str]] | None = None


def invalidate_cache() -> None:
    """角色/权限变更后调用，使缓存失效。"""
    global _id_to_code_cache, _code_to_perms_cache
    _id_to_code_cache = None
    _code_to_perms_cache = None


def _load_mappings(db: Session) -> None:
    global _id_to_code_cache, _code_to_perms_cache
    roles = db.execute(
        select(RbacRole.role_code, RbacRole.external_role_id).where(RbacRole.enabled.is_(True))
    ).all()
    _id_to_code_cache = {ext: code for code, ext in roles if ext}

    rows = db.execute(
        select(RbacRole.role_code, RbacPermission.permission_code)
        .join(RbacRolePermission, RbacRolePermission.role_id == RbacRole.id)
        .join(RbacPermission, RbacPermission.id == RbacRolePermission.permission_id)
        .where(RbacRole.enabled.is_(True))
    ).all()
    _code_to_perms_cache = {}
    for code, perm in rows:
        _code_to_perms_cache.setdefault(code, set()).add(perm)


def resolve_roles(db: Session, role_ids: list[str]) -> set[str]:
    """把网关注入的角色 ID 映射成平台角色码。

    兼容两种输入：19 位 MaxKey 角色 ID（经 external_role_id 映射），
    或本身就是平台角色码（本地 mock 联调用）。
    """
    if _id_to_code_cache is None:
        _load_mappings(db)
    result: set[str] = set()
    for rid in role_ids:
        if rid in _id_to_code_cache:
            result.add(_id_to_code_cache[rid])
        elif rid in _code_to_perms_cache:
            result.add(rid)
    return result


def get_permissions(db: Session, role_codes: set[str]) -> set[str]:
    """由角色码求权限集。"""
    if _code_to_perms_cache is None:
        _load_mappings(db)
    result: set[str] = set()
    for code in role_codes:
        result.update(_code_to_perms_cache.get(code, set()))
    return result
