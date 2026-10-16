from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_code: str = Field(min_length=1, max_length=100)
    instance_name: str = Field(min_length=1, max_length=200)
    db_type: str = Field(min_length=1, max_length=50)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database_name: str | None = Field(default=None, max_length=100)
    username: str | None = Field(default=None, max_length=100)
    password: str = Field(default="", max_length=500)
    environment: str | None = Field(default=None, max_length=50)
    enabled: bool = True
    attributes: dict[str, Any] | list[Any] | None = None


class InstanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_name: str | None = Field(default=None, max_length=200)
    db_type: str | None = Field(default=None, max_length=50)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, max_length=100)
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=500)
    environment: str | None = Field(default=None, max_length=50)
    enabled: bool | None = None
    attributes: dict[str, Any] | list[Any] | None = None


class BackupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_code: str = Field(min_length=1, max_length=100)
    backup_type: str = Field(default="full", max_length=50)
    status: str = Field(default="success", max_length=24)
    size: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: str | None = None
