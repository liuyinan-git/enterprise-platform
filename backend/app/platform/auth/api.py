from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user, get_oidc_config

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/auth/config")
def auth_config():
    """前端登录所需的公开 OIDC 配置（不含 client_secret）。"""
    return {"code": 0, "message": "success", "data": get_oidc_config()}


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
