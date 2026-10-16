"""业务模块汇总：导入各模块 models，注册到 Base.metadata（供 Alembic 使用）。"""

from app.modules.agent import models as agent_models  # noqa: F401
from app.modules.database import models as database_models  # noqa: F401
from app.modules.log import models as log_models  # noqa: F401
from app.modules.model import models as model_models  # noqa: F401
