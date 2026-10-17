from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.response import created, ok
from app.modules.rbac.models import RbacPermission, RbacRole, RbacRolePermission
from app.modules.rbac.schemas import RoleIn, RolePermissionsIn, RoleUpdate
from app.modules.rbac.services import invalidate_cache

router = APIRouter(
    prefix="/api/v1",
    tags=["rbac"],
    dependencies=[Depends(require_permission("platform:rbac"))],
)


def _serialize_role(r: RbacRole, perm_codes: list[str]) -> dict:
    return {
        "id": r.id,
        "role_code": r.role_code,
        "role_name": r.role_name,
        "external_role_id": r.external_role_id,
        "description": r.description,
        "enabled": r.enabled,
        "permission_codes": perm_codes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _role_perms(db: Session, role_id: int) -> list[str]:
    return list(db.scalars(
        select(RbacPermission.permission_code)
        .join(RbacRolePermission, RbacRolePermission.permission_id == RbacPermission.id)
        .where(RbacRolePermission.role_id == role_id)
        .order_by(RbacPermission.id)
    ).all())


@router.get("/rbac/roles")
def list_roles(db: Session = Depends(get_db)):
    roles = db.scalars(select(RbacRole).order_by(RbacRole.id)).all()
    items = [_serialize_role(r, _role_perms(db, r.id)) for r in roles]
    return {"code": 0, "message": "success", "data": {"items": items, "total": len(items)}}


@router.post("/rbac/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleIn, db: Session = Depends(get_db)):
    if db.scalar(select(RbacRole.id).where(RbacRole.role_code == payload.role_code)):
        raise HTTPException(status_code=409, detail=f"角色 {payload.role_code} 已存在")
    if payload.external_role_id and db.scalar(
        select(RbacRole.id).where(RbacRole.external_role_id == payload.external_role_id)
    ):
        raise HTTPException(status_code=409, detail=f"外部角色ID {payload.external_role_id} 已被占用")
    role = RbacRole(
        role_code=payload.role_code,
        role_name=payload.role_name,
        external_role_id=payload.external_role_id,
        description=payload.description,
        enabled=payload.enabled,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    invalidate_cache()
    return created(_serialize_role(role, []))


@router.put("/rbac/roles/{role_code}")
def update_role(role_code: str, payload: RoleUpdate, db: Session = Depends(get_db)):
    role = db.scalar(select(RbacRole).where(RbacRole.role_code == role_code))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if payload.external_role_id is not None and payload.external_role_id != role.external_role_id:
        if db.scalar(
            select(RbacRole.id).where(
                RbacRole.external_role_id == payload.external_role_id,
                RbacRole.id != role.id,
            )
        ):
            raise HTTPException(status_code=409, detail=f"外部角色ID {payload.external_role_id} 已被占用")
    for field in ("role_name", "external_role_id", "description", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(role, field, value)
    db.commit()
    db.refresh(role)
    invalidate_cache()
    return ok(_serialize_role(role, _role_perms(db, role.id)))


@router.delete("/rbac/roles/{role_code}")
def delete_role(role_code: str, db: Session = Depends(get_db)):
    role = db.scalar(select(RbacRole).where(RbacRole.role_code == role_code))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    db.execute(delete(RbacRolePermission).where(RbacRolePermission.role_id == role.id))
    db.delete(role)
    db.commit()
    invalidate_cache()
    return ok({"role_code": role_code}, message="deleted")


@router.get("/rbac/permissions")
def list_permissions(db: Session = Depends(get_db)):
    perms = db.scalars(
        select(RbacPermission).order_by(RbacPermission.module, RbacPermission.sort_order, RbacPermission.id)
    ).all()
    groups: dict[str, list[dict]] = {}
    for p in perms:
        groups.setdefault(p.module, []).append({
            "permission_code": p.permission_code,
            "permission_name": p.permission_name,
        })
    items = [{"module": m, "permissions": groups[m]} for m in groups]
    return {"code": 0, "message": "success", "data": {"items": items}}


@router.put("/rbac/roles/{role_code}/permissions")
def set_role_permissions(role_code: str, payload: RolePermissionsIn, db: Session = Depends(get_db)):
    role = db.scalar(select(RbacRole).where(RbacRole.role_code == role_code))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    codes = list(dict.fromkeys(payload.permission_codes))  # 去重保序
    perms = list(db.scalars(select(RbacPermission).where(RbacPermission.permission_code.in_(codes))).all()) if codes else []
    if len(perms) != len(codes):
        raise HTTPException(status_code=400, detail="包含无效的权限码")
    db.execute(delete(RbacRolePermission).where(RbacRolePermission.role_id == role.id))
    for p in perms:
        db.add(RbacRolePermission(role_id=role.id, permission_id=p.id))
    db.commit()
    invalidate_cache()
    return ok({"role_code": role_code, "permission_codes": codes})
