from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str | None = Field(default=None, max_length=255)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    department_id: str | None = None
    role_ids: list[str] = Field(min_length=1)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: str | None = None


class UserStatusUpdate(BaseModel):
    status: Literal["active", "disabled"]


class UserRolesUpdate(BaseModel):
    role_ids: list[str] = Field(min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str | None
    display_name: str
    department_id: str | None
    department_name: str | None = None
    status: Literal["active", "disabled"]
    role_codes: list[str] = Field(default_factory=list)
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
