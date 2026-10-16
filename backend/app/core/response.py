"""统一响应帮助函数：新模块端点用它减少样板代码，保持 `{code, message, data}` 结构。"""

from typing import Any


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def created(data: Any = None, message: str = "created") -> dict:
    return {"code": 0, "message": message, "data": data}


def paginated(items: list, total: int, page: int, page_size: int) -> dict:
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}
