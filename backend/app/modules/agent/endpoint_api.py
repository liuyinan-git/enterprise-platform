"""端点台账接口：CRUD + 单个/批量健康检查 + 监控历史查询。

AI 服务接口（OpenClaw / Hermes / Codex / Dify）与 LangGraph **共用这一套接口**，
用 `service_type` 区分 —— LangGraph 页只是把 service_type 锁死成 langgraph 调用同一批端点。

读接口由父 router 覆盖；写接口逐路由加 `require_roles("admin", "agent_admin")`。
本 router 不带 prefix，被 `api.py` 的父 router include。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.response import created, ok, paginated
from app.modules.agent.models import AgentEndpoint, AgentHealthHistory
from app.modules.agent.schemas import CheckBatchIn, EndpointIn, EndpointUpdate
from app.modules.agent.services import check_endpoint
from app.tasks.celery_app import celery_app

router = APIRouter(tags=["agent-platform"])

_LEDGER_ROLES = ("admin", "agent_admin")


def _serialize(e: AgentEndpoint) -> dict:
    return {
        "id": e.id,
        "endpoint_code": e.endpoint_code,
        "name": e.name,
        "service_type": e.service_type,
        # 列名是 group_name（group 是 SQL 保留字），对外仍叫 group
        "group": e.group_name,
        "url": e.url,
        "method": e.method,
        "headers": e.headers,
        "request_body": e.request_body,
        "expected_status": e.expected_status or [],
        "timeout_seconds": e.timeout_seconds,
        "enabled": e.enabled,
        "description": e.description,
        "attributes": e.attributes,
        # 最近检查快照
        "health_status": e.health_status,
        "last_check_at": e.last_check_at.isoformat() if e.last_check_at else None,
        "last_http_status": e.last_http_status,
        "last_latency_ms": e.last_latency_ms,
        "last_error": e.last_error,
        "last_ok_at": e.last_ok_at.isoformat() if e.last_ok_at else None,
        "consecutive_failures": e.consecutive_failures or 0,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _get(db: Session, endpoint_code: str) -> AgentEndpoint:
    endpoint = db.scalar(select(AgentEndpoint).where(AgentEndpoint.endpoint_code == endpoint_code))
    if endpoint is None:
        raise HTTPException(status_code=404, detail="端点不存在")
    return endpoint


@router.get("/agent/endpoints")
def list_endpoints(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service_type: str | None = Query(default=None),
    group: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentEndpoint)
    if service_type:
        stmt = stmt.where(AgentEndpoint.service_type == service_type)
    if group:
        stmt = stmt.where(AgentEndpoint.group_name == group)
    if health_status:
        stmt = stmt.where(AgentEndpoint.health_status == health_status)
    if enabled is not None:
        stmt = stmt.where(AgentEndpoint.enabled.is_(enabled))
    if q:
        keyword = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            AgentEndpoint.endpoint_code.like(keyword),
            AgentEndpoint.name.like(keyword),
            AgentEndpoint.url.like(keyword),
        ))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AgentEndpoint.service_type, AgentEndpoint.endpoint_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginated([_serialize(e) for e in rows], total, page, page_size)


@router.get("/agent/endpoints/options")
def endpoint_options(db: Session = Depends(get_db)):
    """筛选项下拉用的轻量清单（监控历史页的端点筛选）。"""
    rows = db.scalars(
        select(AgentEndpoint).order_by(AgentEndpoint.service_type, AgentEndpoint.endpoint_code)
    ).all()
    return ok({
        "service_types": sorted({e.service_type for e in rows}),
        "groups": sorted({e.group_name for e in rows if e.group_name}),
        "items": [{"endpoint_code": e.endpoint_code, "name": e.name, "service_type": e.service_type} for e in rows],
    })


@router.post("/agent/endpoints", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission("agent:manage"))])
def create_endpoint(payload: EndpointIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(AgentEndpoint).where(AgentEndpoint.endpoint_code == payload.endpoint_code))
    if exists is not None:
        raise HTTPException(status_code=409, detail="端点编码已存在")
    endpoint = AgentEndpoint(
        endpoint_code=payload.endpoint_code,
        name=payload.name,
        service_type=payload.service_type,
        group_name=payload.group,
        url=payload.url,
        method=payload.method,
        headers=payload.headers,
        request_body=payload.request_body,
        expected_status=payload.expected_status,
        timeout_seconds=payload.timeout_seconds,
        enabled=payload.enabled,
        description=payload.description,
        attributes=payload.attributes,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return created(_serialize(endpoint))


@router.post("/agent/endpoints/check-batch", dependencies=[Depends(require_permission("agent:manage"))])
def check_endpoints_batch(payload: CheckBatchIn | None = None, db: Session = Depends(get_db)):
    """批量检查。codes 为空/省略 = 检查全部启用中的端点。

    同步执行：逐个探测，串行。端点数量在内网场景是几十个量级、每个默认 5s 超时，
    最坏情况会顶到前端的 10s —— 所以前端对这个接口单独放宽 timeout（见 api.ts）。
    """
    codes = [c for c in (payload.codes if payload else None) or [] if c and c.strip()]
    stmt = select(AgentEndpoint)
    if codes:
        stmt = stmt.where(AgentEndpoint.endpoint_code.in_(codes))
    else:
        stmt = stmt.where(AgentEndpoint.enabled.is_(True))
    endpoints = list(db.scalars(stmt.order_by(AgentEndpoint.endpoint_code)).all())
    if not endpoints:
        return ok({"items": [], "total": 0, "summary": {"healthy": 0, "unhealthy": 0, "timeout": 0, "error": 0}})

    results = [check_endpoint(db, endpoint, check_type="manual") for endpoint in endpoints]
    db.commit()
    summary = {"healthy": 0, "unhealthy": 0, "timeout": 0, "error": 0}
    for item in results:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return ok({"items": results, "total": len(results), "summary": summary})


@router.get("/agent/endpoints/{endpoint_code}")
def get_endpoint(endpoint_code: str, db: Session = Depends(get_db)):
    return ok(_serialize(_get(db, endpoint_code)))


@router.put("/agent/endpoints/{endpoint_code}", dependencies=[Depends(require_permission("agent:manage"))])
def update_endpoint(endpoint_code: str, payload: EndpointUpdate, db: Session = Depends(get_db)):
    endpoint = _get(db, endpoint_code)
    # group 在请求体里叫 group，落到列上是 group_name
    mapping = {
        "group": "group_name",
    }
    for field in ("name", "service_type", "group", "url", "method", "headers",
                  "request_body", "expected_status", "timeout_seconds", "enabled",
                  "description", "attributes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(endpoint, mapping.get(field, field), value)
    db.commit()
    db.refresh(endpoint)
    return ok(_serialize(endpoint))


@router.delete("/agent/endpoints/{endpoint_code}", dependencies=[Depends(require_permission("agent:manage"))])
def delete_endpoint(endpoint_code: str, db: Session = Depends(get_db)):
    """删除的**只是监控配置**，不会删除任何实际容器 / 服务。

    监控历史刻意不随之删除（`agent_health_history` 无 FK 且冗余了端点信息），
    删完之后历史页仍能查到「这个接口上周的状态」。
    """
    endpoint = _get(db, endpoint_code)
    db.delete(endpoint)
    db.commit()
    return ok({"endpoint_code": endpoint_code}, message="deleted")


@router.post("/agent/endpoints/{endpoint_code}/check", dependencies=[Depends(require_permission("agent:manage"))])
def check_single_endpoint(endpoint_code: str, db: Session = Depends(get_db)):
    endpoint = _get(db, endpoint_code)
    result = check_endpoint(db, endpoint, check_type="manual")
    db.commit()
    return ok(result)


@router.get("/agent/health-history")
def list_health_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    endpoint_code: str | None = Query(default=None),
    service_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    checked_from: datetime | None = Query(default=None),
    checked_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AgentHealthHistory)
    if endpoint_code:
        stmt = stmt.where(AgentHealthHistory.endpoint_code == endpoint_code)
    if service_type:
        stmt = stmt.where(AgentHealthHistory.service_type == service_type)
    if status:
        stmt = stmt.where(AgentHealthHistory.status == status)
    if checked_from:
        stmt = stmt.where(AgentHealthHistory.checked_at >= checked_from)
    if checked_to:
        stmt = stmt.where(AgentHealthHistory.checked_at <= checked_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(desc(AgentHealthHistory.checked_at), desc(AgentHealthHistory.id))
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "endpoint_id": r.endpoint_id,
            "endpoint_code": r.endpoint_code,
            "endpoint_name": r.endpoint_name,
            "service_type": r.service_type,
            "status": r.status,
            "http_status": r.http_status,
            "latency_ms": r.latency_ms,
            "error": r.error,
            "check_type": r.check_type,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        }
        for r in rows
    ]
    return paginated(items, total, page, page_size)


def _beat_schedule() -> list[dict]:
    """直读 Celery beat 的实时调度表。

    间隔的**唯一真相**就在这里 —— 刻意不设 AGENT_CHECK_INTERVAL_SECONDS 之类的配置项，
    否则两者会悄悄脱节。改间隔要改 `tasks/celery_app.py` 并重启 scheduler。
    """
    schedule = celery_app.conf.beat_schedule or {}
    items: list[dict] = []
    for name, entry in schedule.items():
        if not str(entry.get("task", "")).startswith(("check_agent", "cleanup_agent")):
            continue
        seconds = entry.get("schedule")
        items.append({
            "name": name,
            "task": entry.get("task"),
            "interval_seconds": seconds if isinstance(seconds, (int, float)) else None,
        })
    return items


def agent_beat_schedule() -> list[dict]:
    """供 overview_api 的系统设置页复用。"""
    return _beat_schedule()
