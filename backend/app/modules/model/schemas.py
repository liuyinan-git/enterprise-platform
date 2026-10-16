from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_code: str = Field(min_length=1, max_length=100)
    provider_name: str = Field(min_length=1, max_length=200)
    provider_type: str = Field(default="openai", max_length=50)
    base_url: str = Field(default="", max_length=500)
    api_key: str = Field(default="", max_length=500)
    enabled: bool = True


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_name: str | None = Field(default=None, max_length=200)
    provider_type: str | None = Field(default=None, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None


class ModelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_code: str = Field(min_length=1, max_length=100)
    provider_code: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    version: str | None = Field(default=None, max_length=50)
    context_window: int | None = Field(default=None, ge=0)
    parameters: dict[str, Any] | list[Any] | None = None
    enabled: bool = True


class ModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_name: str | None = Field(default=None, max_length=200)
    version: str | None = Field(default=None, max_length=50)
    context_window: int | None = Field(default=None, ge=0)
    parameters: dict[str, Any] | list[Any] | None = None
    enabled: bool | None = None


class UsageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_code: str = Field(min_length=1, max_length=100)
    call_count: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    recorded_day: str = Field(min_length=1, max_length=10)
