"""手动执行规则分析与告警（Celery 接入前的临时运行入口）。

用法（在 backend/ 目录下）：
  python -m app.modules.log.scripts.analyze --seed                    # 先写入内置规则再分析
  python -m app.modules.log.scripts.analyze --loop --interval 10      # 循环执行，模拟调度
"""

import argparse
import time

from app.core.db import SessionLocal
from app.modules.log.rules.builtins import seed_rules
from app.modules.log.services.analyze import analyze


def main() -> None:
    parser = argparse.ArgumentParser(description="规则引擎 + 事件聚合 + 告警")
    parser.add_argument("--seed", action="store_true", help="先写入内置规则")
    parser.add_argument("--loop", action="store_true", help="循环执行")
    parser.add_argument("--interval", type=int, default=10, help="循环间隔（秒）")
    args = parser.parse_args()

    if args.seed:
        db = SessionLocal()
        try:
            n = seed_rules(db)
            print(f"[seed] 新增内置规则 {n} 条")
        finally:
            db.close()

    while True:
        db = SessionLocal()
        try:
            result = analyze(db)
            print(f"[analyze] rules={result['rules']} events={result['events']} alerts={result['alerts']}")
        finally:
            db.close()
        if not args.loop:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
