"""手动执行日志标准化处理（Celery 接入前的临时运行入口）。

用法（在 backend/ 目录下）：
  python -m app.tasks.process_logs --limit 100
  python -m app.tasks.process_logs --loop --interval 5   # 循环处理，模拟 worker
"""

import argparse
import time

from app.db.session import SessionLocal
from app.services.normalize import process_pending_logs


def main() -> None:
    parser = argparse.ArgumentParser(description="处理 pending 原始日志，标准化为 log_event")
    parser.add_argument("--limit", type=int, default=100, help="单轮处理条数上限")
    parser.add_argument("--loop", action="store_true", help="循环处理")
    parser.add_argument("--interval", type=int, default=5, help="循环间隔（秒）")
    args = parser.parse_args()

    while True:
        db = SessionLocal()
        try:
            result = process_pending_logs(db, args.limit)
            print(f"[process] processed={result['processed']} failed={result['failed']}")
        finally:
            db.close()
        if not args.loop:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
