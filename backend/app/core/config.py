from functools import lru_cache
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 7550
    log_level: str = "INFO"
    mysql_database: str = "enterprise_platform"
    mysql_user: str = "log_app"
    mysql_password: str = "CHANGE_ME_app_password"
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_pool_size: int = 5
    mysql_max_overflow: int = 10
    collector_api_key: str = "CHANGE_ME_use_a_long_random_secret"
    max_logs_per_batch: int = 1000
    max_raw_message_chars: int = 20000
    raw_log_retention_days: int = 90
    event_retention_days: int = 365
    wecom_enabled: bool = False
    wecom_corpid: str = ""
    wecom_corpsecret: str = ""
    wecom_agentid: int = 0
    wecom_touser: str = ""
    wecom_notify_min_severity: str = "medium"
    wecom_timeout_seconds: int = 5
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    ai_enabled: bool = False
    ai_provider: str = "ollama"
    ai_base_url: str = "http://ollama:11434/v1"
    ai_model: str = ""
    ai_api_key: str = ""
    ai_timeout_seconds: int = 60
    ai_max_input_chars: int = 12000
    ai_max_retries: int = 2
    ai_wecom_min_risk: str = "suspicious"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 200
    agent_offline_grace_seconds: int = 300
    model_check_timeout_seconds: int = 5
    # vLLM 用量采集：/metrics 计数器指标名（不同 vLLM 版本命名可能不同，可按模型覆盖）
    model_usage_metric: str = "vllm:request_success_total"
    model_metrics_timeout_seconds: int = 10
    # 模型服务告警：连续失败 N 次触发企业微信；恢复时发恢复通知
    model_alert_enabled: bool = True
    model_alert_failure_threshold: int = 3
    model_alert_recovery_enabled: bool = True
    # 容器实况：经 docker-socket-proxy 只读读取模型容器状态（model 模块只读不启停）。
    # 生产（compose 内）默认地址 http://docker-proxy:2375；本地 mock 联调用 http://127.0.0.1:23750
    model_container_enabled: bool = False
    model_container_proxy_url: str = "http://docker-proxy:2375"
    model_container_timeout_seconds: int = 3
    database_check_timeout_seconds: int = 3
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_authorize_url: str = ""
    oidc_token_url: str = ""
    oidc_jwks_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:5170/auth/callback"
    oidc_audience: str = ""
    oidc_roles_claim: str = "roles"
    oidc_scopes: str = "openid profile"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.mysql_user)}:{quote_plus(self.mysql_password)}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{quote_plus(self.redis_password)}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
