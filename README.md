# 企业全域管控与智能告警平台

部署于企业内网的统一管控平台，按 **日志 / 智能体 / 模型 / 数据库** 四大业务模块组织，对企业 PC 终端、网络设备、服务器、应用、数据库、AI 智能体与模型等资产进行集中登记、状态监控、配置管理、审计与告警。

> 详细设计见《企业全域日志管控与智能告警平台 V1.0 技术设计说明书》（本仓库根目录）。

## 目录结构

单仓模块化：一个后端 + 一个前端，内部按四大业务模块分目录，共享 DB / Celery / 鉴权 / 前端框架，供多人分模块并行开发。

```
backend/app/
├── core/           # 核心基础设施：config / db / security / timeutil / response / ai_client
├── platform/       # 平台公共资源：企业微信通知 / 附件 / 系统监控与总览
├── modules/        # 业务模块
│   ├── log/        #   日志管控（采集、标准化、规则、事件、告警、设备）
│   ├── agent/      #   智能体管控（台账、心跳、审计）
│   ├── model/      #   模型管控（供应商/模型台账、端点健康、用量）
│   └── database/   #   数据库管控（实例台账、健康、备份）
├── tasks/          # Celery 装配（beat + 各模块任务注册）
└── main.py         # FastAPI 入口，聚合各模块路由

frontend/src/
├── core/           # 共享 http 客户端
├── platform/       # 平台页面（总览/企业微信/附件/系统监控）
├── modules/        # 与后端一一对应的四模块页面
├── layouts/        # 侧边栏（按模块分组）
└── router/         # 路由聚合
```

## 快速开始（Docker Compose）

```bash
cp .env.example .env      # 修改其中的 CHANGE_ME 占位密钥
docker compose up -d
curl http://localhost:7550/health/ready
```

后端容器启动时会自动执行 `alembic upgrade head` 完成数据库迁移。

## 本地开发（不使用 Docker）

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # 首次先复制本地环境变量模板，改 CHANGE_ME 占位
# 需要可用的 MySQL，并已创建 enterprise_platform 数据库
alembic upgrade head
uvicorn app.main:app --reload --port 7550

# 另开终端启动异步 Worker / 调度（Windows 需 --pool=solo）
celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo
celery -A app.tasks.celery_app.celery_app beat --loglevel=info
```

前端：

```bash
cd frontend
npm install
npm run dev      # Vite 5170，代理 /api、/health 到 7550
```

接口文档：http://localhost:7550/docs
