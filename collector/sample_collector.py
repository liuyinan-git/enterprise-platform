#!/usr/bin/env python3
"""采集端样例程序。

演示要点：
1. 本地持久化队列（pending.jsonl）：平台确认成功后才删除已发送数据；
2. 失败时指数退避重试，重试复用同一 batch_id / event_id，保证幂等；
3. 与平台接口约定对齐：X-API-Key 认证、POST /api/v1/logs/batch 批量上报。

用法：
  python sample_collector.py --base-url http://localhost:7550 \\
      --api-key dev-local-collector-key --source collector01 --count 100

仅重发本地已缓存、未发送成功的队列：
  python sample_collector.py --base-url http://localhost:7550 \\
      --api-key dev-local-collector-key --source collector01 --flush-only
"""

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

DEFAULT_BATCH_SIZE = 200
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 1.0
PENDING_FILE = "pending.jsonl"


def now_iso() -> str:
    # 带时区的 ISO 8601，符合平台接口约定
    return datetime.now(timezone.utc).isoformat()


def generate_logs(source_id: str, count: int) -> list[dict]:
    """生成一批样例日志，模拟 server / firewall / pc 三类来源。"""
    templates = [
        {
            "device_type": "server",
            "hostname": "app-server-01",
            "raw_message": "SSH authentication failed for user admin",
            "fields": {"source_ip": "10.10.1.25", "username": "admin", "protocol": "ssh"},
        },
        {
            "device_type": "firewall",
            "hostname": "fw-01",
            "raw_message": "ACCEPT tcp 10.10.1.25:52331 -> 10.10.1.30:22",
            "fields": {"source_ip": "10.10.1.25", "dest_ip": "10.10.1.30", "action": "accept"},
        },
        {
            "device_type": "pc",
            "hostname": "pc-001",
            "raw_message": "user login success",
            "fields": {"username": "zhangsan", "result": "success"},
        },
    ]
    logs = []
    for i in range(count):
        tpl = templates[i % len(templates)]
        logs.append({
            # event_id 一旦生成即持久化到队列，重试时复用，保证平台侧去重幂等
            "event_id": f"{source_id}-{uuid.uuid4().hex}",
            "event_time": now_iso(),
            "device_id": f"{tpl['device_type']}-{i % 5:03d}",
            "device_type": tpl["device_type"],
            "hostname": tpl["hostname"],
            "format": "json",
            "raw_message": tpl["raw_message"],
            "fields": tpl["fields"],
        })
    return logs


def enqueue(logs: list[dict], path: Path) -> None:
    with path.open("a", encoding="utf-8") as f:
        for log in logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")


def load_pending(path: Path) -> list[dict]:
    if not path.exists():
        return []
    logs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            logs.append(json.loads(line))
    return logs


def save_pending(logs: list[dict], path: Path) -> None:
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logs),
        encoding="utf-8",
    )


def post_batch(base_url: str, api_key: str, source_id: str, batch_id: str, logs: list[dict]) -> bool:
    payload = {"batch_id": batch_id, "source_id": source_id, "logs": logs}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/api/v1/logs/batch",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            accepted = (data.get("data") or {}).get("accepted")
            print(f"[ok] batch={batch_id} HTTP {resp.status} accepted={accepted}")
            return True
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", "ignore")
        print(f"[fail] batch={batch_id} HTTP {exc.code}: {body_text[:200]}")
        return False
    except Exception as exc:  # 网络异常等
        print(f"[fail] batch={batch_id} {type(exc).__name__}: {exc}")
        return False
    return False


def flush(base_url: str, api_key: str, source_id: str, batch_size: int, path: Path) -> int:
    """把本地队列按批次上报；成功才删除，失败按指数退避重试。"""
    pending = load_pending(path)
    sent = 0
    while pending:
        chunk = pending[:batch_size]
        batch_id = f"{source_id}-{uuid.uuid4()}"  # 同一批重试复用，保证幂等
        ok = False
        for attempt in range(1, MAX_RETRIES + 1):
            ok = post_batch(base_url, api_key, source_id, batch_id, chunk)
            if ok:
                break
            sleep = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            print(f"[retry] batch={batch_id} 第 {attempt} 次失败，等待 {sleep:.1f}s 后重试")
            time.sleep(sleep)
        if not ok:
            print(f"[abort] batch={batch_id} 超过最大重试次数，保留在本地队列，停止本轮发送")
            break
        pending = pending[len(chunk):]
        save_pending(pending, path)
        sent += len(chunk)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description="采集端样例程序")
    parser.add_argument("--base-url", default="http://localhost:7550")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--source", default="collector01")
    parser.add_argument("--count", type=int, default=100, help="生成的样例日志条数")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--pending-file", default=PENDING_FILE)
    parser.add_argument("--flush-only", action="store_true", help="只发送已有队列，不生成新日志")
    args = parser.parse_args()

    path = Path(args.pending_file)

    if not args.flush_only:
        logs = generate_logs(args.source, args.count)
        enqueue(logs, path)
        print(f"[enqueue] 已生成并缓存 {len(logs)} 条日志到 {path}")

    sent = flush(args.base_url, args.api_key, args.source, args.batch_size, path)
    print(f"[done] 本次成功上报 {sent} 条")


if __name__ == "__main__":
    main()
