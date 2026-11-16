from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.data_scope import DataScopeContext, data_scope_service
from app.modules.auth.model import User
from app.modules.customers.model import Customer
from app.modules.followups.model import FollowUpRecord, Reminder
from app.modules.organizations.model import Department


def count_my_customers(db: Session, *, scope: DataScopeContext) -> int:
    statement = select(func.count(Customer.id)).where(
        Customer.owner_id == scope.user_id,
        *_customer_scope_conditions(scope),
    )
    return int(db.scalar(statement) or 0)


def count_my_new_customers(
    db: Session,
    *,
    scope: DataScopeContext,
    start_at: datetime,
    end_at: datetime,
) -> int:
    statement = select(func.count(Customer.id)).where(
        Customer.owner_id == scope.user_id,
        Customer.created_at >= start_at,
        Customer.created_at < end_at,
        *_customer_scope_conditions(scope),
    )
    return int(db.scalar(statement) or 0)


def count_my_follow_ups(
    db: Session,
    *,
    scope: DataScopeContext,
    start_at: datetime,
    end_at: datetime,
) -> int:
    statement = (
        select(func.count(FollowUpRecord.id))
        .select_from(FollowUpRecord)
        .join(Customer, Customer.id == FollowUpRecord.customer_id)
        .where(
            FollowUpRecord.user_id == scope.user_id,
            FollowUpRecord.followed_at >= start_at,
            FollowUpRecord.followed_at < end_at,
            *_customer_scope_conditions(scope),
        )
    )
    return int(db.scalar(statement) or 0)


def count_personal_reminders(
    db: Session,
    *,
    user_id: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    before: datetime | None = None,
) -> int:
    conditions: list[Any] = [Reminder.user_id == user_id, Reminder.status == "pending"]
    if start_at is not None:
        conditions.append(Reminder.remind_at >= start_at)
    if end_at is not None:
        conditions.append(Reminder.remind_at < end_at)
    if before is not None:
        conditions.append(Reminder.remind_at < before)
    return int(db.scalar(select(func.count(Reminder.id)).where(*conditions)) or 0)


def list_recent_follow_ups(
    db: Session,
    *,
    scope: DataScopeContext,
    limit: int = 10,
) -> list[dict[str, Any]]:
    statement = (
        select(
            FollowUpRecord.id,
            FollowUpRecord.customer_id,
            Customer.name.label("customer_name"),
            FollowUpRecord.user_id,
            User.display_name.label("user_name"),
            FollowUpRecord.method,
            FollowUpRecord.content,
            FollowUpRecord.followed_at,
            FollowUpRecord.result,
        )
        .select_from(FollowUpRecord)
        .join(Customer, Customer.id == FollowUpRecord.customer_id)
        .join(User, User.id == FollowUpRecord.user_id)
        .where(*_customer_scope_conditions(scope))
        .order_by(FollowUpRecord.followed_at.desc(), FollowUpRecord.id.desc())
        .limit(limit)
    )
    return [dict(row._mapping) for row in db.execute(statement).all()]


def count_customers(db: Session, *, scope: DataScopeContext) -> int:
    statement = select(func.count(Customer.id)).where(*_customer_scope_conditions(scope))
    return int(db.scalar(statement) or 0)


def list_department_customer_counts(
    db: Session, *, scope: DataScopeContext
) -> list[tuple[str, str, int]]:
    statement = (
        select(Department.id, Department.name, func.count(Customer.id))
        .select_from(Customer)
        .join(Department, Department.id == Customer.department_id)
        .where(*_customer_scope_conditions(scope))
        .group_by(Department.id, Department.name)
        .order_by(Department.name, Department.id)
    )
    return [
        (department_id, name, int(count)) for department_id, name, count in db.execute(statement)
    ]


def list_employee_customer_counts(
    db: Session, *, scope: DataScopeContext
) -> list[tuple[str, str, str | None, int]]:
    statement = (
        select(User.id, User.display_name, User.department_id, func.count(Customer.id))
        .select_from(Customer)
        .join(User, User.id == Customer.owner_id)
        .where(*_customer_scope_conditions(scope))
        .group_by(User.id, User.display_name, User.department_id)
        .order_by(User.display_name, User.id)
    )
    return [
        (user_id, name, department_id, int(count))
        for user_id, name, department_id, count in db.execute(statement)
    ]


def list_customer_source_distribution(
    db: Session, *, scope: DataScopeContext
) -> list[tuple[str | None, int]]:
    statement = (
        select(Customer.source, func.count(Customer.id))
        .where(*_customer_scope_conditions(scope))
        .group_by(Customer.source)
        .order_by(Customer.source)
    )
    return [(source, int(count)) for source, count in db.execute(statement)]


def list_customer_level_distribution(
    db: Session, *, scope: DataScopeContext
) -> list[tuple[str, int]]:
    statement = (
        select(Customer.level, func.count(Customer.id))
        .where(*_customer_scope_conditions(scope))
        .group_by(Customer.level)
        .order_by(Customer.level)
    )
    return [(level, int(count)) for level, count in db.execute(statement)]


def list_customer_new_trend(
    db: Session,
    *,
    scope: DataScopeContext,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[Any, int]]:
    bucket = _day_bucket(db, Customer.created_at)
    statement = (
        select(bucket.label("day"), func.count(Customer.id))
        .where(
            Customer.created_at >= start_at,
            Customer.created_at < end_at,
            *_customer_scope_conditions(scope),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    return [(day, int(count)) for day, count in db.execute(statement)]


def list_follow_up_trend(
    db: Session,
    *,
    scope: DataScopeContext,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[Any, int]]:
    bucket = _day_bucket(db, FollowUpRecord.followed_at)
    statement = (
        select(bucket.label("day"), func.count(FollowUpRecord.id))
        .select_from(FollowUpRecord)
        .join(Customer, Customer.id == FollowUpRecord.customer_id)
        .where(
            FollowUpRecord.followed_at >= start_at,
            FollowUpRecord.followed_at < end_at,
            *_customer_scope_conditions(scope),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    return [(day, int(count)) for day, count in db.execute(statement)]


def _customer_scope_conditions(scope: DataScopeContext) -> list[Any]:
    return [
        Customer.deleted_at.is_(None),
        data_scope_service.condition(scope, Customer),
    ]


def _day_bucket(db: Session, column: Any) -> Any:
    """Return a UTC day key without loading rows into Python.

    SQLite stores the test timestamps as ISO strings, while PostgreSQL uses
    timestamptz.  PostgreSQL is explicitly converted to UTC before grouping;
    the SQLite expression keeps the same ISO date prefix used by the test DB.
    """

    dialect_name = db.bind.dialect.name if db.bind is not None else ""
    if dialect_name == "postgresql":
        return func.to_char(column.op("AT TIME ZONE")("UTC"), "YYYY-MM-DD")
    return func.strftime("%Y-%m-%d", column)
