from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedEvent:
    """标准化事件字段（对应 log_event 表，缺省值保证 NOT NULL 列始终有值）。"""

    device_type: str = "other"
    event_category: str = "unknown"
    event_type: str = "unknown"
    severity: str = "info"
    security_label: str = "unknown"
    hostname: str | None = None
    source_ip: str | None = None
    dest_ip: str | None = None
    source_port: int | None = None
    dest_port: int | None = None
    username: str | None = None
    process_name: str | None = None
    event_time: datetime | None = None
    normalized_data: dict[str, Any] = field(default_factory=dict)


class Parser:
    """解析器基类。

    parse 返回 NormalizedEvent；无法解析时返回 None，由后续解析器兜底。
    """

    name: str = "base"

    def parse(self, raw_message: str, payload: dict | None, format_type: str) -> NormalizedEvent | None:
        raise NotImplementedError
