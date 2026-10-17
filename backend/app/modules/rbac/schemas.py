from pydantic import BaseModel, ConfigDict, Field


class RoleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str = Field(min_length=1, max_length=64)
    role_name: str = Field(min_length=1, max_length=100)
    external_role_id: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_name: str | None = Field(default=None, max_length=100)
    external_role_id: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None


class RolePermissionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission_codes: list[str] = Field(default_factory=list)
