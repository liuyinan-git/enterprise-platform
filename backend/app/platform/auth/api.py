from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_auth_config, get_current_user

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/auth/config")
def auth_config():
    """返回认证开关（网关统一认证由 APISIX 完成，前端只需知道是否启用）。"""
    return {"code": 0, "message": "success", "data": get_auth_config()}


@router.get("/auth/me")
def auth_me(user: CurrentUser = Depends(get_current_user)):
    """返回当前登录用户及其角色，供前端做菜单过滤。"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "user_id": user.user_id,
            "username": user.username,
            "roles": sorted(user.roles),
        },
    }
