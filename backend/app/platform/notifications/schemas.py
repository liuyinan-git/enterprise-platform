from pydantic import BaseModel, ConfigDict, Field


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
