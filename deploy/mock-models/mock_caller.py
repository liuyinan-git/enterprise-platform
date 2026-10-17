"""本地模拟「调用方」容器：周期向 mock 模型发推理请求，制造 access log 流量。

配合 mock_service.py：模型容器把每次 POST 打成 uvicorn 格式 access log，
后端 collect_model_callers 读到后按 source_ip（= 本容器的桥接网络 IP）经
container_ip_map 反查成容器名，再匹配调用方台账的 identifier（container 型）。

TARGETS 形如 "host:port:/path,host:port:/path"（逗号分隔），本容器只负责发
请求，成败无关紧要 —— 有 POST 就有 access log。
"""

import os
import time
import urllib.request

TARGETS = [t for t in os.environ.get("TARGETS", "").split(",") if t]
INTERVAL = float(os.environ.get("INTERVAL", "6"))
BODY = os.environ.get("BODY", '{"input":"mock"}')


def _post(target: str) -> None:
    host, port, path = target.split(":", 2)
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(
        url, data=BODY.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:  # noqa: BLE001  # 偶发失败无碍，本容器只负责制造流量
        pass


def main() -> None:
    print(f"caller targets={TARGETS} interval={INTERVAL}s", flush=True)
    while True:
        for target in TARGETS:
            _post(target)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
