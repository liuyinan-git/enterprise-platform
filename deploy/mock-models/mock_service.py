"""本地模拟模型服务（仅外网开发机联调用，绝不部署到服务器）。

单文件、纯标准库，按 ROLE 环境变量分角色模拟内网 172.28.110.11 的模型服务：
- vllm: GET /v1/models 返回 OpenAI 兼容模型列表；GET /metrics 返回含
        vllm:request_success_total 的 Prometheus 文本。计数器每次 /v1/models
        请求 +1，AUTO_QPM>0 时后台线程按速率自动累加（模拟持续业务流量）。
- http: 任意 GET 一律 404 —— 印证「HTTP 探活：有响应即存活」。
- tcp:  裸 socket 监听 —— 模拟 WebSocket 等非标准协议服务的端口探活。

由同目录 docker-compose.yml 编排，容器名与内网真实容器一致（model_code = 容器名）。
"""

import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ.get("ROLE", "vllm")
PORT = int(os.environ.get("PORT", "18033"))
MODEL_NAME = os.environ.get("MODEL_NAME", "mock-model")
COUNTER_START = int(os.environ.get("COUNTER_START", "1000"))
# 每分钟自动累加的调用量；0 表示只按 /v1/models 实际请求计数
AUTO_QPM = float(os.environ.get("AUTO_QPM", "0"))

_counter = COUNTER_START
_lock = threading.Lock()


def _bump(n: int = 1) -> None:
    global _counter
    with _lock:
        _counter += n


def _metrics_text() -> bytes:
    with _lock:
        value = _counter
    text = (
        "# HELP vllm:request_success_total Number of requests successfully processed.\n"
        "# TYPE vllm:request_success_total counter\n"
        f'vllm:request_success_total{{model_name="{MODEL_NAME}"}} {value}\n'
    )
    return text.encode("utf-8")


def _start_auto_increment() -> None:
    if AUTO_QPM <= 0:
        return
    interval = 60.0 / AUTO_QPM

    def worker() -> None:
        while True:
            time.sleep(interval)
            _bump()

    threading.Thread(target=worker, daemon=True).start()


class _BaseHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # 精简为单行日志，避免刷屏
        print(f"{time.strftime('%H:%M:%S')} {self.address_string()} {fmt % args}", flush=True)


class _VllmHandler(_BaseHandler):
    def do_GET(self) -> None:
        if self.path == "/v1/models":
            _bump()  # 每次模型列表请求计一次成功调用（模拟真实推理调用）
            body = (
                '{"object":"list","data":['
                f'{{"id":"{MODEL_NAME}","object":"model","created":1700000000,"owned_by":"vllm"}}]}}'
            ).encode("utf-8")
            self._send(200, "application/json", body)
        elif self.path == "/metrics":
            self._send(200, "text/plain; version=0.0.4; charset=utf-8", _metrics_text())
        else:
            self._send(404, "text/plain", b"not found")


class _Http404Handler(_BaseHandler):
    def do_GET(self) -> None:  # 任意响应即存活（HTTP 探活口径）
        self._send(404, "text/plain", b"not found")


def _run_tcp() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(16)
    print(f"tcp listener on {PORT}", flush=True)
    while True:
        conn, _ = srv.accept()  # 接受连接即满足端口探活
        conn.close()


def main() -> None:
    if ROLE == "tcp":
        _run_tcp()
        return
    _start_auto_increment()
    handler = _Http404Handler if ROLE == "http" else _VllmHandler
    server = ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    print(f"{ROLE} service on {PORT} (model={MODEL_NAME})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
