import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.routes import router
from app.core.config import settings
from app.db.session import engine

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("enterprise_log")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Log Platform API; env=%s", settings.app_env)
    yield
    engine.dispose()
    logger.info("Enterprise Log Platform API stopped")


app = FastAPI(
    title="企业全域日志管控与智能告警平台 API",
    version="1.0.0-phase1",
    description="第一阶段：健康检查、批量日志接收与批次查询。",
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
        "name": "企业全域日志管控与智能告警平台",
        "version": "1.0.0-phase1",
        "docs": "/docs",
        "health": "/health/ready",
    }


app.include_router(router)
