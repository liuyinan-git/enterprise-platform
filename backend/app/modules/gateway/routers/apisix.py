from fastapi import APIRouter, Depends

from app.core.auth import require_roles

apisix_router = APIRouter(
    prefix="/gateway/apisix",
    tags=["gateway-apisix"],
    dependencies=[Depends(require_roles("admin", "viewer", "gateway_admin"))],
)
