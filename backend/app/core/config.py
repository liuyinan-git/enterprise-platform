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
    raw_log_retention_days: int = 7
    event_retention_days: int = 7
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
    # 调用方监控：读模型容器 stdout 的 access log（uvicorn 格式），按 source_ip 聚合「谁在调模型」。
    # tail = 每周期读日志行数上限；max_chars = 单次日志文本字符上限（对齐 AGENT_LOG_* 语义）
    model_access_log_tail: int = 500
    model_access_log_max_chars: int = 262144
    database_check_timeout_seconds: int = 3
    # 网关统一认证（APISIX openid-connect + forward-auth 注入用户头）
    gateway_auth_enabled: bool = False
    gateway_user_id_header: str = "x-user-id"
    gateway_username_header: str = "x-user-num"
    gateway_roles_header: str = "x-user-roles"
    # 网关模块数据库（3 套独立库，分布在不同服务器）
    gateway_squid_db_host: str = "127.0.0.1"
    gateway_squid_db_port: int = 3306
    gateway_squid_db_user: str = "squid_writer"
    gateway_squid_db_password: str = "your_password"
    gateway_squid_db_database: str = "squid_log"
    gateway_apisix_logs_db_host: str = "172.26.99.22"
    gateway_apisix_logs_db_port: int = 3307
    gateway_apisix_logs_db_user: str = "apisix_user"
    gateway_apisix_logs_db_password: str = "apisix"
    gateway_apisix_logs_db_database: str = "apisix_logs"
    gateway_apisix_monitor_db_host: str = "127.0.0.1"
    gateway_apisix_monitor_db_port: int = 3307
    gateway_apisix_monitor_db_user: str = "apisix"
    gateway_apisix_monitor_db_password: str = "apisix"
    gateway_apisix_monitor_db_database: str = "apisix_monitor"
    # 网关运行配置（Squid 容器 / 文件路径 / APISIX 节点）
    gateway_squid_container: str = "squid-proxy"
    gateway_squid_conf_path: str = "/ops/squid/squid.conf"
    gateway_squid_details_dir: str = "/ops/squid/details"
    gateway_squid_details_backup_dir: str = "/ops/squid_platform/squid_details_backup"
    gateway_squid_conf_backup_dir: str = "/ops/squid_platform/squid_conf_backup"
    gateway_squid_log_file: str = "/ops/squid/logs/access.log"
    gateway_apisix_admin_key: str = ""
    gateway_apisix_base_urls: str = ""  # 逗号分隔多个 APISIX 节点 base_url

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

    def _mysql_url(self, user: str, password: str, host: str, port: int, database: str) -> str:
        return (
            f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{database}?charset=utf8mb4"
        )

    @property
    def gateway_squid_db_url(self) -> str:
        return self._mysql_url(self.gateway_squid_db_user, self.gateway_squid_db_password,
                               self.gateway_squid_db_host, self.gateway_squid_db_port,
                               self.gateway_squid_db_database)

    @property
    def gateway_apisix_logs_db_url(self) -> str:
        return self._mysql_url(self.gateway_apisix_logs_db_user, self.gateway_apisix_logs_db_password,
                               self.gateway_apisix_logs_db_host, self.gateway_apisix_logs_db_port,
                               self.gateway_apisix_logs_db_database)

    @property
    def gateway_apisix_monitor_db_url(self) -> str:
        return self._mysql_url(self.gateway_apisix_monitor_db_user, self.gateway_apisix_monitor_db_password,
                               self.gateway_apisix_monitor_db_host, self.gateway_apisix_monitor_db_port,
                               self.gateway_apisix_monitor_db_database)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
