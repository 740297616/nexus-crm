from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DashboardRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date


class DashboardTrendPoint(BaseModel):
    date: date
    count: int = Field(ge=0)


class DashboardDepartmentCount(BaseModel):
    department_id: str
    department_name: str
    count: int = Field(ge=0)


class DashboardEmployeeCount(BaseModel):
    user_id: str
    user_name: str
    department_id: str | None
    count: int = Field(ge=0)


class DashboardSourceCount(BaseModel):
    source: str | None
    count: int = Field(ge=0)


class DashboardLevelCount(BaseModel):
    level: Literal["A", "B", "C", "D"]
    count: int = Field(ge=0)


class DashboardFollowUp(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    user_id: str
    user_name: str
    method: Literal["phone", "visit", "wechat", "email", "other"]
    content: str
    followed_at: datetime
    result: str | None


class DashboardPersonalStats(BaseModel):
    my_customer_total: int = Field(ge=0)
    current_month_new_customers: int = Field(ge=0)
    current_month_follow_up_count: int = Field(ge=0)
    today_pending_reminder_count: int = Field(ge=0)
    overdue_reminder_count: int = Field(ge=0)
    recent_follow_ups: list[DashboardFollowUp]


class DashboardManagementStats(BaseModel):
    customer_total: int = Field(ge=0)
    department_customer_counts: list[DashboardDepartmentCount]
    employee_customer_counts: list[DashboardEmployeeCount]
    customer_source_distribution: list[DashboardSourceCount]
    customer_level_distribution: list[DashboardLevelCount]
    customer_new_trend: list[DashboardTrendPoint]
    follow_up_trend: list[DashboardTrendPoint]


class DashboardSummaryResponse(BaseModel):
    personal: DashboardPersonalStats
    management: DashboardManagementStats
    range: DashboardRange
