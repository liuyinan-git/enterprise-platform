"""统一响应帮助函数：新模块端点用它减少样板代码，保持 `{code, message, data}` 结构。"""

from typing import Any


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def created(data: Any = None, message: str = "created") -> dict:
    return {"code": 0, "message": message, "data": data}


def paginated(items: list, total: int, page: int, page_size: int, extra: dict | None = None) -> dict:
    """分页响应；`extra` 用于附带页面级状态（如 Docker 降级标记），保持向后兼容。"""
    data = {"items": items, "total": total, "page": page, "page_size": page_size}
    if extra:
        data.update(extra)
    return {"code": 0, "message": "success", "data": data}
