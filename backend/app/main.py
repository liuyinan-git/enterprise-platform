import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.db import engine
from app.modules.agent.api import router as agent_router
from app.modules.agent.ingest_api import ingest_router as agent_ingest_router
from app.modules.database.api import router as database_router
from app.modules.gateway.api import router as gateway_router
from app.modules.log.api import router as log_router
from app.modules.log.ingest_api import ingest_router as log_ingest_router
from app.modules.model.api import router as model_router
from app.platform.attachments.api import router as attachments_router
from app.platform.auth.api import router as auth_router
from app.platform.monitoring.api import router as monitoring_router
from app.platform.notifications.api import router as notifications_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("enterprise_platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Platform API; env=%s", settings.app_env)
    yield
    engine.dispose()
    logger.info("Enterprise Platform API stopped")


app = FastAPI(
    title="企业全域管控与智能告警平台 API",
    version="2.0.0",
    description="日志 / 智能体 / 模型 / 数据库 四大模块的统一管控平台。",
    lifespan=lifespan,
)


@app.get("/health/live", tags=["health"])
def liveness():
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except SQLAlchemyError:
        logger.exception("Database readiness check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "企业全域管控与智能告警平台",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health/ready",
    }


for _router in (
    auth_router,
    log_ingest_router,
    agent_ingest_router,
    log_router,
    agent_router,
    model_router,
    database_router,
    gateway_router,
    notifications_router,
    attachments_router,
    monitoring_router,
):
    app.include_router(_router)
