# AGENTS.md — 项目说明

> 本文档供 AI 编码助手及新成员快速了解本项目。最后更新：2026-10-16。

## 一、项目概况

**企业全域管控与智能告警平台（Enterprise Platform）** 的后端 + 前端，已从单一「日志管控」重构为 **单仓模块化** 架构，按 **log（日志）/ agent（智能体）/ model（模型）/ database（数据库）** 四大业务模块组织，供多人分模块并行开发。

已完成的能力：

- 健康检查（存活 / 就绪）
- 日志接入（批量接收、幂等 + Outbox；兼容 Fluent Bit HTTP output）与批次查询
- 日志标准化（`log_raw → log_event`，JSON/Syslog 解析 + 关键词规则映射）
- 规则引擎（阈值规则）+ 事件聚合（SHA256 指纹）+ 企业微信告警
- 异步调度（Celery + Redis）：Outbox 调度、批次标准化、规则分析、告警重试
- AI 研判（DeepSeek 大模型辅助分析，结构化输出）
- 智能体管控（注册台账、心跳状态、操作审计）
- 模型管控（供应商/模型台账、端点健康探测、用量统计）
- 数据库管控（实例台账、连接健康探测、备份记录、**容器实况与启停**）
- 管理前端（Vue 3）：按模块分组的侧边栏 + 总览/日志/智能体/模型/数据库/平台管理页面

**技术栈**

| 类别 | 技术 |
| ---- | ---- |
| 后端语言 | Python 3.12 |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0（Mapped/mapped_column） |
| 数据库 | MySQL 8.0（驱动 PyMySQL） |
| 迁移 | Alembic |
| 配置 | pydantic-settings |
| 异步任务 | Celery + Redis |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts |
| 部署 | Docker Compose（python:3.12-slim 镜像） |

依赖清单见 [backend/requirements.txt](backend/requirements.txt)、[frontend/package.json](frontend/package.json)。完整设计见根目录《企业全域日志管控与智能告警平台 V1.0 技术设计说明书》。

## 二、目录结构（单仓模块化）

```
enterprise-platform/
├── docker-compose.yml            # 容器编排（mysql/redis/api/worker/scheduler）
├── .env.example                  # 环境变量示例（复制为 .env 使用）
├── README.md
├── nginx/                        # 反向代理（HTTPS 后续接入）
├── backend/
│   ├── Dockerfile                # 容器构建，启动时先迁移后运行 uvicorn
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                # 读 settings.database_url + Base.metadata（import app.modules / app.platform）
│   │   └── versions/             # 0001..0012 迁移
│   ├── app/
│   │   ├── main.py               # FastAPI 入口：health/root + 聚合各模块 router
│   │   ├── core/                 # 核心基础设施（无业务表）
│   │   │   ├── config.py         # Settings（读 .env）
│   │   │   ├── db.py             # Base + engine + SessionLocal + get_db
│   │   │   ├── security.py       # require_collector_key / mask_secret
│   │   │   ├── timeutil.py       # local_now / to_naive_local（本地时间 +8）
│   │   │   ├── response.py       # ok()/created()/paginated() 统一响应
│   │   │   └── ai_client.py      # OpenAI 兼容 chat_completion
│   │   ├── platform/             # 平台级公共资源（不属于任一业务模块）
│   │   │   ├── notifications/    #   企业微信：models/schemas/service/wecom/api
│   │   │   ├── attachments/      #   附件：models + api（/files）
│   │   │   └── monitoring/       #   系统监控 + 总览（/system/* /dashboard/*）
│   │   ├── modules/              # 业务模块（4 个，结构一致）
│   │   │   ├── log/              #   日志管控：models/schemas/api/services/parsers/rules/ai/tasks
│   │   │   ├── agent/            #   智能体管控：models/schemas/api/services/tasks
│   │   │   ├── model/            #   模型管控：models/schemas/api/services/tasks
│   │   │   └── database/         #   数据库管控：models/schemas/api/services/tasks
│   │   │                         #     + 容器实况：docker_client/containers/container_api/container_config
│   │   └── tasks/                # Celery 装配：celery_app.py + registry.py
│   └── tests/                    # 测试（占位）
├── frontend/
│   └── src/
│       ├── core/api/client.ts    # axios 实例 + ListResult + getHealth
│       ├── platform/             # 平台页面（Dashboard/Wecom/Files/System）+ 各 api/routes
│       ├── modules/              # 与后端一一对应的四模块（api.ts + routes.ts + views/）
│       ├── layouts/MainLayout.vue# 侧边栏（按模块分组）
│       └── router/index.ts       # 聚合各模块 routes
├── collector/                    # 采集端样例 + fluent-bit.conf 样例
├── database/{init,seeds}/        # 数据库初始化/种子（预留）
├── deploy/                       # 部署脚本（预留）
└── docs/                         # 文档
```

**模块边界约定（多人协作关键）**：每个模块独立拥有自己的 `models.py` / `schemas.py` / `api.py`（`APIRouter` 自声明 prefix + tags）/ `services.py` / `tasks.py`。跨模块只允许依赖 `core/`（基础设施）与 `platform/`（公共资源），业务模块之间不互相 import（`platform/monitoring` 聚合展示可读 `modules.log` 的模型，属唯一例外）。

## 三、配置（backend/app/core/config.py）

通过 `pydantic-settings` 的 `BaseSettings` 读取环境变量或 `.env`。关键字段（新增三项见末尾）：

| 配置项 | 默认值 | 说明 |
| ------ | ------ | ---- |
| `app_env` / `app_port` / `log_level` | `development` / `7550` / `INFO` | 运行环境 / 端口 / 日志级别 |
| `mysql_*` | `enterprise_platform` / `log_app` / `CHANGE_ME_*` | ⚠️ 数据库连接，密码需替换 |
| `mysql_pool_size` / `mysql_max_overflow` | `5` / `10` | 连接池 |
| `collector_api_key` | `CHANGE_ME_use_a_long_random_secret` | ⚠️ 采集端认证密钥 |
| `max_logs_per_batch` / `max_raw_message_chars` | `1000` / `20000` | 接入限制 |
| `wecom_*` | — | 企业微信自建应用配置与通知级别 |
| `redis_*` | `localhost` / `6379` | Celery broker/backend |
| `ai_*` | — | AI 研判（OpenAI 兼容接口） |
| `upload_dir` / `max_upload_size_mb` | `uploads` / `200` | 附件存储 |
| `agent_offline_grace_seconds` | `300` | 智能体心跳超时判定离线宽限 |
| `model_check_timeout_seconds` | `5` | 模型端点探测超时 |
| `database_check_timeout_seconds` | `3` | 数据库连接探测超时 |

- `database_url` / `redis_url` 为派生属性；`get_settings()` 用 `@lru_cache` 缓存。
- **例外：容器管控的配置不在这里**，而在 [modules/database/container_config.py](backend/app/modules/database/container_config.py)（读 `CONTAINER_*`）。因为本文件的 `Settings` 是 `extra="ignore"`，`.env` 里多出的键不会让它报错，模块自带一份 `BaseSettings` 读同一份 `.env` 即可——多人协作时新增配置不必改这个共享文件。

## 四、HTTP 端点（前缀 `/api/v1`）

### 健康检查（无鉴权，[app/main.py](backend/app/main.py)）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/health/live` / `/health/ready` / `/` | 存活 / 就绪 / 服务信息 |

### 采集接口（需 `X-API-Key`，见 [core/security.py](backend/app/core/security.py)）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/logs/batch` | 批量日志接收（202） |
| POST | `/ingest/fluentbit` | Fluent Bit HTTP output |
| GET | `/batches/{batch_id}` | 批次状态查询 |
| POST | `/agents/{agent_id}/heartbeat` | 智能体心跳上报（同样需采集密钥） |

### 日志模块（[modules/log/api.py](backend/app/modules/log/api.py)，tag=log）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET/POST | `/batches` / `/logs` / `/raw-logs` / `/collectors` | 批次/日志/原始/采集端列表 |
| GET | `/logs/{log_id}` | 日志详情 |
| GET/PATCH | `/events` / `/events/{event_no}` | 安全事件列表/详情/流转 |
| POST | `/events/{event_no}/ai-analyze` | 手动 AI 研判 |
| GET/POST | `/alerts` / `/alerts/{alert_no}/retry` | 告警列表/重试 |
| GET/POST/PUT | `/rules` / `/rules/{rule_code}` | 规则 CRUD |
| GET/POST | `/rule-suggestions` | 规则建议 |
| GET/POST/DELETE | `/devices` / `/devices/{device_id}` | 设备登记 |

### 智能体模块（[modules/agent/api.py](backend/app/modules/agent/api.py)，tag=agent）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET/POST | `/agents` | 台账列表 / 登记（agent_id 幂等 upsert） |
| GET/PATCH/DELETE | `/agents/{agent_id}` | 详情 / 更新 / 删除 |
| GET | `/agent-audits` | 操作审计列表 |

### 模型模块（[modules/model/api.py](backend/app/modules/model/api.py)，tag=model）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET/POST | `/model-providers`；GET/PUT/DELETE `/model-providers/{code}` | 供应商台账（api_key 脱敏） |
| GET/POST | `/models`；GET/PUT/DELETE `/models/{code}` | 模型台账 |
| POST | `/models/{code}/check` | 端点健康探测 |
| GET/POST | `/model-usages` | 用量统计 |

### 数据库模块（[modules/database/api.py](backend/app/modules/database/api.py)，tag=database）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET/POST | `/database-instances`；GET/PUT/DELETE `/database-instances/{code}` | 实例台账（password 脱敏） |
| POST | `/database-instances/{code}/check` | 连接健康探测 |
| GET | `/database-health` | 健康检查记录 |
| GET/POST | `/database-backups` | 备份记录（自运维） |
| GET | `/database-overview` | **台账 + 容器实况合并视图**（「数据库实例」页用） |
| GET | `/database-containers`；`/database-containers/{id}`、`/logs`、`/exec-command` | 容器列表 / 详情 / 日志 / 可复制的 exec 命令（前端已撤掉「复制命令」按钮，接口保留待用） |
| POST | `/database-containers/{id}/start`·`/stop`·`/restart` | 容器启停重启（需 `admin` 或 `database_container_admin`） |
| GET | `/database-container-audits` | 容器操作审计 |

### 平台资源（platform/*，tag=notifications/attachments/monitoring）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET/PUT | `/wecom/config`；POST `/wecom/test` | 企业微信配置/测试 |
| GET/POST/DELETE | `/files` 等 | 附件管理 |
| GET | `/system/overview`；POST `/system/reset` | 系统监控/还原 |
| GET | `/dashboard/overview` | 首页态势总览 |

### 鉴权与响应格式

- 采集接口通过 **`X-API-Key`** 鉴权（`require_collector_key`，`compare_digest` 防时序攻击）；未配置返回 503、不匹配返回 401。
- 管理接口走 `Depends(require_roles(...))`；`OIDC_ENABLED=false`（当前默认）时降级为**匿名 admin**，即内网开放现状，开启 OIDC 后按 token 角色控制。**容器启停额外要求 `database_container_admin`**，`viewer` 只能看。
- 统一响应 `{"code": 0, "message": "...", "data": ...}`（新模块用 `core/response.py` 的 `ok()/created()/paginated()`）。

## 五、数据模型

共 **21 张表**，MySQL InnoDB，主键无符号 BIGINT 自增，时间列 `DATETIME(3)`。ORM 按模块拆分：

| 模块 | 表 | 关键约束 |
| ---- | ---- | ---- |
| log（12 张） | `device_registry` `log_batch` `log_raw` `processing_task` `log_event` `analysis_rule` `security_event` `security_event_log` `alert_record` `rule_suggestion` | 唯一键 + 查询索引，见 [modules/log/models.py](backend/app/modules/log/models.py) |
| platform（2 张） | `wecom_config`（单行 id=1）、`attachment` | — |
| agent（2 张） | `agent_registry`（uk_agent_id）、`agent_audit` | 心跳 + 审计 |
| model（3 张） | `model_provider`（uk_provider_code）、`model_registry`（uk_model_code + FK provider）、`model_usage`（uk model+day） | 供应商/模型/用量 |
| database（4 张） | `database_instance`（uk_instance_code）、`database_health`、`database_backup`、`database_container_audit` | 实例/健康/备份/容器操作审计 |

迁移脚本 `0001..0012`，其中 `0009_agent_module`、`0010_model_module`、`0011_database_module`、`0012_database_container` 为新增模块表。

## 六、核心逻辑

### 日志模块（modules/log/）

- **接入** [services/ingest.py](backend/app/modules/log/services/ingest.py)：上限校验 → 批次幂等 → `LogBatch` + Outbox 落 `ProcessingTask` → 逐条 `INSERT ... IGNORE` 写 `LogRaw` → 计数回写。同时 `_touch_devices()` 心跳联动（未知设备自动登记、刷新 `last_seen_at`）。`ingest_fluentbit()` 兼容 JSON 数组/单对象/NDJSON/msgpack，event_id 取记录内容哈希幂等。
- **标准化** [services/normalize.py](backend/app/modules/log/services/normalize.py) + parsers/：解析器链（JSON/Syslog）→ `classify()` 关键词映射 → 未知兜底；`process_pending_logs()` 批量写 `log_event`。
- **规则分析** [services/analyze.py](backend/app/modules/log/services/analyze.py) + rules/：阈值规则评估 → `sha256(rule_code|group_key)` 指纹聚合事件 → 新建 `AlertRecord` → `_send_alert()`。
- **AI 研判** [services/analyze_ai.py](backend/app/modules/log/services/analyze_ai.py) + ai/：组装输入 → `core/ai_client.chat_completion` → 结构化校验写回 `event.ai_analysis`。由 `run_ai_analysis`（30s）驱动。
- **设备健康** [services/device_health.py](backend/app/modules/log/services/device_health.py)：`detect_offline_devices()` 判定失联 → 生成/关闭 `DEVICE_OFFLINE` 事件与告警。

### 智能体模块（modules/agent/）

`agent_status()` 按 `last_seen_at` + `agent_offline_grace_seconds` 判定在线/离线；`check_agent_offline` 周期任务（60s）统计离线数。心跳由 `POST /agents/{id}/heartbeat` 上报。操作经 `record_audit()` 落 `agent_audit`。

### 模型模块（modules/model/）

`probe_provider()` 对供应商 `base_url` 发 `GET /models`（OpenAI 兼容）探测；`check_model_endpoints` 周期任务（60s）批量刷新 `health_status`。供应商 `api_key`、实例 `password` 读写均经 `core/security.mask_secret` 脱敏。

### 数据库模块（modules/database/）

`probe_instance()` 用 `socket.create_connection` 探测 host:port；`check_database_health` 周期任务（60s）刷新 `health_status` 并落 `database_health` 记录。`database_backup` 登记备份记录（自运维）。

### 容器管控（modules/database/，与数据库台账同页合并）

这是**全平台第一个能改变外部系统状态的能力**（其余模块都是台账 + 只读探测），所以读写守卫、自保护、审计三件事都做了。

- [docker_client.py](backend/app/modules/database/docker_client.py)：只用标准库 `urllib` 访问 **docker-socket-proxy 白名单代理**（刻意不引入 docker SDK，与 `core/ai_client.py` 的零额外依赖一致）。含**日志多路复用解帧**（无 TTY 容器的 `/logs` 是 `[stream(1)][0,0,0][size(4,大端)]` 帧序列，不解帧会把 8 字节二进制头混进文本）。
- [containers.py](backend/app/modules/database/containers.py)：类型识别 / 自保护 / 台账关联 / 序列化，规则集中一处。
- [container_api.py](backend/app/modules/database/container_api.py)：容器接口。它被 [api.py](backend/app/modules/database/api.py) 的 router **include** 进来，所以 `main.py` 不需要改。
- 合并视图 `GET /database-overview` 在 `api.py`（它是 `list_instances` 的超集）：每行台账带上 `container` + `container_link`，另返回 `unregistered`（不在台账、也未被任何台账行关联的容器）。`unregistered_scope` 默认 `managed`——**只列受管类型**，因为宿主机上跑的应用容器（kafka / 后端 / 前端……）不是纳管对象，全列出来会把真正要纳管的数据库淹掉；`all` 则连未分类的一起列。同时返回 `unregistered_hidden_unknown`（被滤掉几个）与 `unregistered_by_type`（各类型计数，供筛选下拉显示），**隐藏是可见的**。
- **类型识别**：label `platform.type` 优先 → 镜像名正则 → 容器名正则 → `unknown`（前端显示「未分类」，只读）。未识别出类型的容器**不给**启停按钮。受管类型共 **19 种**，`MANAGED_TYPES` 一张表管全：关系型（postgres/mysql/mariadb/oracle/sqlserver）、缓存与文档图库（redis/memcached/mongodb/cassandra/neo4j）、搜索分析时序（elasticsearch/clickhouse/influxdb）、向量库（milvus/qdrant/weaviate/chroma）、知识库（weknora/cognee）。**加一个类型只需在 `containers.py` 的三张表（别名/镜像名/容器名）各加一行**，前端同步 `container-display.ts` 的 `MANAGED_TYPES`（仅用于渲染筛选下拉）。镜像名匹配刻意**不**把 `-` 当分隔符，否则 `mysql-backup-tool`、`mysql-exporter` 这类工具镜像会被判成数据库；容器名兜底也只收毫无歧义的写法。
- **可见范围**：全部容器只读可见；只有识别出的类型且**非平台自身**的容器才开放生命周期操作。
- **自保护**：命中 `platform.protected=true`，或 `com.docker.compose.project == CONTAINER_PROTECTED_PROJECT`（平台自身 compose 项目，无需人工打标）→ 服务端 **409** 拒绝，且在调用 Docker **之前**就拒绝。代理只能按 API section 放行、**无法按容器名限制**，所以这个应用层检查是唯一的逐容器防线。
- **读写分离**：读接口由 router 级 `require_roles("admin","viewer","database_admin")` 覆盖；三个写接口**逐路由**再加 `require_roles("admin","database_container_admin")`。`database_container_admin` 刻意不复用 `database_admin`——台账编辑权与「重启宿主机数据库容器」的影响面差一个量级。
- **降级**：Docker 不可达时列表类接口仍返回 **200 + `degraded: true`**（前端显示告警条，台账照常可用），日志与写接口返回 **503**。
- **时间是坑**：Docker 的 `Created` 是 epoch UTC、`State.StartedAt` 是 RFC3339 UTC，都必须过 `parse_docker_time()` / `to_naive_local()` 归一，否则违反「全库 naive 北京时」约定。

### 异步调度（[tasks/celery_app.py](backend/app/tasks/celery_app.py) + [tasks/registry.py](backend/app/tasks/registry.py)）

`registry.TASK_MODULES` 集中登记各模块 tasks；beat schedule 含 7 个日志任务 + 3 个新模块周期任务（`check_agent_offline` / `check_model_endpoints` / `check_database_health`，均 60s）。

### 时区处理

`to_naive_local()` / `local_now()`：统一本地时间（北京 +8）；DB 会话 `SET time_zone='+08:00'`。**约定：采集端发送带时区的 ISO 8601 时间；全库时间存 naive 本地时间。**

## 七、请求模型

- [modules/log/schemas.py](backend/app/modules/log/schemas.py)：`LogItemIn`、`LogBatchIn`、`DeviceIn`、`RuleIn`、`RuleUpdate`、`EventPatch`。
- 各新模块 `schemas.py`：`AgentIn/AgentUpdate`、`ProviderIn/ProviderUpdate`、`ModelIn/ModelUpdate`、`UsageIn`、`InstanceIn/InstanceUpdate`、`BackupIn`、`ContainerActionIn`。

## 八、数据库会话（[core/db.py](backend/app/core/db.py)）

- `engine`：`pool_pre_ping=True`、`pool_recycle=1800`；`init_command="SET time_zone='+08:00'"`。
- `SessionLocal`：`sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)`；`get_db()` FastAPI 依赖。

## 九、启动与部署

- **Docker Compose**：`cp .env.example .env` 后 `docker compose up -d`；api 容器启动先 `alembic upgrade head` 再 uvicorn。
- **docker-socket-proxy**：compose 里的 `docker-proxy` 是**唯一**挂载 `docker.sock` 的服务（`api`/`worker`/`scheduler` 都不挂，只经 `backend_net` 访问 `docker-proxy:2375`）。该代理自身**无鉴权**，因此不发布宿主机端口。白名单开 `CONTAINERS` + `POST` + `ALLOW_START/STOP/RESTARTS`，其余 section 保持默认的 0（拒绝）。`docker.sock` 挂成 `:ro` 并不能阻止 API 写操作（socket 是套接字不是普通文件），隔离只来自这份白名单。
- **前端容器配套**：`DatabaseInstances.vue` 每 30s 静默轮询一次（页面可见且无在途请求时才刷，`onUnmounted` 清理定时器）；这也是全站第一处轮询。
- **后端本地**：`cd backend && cp .env.example .env`（改 `CHANGE_ME` 占位后）`&& uvicorn app.main:app --reload --port 7550`。
- **前端本地**：`cd frontend && npm run dev`（Vite 5170，代理到 7550）。
- **迁移**：`cd backend && alembic upgrade head`。
- **异步 Worker / 调度**：`celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo` 与 `... beat --loglevel=info`。
- **手动跑批（临时）**：`python -m app.modules.log.scripts.process_logs --limit 100`、`python -m app.modules.log.scripts.analyze --seed`。

## 十、注意事项 / 已知待办

1. **占位密钥未替换**：`.env.example` 中 `CHANGE_ME` 占位符生产必须替换。
2. **git 已初始化**：已 `git init` 并提交基线；`.gitignore` 已补齐（忽略 `.env`、`node_modules/`、`dist/`、`__pycache__/`、`backend/uploads/`、`*.log`、celerybeat 文件）。
3. **模块边界**：新增功能放对应 `modules/<name>/`；公共能力放 `core/` 或 `platform/`；不要跨业务模块 import（例外见第二节）。
4. **企业微信 / AI 研判**：配置存 `wecom_config` 单行表；AI 客户端在 `core/ai_client.py`，AI 研判业务在 log 模块。
5. **TypeScript 版本**：`frontend/package.json` 固定 `typescript@^5.9.3`。
6. **附件存储目录**：`uploads/` 需挂载卷持久化。
7. **⚠️ 容器管控上线前必须先开 OIDC**：`OIDC_ENABLED=false`（当前默认）时 `core/auth.py` 返回**匿名 admin**，即内网任何能访问 7550 的人都能启停宿主机的数据库容器。引入挂 `docker.sock` 类能力之前务必先接好 OIDC，并在 IdP 侧配置 `database_container_admin` 角色（未配置前实际只有 `admin` 可操作）。
8. **受管容器的识别约定**：给容器打 `platform.type` 标签（取值见 `containers.py` 的 `MANAGED_TYPES`，共 19 种，含 postgres/mysql/mariadb/oracle/sqlserver/redis/mongodb/elasticsearch/clickhouse/milvus/qdrant/weknora/cognee 等），且 label 优先级最高、可覆盖镜像名推断；不打标则回退按镜像名、容器名推断。台账侧可用 `database_instance.attributes.docker_container`（容器名或 ID）显式指定关联的容器，否则按 `instance_code` 与容器名同名匹配。**注意 `platform.protected=true` 只能创建时打，容器标签创建后不可变**，无法事后给已在跑的容器补保护——要收窄范围只能靠开 OIDC 或防火墙。
9. **容器操作审计**：所有启停（含被拒绝的）写 `database_container_audit`，可在前端「数据库实例」页的「操作记录」抽屉里看。容器清单本身**不落库**，始终实时读 Docker。
