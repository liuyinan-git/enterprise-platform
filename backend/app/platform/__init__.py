"""平台级公共资源汇总：导入各子模块 models，注册到 Base.metadata（供 Alembic 使用）。"""

from app.platform.attachments import models as attachment_models  # noqa: F401
from app.platform.notifications import models as wecom_models  # noqa: F401
