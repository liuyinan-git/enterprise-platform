# 规则管理使用与开发说明

> 适用对象：负责配置、新增、维护检测规则的安全/运维人员。
> 平台：Enterprise Log Platform V1.0。

## 1. 规则是什么

规则（`analysis_rule`）用于「从标准化日志里，按阈值统计某个事件类型，超阈值就聚合出一个安全事件并告警」。

当前只实现了一种规则类型：**threshold（阈值计数）**。规则引擎（[rules/engine.py](../backend/app/rules/engine.py)）每 30 秒由 Celery 的 `run_analysis` 任务跑一轮。

## 2. 新增规则的三种方式

| 方式 | 入口 | 适用 |
| --- | --- | --- |
| 界面新增 | 前端「规则管理」页 → 新增规则 | 日常使用，推荐 |
| API | `POST /api/v1/rules` | 脚本/自动化 |
| 代码 seed | [rules/builtins.py](../backend/app/rules/builtins.py) + `seed_rules()` | 内置规则、随版本发布 |

### 2.1 界面表单字段

| 表单字段 | 说明 |
| --- | --- |
| 规则编码 `rule_code` | 唯一，不可与现有规则重复；如 `SSH_LOGIN_FAILURE_BURST`。编辑时锁定 |
| 规则名称 `rule_name` | 人类可读名称 |
| 风险等级 `severity` | `critical / high / medium / low` |
| 事件类型 `event_type` | **必须精确匹配** `log_event.event_type`，见 §5 |
| 时间窗口 `window_seconds` | 秒，统计窗口长度，默认 300 |
| 阈值 `threshold` | 窗口内条数 ≥ 该值才触发 |
| 分组字段 `group_by` | 逗号分隔，如 `source_ip,device_id,username`；决定聚合粒度 |
| 冷却 `cooldown_seconds` | 秒，默认 600（**当前引擎未强制使用**，见 §7） |
| 接收人 `touser` | 企业微信 UserID，留空则用设备/全局；多人用 `\|` 分隔 |

### 2.2 API 请求体

```json
{
  "rule_code": "KAFKA_CONNECTION_ERROR",
  "rule_name": "Kafka 连接故障",
  "severity": "high",
  "enabled": true,
  "cooldown_seconds": 600,
  "touser": "YiNan",
  "rule_config": {
    "event_type": "kafka_error",
    "window_seconds": 300,
    "threshold": 3,
    "group_by": ["device_id"]
  }
}
```

> `POST /api/v1/rules` 新建；`PUT /api/v1/rules/{rule_code}` 修改（修改 `rule_config` 会让 `version` +1）。
> `rule_code` 重复 → `409`；`rule_code` 不存在 → `404`。

## 3. 规则引擎工作原理

对每条启用规则，`run_analysis` 每 30s 执行：

1. 取时间窗口内（`event_time >= now - window_seconds`）且 `event_type` 精确相等的 `log_event`。
2. 按 `group_by` 字段分组（字段值为 `null` 记作空串）。
3. 每组条数 ≥ `threshold` → 产出一个「发现」（finding）。
4. 用 `sha256(rule_code | group_key)` 做指纹去重：
   - 已存在**未关闭**（`status=open`）的同指纹安全事件 → 仅更新 `last_seen_at`/次数/证据，**不重复告警**。
   - 不存在 → 新建 `security_event`（等级取规则的 `severity`）+ `alert_record`，并按通知门槛推送企业微信。

## 4. 现有可用的 event_type（重要）

规则引擎按 `event_type` **精确匹配**，所以填的必须是标准化后真实会出现的值。当前 [normalize.py](../backend/app/services/normalize.py) 会产生：

| event_type | 来源 | 含义 |
| --- | --- | --- |
| `login_failure` | 关键词 | 登录失败 |
| `login_success` | 关键词 | 登录成功 |
| `traffic_block` | 关键词 | 网络阻断/deny |
| `traffic_allow` | 关键词 | 网络放行/accept |
| `ssh_event` | 关键词 | SSH 事件 |
| `kafka_error` | 关键词 | Kafka 连接/心跳故障 |
| `redis_error` | 关键词 | Redis 连接失败 |
| `upstream_error` | 关键词 | 上游 B/LLM 服务调用失败 |
| `error` | 关键词兜底 | 其他 error/exception/fail |
| `unknown` | 默认 | 未分类（不建议做规则，范围太泛） |

> **要新增 event_type**：在 `normalize.py` 的 `KEYWORD_RULES` 里加一条 `(正则, (category, event_type, severity, security_label))`，注意放到通用 `fail|error|exception|critical` 规则**之前**，否则会被它吞掉。

## 5. 需要注意的地方（踩坑清单）

1. **`event_type` 必须精确匹配**：引擎是 `==` 比较，大小写、拼写、前后空格都不能错。填了个分类里不存在的 event_type → 规则永远不触发。
2. **`group_by` 必须是 `log_event` 的字段名**：引擎用 `getattr(row, field)` 取值，乱填会报错。可用字段：`device_id / hostname / device_type / event_category / event_type / severity / security_label / source_ip / dest_ip / source_port / dest_port / username / process_name` 等。
3. **`group_by` 决定聚合粒度，也决定指纹**：改 `group_by` 会改变指纹 → 产生全新的安全事件。例如 `["source_ip"]` 按来源 IP 聚，`["source_ip","username"]` 按「IP+账号」聚。
4. **`event_time` 是北京时间**：平台已统一存 naive 北京时间（UTC+8）。时间窗口按此计算，与设备/采集端时区无关。
5. **`severity` 是风险等级，不是日志级别**：规则/事件的 `severity` 用 `low/medium/high/critical`；日志本身的「日志级别」是 `debug/info/notice/warning/error/critical`。两套不要混（见文档「日志检索」）。
6. **通知门槛**：只有 `security_event.severity >= 企业微信配置的 notify_min_severity`（默认 `medium`）才会真正推送。规则设成 `low` 且门槛是 `medium` → 只记录不推送。
7. **接收人三级解析**：规则 `touser` > 设备 `touser` > 全局企业微信 `touser`。留空则逐级回退。
8. **`cooldown_seconds` 当前不生效**：引擎没有读取该字段，真正的「去重」靠「同指纹的**未关闭**事件」——事件只要还开着就不会重复告警；关闭后才可能再次触发。`cooldown_seconds` 只是先存着，留待后续实现冷却逻辑。
9. **`device_types` 字段未启用**：模型里有但引擎没用它，界面/API 也不暴露，先忽略。
10. **中文关键词匹配不上**：当前采集的日志正文中文是 GBK 乱码（源头应用编码问题），所以 `normalize.py` 里的中文关键词正则不会命中。新增分类规则时**只用英文关键词**（如 `KafkaConnectionError`、`Connection refused`、`HTTP 404`），并建议源头应用设 `PYTHONIOENCODING=utf-8`。
11. **改规则后只影响新评估**：阈值/窗口/等级修改即时生效（下个 30s 周期）；但已产生的历史安全事件不会被改动。
12. **已有日志不追溯**：`event_type` 是标准化时定死的，新增分类后，**已入库日志不会被重新分类**，只有新日志按新规则走。

## 6. 内置规则示例（[builtins.py](../backend/app/rules/builtins.py)）

```python
{
    "rule_code": "KAFKA_CONNECTION_ERROR",
    "rule_name": "Kafka 连接故障",
    "rule_type": "threshold",
    "severity": "high",
    "cooldown_seconds": 600,
    "rule_config": {
        "event_type": "kafka_error",
        "window_seconds": 300,
        "group_by": ["device_id"],
        "threshold": 3,
    },
}
```

## 7. 如何验证一条规则

1. 在「规则管理」新增/启用规则。
2. 制造/等待对应的日志事件（或临时调低阈值观察）。
3. 看「安全事件」页是否出现新事件；「告警」页是否产生告警记录。
4. 确认企业微信是否按 `notify_min_severity` 收到推送。
5. 想快速验证：临时把 `threshold` 调到 1，触发后记得改回。
