from __future__ import annotations

from datetime import date, datetime
from re import fullmatch
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CustomerLevel = Literal["A", "B", "C", "D"]
CustomerStatus = Literal["active", "inactive"]


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_no: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    owner_id: str | None = None
    source: str | None = Field(default=None, max_length=80)
    industry: str | None = Field(default=None, max_length=100)
    level: CustomerLevel = "C"
    status: CustomerStatus = "active"
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("customer_no", mode="before")
    @classmethod
    def normalize_customer_no(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, max_length=80)
    industry: str | None = Field(default=None, max_length=100)
    level: CustomerLevel | None = None
    status: CustomerStatus | None = None
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value

    @model_validator(mode="after")
    def reject_null_required_values(self) -> CustomerUpdate:
        for field_name in ("name", "level", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class CustomerAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(min_length=36, max_length=36)
    reason: str | None = Field(default=None, max_length=500)


class CustomerTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CustomerResponse(BaseModel):
    id: str
    customer_no: str
    name: str
    owner_id: str
    owner_name: str
    department_id: str
    department_name: str
    source: str | None
    industry: str | None
    level: CustomerLevel
    status: CustomerStatus
    phone: str | None
    email: str | None
    address: str | None
    description: str | None
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class CustomerOwnershipHistoryResponse(BaseModel):
    id: str
    action: Literal["assigned", "transferred"]
    previous_owner_id: str | None
    previous_owner_name: str | None
    previous_department_id: str | None
    new_owner_id: str
    new_owner_name: str
    new_department_id: str
    new_department_name: str
    transferred_by: str
    transferred_by_name: str
    reason: str | None
    created_at: datetime


class CustomerDetailResponse(CustomerResponse):
    ownership_history: list[CustomerOwnershipHistoryResponse] = Field(default_factory=list)


class CustomerDuplicateMatch(BaseModel):
    id: str
    customer_no: str
    name: str
    owner_name: str


class CustomerNameCheckResponse(BaseModel):
    has_duplicates: bool
    matches: list[CustomerDuplicateMatch]


class CustomerAssigneeResponse(BaseModel):
    id: str
    username: str
    display_name: str
    department_id: str
    department_name: str


class CustomerListFilters(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=80)
    industry: str | None = Field(default=None, max_length=100)
    level: CustomerLevel | None = None
    status: CustomerStatus | None = None
    owner_id: str | None = None
    department_id: str | None = None
    tag_id: str | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort_by: Literal["created_at", "updated_at", "customer_no", "name", "level", "status"] = (
        "created_at"
    )
    sort_order: Literal["asc", "desc"] = "desc"
