from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.common.data_scope import data_scope_service
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.dashboard import repository
from app.modules.dashboard.schema import (
    DashboardDepartmentCount,
    DashboardEmployeeCount,
    DashboardFollowUp,
    DashboardLevelCount,
    DashboardManagementStats,
    DashboardPersonalStats,
    DashboardRange,
    DashboardSourceCount,
    DashboardSummaryResponse,
    DashboardTrendPoint,
)

MAX_RANGE_DAYS = 366
RECENT_FOLLOW_UP_LIMIT = 10


def get_dashboard_summary(
    db: Session,
    *,
    actor: User,
    start_date: date | None,
    end_date: date | None,
) -> DashboardSummaryResponse:
    today = datetime.now(UTC).date()
    resolved_start, resolved_end = _resolve_range(
        start_date=start_date or (today - timedelta(days=29)),
        end_date=end_date or today,
    )
    scope = data_scope_service.resolve(db, actor)
    range_start = _at_start_of_day(resolved_start)
    range_end = _at_start_of_day(resolved_end + timedelta(days=1))
    month_start = _at_start_of_day(today.replace(day=1))
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = _at_start_of_day(next_month)
    today_end = _at_start_of_day(today + timedelta(days=1))
    now = datetime.now(UTC)

    personal = DashboardPersonalStats(
        my_customer_total=repository.count_my_customers(db, scope=scope),
        current_month_new_customers=repository.count_my_new_customers(
            db, scope=scope, start_at=month_start, end_at=month_end
        ),
        current_month_follow_up_count=repository.count_my_follow_ups(
            db, scope=scope, start_at=month_start, end_at=month_end
        ),
        today_pending_reminder_count=repository.count_personal_reminders(
            db, user_id=actor.id, start_at=_at_start_of_day(today), end_at=today_end
        ),
        overdue_reminder_count=repository.count_personal_reminders(
            db, user_id=actor.id, before=now
        ),
        recent_follow_ups=[
            _recent_follow_up_response(item)
            for item in repository.list_recent_follow_ups(
                db, scope=scope, limit=RECENT_FOLLOW_UP_LIMIT
            )
        ],
    )

    management = DashboardManagementStats(
        customer_total=repository.count_customers(db, scope=scope),
        department_customer_counts=[
            DashboardDepartmentCount(
                department_id=department_id,
                department_name=name,
                count=count,
            )
            for department_id, name, count in repository.list_department_customer_counts(
                db, scope=scope
            )
        ],
        employee_customer_counts=[
            DashboardEmployeeCount(
                user_id=user_id,
                user_name=name,
                department_id=department_id,
                count=count,
            )
            for user_id, name, department_id, count in repository.list_employee_customer_counts(
                db, scope=scope
            )
        ],
        customer_source_distribution=[
            DashboardSourceCount(source=source, count=count)
            for source, count in repository.list_customer_source_distribution(db, scope=scope)
        ],
        customer_level_distribution=[
            DashboardLevelCount(level=level, count=count)
            for level, count in repository.list_customer_level_distribution(db, scope=scope)
        ],
        customer_new_trend=_fill_trend(
            resolved_start,
            resolved_end,
            repository.list_customer_new_trend(
                db, scope=scope, start_at=range_start, end_at=range_end
            ),
        ),
        follow_up_trend=_fill_trend(
            resolved_start,
            resolved_end,
            repository.list_follow_up_trend(
                db, scope=scope, start_at=range_start, end_at=range_end
            ),
        ),
    )
    return DashboardSummaryResponse(
        personal=personal,
        management=management,
        range=DashboardRange(start_date=resolved_start, end_date=resolved_end),
    )


def _resolve_range(*, start_date: date, end_date: date) -> tuple[date, date]:
    if start_date > end_date:
        raise AppException("VALIDATION_ERROR", "统计开始日期不能晚于结束日期", status_code=400)
    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise AppException(
            "VALIDATION_ERROR",
            f"统计时间范围不能超过 {MAX_RANGE_DAYS} 天",
            status_code=400,
        )
    return start_date, end_date


def _at_start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _fill_trend(
    start_date: date, end_date: date, rows: list[tuple[Any, int]]
) -> list[DashboardTrendPoint]:
    counts = {_normalize_day(day): count for day, count in rows}
    current = start_date
    result: list[DashboardTrendPoint] = []
    while current <= end_date:
        result.append(DashboardTrendPoint(date=current, count=counts.get(current, 0)))
        current += timedelta(days=1)
    return result


def _normalize_day(value: Any) -> date:
    if isinstance(value, datetime):
        return value.astimezone(UTC).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _recent_follow_up_response(value: dict[str, Any]) -> DashboardFollowUp:
    followed_at = value["followed_at"]
    if isinstance(followed_at, datetime):
        followed_at = followed_at.replace(tzinfo=UTC) if followed_at.tzinfo is None else followed_at
    return DashboardFollowUp(
        id=value["id"],
        customer_id=value["customer_id"],
        customer_name=value["customer_name"],
        user_id=value["user_id"],
        user_name=value["user_name"],
        method=value["method"],
        content=value["content"],
        followed_at=followed_at,
        result=value["result"],
    )
