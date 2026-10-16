from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_collector_key
from app.modules.log.models import LogBatch
from app.modules.log.schemas import LogBatchIn
from app.modules.log.services.ingest import ingest_batch, ingest_fluentbit, parse_fluentbit_body, parse_msgpack_body

ingest_router = APIRouter(prefix="/api/v1", tags=["log-ingestion"])


@ingest_router.post("/logs/batch", status_code=status.HTTP_202_ACCEPTED)
def receive_log_batch(
    payload: LogBatchIn,
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    try:
        data = ingest_batch(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "accepted", "data": data}


@ingest_router.post("/ingest/fluentbit")
async def ingest_fluentbit_endpoint(
    request: Request,
    x_source_id: str | None = Header(default=None, alias="X-Source-Id"),
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    """接收 Fluent Bit HTTP output 上报的日志（JSON 数组 / 单对象 / NDJSON / msgpack）。"""
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "msgpack" in content_type.lower():
        records = parse_msgpack_body(body)
    else:
        records = parse_fluentbit_body(body)
    source_id = x_source_id or "fluentbit"
    try:
        data = ingest_fluentbit(db, records, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "accepted", "data": data}


@ingest_router.get("/batches/{batch_id}")
def get_batch(
    batch_id: str,
    source_id: str = Query(min_length=1, max_length=100),
    _: None = Depends(require_collector_key),
    db: Session = Depends(get_db),
):
    batch = db.scalar(select(LogBatch).where(
        LogBatch.batch_id == batch_id,
        LogBatch.source_id == source_id,
    ))
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "code": 0,
        "message": "success",
        "data": {
            "batch_id": batch.batch_id,
            "source_id": batch.source_id,
            "received": batch.received_count,
            "accepted": batch.accepted_count,
            "rejected": batch.rejected_count,
            "status": batch.status,
            "received_at": batch.received_at.isoformat() if batch.received_at else None,
        },
    }
