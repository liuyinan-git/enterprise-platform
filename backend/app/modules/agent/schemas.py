from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
