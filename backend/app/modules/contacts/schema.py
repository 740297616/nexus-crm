from __future__ import annotations

from datetime import datetime
from re import fullmatch
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    contact_method: str | None = Field(default=None, max_length=50)
    is_primary: bool = False
    remark: str | None = Field(default=None, max_length=4000)

    @field_validator("name", "title", "phone", "email", "contact_method", "remark", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    contact_method: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None, max_length=4000)

    @field_validator("name", "title", "phone", "email", "contact_method", "remark", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value

    @model_validator(mode="after")
    def reject_null_name(self) -> ContactUpdate:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class ContactResponse(BaseModel):
    id: str
    customer_id: str
    name: str
    title: str | None
    phone: str | None
    email: str | None
    contact_method: str | None
    is_primary: bool
    remark: str | None
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class ContactListFilters(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    sort_order: Literal["asc", "desc"] = "asc"
