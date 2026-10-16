# 采集端样例程序

用于演示安全员采集程序如何对接平台日志接收接口。运行在受管设备侧，非平台服务组件。

## 能力

- 本地持久化队列（`pending.jsonl`）：平台确认成功后才删除已发送数据，断网/重试不丢日志。
- 失败指数退避重试（上限 5 次），重试复用同一 `batch_id` / `event_id`，保证幂等。
- 通过 `X-API-Key` 认证，批量上报到 `POST /api/v1/logs/batch`。

## 结构化字段（可选）

上报日志时，可在 `fields`（`/logs/batch`）或 Fluent Bit 的 record 里附带以下键，平台标准化时会识别并写入「日志检索」页对应列：

| 键 | 落库字段 |
| ---- | ---- |
| `source_ip` / `source_port` | 来源 IP / 来源端口 |
| `dest_ip` / `dest_port` | 目标 IP / 目标端口 |
| `username` | 用户 |
| `process_name` | 进程 |
| `hostname` / `device_type` | 主机名 / 设备类型 |

`generate_logs()` 里的样例日志已经演示了 `source_ip` / `username` / `dest_ip` 的写法。注意：这些字段只能来自采集端/应用侧，平台不会从日志正文猜测（`username` 尤其需要应用结构化输出才拿得到）。

## 用法

```bash
# 生成 100 条样例日志并上报
python sample_collector.py --base-url http://localhost:7550 \
    --api-key dev-local-collector-key --source collector01 --count 100

# 只重发本地队列中未发送成功的数据（例如断网恢复后）
python sample_collector.py --base-url http://localhost:7550 \
    --api-key dev-local-collector-key --source collector01 --flush-only
```

`--api-key` 需与后端 `COLLECTOR_API_KEY` 一致；本地开发默认是 `backend/.env` 里的 `dev-local-collector-key`。
