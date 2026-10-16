# AGENTS.md — 项目说明

> 本文档供 AI 编码助手及新成员快速了解本项目。最后更新：2026-10-13。

## 一、项目概况

**企业全域日志管控与智能告警平台（Enterprise Log Platform）** 的后端 + 前端，已推进至 **阶段 05（AI 研判，DeepSeek 大模型辅助分析）**。

已完成的能力：

- 健康检查（存活 / 就绪）
- 批量日志接收（采集端上报原始日志，幂等 + Outbox 落任务；兼容 Fluent Bit HTTP output）
- 批次查询
- 日志标准化（`log_raw → log_event`，JSON/Syslog 解析 + 关键词规则映射）
- 规则引擎（阈值规则）+ 事件聚合（SHA256 指纹）+ 企业微信告警
- 异步调度（Celery + Redis）：Outbox 调度、批次标准化、规则分析、告警重试（beat + worker）
- AI 研判（DeepSeek 大模型辅助分析，结构化输出：摘要/风险/置信度/证据/局限/建议）
- 管理前端（Vue 3）：态势总览、日志检索、安全事件、告警、规则、设备、采集端、消息发送管理、附件管理、系统监控

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

## 二、目录结构

```
enterprise-log-platform-v1/
├── docker-compose.yml            # 容器编排（mysql/redis/api/worker/scheduler）
├── .env.example                  # 环境变量示例（复制为 .env 使用）
├── README.md
├── nginx/
│   ├── nginx.conf                # 反向代理（HTTPS 后续接入）
│   └── certs/                    # TLS 证书目录
├── backend/
│   ├── Dockerfile                # 容器构建，启动时先迁移后运行 uvicorn
│   ├── requirements.txt          # Python 依赖
│   ├── alembic.ini               # Alembic 配置（URL 占位，运行时被 settings 覆盖）
│   ├── alembic/
│   │   ├── env.py                # 迁移入口，读 settings.database_url 与 Base.metadata
│   │   └── versions/
│   │       ├── 0001_initial_schema.py   # 4 张接入表
│   │       ├── 0002_analysis_tables.py  # 5 张分析/告警表
│   │       ├── 0003_wecom_config.py     # 企业微信配置表
│   │       ├── 0004_attachment.py       # 附件表
│   │       ├── 0005_wecom_notify_severity.py  # 通知级别字段
│   │       ├── 0006_rule_device_touser.py  # 规则/设备接收人字段
│   │       └── 0007_attachment_uploader.py  # 附件上传人字段
│   ├── app/
│   │   ├── main.py               # FastAPI 应用入口（health/root 端点）
│   │   ├── api/v1/routes.py      # 全部业务/管理路由
│   │   ├── core/config.py        # 配置（Settings，读 .env）
│   │   ├── db/{base.py, session.py}
│   │   ├── models/log_models.py  # 11 张表 ORM 模型
│   │   ├── schemas/{logs.py, management.py}  # Pydantic 请求模型
│   │   ├── services/
│   │   │   ├── ingest.py         # 日志接入（去重、Outbox 落任务）
│   │   │   ├── normalize.py      # 标准化：log_raw → log_event
│   │   │   ├── analyze.py        # 规则评估 → 事件聚合 → 告警
│   │   │   ├── analyze_ai.py     # AI 研判（候选事件 → 大模型 → 结构化写回）
│   │   │   ├── device_health.py  # 设备失联检测（事件+告警+自动恢复）
│   │   │   └── wecom_config.py   # 企业微信配置读写（单行 id=1）
│   │   ├── parsers/              # 解析器：base / json / syslog
│   │   ├── rules/{engine.py, builtins.py}   # 阈值规则引擎 + 内置规则
│   │   ├── ai/{client.py, prompts.py, schemas.py}  # AI 客户端/提示词/输出校验（OpenAI 兼容）
│   │   ├── notifications/wecom.py           # 企业微信自建应用发送（gettoken + message/send）
│   │   ├── tasks/                # celery_app/celery_tasks（自动化）+ process_logs/analyze（手动入口）
│   │   └── repositories/         # 占位，后续阶段实现
│   └── tests/                    # 测试（占位）
├── frontend/                     # Vue 3 前端（10 个页面全部实现）
│   └── src/{api,layouts,router,views}/
├── collector/                    # 采集端样例程序 + fluent-bit.conf 配置样例
├── database/{init,seeds}/        # 数据库初始化/种子（预留）
├── deploy/                       # 部署脚本（预留）
└── docs/                         # 文档（预留）
```

## 三、配置（backend/app/core/config.py）

通过 `pydantic-settings` 的 `BaseSettings` 读取环境变量或 `.env`（`case_sensitive=False`，`extra="ignore"`）。关键字段：

| 配置项 | 默认值 | 说明 |
| ------ | ------ | ---- |
| `app_env` | `development` | 运行环境 |
| `app_port` | `7552` | 服务端口 |
| `log_level` | `INFO` | 日志级别 |
| `mysql_database` / `mysql_user` | `enterprise_log` / `log_app` | 数据库名/用户 |
| `mysql_password` | `CHANGE_ME_app_password` | ⚠️ 占位符，需替换 |
| `mysql_host` / `mysql_port` | `mysql` / `3306` | 数据库主机/端口 |
| `mysql_pool_size` / `mysql_max_overflow` | `5` / `10` | 连接池参数 |
| `collector_api_key` | `CHANGE_ME_use_a_long_random_secret` | ⚠️ 采集端认证密钥，需替换 |
| `max_logs_per_batch` | `1000` | 单批次最大日志条数 |
| `max_raw_message_chars` | `20000` | 单条 `raw_message` 最大字符数 |
| `wecom_enabled` | `False` | 企业微信告警开关 |
| `wecom_corpid` / `wecom_corpsecret` | `""` | 企业微信自建应用 corpId / 应用密钥 |
| `wecom_agentid` | `0` | 自建应用 AgentId |
| `wecom_touser` | `""` | 默认接收成员 UserID（`|` 分隔多人） |
| `wecom_notify_min_severity` | `medium` | 通知最低级别（low/medium/high/critical） |
| `wecom_timeout_seconds` | `5` | 取 token / 推送超时 |
| `redis_host` / `redis_port` | `localhost` / `6379` | Redis 地址（Celery broker/backend） |
| `redis_password` / `redis_db` | `""` / `0` | Redis 密码 / 库 |
| `ai_enabled` | `False` | AI 研判开关 |
| `ai_provider` / `ai_model` | `ollama` / `""` | 模型服务与模型名（deepseek / ollama） |
| `ai_base_url` / `ai_api_key` | `http://ollama:11434/v1` / `""` | OpenAI 兼容接口地址与密钥 |
| `ai_timeout_seconds` / `ai_max_retries` | `60` / `2` | 调用超时 / 重试次数 |
| `ai_wecom_min_risk` | `suspicious` | AI 研判微信补发的最低风险等级（normal/suspicious/malicious，留空关闭） |
| `upload_dir` | `uploads` | 附件存储目录（相对后端运行目录） |
| `max_upload_size_mb` | `200` | 单文件上传大小上限（MB） |

- `database_url` 为派生属性，拼装为 `mysql+pymysql://...?...&charset=utf8mb4`，用户名/密码经 `quote_plus` 转义。
- `redis_url` 为派生属性，拼装为 `redis://[:password@]host:port/db`，作为 Celery 的 broker/backend。
- `get_settings()` 使用 `@lru_cache` 缓存，模块级 `settings = get_settings()` 单例。

## 四、HTTP 端点

### 健康检查（无鉴权，[backend/app/main.py](backend/app/main.py)）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/health/live` | 存活检查，恒返回 `{"status":"alive"}` |
| GET | `/health/ready` | 就绪检查，执行 `SELECT 1`，失败返回 503 |
| GET | `/` | 服务信息（name/version/docs/health） |

### 采集接口（[backend/app/api/v1/routes.py](backend/app/api/v1/routes.py)，前缀 `/api/v1`，需 `X-API-Key` 鉴权）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/logs/batch` | 批量日志接收，成功返回 **202 Accepted** |
| POST | `/ingest/fluentbit` | Fluent Bit HTTP output 接收（JSON 数组 / 单对象 / NDJSON / msgpack，`X-Source-Id` 标识来源） |
| GET | `/batches/{batch_id}` | 按 `batch_id` + `source_id` 查询批次状态 |

### 管理接口（前缀 `/api/v1`，当前内网开放、无鉴权）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/batches` | 批次列表（分页） |
| GET | `/logs` | 标准化日志列表（分页 + 筛选） |
| GET | `/logs/{log_id}` | 日志详情（含关联原始报文） |
| GET | `/raw-logs` | 原始日志列表（分页 + 筛选） |
| GET | `/collectors` | 采集端列表（按 source_id 聚合统计） |
| GET | `/events` | 安全事件列表（分页 + 筛选） |
| GET | `/events/{event_no}` | 事件详情（含证据日志 + 告警记录） |
| PATCH | `/events/{event_no}` | 确认 / 分派 / 关闭事件 |
| POST | `/events/{event_no}/ai-analyze` | 手动触发安全事件 AI 研判 |
| GET | `/alerts` | 告警记录列表（分页 + 筛选） |
| POST | `/alerts/{alert_no}/retry` | 手动重试告警 |
| GET | `/rules` | 规则列表 |
| POST | `/rules` | 新增规则 |
| PUT | `/rules/{rule_code}` | 修改规则（启停/阈值/级别等） |
| GET | `/devices` | 设备列表（分页 + 筛选） |
| POST | `/devices` | 登记设备（按 device_id 幂等 upsert） |
| GET | `/dashboard/overview` | 首页态势统计 + 近 7 日日志趋势 |
| GET | `/system/overview` | 系统运行监控统计 |
| GET/PUT | `/wecom/config` | 企业微信配置读取 / 保存（密钥脱敏，单行 id=1） |
| POST | `/wecom/test` | 企业微信测试消息发送 |
| GET | `/files` | 附件目录列表（分页 + 按类别筛选） |
| POST | `/files` | 上传附件（multipart：file + 可选 uploader，文档/表格/图片/视频） |
| GET | `/files/{file_id}/download` | 下载附件 |
| GET | `/files/{file_id}/preview` | 预览附件（inline，图片/PDF） |
| DELETE | `/files/{file_id}` | 删除附件（磁盘文件 + 库记录） |

### 鉴权方式

采集接口通过请求头 **`X-API-Key`** 鉴权（依赖 `require_collector_key`）：

- 未配置密钥或仍是 `CHANGE_ME` 占位符 → 返回 **503**（提示未配置）。
- 缺失或不匹配 → 返回 **401**。比较使用 `secrets.compare_digest` 防止时序攻击。

> 管理接口第一版不做登录，仅限内网/受控网络访问；生产需用反向代理 + 网段控制收紧。

### 响应格式

统一包裹为 `{"code": 0, "message": "...", "data": ...}`；错误时 `code != 0` 或直接抛 `HTTPException`。

## 五、数据模型（backend/app/models/log_models.py）

共 11 张表，均使用 MySQL InnoDB，主键为无符号 BIGINT 自增。ORM 模型与迁移脚本 [0001_initial_schema.py](backend/alembic/versions/0001_initial_schema.py) / [0002_analysis_tables.py](backend/alembic/versions/0002_analysis_tables.py) / [0003_wecom_config.py](backend/alembic/versions/0003_wecom_config.py) / [0004_attachment.py](backend/alembic/versions/0004_attachment.py) / [0005_wecom_notify_severity.py](backend/alembic/versions/0005_wecom_notify_severity.py) / [0006_rule_device_touser.py](backend/alembic/versions/0006_rule_device_touser.py) / [0007_attachment_uploader.py](backend/alembic/versions/0007_attachment_uploader.py) 一一对应。时间列均为 `DATETIME(3)`。

| 表名 | 用途 | 关键约束/索引 |
| ---- | ---- | ---- |
| `device_registry` | 设备注册表（元数据、环境、等级、心跳间隔、接收人） | 唯一 `uk_device_id(device_id)` |
| `log_batch` | 日志批次（收/接/拒计数、状态） | 唯一 `uk_batch_source(source_id, batch_id)` |
| `log_raw` | 原始日志（设备、原始报文、处理状态/重试） | 唯一 `uk_source_event(source_id, event_id)` |
| `processing_task` | 处理任务（Outbox，类型、业务键、状态） | 唯一 `uk_task_business(task_type, business_key)` |
| `log_event` | 标准化日志（类别/类型/级别/IP/用户等） | 唯一 `uk_event_raw(raw_log_id)`；多个查询索引 |
| `analysis_rule` | 分析规则（阈值/级别/冷却/接收人/配置） | 唯一 `uk_rule_code(rule_code)` |
| `security_event` | 安全事件（指纹聚合、状态、分派、次数） | 唯一 `uk_event_no`、`uk_event_fingerprint` |
| `security_event_log` | 事件-证据日志关联 | 复合主键 `(security_event_id, log_event_id)` |
| `alert_record` | 告警记录（渠道、状态、重试、错误） | 唯一 `uk_alert_no(alert_no)` |
| `wecom_config` | 企业微信自建应用配置（单行 id=1，corpid/secret/agentid/touser） | 主键即 id=1 约定 |
| `attachment` | 附件（原始文件名、存储名、上传人、类别、大小、上传时间） | 索引 `idx_attachment_category`、`idx_attachment_created` |

## 六、核心逻辑

### 接入（services/ingest.py）

`ingest_batch(db, payload)` 完成批量日志接入：上限校验 → 批次幂等（`(source_id, batch_id)`）→ 写 `LogBatch` → 同一事务 Outbox 落 `ProcessingTask`（`task_type="process_batch"`）→ 逐条 `INSERT ... IGNORE` 写 `LogRaw`（事件级去重）→ 计数回写 → commit。异常 rollback 后重抛。

接入同时执行 `_touch_devices()` 心跳联动：对批次中出现的 `device_id` 做 upsert——未知设备自动登记（`device_name` 取 device_id、`device_type`/`hostname` 取自日志），已知设备刷新 `last_seen_at`（不覆盖已手动配置的字段）。

`ingest_fluentbit(db, records, source_id)`：接收 Fluent Bit HTTP output 的日志（JSON 数组 / 单对象 / NDJSON / msgpack），映射字段（`log`→raw_message、`@timestamp`/`timestamp`→event_time、`hostname`/`host`→device_id）后复用同一落库/标准化流水线；event_id 取整条记录内容哈希做幂等去重（Fluent Bit 无事件 ID，重试不重复入库）。msgpack 的 Fluent Bit 事件时间（ExtType code=0，8 字节 sec+nsec）解码为 naive UTC。

### 标准化（services/normalize.py + parsers/）

`normalize_raw()`：解析器链（JSON/Syslog）→ `classify()` 关键词规则映射（login_failure、traffic_block 等）→ 未知兜底。`process_pending_logs()`：批量取 `process_status=pending` 的 `log_raw`，标准化写入 `log_event`（幂等跳过已处理）。

### 规则分析（services/analyze.py + rules/）

`evaluate_threshold_rule()`：按 `event_type` 取时间窗口内日志，按 `group_by` 分组，超 `threshold` 产出发现。`analyze()`：评估启用规则 → `aggregate_finding()` 用 `sha256(rule_code|group_key)` 指纹匹配未关闭事件（命中累加，否则新建）→ 新建 `AlertRecord` → `_send_alert()`（`wecom_enabled` 时推企业微信，否则保持 pending）。

### AI 研判（services/analyze_ai.py + ai/）

`analyze_event_ai()`：对候选事件（未关闭的高/中危、未研判过）组装「规则发现 + 资产信息 + 证据日志」输入，调用 OpenAI 兼容大模型（DeepSeek / 本地 Ollama），结构化校验（`summary`/`risk_assessment`/`confidence`/`evidence`/`limitations`/`recommendations`/`needs_human_review`）后写回 `event.ai_analysis` 与 `event.summary`；失败有限次重试后记为 failed。由 `run_ai_analysis` 周期任务（30s）驱动，也可用 `POST /events/{event_no}/ai-analyze` 手动触发。

### 异步调度（tasks/celery_app.py + celery_tasks.py）

Celery + Redis 自动化：`beat` 每 5s 跑 `dispatch_outbox`（投递到期 `processing_task`）、每 30s 跑 `run_analysis`（规则分析+聚合+告警）、`retry_alerts`（重试失败告警）与 `run_ai_analysis`（AI 研判）、每 60s 跑 `check_device_offline`（设备失联检测）；`worker` 消费 `process_batch`（按批次标准化）等任务。任务失败按 `attempt_count` 指数退避，超 `MAX_BATCH_ATTEMPTS` 进入 `failed`（死信）。

### 设备健康（services/device_health.py）

`detect_offline_devices()`：扫描启用设备，`last_seen_at` 超过 `grace_seconds`（预期周期 2 倍，至少 60s）判定失联。失联且无未关闭的 `DEVICE_OFFLINE` 事件时新建 `security_event` + `alert_record`（指纹 `sha256(DEVICE_OFFLINE|device_id)` 去重）；设备恢复上报后自动关闭该事件。由 `check_device_offline` 周期任务（60s）驱动。

### 时区处理

`to_naive_utc()`：带时区时间转 UTC 后去 tzinfo；无时区按 UTC 解释。**约定：采集端应发送带时区的 ISO 8601 时间。** 全库时间存 naive UTC。

## 七、请求模型

- [schemas/logs.py](backend/app/schemas/logs.py)：`LogItemIn`（`extra="forbid"`，含 `format`→`format_type` 别名、必填非空 `raw_message`）、`LogBatchIn`。
- [schemas/management.py](backend/app/schemas/management.py)：`DeviceIn`、`RuleIn`、`RuleUpdate`、`EventPatch`（至少一个字段，`status` 限 `open|confirmed|closed`）。

## 八、数据库会话（backend/app/db/session.py）

- `engine`：`create_engine`，启用 `pool_pre_ping=True`、`pool_recycle=1800`；`connect_args` 设 `init_command="SET time_zone='+00:00'"`，强制 MySQL 会话 UTC，保证 `CURRENT_TIMESTAMP` 默认值与 naive-UTC 约定一致。
- `SessionLocal`：`sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)`。
- `get_db()`：FastAPI 依赖，`yield` 会话并在 `finally` 中关闭。

## 九、启动与部署

- **Docker Compose**：根目录 `cp .env.example .env` 后 `docker compose up -d`。`api` 容器启动时先执行 `alembic upgrade head` 再运行 uvicorn（见 [backend/Dockerfile](backend/Dockerfile)）。
- **后端本地启动**：`cd backend && uvicorn app.main:app --reload --port 7553`（本地开发约定用 7553；Docker 内用 7552）。
- **前端本地启动**：`cd frontend && npm run dev`（Vite 5173，代理 `/api`、`/health` 到 7553）。
- **数据库迁移**：`cd backend && alembic upgrade head`。`alembic.ini` 的 `sqlalchemy.url` 是占位值，实际由 [alembic/env.py](backend/alembic/env.py) 用 `settings.database_url` 覆盖。
- **异步 Worker / 调度（本地）**：`cd backend && celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo`（Windows 需 `--pool=solo`）与 `celery -A app.tasks.celery_app.celery_app beat --loglevel=info`。
- **手动跑批（临时）**：`python -m app.tasks.process_logs --limit 100`（标准化）、`python -m app.tasks.analyze --seed`（写入内置规则并分析）；现已由 Celery 自动化替代。

## 十、注意事项 / 已知待办

1. **占位密钥未替换**：`.env.example` 中 `CHANGE_ME` 占位符生产必须替换；密钥未配置时采集接口返回 503。
2. **Celery 自动化已接入**：`beat` + `worker` 自动化 Outbox 调度/标准化/分析/告警重试；生产需确保 Redis 可用并配置 `REDIS_*`。Docker 内 `worker`/`scheduler` 服务已编排。
3. **设备心跳 + 失联告警已联动**：接入日志时自动登记未知设备并刷新 `last_seen_at`；设备列表按在线/离线判定；`check_device_offline` 周期任务（60s）检测失联设备生成 `DEVICE_OFFLINE` 事件 + 告警，恢复上报后自动关闭事件。
4. **企业微信（自建应用）**：`notifications/wecom.py` 用 corpid+corpsecret 取 access_token（内存缓存）再 `message/send` 发 Markdown；配置存 `wecom_config` 单行表（环境变量为初始值），可在「消息发送管理」页读写与测试发送。告警通知按 `notify_min_severity` 级别过滤（低于该级别的事件只记录、不推送）；接收人按「规则 > 设备 > 全局」三级解析（`analysis_rule.touser` / `device_registry.touser` / `wecom_config.touser`）。
5. **AI 研判已接入（DeepSeek）**：`app/ai/` 提供 OpenAI 兼容客户端/提示词/输出校验；部署到服务器后改 `AI_BASE_URL`/`AI_MODEL` 切回本地 Ollama，`AI_ENABLED=false` 时全链路照常运行（失败降级）。
6. **TypeScript 版本**：`frontend/package.json` 固定 `typescript@^5.9.3`（曾用 `7.x` 与 `vue-tsc` 不兼容导致 `npm run type-check` 失败）。
7. **非 git 仓库**：当前目录未初始化 git；`.gitignore` 亦缺失。
8. **历史数据时区**：MySQL 会话已强制 UTC（`init_command`），但修复前写入的 `received_at`/`created_at` 等旧数据仍为本地时间（+8h），仅影响历史展示，新数据一致。
9. **附件存储目录**：`uploads/`（可配 `UPLOAD_DIR`）在 Docker 内是容器内目录，需挂载卷持久化，否则容器重启文件丢失。
