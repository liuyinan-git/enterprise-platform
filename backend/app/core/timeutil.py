"""统一时间约定：平台全库时间存 naive 本地时间（北京，UTC+8）。

历史设计为「naive UTC」，按业务需要统一切到本地时间：
所有「当前时间」与带时区时间戳的转换都落到 UTC+8，DB 会话也同步 `SET time_zone='+08:00'`。
"""

from datetime import datetime, timedelta, timezone

LOCAL_OFFSET = timedelta(hours=8)
LOCAL_TZ = timezone(LOCAL_OFFSET)


def local_now() -> datetime:
    """当前本地（北京）时间，naive（无 tzinfo）。"""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def to_naive_local(value: datetime | None) -> datetime | None:
    """带时区时间转本地（北京）后去 tzinfo；无时区时间按本地解释（原样保留）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TZ).replace(tzinfo=None)
    return value.astimezone(LOCAL_TZ).replace(tzinfo=None)
