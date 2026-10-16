import hashlib
import json
import uuid
from datetime import datetime, timezone
from app.core.timeutil import LOCAL_TZ, local_now, to_naive_local

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.log.models import DeviceRegistry, LogBatch, LogRaw, ProcessingTask
from app.modules.log.schemas import LogBatchIn


def build_raw_payload(item) -> dict | None:
    """把结构化字段（device_type/hostname 等）合并进 raw_payload，供解析器标准化时使用。"""
    payload = dict(item.fields) if isinstance(item.fields, dict) else {}
    if item.device_type:
        payload.setdefault("device_type", item.device_type)
    if item.hostname:
        payload.setdefault("hostname", item.hostname)
    return payload or None


def _touch_devices(db: Session, devices: list[dict]) -> None:
    """心跳联动：登记未知设备，并刷新已知设备的 last_seen_at。"""
    seen: dict[str, dict] = {}
    for d in devices:
        device_id = d.get("device_id")
        if device_id:
            seen.setdefault(device_id, {
                "device_type": d.get("device_type") or "other",
                "hostname": d.get("hostname"),
                "container_id": d.get("container_id"),
            })

    if not seen:
        return

    now = local_now()
    for device_id, info in seen.items():
        device = db.scalar(select(DeviceRegistry).where(DeviceRegistry.device_id == device_id))
        if device is None:
            db.add(DeviceRegistry(
                device_id=device_id,
                device_name=device_id,
                device_type=info["device_type"],
                hostname=info["hostname"],
                last_seen_at=now,
                attributes={"container_id": info["container_id"]} if info["container_id"] else None,
            ))
        else:
            device.last_seen_at = now
            if info["hostname"] and not device.hostname:
                device.hostname = info["hostname"]
            if info["container_id"]:
                attrs = dict(device.attributes) if isinstance(device.attributes, dict) else {}
                if attrs.get("container_id") != info["container_id"]:
                    attrs["container_id"] = info["container_id"]
                    device.attributes = attrs


def ingest_batch(db: Session, payload: LogBatchIn) -> dict:
    if len(payload.logs) > settings.max_logs_per_batch:
        raise ValueError(f"logs exceeds MAX_LOGS_PER_BATCH={settings.max_logs_per_batch}")
    for item in payload.logs:
        if len(item.raw_message) > settings.max_raw_message_chars:
            raise ValueError(f"raw_message exceeds MAX_RAW_MESSAGE_CHARS={settings.max_raw_message_chars}")

    existing = db.scalar(select(LogBatch).where(
        LogBatch.source_id == payload.source_id,
        LogBatch.batch_id == payload.batch_id,
    ))
    if existing:
        return {
            "batch_id": existing.batch_id,
            "source_id": existing.source_id,
            "received": existing.received_count,
            "accepted": existing.accepted_count,
            "rejected": existing.rejected_count,
            "status": existing.status,
            "duplicate_batch": True,
        }

    try:
        batch = LogBatch(
            batch_id=payload.batch_id,
            source_id=payload.source_id,
            received_count=len(payload.logs),
            accepted_count=0,
            rejected_count=0,
            status="accepted",
        )
        db.add(batch)
        db.flush()  # 拿到 batch.id

        # Outbox：与批次、原始日志在同一事务中记录一条待处理任务，
        # 供后台 Worker 解析/标准化/分析。唯一约束 uk_task_business
        # (task_type, business_key) 保证同一批次只生成一条任务。
        db.add(ProcessingTask(
            task_type="process_batch",
            business_key=str(batch.id),
            status="pending",
        ))

        accepted = 0
        for item in payload.logs:
            stmt = mysql_insert(LogRaw).prefix_with("IGNORE").values(
                batch_id=payload.batch_id,
                source_id=payload.source_id,
                event_id=item.event_id,
                device_id=item.device_id,
                event_time=to_naive_local(item.event_time),
                format_type=item.format_type,
                raw_message=item.raw_message,
                raw_payload=build_raw_payload(item),
                process_status="pending",
            )
            result = db.execute(stmt)
            accepted += max(result.rowcount or 0, 0)

        # 心跳联动：登记未知设备并刷新 last_seen_at
        _touch_devices(db, [
            {"device_id": i.device_id, "device_type": i.device_type or "other", "hostname": i.hostname}
            for i in payload.logs
        ])

        batch.accepted_count = accepted
        batch.rejected_count = len(payload.logs) - accepted
        db.commit()
        return {
            "batch_id": batch.batch_id,
            "source_id": batch.source_id,
            "received": batch.received_count,
            "accepted": batch.accepted_count,
            "rejected": batch.rejected_count,
            "status": batch.status,
            "duplicate_batch": False,
        }
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Fluent Bit 适配
# ---------------------------------------------------------------------------

_TIMESTAMP_KEYS = ("@timestamp", "timestamp", "time", "event_time", "date")
_MESSAGE_KEYS = ("log", "message", "msg", "log_message")
_DEVICE_KEYS = ("device_id", "container_name", "hostname", "host", "source", "agent", "host.name")


def _first(record: dict, keys: tuple[str, ...]):
    for k in keys:
        v = record.get(k)
        if v not in (None, ""):
            return v
    return None


def _parse_event_time(value) -> datetime | None:
    """把 Fluent Bit 记录里的时间字段解析为 naive 本地时间；无法解析返回 None。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_naive_local(value)
    if isinstance(value, (int, float)):
        ts = value / 1000.0 if value > 10**12 else value
        try:
            return datetime.fromtimestamp(ts, tz=LOCAL_TZ).replace(tzinfo=None)
        except (ValueError, OSError):
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return to_naive_local(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except ValueError:
        return None


def parse_fluentbit_body(body: bytes) -> list[dict]:
    """解析 Fluent Bit HTTP output 的 body：JSON 数组 / 单对象 / NDJSON / [ts, record] 对。"""
    if not body:
        return []
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        records = []
        for elem in data:
            if isinstance(elem, dict):
                records.append(elem)
            elif isinstance(elem, list) and len(elem) == 2 and isinstance(elem[1], dict):
                records.append(elem[1])
        return records
    if isinstance(data, dict):
        return [data]

    # NDJSON：每行一个 JSON 对象
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def _decode_flb_time(value) -> datetime | None:
    """解析 Fluent Bit msgpack 事件时间（ExtType code=0，8 字节 = sec(uint32 BE) + nsec(uint32 BE)）。"""
    import msgpack

    if isinstance(value, msgpack.ExtType):
        if value.code == 0 and len(value.data) == 8:
            sec = int.from_bytes(value.data[0:4], "big")
            frac = int.from_bytes(value.data[4:8], "big")
            return datetime.fromtimestamp(sec + frac / 1_000_000_000, tz=LOCAL_TZ).replace(tzinfo=None)
        if value.code == -1:
            ts = msgpack.Timestamp.from_bytes(value.data)
            return datetime.fromtimestamp(ts.seconds + ts.nanoseconds / 1_000_000_000, tz=LOCAL_TZ).replace(tzinfo=None)
    return None


def parse_msgpack_body(body: bytes) -> list[dict]:
    """解析 Fluent Bit msgpack 格式：[[时间, 记录], ...]。"""
    import msgpack

    data = msgpack.unpackb(body, raw=False, strict_map_key=False)
    records: list[dict] = []
    if isinstance(data, list):
        for elem in data:
            if isinstance(elem, dict):
                records.append(elem)
            elif isinstance(elem, list) and len(elem) == 2 and isinstance(elem[1], dict):
                record = dict(elem[1])
                ts = _decode_flb_time(elem[0])
                if ts is not None:
                    record.setdefault("@timestamp", ts.isoformat())
                records.append(record)
    elif isinstance(data, dict):
        records.append(data)
    return records


def _map_fluentbit_record(record: dict, source_id: str, batch_id: str) -> dict:
    """把一条 Fluent Bit 记录映射为 log_raw 字段。"""
    raw_message = _first(record, _MESSAGE_KEYS)
    if raw_message is None:
        raw_message = json.dumps(record, ensure_ascii=False, default=str)
    else:
        raw_message = str(raw_message)
    raw_message = raw_message[: settings.max_raw_message_chars]

    # 用整条记录内容的哈希做事件级去重键（Fluent Bit 无事件 ID，重试时避免重复入库）
    event_id = hashlib.sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()

    # device_id 优先取容器名（区分不同服务），并去掉 Docker 容器名的前导 "/"
    device_id = _first(record, _DEVICE_KEYS)
    if isinstance(device_id, str):
        device_id = device_id.lstrip("/") or None
    # 同一容器名可能部署在多台采集主机上，用 source_id（每台不同的采集端标识）前缀区分
    if device_id and source_id:
        device_id = f"{source_id}-{device_id}"

    return {
        "batch_id": batch_id,
        "source_id": source_id,
        "event_id": event_id,
        "device_id": device_id,
        "event_time": _parse_event_time(_first(record, _TIMESTAMP_KEYS)),
        "format_type": "json",
        "raw_message": raw_message,
        "raw_payload": record,
        "process_status": "pending",
    }


def ingest_fluentbit(db: Session, records: list[dict], source_id: str) -> dict:
    """接收 Fluent Bit 上报的日志记录，落库并复用标准化/分析流水线。"""
    if not records:
        return {"batch_id": None, "source_id": source_id, "received": 0, "accepted": 0, "rejected": 0, "status": "empty"}
    if len(records) > settings.max_logs_per_batch:
        raise ValueError(f"logs exceeds MAX_LOGS_PER_BATCH={settings.max_logs_per_batch}")

    batch_id = f"fb-{uuid.uuid4().hex[:24]}"
    batch = LogBatch(
        batch_id=batch_id,
        source_id=source_id,
        received_count=len(records),
        accepted_count=0,
        rejected_count=0,
        status="accepted",
    )
    db.add(batch)
    db.flush()

    db.add(ProcessingTask(task_type="process_batch", business_key=str(batch.id), status="pending"))

    accepted = 0
    devices: list[dict] = []
    for record in records:
        mapped = _map_fluentbit_record(record, source_id, batch_id)
        stmt = mysql_insert(LogRaw).prefix_with("IGNORE").values(**mapped)
        result = db.execute(stmt)
        accepted += max(result.rowcount or 0, 0)
        if mapped["device_id"]:
            devices.append({
                "device_id": mapped["device_id"],
                "device_type": record.get("device_type") or "other",
                "hostname": _first(record, ("hostname", "host")),
                "container_id": record.get("container_id"),
            })

    _touch_devices(db, devices)

    batch.accepted_count = accepted
    batch.rejected_count = len(records) - accepted
    db.commit()
    return {
        "batch_id": batch_id,
        "source_id": source_id,
        "received": len(records),
        "accepted": accepted,
        "rejected": batch.rejected_count,
        "status": batch.status,
    }
