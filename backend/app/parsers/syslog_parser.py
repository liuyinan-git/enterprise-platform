import re

from app.parsers.base import NormalizedEvent, Parser

# 典型 Syslog 报文：<PRI>MMM dd HH:MM:SS hostname tag[pid]: message
SYSLOG_RE = re.compile(
    r"^(?:<(?P<pri>\d{1,3})>)?"
    r"(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<tag>\S+?)(?:\[(?P<pid>\d+)\])?:\s?"
    r"(?P<message>.*)$"
)


class SyslogParser(Parser):
    """Syslog 标准格式解析：提取主机名与程序标签，正文交给规则映射分类。"""

    name = "syslog"

    def parse(self, raw_message: str, payload: dict | None, format_type: str) -> NormalizedEvent | None:
        m = SYSLOG_RE.match((raw_message or "").strip())
        if not m:
            return None

        event = NormalizedEvent()
        event.hostname = m.group("host")
        event.process_name = m.group("tag")
        event.normalized_data = {
            "syslog_pri": m.group("pri"),
            "syslog_message": m.group("message"),
        }
        return event
