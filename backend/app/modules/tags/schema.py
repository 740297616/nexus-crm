from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_null_name(self) -> TagUpdate:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class TagResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class CustomerTagResponse(BaseModel):
    id: str
    customer_id: str
    tag_id: str
    tag_name: str
    tag_description: str | None
    created_by: str
    created_at: datetime


class TagBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: str = Field(min_length=36, max_length=36)
