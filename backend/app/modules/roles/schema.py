from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.data_scope import DataScope as DataScopeValue

DataScope = Literal["self", "department", "subtree", "all"]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    description: str | None = Field(default=None, max_length=500)
    data_scope: DataScope = "self"
    permission_codes: list[str] = Field(default_factory=list)

    @field_validator("data_scope", mode="before")
    @classmethod
    def normalize_data_scope(cls, value: str) -> str:
        return DataScopeValue.from_value(value).value


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    data_scope: DataScope | None = None

    @field_validator("data_scope", mode="before")
    @classmethod
    def normalize_data_scope(cls, value: str | None) -> str | None:
        return None if value is None else DataScopeValue.from_value(value).value


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    resource: str
    action: str
    permission_type: Literal["menu", "page", "api"]
    description: str | None


class RoleResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None
    data_scope: DataScope
    is_system: bool
    permission_codes: list[str]
    created_at: datetime
    updated_at: datetime
