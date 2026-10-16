"""容器管控配置（模块私有）。

`core/config.py` 的 Settings 是 `extra="ignore"`，因此 `.env` 里多出的 `CONTAINER_*`
不会影响既有配置；本模块自带一份 BaseSettings 读同一份 `.env`，从而**不必改
`core/config.py`** —— 这是「只共用配置层面」的落点。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ContainerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # docker-socket-proxy 白名单代理地址。proxy 自身无鉴权，绝不能发布到宿主机。
    container_proxy_url: str = "http://docker-proxy:2375"
    # 读请求超时，须落在前端 axios 的 10s 之内
    container_request_timeout_seconds: int = 5
    # 写请求超时，须大于停止宽限期
    container_action_timeout_seconds: int = 8
    container_stop_grace_seconds: int = 5
    container_log_tail_default: int = 200
    container_log_tail_max: int = 1000
    # 解帧后日志文本的硬上限（字符数）
    container_log_max_chars: int = 262144
    # 平台自身 compose 项目名：该项目下的容器一律受保护，禁止启停
    container_protected_project: str = "enterprise-platform"


container_settings = ContainerSettings()
