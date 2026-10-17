from fastapi import APIRouter, Depends

from app.core.auth import require_roles

squid_router = APIRouter(
    prefix="/gateway/squid",
    tags=["gateway-squid"],
    dependencies=[Depends(require_roles("admin", "viewer", "gateway_admin"))],
)
