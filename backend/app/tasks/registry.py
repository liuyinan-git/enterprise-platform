"""集中登记各业务模块的 Celery 任务模块，供 celery_app include。"""

TASK_MODULES = [
    "app.modules.log.tasks",
    "app.modules.agent.tasks",
    "app.modules.model.tasks",
    "app.modules.database.tasks",
]
