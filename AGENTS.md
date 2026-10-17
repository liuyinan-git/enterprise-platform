# AGENTS.md — 项目说明

> 本文档供 AI 编码助手及新成员快速了解本项目。最后更新：2026-10-17。

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
- **AI Agent 统一管理平台**（并入智能体模块）：Docker 容器实况与启停、项目分类规则、AI 服务接口健康监控（OpenClaw/Hermes/Codex/Dify）、LangGraph 接口管理、监控历史、只读系统设置
- 模型管控（供应商/模型台账、端点健康探测、用量统计）
- 数据库管控（实例台账、连接健康探测、备份记录、**容器实况与启停**）
- 管理前端（Vue 3）：按模块分组的侧边栏 + 总览/日志/智能体/模型/数据库/平台管理页面（智能体分组下 8 项）

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
│   │   └── versions/             # 0001..0013 迁移
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
│   │   ├── modules/              # 业务模块（5 个，结构一致）
│   │   │   ├── log/              #   日志管控：models/schemas/api/services/parsers/rules/ai/tasks
│   │   │   ├── agent/            #   智能体管控：models/schemas/api/services/tasks
│   │   │   │                     #     + AI Agent 平台：agent_config/docker_client/containers/
│   │   │   │                     #       probes/container_api/project_api/endpoint_api/overview_api
│   │   │   ├── model/            #   模型管控：models/schemas/api/services/tasks
│   │   │   ├── database/         #   数据库管控：models/schemas/api/services/tasks
│   │   │   │                     #     + 容器实况：docker_client/containers/container_api/container_config
│   │   │   └── gateway/          #   网关管控（Squid/APISIX，后端已有，前端菜单暂注释）：db/models/routers/services
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

通过 `pydantic-settings` 的 `BaseSettings` 读取环境变量或 `.env`。关键字段：

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
| `gateway_auth_enabled` | `False` | 网关统一认证开关（APISIX openid-connect + forward-auth 对接 MaxKey） |
| `gateway_user_id_header` / `gateway_username_header` / `gateway_roles_header` | `x-user-id` / `x-user-num` / `x-user-roles` | APISIX 注入的用户头字段名（ID / 工号 / 角色） |

- `database_url` / `redis_url` 为派生属性；`get_settings()` 用 `@lru_cache` 缓存。
- **例外：容器相关的两份配置都不在这里**——数据库模块的在 [modules/database/container_config.py](backend/app/modules/database/container_config.py)（读 `CONTAINER_*`），AI Agent 平台的在 [modules/agent/agent_config.py](backend/app/modules/agent/agent_config.py)（读 `AGENT_*`，见第六节）。因为本文件的 `Settings` 是 `extra="ignore"`，`.env` 里多出的键不会让它报错，模块自带一份 `BaseSettings` 读同一份 `.env` 即可——**多人协作时新增配置不必改这个共享文件**。
- ⚠️ 别把上面的 `agent_offline_grace_seconds` 与 agent 平台的 `AGENT_*` 搞混：前者是**智能体台账心跳**的宽限期，仍在本文件里、**刻意没有搬动**（搬它要牵动四个文件却没有行为收益）；后者是 AI Agent 平台自己的那套。

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

**注意 `agents` 与 `agent/...` 是两个不同前缀**，分别是「智能体台账」和「AI Agent 平台」（见下）。

#### AI Agent 平台（`/agent/*`，tag=agent-platform，由 4 个子 router include 进 `api.py`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/agent/overview` | 首页统计（项目/容器/接口数）。Docker 不可达返回 200 + `degraded:true` |
| GET | `/agent/containers` | 容器列表，筛选 `project_key`/`status`/`keyword`/`include_stopped`。Docker 不可达 200 + `degraded:true` |
| POST | `/agent/containers/discover` | 重新发现 + 分类，返回 `discovered/classified/unclassified` |
| GET | `/agent/containers/{id}` | 详情（inspect；**不返回 `Config.Env`**） |
| GET | `/agent/containers/{id}/logs` | 日志，`tail`/`since`/`timestamps` |
| GET | `/agent/containers/{id}/exec-command` | 可复制的 exec 命令文本（**不执行**） |
| POST | `/agent/containers/{id}/start`·`/stop`·`/restart` | 容器启停重启（需 `admin` 或 `agent_container_admin`） |
| GET | `/agent/container-audits` | 容器操作审计 |
| GET | `/agent/projects` | 项目分组汇总 + 各项目容器数 |
| GET | `/agent/project-rules` | 分类规则列表（附 `conflicts`） |
| POST/PUT/DELETE | `/agent/project-rules`、`/agent/project-rules/{project_key}` | 规则 CRUD（需 `agent_admin`） |
| PATCH | `/agent/project-rules/{project_key}/enabled` | 启用/停用（需 `agent_admin`） |
| GET | `/agent/endpoints` | 端点台账（AI 服务 + LangGraph 共用），筛选 `service_type`/`group_name`/`health_status`/`keyword` |
| GET | `/agent/endpoints/options` | 端点下拉项（历史页筛选用） |
| POST/PUT/DELETE | `/agent/endpoints`、`/agent/endpoints/{code}` | 端点 CRUD（需 `agent_admin`） |
| POST | `/agent/endpoints/{code}/check` | 单个检查（需 `agent_admin`） |
| POST | `/agent/endpoints/check-batch` | 批量检查，`{codes?: []}` 空=全部启用（需 `agent_admin`） |
| GET | `/agent/health-history` | 监控历史：`endpoint_code`/`status`/`checked_from`/`checked_to` + 分页 |
| GET | `/agent/system-status` | 系统设置只读状态（调度/超时/连接/权限） |

LangGraph **不另开端点**：LangGraph 页直接以 `service_type=langgraph` 调 `/agent/endpoints` 系列，前端用 `:fixed-service-type` 锁死类型，避免在错误的页面建出错误类型的端点。

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
- 管理接口走 `Depends(require_roles(...))`；`GATEWAY_AUTH_ENABLED=false`（当前默认）时降级为**匿名 admin**（内网开放现状）。开启后，登录认证由 **APISIX 网关**完成（`openid-connect` + `forward-auth` 插件对接 MaxKey 统一认证中心），后端 [core/auth.py](backend/app/core/auth.py) 从 APISIX 注入的请求头读取用户与角色：`x-user-id`（用户 ID）、`x-user-num`（工号/用户名）、`x-user-roles`（角色，逗号/空格分隔或 JSON 数组）。**容器启停额外要求 `database_container_admin`（数据库模块）或 `agent_container_admin`（agent 模块）**，`viewer` 只能看。台账写权限（`agent_admin`）与容器启停权限刻意分开。
- 统一响应 `{"code": 0, "message": "...", "data": ...}`（新模块用 `core/response.py` 的 `ok()/created()/paginated()`）。

## 五、数据模型

共 **25 张表**，MySQL InnoDB，主键无符号 BIGINT 自增，时间列 `DATETIME(3)`。ORM 按模块拆分：

| 模块 | 表 | 关键约束 |
| ---- | ---- | ---- |
| log（12 张） | `device_registry` `log_batch` `log_raw` `processing_task` `log_event` `analysis_rule` `security_event` `security_event_log` `alert_record` `rule_suggestion` | 唯一键 + 查询索引，见 [modules/log/models.py](backend/app/modules/log/models.py) |
| platform（2 张） | `wecom_config`（单行 id=1）、`attachment` | — |
| agent（6 张） | `agent_registry`（uk_agent_id）、`agent_audit`、`agent_project_rule`（uk_agent_project_key）、`agent_endpoint`（uk_agent_endpoint_code + 4 索引）、`agent_health_history`（**无 FK**）、`agent_container_audit` | 心跳 + 审计 + 分类规则 + 端点台账 + 监控历史 |
| model（3 张） | `model_provider`（uk_provider_code）、`model_registry`（uk_model_code + FK provider）、`model_usage`（uk model+day） | 供应商/模型/用量 |
| database（4 张） | `database_instance`（uk_instance_code）、`database_health`、`database_backup`、`database_container_audit` | 实例/健康/备份/容器操作审计 |

`agent_endpoint` 的 `group` 字段落库列名是 **`group_name`**（`group` 是 SQL 保留字），API 的 JSON 里仍叫 `group`，由 `endpoint_api._serialize()` 做映射。端点标识统一用业务码 `endpoint_code`，不暴露自增 ID（与 `agent_id`/`instance_code`/`provider_code` 一致）。

`agent_health_history` **刻意不加 FK**，并把 `endpoint_code`/`endpoint_name`/`service_type` 冗余进来：这样**删掉监控配置后历史仍可查**（「这接口上周一直挂」是有价值的信息），历史页也无需 join。对比 `database_health` 带 FK，删实例时会被历史行挡住报 IntegrityError —— 这里不重蹈。三条索引对应三条独立筛选路径：`idx_agent_hist_endpoint_time(endpoint_id, checked_at)`、`idx_agent_hist_status_time(status, checked_at)`、`idx_agent_hist_checked(checked_at)`（供保留期清理）。

**容器清单本身不落库**，始终实时读 Docker —— 新鲜度正是这个页面的意义，而分类是「实时容器 × 落库规则」的纯函数，落库只会引入一类陈旧数据的 bug。**系统设置页也不建表**（决策：只读展示，间隔走 `.env`）。

迁移脚本 `0001..0015`，其中 `0009_agent_module`、`0010_model_module`、`0011_database_module`、`0012_database_container`、`0013_agent_platform`、`0014_model_monitor`、`0015_model_consumer_alert` 为新增模块表。

## 六、核心逻辑

### 日志模块（modules/log/）

- **接入** [services/ingest.py](backend/app/modules/log/services/ingest.py)：上限校验 → 批次幂等 → `LogBatch` + Outbox 落 `ProcessingTask` → 逐条 `INSERT ... IGNORE` 写 `LogRaw` → 计数回写。同时 `_touch_devices()` 心跳联动（未知设备自动登记、刷新 `last_seen_at`）。`ingest_fluentbit()` 兼容 JSON 数组/单对象/NDJSON/msgpack，event_id 取记录内容哈希幂等。
- **标准化** [services/normalize.py](backend/app/modules/log/services/normalize.py) + parsers/：解析器链（JSON/Syslog）→ `classify()` 关键词映射 → 未知兜底；`process_pending_logs()` 批量写 `log_event`。
- **规则分析** [services/analyze.py](backend/app/modules/log/services/analyze.py) + rules/：阈值规则评估 → `sha256(rule_code|group_key)` 指纹聚合事件 → 新建 `AlertRecord` → `_send_alert()`。
- **AI 研判** [services/analyze_ai.py](backend/app/modules/log/services/analyze_ai.py) + ai/：组装输入 → `core/ai_client.chat_completion` → 结构化校验写回 `event.ai_analysis`。由 `run_ai_analysis`（30s）驱动。
- **设备健康** [services/device_health.py](backend/app/modules/log/services/device_health.py)：`detect_offline_devices()` 判定失联 → 生成/关闭 `DEVICE_OFFLINE` 事件与告警。

### 智能体模块（modules/agent/）

`agent_status()` 按 `last_seen_at` + `agent_offline_grace_seconds` 判定在线/离线；`check_agent_offline` 周期任务（60s）统计离线数。心跳由 `POST /agents/{id}/heartbeat` 上报。操作经 `record_audit()` 落 `agent_audit`。

### AI Agent 平台（modules/agent/，与智能体台账同模块同页组）

管理宿主机 Docker 容器、AI 服务 HTTP 接口（OpenClaw / Hermes / Codex / Dify）与 LangGraph 接口。**与台账共用 `modules/agent/` 是因为同属「智能体管控」这一件事**，相似功能一律在既有文件里扩展（`models.py` / `schemas.py` / `services.py` / `api.py` / `tasks.py`），新增能力拆到独立文件。

- **配置各自独立**：[agent_config.py](backend/app/modules/agent/agent_config.py) 是一份模块私有 `BaseSettings`，读 `AGENT_*`（照 `database/container_config.py` 的写法）。因为 `core/config.py` 是 `extra="ignore"`，`.env` 里多出的键不会让它报错，**多人协作时新增配置不必改共享文件**。注意既有的 `AGENT_OFFLINE_GRACE_SECONDS` 仍在 `core/config.py`，**没有搬动**（搬它要牵动四个文件却没有行为收益）。刻意**不设** `AGENT_CHECK_INTERVAL_SECONDS`——间隔的唯一真相是 `celery_app.py` 的 `beat_schedule`，系统设置页直读它，再设一个配置项只会让两者脱节。
- **读内核**：[docker_client.py](backend/app/modules/agent/docker_client.py)（urllib 打代理 + 解帧，**从 database 版复制而非 import**，这份重复是模块边界约定的必然代价）、[containers.py](backend/app/modules/agent/containers.py)（分类/自保护/序列化）、[probes.py](backend/app/modules/agent/probes.py)（HTTP 探测，纯函数不碰 ORM，可单测）。
- **容器自动分类**（[containers.py](backend/app/modules/agent/containers.py) `classify_container`）：只取启用规则 → **一级 compose**：label `com.docker.compose.project` 精确命中 `compose_project_names` → **二级容器名**：仅当一级为空时用 `re.search(pattern, name, re.I)` 匹配 `container_name_patterns` → 命中 0 条为 `none`（未分类）、1 条采用、**≥2 条为 `conflict` 且不指派**。冲突时**不按 `priority` 自动挑一条**：文档要求「规则冲突时应标记为待处理，避免错误归类」，自动指派会把配置错误藏起来；`priority` 只在 UI 上作为解决建议展示。正则之间的重叠检测在通用意义上是不可判定的，**明确不做**（`detect_rule_conflicts` 只查同一 compose 项目名被 ≥2 条启用规则声明、或正则列表里有重复字面量）。
- **HTTP 健康探测**（[probes.py](backend/app/modules/agent/probes.py)，四态）：`HTTPError` **必须先于 `URLError` 捕获**——它是 `URLError` 的子类且带 `.code`；[model/services.py](backend/app/modules/model/services.py) 的 `probe_provider` 正是先捕 `URLError`，把 404 报成了 `str(exc.reason)` 并丢掉状态码，这里不重蹈。状态码策略：`expected_status` 有值 → 健康当且仅当 `http_status in expected_status`；无值 → **2xx 为健康**。**响应收到了但不符合预期算 `unhealthy`，绝不归为 `error`**（401/403 可逐端点声明为可达）。`verify_tls=False` 只把 `context=ssl._create_unverified_context()` 传给该次 `urlopen`，**绝不改全局默认**。响应体只在**非 healthy 时**存前 `AGENT_PROBE_MAX_EXCERPT_CHARS` 字符（成功的历史行保持干净）。
- **容器操作的角色与守卫**：读接口由父 router 级 `require_roles("admin","viewer","agent_admin")` 覆盖；**三个写接口逐路由**再加 `require_roles("admin","agent_container_admin")`。`agent_container_admin` **刻意不复用 `agent_admin`**：台账编辑是可逆的库内操作，容器启停会真的中断在跑的服务，影响面差一个量级（沿用 `database_container_admin` 的既有立场）。
- **启停范围比数据库模块更窄**：仅**已分类到唯一项目**的容器可操作。`unclassified` **与 `conflict` 一律只读**——归属不明的容器不该拿到重启权。`refusal_reason()` 因此比 database 版更严（多了 conflict 与未分类两条）。
- **自保护**：命中 `platform.protected=true` 或 `com.docker.compose.project == AGENT_PROTECTED_PROJECT` → **409**，且在调用 Docker **之前**就拒绝。Docker 代理只能按 API section 放行、**无法按容器名限制**，所以自保护 + 分类收窄是仅有的两道逐容器防线，务必落实。aiagent 的启停面**远宽于** database 模块（那边只放行 19 类受管类型，这里是「属于某项目的容器」都能启停），这也是默认值更保守的原因。
- **审计**：启停（含被拒绝的）写 `agent_container_audit`，`result` 取 `success/failed/refused`。审计写失败**不能**把成功的操作变成 500——照 database 版 `_record` 单独兜住 SQLAlchemy 异常。
- **降级**：Docker 不可达时列表类接口仍返回 **200 + `degraded: true`**（前端显示告警条，台账照常可用），日志与写接口返回 **503**。`/agent/system-status` 对 Docker / MySQL / Redis **逐项**降级为 `{ok:false, error}`，**任何一项探测失败都不能让整个接口 500**。
- **不提供 exec / Web 终端**：只有 `GET /agent/containers/{id}/exec-command` 返回一段**可复制的命令文本**，服务端不执行——与接口文档「不允许前端直接执行 Shell 命令」及 database 模块的既有做法一致。
- **日志时间戳的矛盾**：文档要求 `timestamps` 默认 `true`，而 Docker 给的是 RFC3339 **UTC**，与「全库 naive 北京时」冲突。处理：请求 `timestamps=1` 拿到后**逐行把行首时间戳本地化**（`localize_log_timestamps()`：正则摘出 `ts` + `to_naive_local()` + 小数位截到 6 位 + 拼回原 `rest`；不匹配的行原样放行），这样输出**仍完全落在约定内**又不违反文档。逐行转换受 `AGENT_LOG_TAIL_MAX` 与字符上限约束，开销可忽略。
- **容器详情不返回 `Config.Env`**（可能含数据库密码 / API Key）。

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
- **类型识别**：label `platform.type` 优先 → 镜像名正则 → 容器名正则 → **应用层判据** → `unknown`（前端显示「未分类」，只读）。未识别出类型的容器**不给**启停按钮。受管类型共 **19 种**，`MANAGED_TYPES` 一张表管全：关系型（postgres/mysql/mariadb/oracle/sqlserver）、缓存与文档图库（redis/memcached/mongodb/cassandra/neo4j）、搜索分析时序（elasticsearch/clickhouse/influxdb）、向量库（milvus/qdrant/weaviate/chroma）、知识库（weknora/cognee）。**加一个类型只需在 `containers.py` 的三张表（别名/镜像名/容器名）各加一行**，前端同步 `container-display.ts` 的 `MANAGED_TYPES`（仅用于渲染筛选下拉）。镜像名匹配刻意**不**把 `-` 当分隔符，否则 `mysql-backup-tool`、`mysql-exporter` 这类工具镜像会被判成数据库；容器名兜底也只收毫无歧义的写法。
- **应用层判据（`_is_app_tier`）**：镜像名 + 容器名切词后命中 `_APP_TIER_TOKENS`（app / backend / frontend / ui / web / api / mcp / worker / proxy / nginx / exporter / dashboard / admin …）就认定是应用层，**降级为 `unknown` 并把 `managed_type_source` 置成 `app`**（前端 tooltip 借此说明原因，而不是笼统说「未分类」）。加这一层的起因：`weknora` / `cognee` 是**品牌名**只能子串匹配，同一个品牌下既有知识库本体、也有业务方自己起的应用容器，光看品牌名分不开——本机实测这两个类型的 11 个命中**全部**是 `-backend` / `-frontend` / `-mcp` / `rerank` 这类应用层，而它们对应的真数据存储（paradedb / pgvector / redis）早就按镜像名正确识别了；用判据替换品牌名匹配后，受管类型的识别结果**一个没少**。`_APP_TIER_TOKENS` 刻意**不收** `server`（`mcr.microsoft.com/mssql/server` 的末段就是 server，收了会误伤 SQL Server），也不收 `registry` / `database`（oracle 官方镜像路径里就有）。**label 不受这道判据约束**——想强行纳管某个应用容器（例如就要管 WeKnora 本体），给它打 `platform.type` 标签即可。
- **可见范围**：全部容器只读可见；只有识别出的类型且**非平台自身**的容器才开放生命周期操作。
- **自保护**：命中 `platform.protected=true`，或 `com.docker.compose.project == CONTAINER_PROTECTED_PROJECT`（平台自身 compose 项目，无需人工打标）→ 服务端 **409** 拒绝，且在调用 Docker **之前**就拒绝。代理只能按 API section 放行、**无法按容器名限制**，所以这个应用层检查是唯一的逐容器防线。
- **读写分离**：读接口由 router 级 `require_roles("admin","viewer","database_admin")` 覆盖；三个写接口**逐路由**再加 `require_roles("admin","database_container_admin")`。`database_container_admin` 刻意不复用 `database_admin`——台账编辑权与「重启宿主机数据库容器」的影响面差一个量级。
- **降级**：Docker 不可达时列表类接口仍返回 **200 + `degraded: true`**（前端显示告警条，台账照常可用），日志与写接口返回 **503**。
- **时间是坑**：Docker 的 `Created` 是 epoch UTC、`State.StartedAt` 是 RFC3339 UTC，都必须过 `parse_docker_time()` / `to_naive_local()` 归一，否则违反「全库 naive 北京时」约定。

### 异步调度（[tasks/celery_app.py](backend/app/tasks/celery_app.py) + [tasks/registry.py](backend/app/tasks/registry.py)）

`registry.TASK_MODULES` 集中登记各模块 tasks；beat schedule 含 7 个日志任务 + 5 个新模块周期任务：`check_agent_offline`（60s）、`check_agent_endpoints`（60s）、`check_model_endpoints`（60s）、`check_database_health`（60s）、`cleanup_agent_history`（3600s）。**配了 `AGENT_HISTORY_RETENTION_DAYS` 就必须有清理任务**，否则这个配置项是在撒谎（与 log 模块的 `cleanup_retention` 同构）。系统设置页的「调度配置」**直读 `celery_app.conf.beat_schedule` 的实时值**，不是另抄一份，所以改间隔只改 `celery_app.py` 并重启 scheduler 即可，页面自动跟上。

### 时区处理

`to_naive_local()` / `local_now()`：统一本地时间（北京 +8）；DB 会话 `SET time_zone='+08:00'`。**约定：采集端发送带时区的 ISO 8601 时间；全库时间存 naive 本地时间。**

## 七、请求模型

- [modules/log/schemas.py](backend/app/modules/log/schemas.py)：`LogItemIn`、`LogBatchIn`、`DeviceIn`、`RuleIn`、`RuleUpdate`、`EventPatch`。
- 各新模块 `schemas.py`：`AgentIn/AgentUpdate`、`ProviderIn/ProviderUpdate`、`ModelIn/ModelUpdate`、`UsageIn`、`InstanceIn/InstanceUpdate`、`BackupIn`、`ContainerActionIn`。
- [modules/agent/schemas.py](backend/app/modules/agent/schemas.py) 的 AI Agent 平台部分：`ProjectRuleIn/ProjectRuleUpdate/RuleEnabledIn`（`_validate_patterns()` 在入口处逐条 `re.compile` 正则，坏正则当场 422，不留到分类时才炸）、`EndpointIn/EndpointUpdate`（method 校验对照 `ALLOWED_METHODS`、`expected_status` 校验 100–599 并去重排序）、`CheckBatchIn`。`SERVICE_TYPES` 是 `openclaw/hermes/codex/dify/langgraph/custom`。

## 八、数据库会话（[core/db.py](backend/app/core/db.py)）

- `engine`：`pool_pre_ping=True`、`pool_recycle=1800`；`init_command="SET time_zone='+08:00'"`。
- `SessionLocal`：`sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)`；`get_db()` FastAPI 依赖。

## 九、启动与部署

- **Docker Compose**：`cp .env.example .env` 后 `docker compose up -d`；api 容器启动先 `alembic upgrade head` 再 uvicorn。服务共 6 个：`mysql` / `redis` / `api` / `worker` / `scheduler` / `docker-proxy`。
- **⚠️ 改了后端代码后必须 `--build`，`restart` 没用**：api 服务**没有 volumes 挂载**，代码是 `COPY` 进镜像的，所以 `docker compose restart api` 仍跑旧代码（症状是新增的接口全部 404，而老接口正常）。正确做法是
  `docker compose up -d --build api`。排查时可用 `docker exec $(docker compose ps -q api) ls app/modules/<模块>/` 直接看容器内有没有新文件——比看接口返回快。
- **`worker` 与 `scheduler` 不会自动起全**：它们定义了但常被漏掉。只 `docker compose up -d api` 的话，所有周期任务（含 `check_agent_endpoints` 的 60s 探测、`cleanup_agent_history` 的保留期清理）都是**静默不生效**的——页面照常能看，但数据不会自动更新、`AGENT_HISTORY_RETENTION_DAYS` 形同虚设。要自动监控就一并起：`docker compose up -d worker scheduler`。
- **docker-socket-proxy**：compose 里的 `docker-proxy` 是**唯一**挂载 `docker.sock` 的服务（`api`/`worker`/`scheduler` 都不挂，只经 `backend_net` 访问 `docker-proxy:2375`）。该代理自身**无鉴权**，因此不发布宿主机端口。白名单开 `CONTAINERS` + `POST` + `ALLOW_START/STOP/RESTARTS`，其余 section 保持默认的 0（拒绝）。`docker.sock` 挂成 `:ro` 并不能阻止 API 写操作（socket 是套接字不是普通文件），隔离只来自这份白名单。**数据库模块的 `CONTAINER_*` 与 agent 平台的 `AGENT_*` 是两套独立配置**（白名单同一份，语义不同：那边按受管类型放行，这边按项目归属放行）。本地开发在宿主机直接跑后端时，`backend/.env.example` 里附了把代理端口**绑回环**（`-p 127.0.0.1:2375:2375`，**切勿绑 0.0.0.0**）的 `docker run`，两个模块指向同一个代理即可，无需起两个。
- **前端容器配套**：`DatabaseInstances.vue` 每 30s 静默轮询一次（页面可见且无在途请求时才刷，`onUnmounted` 清理定时器）；agent 平台的 `Overview.vue` 用同样的写法（全站仅这两处轮询，且都受 `visibilityState==='visible'` 与在途请求双重门控）。
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
7. **⚠️ 容器管控上线前必须先开网关认证**：`GATEWAY_AUTH_ENABLED=false`（当前默认）时 `core/auth.py` 返回**匿名 admin**，即内网任何能访问 7550 的人都能启停宿主机的数据库容器。引入挂 `docker.sock` 类能力之前务必先接好网关认证，并在 MaxKey/IdP 侧配置 `database_container_admin` 角色（未配置前实际只有 `admin` 可操作）。
8. **受管容器的识别约定**：给容器打 `platform.type` 标签（取值见 `containers.py` 的 `MANAGED_TYPES`，共 19 种，含 postgres/mysql/mariadb/oracle/sqlserver/redis/mongodb/elasticsearch/clickhouse/milvus/qdrant/weknora/cognee 等），且 label 优先级最高、可覆盖镜像名推断；不打标则回退按镜像名、容器名推断。台账侧可用 `database_instance.attributes.docker_container`（容器名或 ID）显式指定关联的容器，否则按 `instance_code` 与容器名同名匹配。**注意 `platform.protected=true` 只能创建时打，容器标签创建后不可变**，无法事后给已在跑的容器补保护——要收窄范围只能靠开网关认证或防火墙。
9. **容器操作审计**：所有启停（含被拒绝的）写 `database_container_audit`，可在前端「数据库实例」页的「操作记录」抽屉里看。容器清单本身**不落库**，始终实时读 Docker。
10. **⚠️ AI Agent 平台的启停面更宽，网关认证更必须先开**：数据库模块只放行 19 类**受管类型**，而 agent 平台放行「**属于某个已分类项目**」的容器——很多。`GATEWAY_AUTH_ENABLED=false`（当前默认）时，内网任何能访问 7550 的人都能启停这些容器。上线前务必先接好网关认证，并在 MaxKey/IdP 侧配置 `agent_container_admin` 与 `agent_admin` 角色（**两个角色刻意分开**：前者能重启服务，后者只能改台账）。未配置该角色前实际只有 `admin` 可操作。
11. **AI Agent 平台的项目分类约定**：分类靠 `agent_project_rule` 两张列表——compose 项目名（一级，精确）与容器名正则（二级，仅一级空时才用），命中 ≥2 条即判 `conflict` **且不指派**（归属不明的容器拿不到启停权）。给容器打 `com.docker.compose.project` 标签或用规范化的容器名是最省事的接入方式。规则只此一处（[containers.py](backend/app/modules/agent/containers.py)），**加规则是运营动作不是发版动作**——在前端「项目与分类规则」页加即可，无需改代码。
12. **监控历史不随配置删除而删除**：`agent_health_history` 刻意无 FK 且冗余了端点名/类型。保留期由 `AGENT_HISTORY_RETENTION_DAYS` 决定，由 `cleanup_agent_history`（3600s）执行；**这个配置项与那个任务是配对的，去掉任务就等于让配置项失效**。
13. **agent 平台与既有智能体台账同模块不同前缀**：台账是 `/api/v1/agents`（前端 `/agents`），平台是 `/api/v1/agent/*`（前端 `/agent/*`）。前端侧边栏两者同在「智能体管控」分组下（8 项）。新增平台接口时记得：`main.py` / `modules/__init__.py` / `tasks/registry.py` / 前端 `router/index.ts` **都不需要改**——子 router 由 `modules/agent/api.py` include，新页面由 `modules/agent/routes.ts` 声明。
