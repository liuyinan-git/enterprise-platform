"""AI Agent 平台配置（模块私有）。

`core/config.py` 的 Settings 是 `extra="ignore"`，因此 `.env` 里多出的 `AGENT_DOCKER_*`
/ `AGENT_PROBE_*` 等键不会影响既有配置；本模块自带一份 BaseSettings 读同一份 `.env`，
从而**不必改 `core/config.py`** —— 这是「配置项各自独立」的落点。

注意：既有的 `AGENT_OFFLINE_GRACE_SECONDS`（心跳宽限）留在 `core/config.py` 里没搬过来。
它已工作正常，搬动要牵动四个文件却没有行为收益。

**刻意不设 `AGENT_CHECK_INTERVAL_SECONDS`**：周期任务间隔的唯一真相是
`app/tasks/celery_app.py` 的 `beat_schedule`，系统设置页直读那份实时调度。
再设一个配置项只会让两者悄悄脱节。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentPlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # docker-socket-proxy 白名单代理地址。proxy 自身无鉴权，绝不能发布到宿主机。
    # 本地开发指向本机回环（见 .env.example 的 docker run），内网服务器指向实际 Docker 主机。
    agent_docker_proxy_url: str = "http://docker-proxy:2375"
    # 读请求超时，须落在前端 axios 的 10s 之内
    agent_docker_request_timeout_seconds: int = 5
    # 写请求超时，须大于停止宽限期
    agent_docker_action_timeout_seconds: int = 8
    agent_docker_stop_grace_seconds: int = 5

    agent_log_tail_default: int = 200
    agent_log_tail_max: int = 1000
    # 解帧后日志文本的硬上限（字符数）
    agent_log_max_chars: int = 262144
    # 是否让 Docker 带时间戳。Docker 给的是 RFC3339 UTC，服务端会逐行转成 naive 北京时
    # 再返回，因此开着它**不违反**「全库 naive 本地时间」的约定。
    agent_log_timestamps: bool = True

    # 平台自身 compose 项目名：该项目下的容器一律受保护，禁止启停
    agent_protected_project: str = "enterprise-platform"

    # 端点未填 timeout_seconds 时的默认值 / 允许填写的上限
    agent_probe_default_timeout_seconds: int = 5
    agent_probe_max_timeout_seconds: int = 60
    # 内网自签证书才关；关掉时只影响本次探测，不改全局 SSL 默认 context
    agent_probe_verify_tls: bool = True
    # 非健康时附带的响应体摘要字符上限
    agent_probe_max_excerpt_chars: int = 500

    # 监控历史保留天数，由 cleanup_agent_history 任务执行（配了就必须有人清理）
    agent_history_retention_days: int = 30


agent_settings = AgentPlatformSettings()
