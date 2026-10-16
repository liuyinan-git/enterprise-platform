import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.agent.probes import ALLOWED_METHODS


class AgentIn(BaseModel):
    """智能体登记/更新请求体，按 agent_id 幂等 upsert。"""
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1, max_length=100)
    agent_name: str = Field(min_length=1, max_length=200)
    agent_type: str = Field(min_length=1, max_length=50)
    version: str | None = Field(default=None, max_length=50)
    owner: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=50)
    enabled: bool = True
    attributes: dict[str, Any] | list[Any] | None = None


class AgentUpdate(BaseModel):
    """智能体部分更新请求体。"""
    model_config = ConfigDict(extra="forbid")
    agent_name: str | None = Field(default=None, max_length=200)
    agent_type: str | None = Field(default=None, max_length=50)
    version: str | None = Field(default=None, max_length=50)
    owner: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=50)
    enabled: bool | None = None
    attributes: dict[str, Any] | list[Any] | None = None


# ===== AI Agent 平台：容器 / 项目规则 / 端点监控 =====

# 容器名那一侧存的是**正则**，必须能编译；这里在入口就拦掉，别让坏正则进库
# （判定时虽然也兜住了 re.error，但保存时不报错会让用户以为配对了）。
_PATTERN_MAX = 200


def _validate_patterns(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if len(value) > 50:
        raise ValueError("列表最多 50 项")
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        if len(text) > _PATTERN_MAX:
            raise ValueError(f"单项长度不能超过 {_PATTERN_MAX}")
        try:
            re.compile(text)
        except re.error as exc:
            raise ValueError(f"正则非法：{text}（{exc}）") from exc
        cleaned.append(text)
    return cleaned


def _validate_plain(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if len(value) > 50:
        raise ValueError("列表最多 50 项")
    return [str(item).strip() for item in value if str(item).strip()]


class ProjectRuleIn(BaseModel):
    """项目分类规则新增请求体。"""
    model_config = ConfigDict(extra="forbid")
    project_key: str = Field(min_length=1, max_length=100)
    project_name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    # compose 项目名：精确匹配 label com.docker.compose.project
    compose_project_names: list[str] | None = None
    # 容器名：**正则**，按 re.search(..., re.I) 匹配
    container_name_patterns: list[str] | None = None
    description: str | None = Field(default=None, max_length=500)
    # 冲突时仅供 UI 提示「先看哪条」，不会被自动用于指派
    priority: int = Field(default=100, ge=0, le=10000)

    @field_validator("compose_project_names")
    @classmethod
    def _check_compose(cls, value):
        return _validate_plain(value)

    @field_validator("container_name_patterns")
    @classmethod
    def _check_patterns(cls, value):
        return _validate_patterns(value)


class ProjectRuleUpdate(BaseModel):
    """项目分类规则部分更新（project_key 是标识，不可改）。"""
    model_config = ConfigDict(extra="forbid")
    project_name: str | None = Field(default=None, max_length=200)
    enabled: bool | None = None
    compose_project_names: list[str] | None = None
    container_name_patterns: list[str] | None = None
    description: str | None = Field(default=None, max_length=500)
    priority: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("compose_project_names")
    @classmethod
    def _check_compose(cls, value):
        return _validate_plain(value)

    @field_validator("container_name_patterns")
    @classmethod
    def _check_patterns(cls, value):
        return _validate_patterns(value)


class RuleEnabledIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


# 服务类型：AI 服务接口 + LangGraph 共用一张端点表，用这个字段区分。
# 只做长度与格式约束，不做枚举 —— 内网可能接入文档之外的服务，写死枚举会挡住它。
SERVICE_TYPES = ("openclaw", "hermes", "codex", "dify", "langgraph", "custom")


class EndpointIn(BaseModel):
    """端点台账新增请求体（AI 服务接口与 LangGraph 共用）。"""
    model_config = ConfigDict(extra="forbid")
    endpoint_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    service_type: str = Field(min_length=1, max_length=50)
    group: str | None = Field(default=None, max_length=100)
    url: str = Field(min_length=1, max_length=1000)
    method: str = Field(default="GET", max_length=10)
    headers: dict[str, Any] | None = None
    request_body: dict[str, Any] | list[Any] | None = None
    # 为空 → 按「2xx 为健康」判定；填了 → 健康当且仅当状态码在其中（如 [200, 401]）
    expected_status: list[int] | None = None
    timeout_seconds: int = Field(default=5, ge=1, le=60)
    enabled: bool = True
    description: str | None = Field(default=None, max_length=500)
    attributes: dict[str, Any] | list[Any] | None = None

    @field_validator("method")
    @classmethod
    def _check_method(cls, value: str) -> str:
        upper = value.strip().upper()
        if upper not in ALLOWED_METHODS:
            raise ValueError(f"HTTP 方法必须是 {'/'.join(ALLOWED_METHODS)} 之一")
        return upper

    @field_validator("expected_status")
    @classmethod
    def _check_expected(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if not value:
            return None
        for item in value:
            if not (100 <= int(item) <= 599):
                raise ValueError("状态码必须在 100..599 之间")
        return sorted({int(item) for item in value})


class EndpointUpdate(BaseModel):
    """端点台账部分更新（endpoint_code 是标识，不可改）。"""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=200)
    service_type: str | None = Field(default=None, max_length=50)
    group: str | None = Field(default=None, max_length=100)
    url: str | None = Field(default=None, max_length=1000)
    method: str | None = Field(default=None, max_length=10)
    headers: dict[str, Any] | None = None
    request_body: dict[str, Any] | list[Any] | None = None
    expected_status: list[int] | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=500)
    attributes: dict[str, Any] | list[Any] | None = None

    @field_validator("method")
    @classmethod
    def _check_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.strip().upper()
        if upper not in ALLOWED_METHODS:
            raise ValueError(f"HTTP 方法必须是 {'/'.join(ALLOWED_METHODS)} 之一")
        return upper

    @field_validator("expected_status")
    @classmethod
    def _check_expected(cls, value: list[int] | None) -> list[int] | None:
        if not value:
            return None
        for item in value:
            if not (100 <= int(item) <= 599):
                raise ValueError("状态码必须在 100..599 之间")
        return sorted({int(item) for item in value})


class CheckBatchIn(BaseModel):
    """批量检查。codes 为空或省略 = 检查全部启用中的端点。"""
    model_config = ConfigDict(extra="forbid")
    codes: list[str] | None = Field(default=None, max_length=500)


class ContainerActionIn(BaseModel):
    """停止 / 重启的宽限期（秒）。不传则用 AGENT_DOCKER_STOP_GRACE_SECONDS。"""
    model_config = ConfigDict(extra="forbid")
    timeout: int | None = Field(default=None, ge=0, le=60)
