from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.common.data_scope import DataScope, DataScopeContext, data_scope_service
from app.modules.auth.model import User
from app.modules.customers.model import Customer
from app.modules.followups.model import FollowUpRecord, Reminder


def list_follow_up_records(
    db: Session,
    *,
    customer_id: str,
    search: str | None,
    method: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    offset: int,
    limit: int,
    sort_order: str,
) -> tuple[list[FollowUpRecord], int]:
    statement = _with_follow_up_details(select(FollowUpRecord)).where(
        FollowUpRecord.customer_id == customer_id
    )
    count_statement = (
        select(func.count())
        .select_from(FollowUpRecord)
        .where(FollowUpRecord.customer_id == customer_id)
    )
    statement, count_statement = _apply_follow_up_filters(
        statement,
        count_statement,
        search=search,
        method=method,
        from_at=from_at,
        to_at=to_at,
    )
    order_column = (
        FollowUpRecord.followed_at.asc()
        if sort_order == "asc"
        else FollowUpRecord.followed_at.desc()
    )
    total = int(db.scalar(count_statement) or 0)
    items = list(
        db.scalars(
            statement.order_by(order_column, FollowUpRecord.id).offset(offset).limit(limit)
        ).all()
    )
    return items, total


def get_follow_up_record(
    db: Session, *, customer_id: str, record_id: str, for_update: bool = False
) -> FollowUpRecord | None:
    statement = _with_follow_up_details(select(FollowUpRecord)).where(
        FollowUpRecord.id == record_id,
        FollowUpRecord.customer_id == customer_id,
    )
    if for_update:
        statement = statement.with_for_update(of=FollowUpRecord)
    return db.scalar(statement)


def get_follow_up_by_id(db: Session, record_id: str) -> FollowUpRecord | None:
    return db.scalar(
        _with_follow_up_details(select(FollowUpRecord)).where(FollowUpRecord.id == record_id)
    )


def add_follow_up_record(db: Session, record: FollowUpRecord) -> None:
    db.add(record)
    db.flush()


def list_reminders(
    db: Session,
    *,
    scope: DataScopeContext,
    status: str | None,
    customer_id: str | None,
    user_id: str | None,
    due_before: datetime | None,
    overdue_only: bool,
    offset: int,
    limit: int,
    sort_order: str,
) -> tuple[list[Reminder], int]:
    statement = _with_reminder_details(select(Reminder))
    count_statement = select(func.count()).select_from(Reminder)
    statement = _apply_reminder_scope(statement, scope)
    count_statement = _apply_reminder_scope(count_statement, scope)
    statement, count_statement = _apply_reminder_filters(
        statement,
        count_statement,
        status=status,
        customer_id=customer_id,
        user_id=user_id,
        due_before=due_before,
        overdue_only=overdue_only,
    )
    order_column = Reminder.remind_at.asc() if sort_order == "asc" else Reminder.remind_at.desc()
    total = int(db.scalar(count_statement) or 0)
    items = list(
        db.scalars(statement.order_by(order_column, Reminder.id).offset(offset).limit(limit)).all()
    )
    return items, total


def get_reminder(
    db: Session,
    *,
    reminder_id: str,
    scope: DataScopeContext,
    for_update: bool = False,
) -> Reminder | None:
    statement = _with_reminder_details(select(Reminder)).where(Reminder.id == reminder_id)
    statement = _apply_reminder_scope(statement, scope)
    if for_update:
        statement = statement.with_for_update(of=Reminder)
    return db.scalar(statement)


def add_reminder(db: Session, reminder: Reminder) -> None:
    db.add(reminder)
    db.flush()


def _with_follow_up_details(statement: Select[Any]) -> Select[Any]:
    return statement.options(
        joinedload(FollowUpRecord.user),
        joinedload(FollowUpRecord.contact),
    )


def _with_reminder_details(statement: Select[Any]) -> Select[Any]:
    return statement.options(
        joinedload(Reminder.user),
        joinedload(Reminder.creator),
        joinedload(Reminder.customer),
    )


def _apply_follow_up_filters(
    statement: Select[Any],
    count_statement: Select[Any],
    *,
    search: str | None,
    method: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[Select[Any], Select[Any]]:
    conditions: list[Any] = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                FollowUpRecord.content.ilike(pattern),
                FollowUpRecord.result.ilike(pattern),
            )
        )
    if method:
        conditions.append(FollowUpRecord.method == method)
    if from_at:
        conditions.append(FollowUpRecord.followed_at >= from_at)
    if to_at:
        conditions.append(FollowUpRecord.followed_at <= to_at)
    for condition in conditions:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    return statement, count_statement


def _apply_reminder_scope(statement: Select[Any], scope: DataScopeContext) -> Select[Any]:
    if scope.scope is DataScope.ALL:
        return statement.outerjoin(Customer, Reminder.customer_id == Customer.id).where(
            or_(Reminder.customer_id.is_(None), Customer.deleted_at.is_(None))
        )
    if scope.scope is DataScope.SELF:
        user_condition = Reminder.user_id == scope.user_id
    elif not scope.department_ids:
        return statement.where(False)
    else:
        statement = statement.join(User, User.id == Reminder.user_id)
        user_condition = User.department_id.in_(scope.department_ids)
    customer_condition = data_scope_service.condition(scope, Customer)
    return statement.outerjoin(Customer, Reminder.customer_id == Customer.id).where(
        user_condition,
        or_(
            Reminder.customer_id.is_(None),
            and_(Customer.deleted_at.is_(None), customer_condition),
        ),
    )


def _apply_reminder_filters(
    statement: Select[Any],
    count_statement: Select[Any],
    *,
    status: str | None,
    customer_id: str | None,
    user_id: str | None,
    due_before: datetime | None,
    overdue_only: bool,
) -> tuple[Select[Any], Select[Any]]:
    conditions: list[Any] = []
    if status:
        conditions.append(Reminder.status == status)
    if customer_id:
        conditions.append(Reminder.customer_id == customer_id)
    if user_id:
        conditions.append(Reminder.user_id == user_id)
    if due_before:
        conditions.append(Reminder.remind_at <= due_before)
    if overdue_only:
        conditions.extend([Reminder.status == "pending", Reminder.remind_at < due_before])
    for condition in conditions:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    return statement, count_statement
