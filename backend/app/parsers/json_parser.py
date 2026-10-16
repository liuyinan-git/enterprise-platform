from app.parsers.base import NormalizedEvent, Parser


class JsonParser(Parser):
    """结构化 JSON 解析：优先读取采集端已提供的明确字段（设计文档 6.3 第 1 步）。"""

    name = "json"

    def parse(self, raw_message: str, payload: dict | None, format_type: str) -> NormalizedEvent | None:
        if not isinstance(payload, dict) or not payload:
            return None

        event = NormalizedEvent()
        event.device_type = payload.get("device_type") or "other"
        event.hostname = payload.get("hostname")
        event.source_ip = payload.get("source_ip")
        event.dest_ip = payload.get("dest_ip")
        event.source_port = payload.get("source_port")
        event.dest_port = payload.get("dest_port")
        event.username = payload.get("username")
        event.process_name = payload.get("process_name")

        if payload.get("event_category"):
            event.event_category = payload["event_category"]
        if payload.get("event_type"):
            event.event_type = payload["event_type"]
        if payload.get("severity"):
            event.severity = payload["severity"]
        if payload.get("security_label"):
            event.security_label = payload["security_label"]

        event.normalized_data = dict(payload)
        return event
