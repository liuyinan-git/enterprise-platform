from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LogItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str | None = Field(default=None, max_length=200)
    event_time: datetime | None = None
    device_id: str | None = Field(default=None, max_length=100)
    device_type: str = Field(default="other", max_length=50)
    hostname: str | None = Field(default=None, max_length=255)
    format_type: str = Field(default="text", max_length=40, alias="format")
    raw_message: str = Field(min_length=1)
    fields: dict[str, Any] | list[Any] | None = None

    @field_validator("raw_message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("raw_message must not be blank")
        return value


class LogBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    logs: list[LogItemIn] = Field(min_length=1)


class DeviceIn(BaseModel):
    """设备登记/更新请求体。按 device_id 幂等 upsert。"""
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=100)
    device_name: str = Field(min_length=1, max_length=200)
    device_type: str = Field(min_length=1, max_length=50)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    environment: str | None = Field(default=None, max_length=50)
    criticality: str = Field(default="normal", max_length=20)
    expected_interval_seconds: int = Field(default=900, ge=1)
    touser: str | None = Field(default=None, max_length=500)
    enabled: bool = True
    attributes: dict[str, Any] | list[Any] | None = None


class RuleIn(BaseModel):
    """新增规则请求体。"""
    model_config = ConfigDict(extra="forbid")
    rule_code: str = Field(min_length=1, max_length=100)
    rule_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    rule_type: str = Field(default="threshold", max_length=40)
    severity: str = Field(default="medium", max_length=20)
    enabled: bool = True
    cooldown_seconds: int = Field(default=600, ge=0)
    touser: str | None = Field(default=None, max_length=500)
    rule_config: dict[str, Any] = Field(default_factory=dict)


class RuleUpdate(BaseModel):
    """修改规则请求体，仅提交需要变更的字段。"""
    model_config = ConfigDict(extra="forbid")
    rule_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    severity: str | None = Field(default=None, max_length=20)
    enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    touser: str | None = Field(default=None, max_length=500)
    rule_config: dict[str, Any] | None = None


class EventPatch(BaseModel):
    """安全事件状态流转请求体：确认、分派、关闭。"""
    model_config = ConfigDict(extra="forbid")
    status: str | None = Field(default=None, pattern="^(open|confirmed|closed)$")
    assigned_to: str | None = Field(default=None, max_length=100)
    resolution_note: str | None = None

    @model_validator(mode="after")
    def check_not_empty(self) -> "EventPatch":
        if self.status is None and self.assigned_to is None and self.resolution_note is None:
            raise ValueError("至少提供一个要更新的字段")
        return self
