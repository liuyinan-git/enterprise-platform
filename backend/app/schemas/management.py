from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class WecomConfigIn(BaseModel):
    """企业微信配置保存请求体。corpsecret 留空或以 **** 开头表示不修改。"""
    model_config = ConfigDict(extra="forbid")
    corpid: str = Field(max_length=200)
    corpsecret: str = Field(default="", max_length=200)
    agentid: int = Field(default=0, ge=0)
    touser: str = Field(default="", max_length=500)
    enabled: bool = True
    notify_min_severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class WecomTestIn(BaseModel):
    """企业微信测试发送请求体。touser 留空则用已配置的默认接收人。"""
    model_config = ConfigDict(extra="forbid")
    touser: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=4000)
