from fastapi import APIRouter

from app.modules.gateway.routers.apisix import apisix_router
from app.modules.gateway.routers.squid import squid_router

router = APIRouter(prefix="/api/v1", tags=["gateway"])


@router.get("/gateway/health")
def gateway_health():
    """网关模块健康检查（不实际连接远端库，仅返回模块状态）。"""
    return {"code": 0, "message": "success", "data": {"status": "ok", "module": "gateway"}}


router.include_router(squid_router)
router.include_router(apisix_router)
