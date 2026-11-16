from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FollowUpMethod = Literal["phone", "visit", "wechat", "email", "other"]
ReminderStatus = Literal["pending", "completed", "cancelled"]


class FollowUpCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: str | None = None
    method: FollowUpMethod
    content: str = Field(min_length=1, max_length=10000)
    followed_at: datetime
    result: str | None = Field(default=None, max_length=2000)
    next_follow_up_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_text(self) -> "FollowUpCreate":
        self.content = self.content.strip()
        if self.result is not None:
            self.result = self.result.strip() or None
        if not self.content:
            raise ValueError("content cannot be blank")
        return self


class FollowUpUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: str | None = None
    method: FollowUpMethod | None = None
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    followed_at: datetime | None = None
    result: str | None = Field(default=None, max_length=2000)
    next_follow_up_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_text(self) -> "FollowUpUpdate":
        for field_name in ("method", "followed_at"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        if self.content is not None:
            self.content = self.content.strip()
            if not self.content:
                raise ValueError("content cannot be blank")
        elif "content" in self.model_fields_set:
            raise ValueError("content cannot be null")
        if self.result is not None:
            self.result = self.result.strip() or None
        return self


class FollowUpResponse(BaseModel):
    id: str
    customer_id: str
    contact_id: str | None
    contact_name: str | None
    user_id: str
    user_name: str
    method: FollowUpMethod
    content: str
    followed_at: datetime
    result: str | None
    next_follow_up_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FollowUpListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, max_length=200)
    method: FollowUpMethod | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    sort_order: Literal["asc", "desc"] = "desc"


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=5000)
    remind_at: datetime
    customer_id: str | None = None
    follow_up_record_id: str | None = None

    @model_validator(mode="after")
    def normalize_text(self) -> "ReminderCreate":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be blank")
        if self.content is not None:
            self.content = self.content.strip() or None
        return self


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=5000)
    remind_at: datetime | None = None
    customer_id: str | None = None
    follow_up_record_id: str | None = None

    @model_validator(mode="after")
    def normalize_text(self) -> "ReminderUpdate":
        if "remind_at" in self.model_fields_set and self.remind_at is None:
            raise ValueError("remind_at cannot be null")
        if self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError("title cannot be blank")
        elif "title" in self.model_fields_set:
            raise ValueError("title cannot be null")
        if self.content is not None:
            self.content = self.content.strip() or None
        return self


class ReminderResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    customer_id: str | None
    customer_name: str | None
    follow_up_record_id: str | None
    title: str
    content: str | None
    remind_at: datetime
    status: ReminderStatus
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    is_overdue: bool


class ReminderListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReminderStatus | None = None
    customer_id: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"
