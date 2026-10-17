from fastapi import APIRouter, Depends

from app.core.auth import require_permission

apisix_router = APIRouter(
    prefix="/gateway/apisix",
    tags=["gateway-apisix"],
    dependencies=[Depends(require_permission("gateway:view"))],
)
