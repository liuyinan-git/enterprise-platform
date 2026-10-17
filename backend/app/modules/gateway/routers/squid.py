from fastapi import APIRouter, Depends

from app.core.auth import require_permission

squid_router = APIRouter(
    prefix="/gateway/squid",
    tags=["gateway-squid"],
    dependencies=[Depends(require_permission("gateway:view"))],
)
