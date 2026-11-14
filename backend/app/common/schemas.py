from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiSuccess[T](BaseModel):
    success: Literal[True] = True
    data: T
    meta: dict[str, Any] | None = None
    request_id: str


class PageData[T](BaseModel):
    items: list[T]
    total: int


class PageMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
