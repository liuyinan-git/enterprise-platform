from app.modules.log.parsers.base import NormalizedEvent, Parser
from app.modules.log.parsers.json_parser import JsonParser
from app.modules.log.parsers.syslog_parser import SyslogParser

# 解析器执行顺序：结构化 JSON 优先，再标准格式（设计文档 6.3）
PARSERS: list[Parser] = [JsonParser(), SyslogParser()]

__all__ = ["NormalizedEvent", "Parser", "JsonParser", "SyslogParser", "PARSERS"]
