from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
