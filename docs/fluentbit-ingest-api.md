# Fluent Bit 日志接入接口文档

> 适用对象：在各主机上配置 Fluent Bit 上报日志的开发 / 运维人员。
> 平台：Enterprise Log Platform V1.0。

## 1. 接口概览

| 项 | 值 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/v1/ingest/fluentbit` |
| 鉴权 | 请求头 `X-API-Key`（= 平台后端 `COLLECTOR_API_KEY`） |
| 来源标识 | 请求头 `X-Source-Id`（**每台主机写不同值**，用于区分多台机上的同名容器） |
| Content-Type | `application/json`（JSON 数组 / 单对象 / NDJSON）或 `application/msgpack` |
| 成功响应 | `200`，统一包裹 `{"code": 0, "message": "accepted", "data": {...}}` |
| 语义 | 接收即确认（异步标准化），不做同步解析结果返回 |

## 2. 鉴权与来源标识

| 请求头 | 必填 | 说明 |
| --- | --- | --- |
| `X-API-Key` | 是 | 采集端密钥，与后端 `.env` 的 `COLLECTOR_API_KEY` 一致。**缺失或不匹配 → `401`**；后端未配置或仍是 `CHANGE_ME` 占位符 → `503` |
| `X-Source-Id` | 建议 | 采集端 / 主机标识。**多机部署时每台必须不同**（如 `docker-01`、`docker-02`、主机名/IP）。缺省值为 `fluentbit`。 |

## 3. 请求体格式

### 3.1 JSON 数组（推荐，Fluent Bit `json_lines` 输出）

```json
[
  {
    "log": "2026-10-15 08:39:04 INFO [app.services.result_stream] ...",
    "date": 1760488744.0,
    "source": "stdout",
    "hostname": "172.27.64.1",
    "container_id": "275a88e742ce...",
    "container_name": "/desd-app"
  }
]
```

### 3.2 单 JSON 对象

一条日志可直接作为单个 JSON 对象上报（平台自动包成数组处理）。

### 3.3 NDJSON

每行一个 JSON 对象，以换行分隔。

### 3.4 msgpack

`Content-Type: application/msgpack`，body 为 Fluent Bit msgpack 流（`[[时间, 记录], ...]`）。Fluent Bit 事件时间（ExtType code=0，8 字节 sec+nsec）会被解码为事件时间。

## 4. 字段映射

记录（record）里的键 → 平台字段：

| record 键（按优先级） | 平台字段 | 说明 |
| --- | --- | --- |
| `log` / `message` / `msg` / `log_message` | `raw_message` | 日志正文，取第一个非空值 |
| `@timestamp` / `timestamp` / `time` / `event_time` / `date` | `event_time` | 事件时间。`date` 是 Fluent Bit HTTP 输出默认时间键（Unix 秒浮点）；正文自带时间戳时优先用正文 |
| `device_id` / `container_name` / `hostname` / `host` / `source` / `agent` / `host.name` | `device_id` | 见下方 device_id 规则 |
| `hostname` / `host` | `hostname` | 设备主机名 |
| `container_id` | 设备 `attributes.container_id` | 容器完整 ID（写进设备注册表） |
| `source` | — | `stdout`/`stderr`；stderr 且正文无日志级别时，严重级别兜底为 `error` |

### device_id 规则

```
device_id = {X-Source-Id} - {container_name 去掉前导 "/"}
```

- 例如 `X-Source-Id=docker-01`、`container_name=/desd-app` → `device_id=docker-01-desd-app`。
- 作用：同一容器名部署在多台主机时，靠 `X-Source-Id` 前缀区分；同一主机不同服务靠容器名区分。
- 记录里若显式带 `device_id` 键，则优先用它（同样会拼 `X-Source-Id` 前缀）。

## 5. 幂等性

- `event_id` = 整条 record 内容（JSON 键排序后）的 **SHA256 哈希**。
- 落库用 `INSERT ... IGNORE` + 唯一约束 `uk_source_event(source_id, event_id)`，**Fluent Bit 重试 / 重复上报不会重复入库**。

## 6. 限制

| 项 | 值 |
| --- | --- |
| 单批最大条数 | `max_logs_per_batch` = **1000**（超出 → `422`） |
| 单条正文最大字符 | `max_raw_message_chars` = **20000**（超出截断） |

## 7. 响应

### 成功（`200`）

```json
{
  "code": 0,
  "message": "accepted",
  "data": {
    "batch_id": "fb-9f3c2a1b...",
    "source_id": "docker-01",
    "received": 1,
    "accepted": 1,
    "rejected": 0,
    "status": "accepted"
  }
}
```

- `status`：`accepted`（正常）、`empty`（空 body / 无记录）。

### 错误

| 状态码 | 含义 |
| --- | --- |
| `401` | `X-API-Key` 缺失或不匹配 |
| `503` | 后端未配置采集密钥（仍是占位符） |
| `422` | 超过单批最大条数 |

## 8. Fluent Bit 客户端配置示例

```ini
[OUTPUT]
    Name            http
    Match           *
    Host            <平台地址>
    Port            <平台端口，本地 7553 / Docker 7552>
    URI             /api/v1/ingest/fluentbit
    Format          json_lines
    header          X-API-Key    <采集密钥>
    header          X-Source-Id  <本机标识，如 docker-01>
    tls             Off
    Retry_Limit     False
```

> 建议用 `record_modifier` 过滤器补 `hostname`（真实主机名）等字段；完整示例见 `collector/fluent-bit.conf`。

## 9. 测试示例

### curl

```bash
curl -X POST http://127.0.0.1:7553/api/v1/ingest/fluentbit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 123456" \
  -H "X-Source-Id: docker-01" \
  -d '[{"log":"test message","date":1760488744.0,"container_name":"/desd-app"}]'
```

### 预期响应

```json
{"code":0,"message":"accepted","data":{"batch_id":"fb-...","source_id":"docker-01","received":1,"accepted":1,"rejected":0,"status":"accepted"}}
```

## 10. 备注

- 该接口**只负责接收并落库原始日志**，标准化、规则分析、告警由后台 Celery 异步完成。
- 采集端应保证日志正文/字段为 UTF-8；时间戳建议带时区或为 Unix 秒。
