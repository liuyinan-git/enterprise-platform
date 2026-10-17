"""模型容器 access log 解析（纯函数，不碰 ORM，可单测）。

数据源是模型容器（vLLM 等）打到 stdout 的 uvicorn access log，每行形如：

    INFO:     172.28.110.11:54321 - "POST /v1/chat/completions HTTP/1.1" 200 OK

从中提取 source_ip + method + path + status，并**只保留真实推理请求**，
排除平台自探测（GET /v1/models、GET /metrics）与健康检查，避免把平台自身
混进「调用方」统计。

access log 只给「调用次数 + 状态码」，不含 token 数（token 在 /metrics 聚合里），
这是本方案的天花板。
"""

import re
from dataclasses import dataclass

# uvicorn access log：INFO: <ip>:<port> - "<METHOD /path HTTP/1.1" <status> ...
# ip 兼容 IPv4 与方括号包裹的 IPv6；HTTP 版本允许缺省（个别定制版 vLLM 会省略）。
ACCESS_LINE_RE = re.compile(
    r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3}|\[[^\]]+\])"
    r":(?P<port>\d+)\s+-\s+"
    r'"(?P<method>[A-Z]+)\s+(?P<path>[^"\s]+)(?:\s+HTTP/\d\.\d)?"\s+'
    r"(?P<status>\d{3})"
)

# 非推理的探活路径（GET 为主），POST 打到这些路径也不计入调用量
_PROBE_PATHS = {"/v1/models", "/metrics", "/health", "/healthz", "/", "/v1"}


@dataclass(frozen=True)
class AccessLine:
    source_ip: str
    method: str
    path: str
    status: int


def is_inference(method: str, path: str) -> bool:
    """只统计真实推理请求：POST 且非探活路径。

    平台自探测是 GET /v1/models、GET /metrics —— method != POST 已天然排除；
    这里再把少数可能以 POST 出现的探活路径挡掉，双保险。
    """
    if method != "POST":
        return False
    p = path.split("?", 1)[0].rstrip("/") or "/"
    return p not in _PROBE_PATHS


def parse_access_lines(text: str) -> list[AccessLine]:
    """解析 access log 文本，返回推理请求行列表（已过滤探活噪声）。"""
    if not text:
        return []
    lines: list[AccessLine] = []
    for match in ACCESS_LINE_RE.finditer(text):
        method = match.group("method")
        path = match.group("path")
        if not is_inference(method, path):
            continue
        status = int(match.group("status"))
        lines.append(
            AccessLine(
                source_ip=match.group("ip"),
                method=method,
                path=path,
                status=status,
            )
        )
    return lines
