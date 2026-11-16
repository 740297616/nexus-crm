from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.common.data_scope import DataScope, DataScopeContext, data_scope_service
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.contacts.repository import get_contact
from app.modules.customers.service import get_customer_for_actor
from app.modules.followups.model import FollowUpRecord, Reminder
from app.modules.followups.repository import (
    add_follow_up_record,
    add_reminder,
    get_follow_up_by_id,
    get_follow_up_record,
    get_reminder,
    list_follow_up_records,
    list_reminders,
)
from app.modules.followups.schema import (
    FollowUpCreate,
    FollowUpListFilters,
    FollowUpUpdate,
    ReminderCreate,
    ReminderListFilters,
    ReminderUpdate,
)


def _scope(db: Session, actor: User) -> DataScopeContext:
    return data_scope_service.resolve(db, actor)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            "CONFLICT", "跟进或提醒数据发生并发冲突，请刷新后重试", status_code=409
        ) from exc


def _validate_follow_up_times(followed_at: datetime, next_follow_up_at: datetime | None) -> None:
    if next_follow_up_at is not None and next_follow_up_at < followed_at:
        raise AppException(
            "BUSINESS_RULE_VIOLATION", "下次跟进时间不能早于跟进时间", status_code=422
        )


def _validate_contact(db: Session, *, customer_id: str, contact_id: str | None):
    if contact_id is None:
        return None
    contact = get_contact(db, customer_id=customer_id, contact_id=contact_id)
    if contact is None:
        raise AppException("RESOURCE_NOT_FOUND", "联系人不存在或不属于当前客户", status_code=404)
    return contact


def list_follow_ups_for_actor(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    filters: FollowUpListFilters,
    page: int,
    page_size: int,
) -> tuple[list[FollowUpRecord], int]:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    normalized_from = _utc(filters.from_at) if filters.from_at else None
    normalized_to = _utc(filters.to_at) if filters.to_at else None
    if normalized_from and normalized_to and normalized_from > normalized_to:
        raise AppException("VALIDATION_ERROR", "时间范围无效", status_code=400)
    return list_follow_up_records(
        db,
        customer_id=customer_id,
        search=filters.search,
        method=filters.method,
        from_at=normalized_from,
        to_at=normalized_to,
        offset=(page - 1) * page_size,
        limit=page_size,
        sort_order=filters.sort_order,
    )


def get_follow_up_for_actor(
    db: Session, *, actor: User, customer_id: str, record_id: str
) -> FollowUpRecord:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    record = get_follow_up_record(db, customer_id=customer_id, record_id=record_id)
    if record is None:
        raise AppException("RESOURCE_NOT_FOUND", "跟进记录不存在", status_code=404)
    return record


def create_follow_up(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    payload: FollowUpCreate,
    request_id: str,
) -> FollowUpRecord:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = _validate_contact(db, customer_id=customer_id, contact_id=payload.contact_id)
    followed_at = _utc(payload.followed_at)
    next_follow_up_at = _utc(payload.next_follow_up_at) if payload.next_follow_up_at else None
    _validate_follow_up_times(followed_at, next_follow_up_at)
    record = FollowUpRecord(
        id=str(uuid4()),
        customer_id=customer_id,
        contact_id=contact.id if contact else None,
        user_id=actor.id,
        followed_at=followed_at,
        method=payload.method,
        content=payload.content,
        result=payload.result,
        next_follow_up_at=next_follow_up_at,
    )
    add_follow_up_record(db, record)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="follow_up_created",
        resource_type="follow_up_record",
        resource_id=record.id,
        request_id=request_id,
        after_data=_follow_up_audit_data(record),
    )
    _commit(db)
    return get_follow_up_record(db, customer_id=customer_id, record_id=record.id) or record


def update_follow_up(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    record_id: str,
    payload: FollowUpUpdate,
    request_id: str,
) -> FollowUpRecord:
    scope = _scope(db, actor)
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    record = get_follow_up_record(db, customer_id=customer_id, record_id=record_id, for_update=True)
    if record is None:
        raise AppException("RESOURCE_NOT_FOUND", "跟进记录不存在", status_code=404)
    if record.user_id != actor.id and scope.scope is DataScope.SELF:
        raise AppException("DATA_SCOPE_DENIED", "普通员工只能修改本人跟进记录", status_code=403)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return record
    if "contact_id" in updates:
        contact = _validate_contact(db, customer_id=customer_id, contact_id=updates["contact_id"])
        updates["contact_id"] = contact.id if contact else None
    for field in ("followed_at", "next_follow_up_at"):
        if field in updates and updates[field] is not None:
            updates[field] = _utc(updates[field])
    followed_at = updates.get("followed_at", record.followed_at)
    next_follow_up_at = updates.get("next_follow_up_at", record.next_follow_up_at)
    _validate_follow_up_times(
        _utc(followed_at), _utc(next_follow_up_at) if next_follow_up_at else None
    )
    before = _follow_up_audit_data(record)
    for key, value in updates.items():
        setattr(record, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="follow_up_updated",
        resource_type="follow_up_record",
        resource_id=record.id,
        request_id=request_id,
        before_data=before,
        after_data=_follow_up_audit_data(record),
    )
    _commit(db)
    return get_follow_up_record(db, customer_id=customer_id, record_id=record.id) or record


def list_reminders_for_actor(
    db: Session,
    *,
    actor: User,
    filters: ReminderListFilters,
    page: int,
    page_size: int,
    due: bool = False,
    overdue: bool = False,
    mine_only: bool = False,
) -> tuple[list[Reminder], int]:
    now = datetime.now(UTC)
    return list_reminders(
        db,
        scope=_scope(db, actor),
        status=filters.status,
        customer_id=filters.customer_id,
        user_id=actor.id if mine_only else None,
        due_before=now if due or overdue else None,
        overdue_only=overdue,
        offset=(page - 1) * page_size,
        limit=page_size,
        sort_order=filters.sort_order,
    )


def get_reminder_for_actor(
    db: Session, *, actor: User, reminder_id: str, for_update: bool = False
) -> Reminder:
    reminder = get_reminder(
        db, reminder_id=reminder_id, scope=_scope(db, actor), for_update=for_update
    )
    if reminder is None:
        raise AppException("RESOURCE_NOT_FOUND", "提醒不存在", status_code=404)
    return reminder


def _resolve_reminder_links(
    db: Session,
    *,
    actor: User,
    customer_id: str | None,
    follow_up_record_id: str | None,
) -> tuple[str | None, str | None]:
    follow_up = None
    if follow_up_record_id is not None:
        follow_up = get_follow_up_by_id(db, follow_up_record_id)
        if follow_up is None:
            raise AppException("RESOURCE_NOT_FOUND", "关联跟进记录不存在", status_code=404)
        get_customer_for_actor(db, actor=actor, customer_id=follow_up.customer_id)
        if customer_id is not None and customer_id != follow_up.customer_id:
            raise AppException(
                "BUSINESS_RULE_VIOLATION", "提醒关联的客户与跟进记录不一致", status_code=422
            )
        customer_id = follow_up.customer_id
    elif customer_id is not None:
        get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    return customer_id, follow_up_record_id


def create_reminder(
    db: Session,
    *,
    actor: User,
    payload: ReminderCreate,
    request_id: str,
) -> Reminder:
    customer_id, follow_up_record_id = _resolve_reminder_links(
        db,
        actor=actor,
        customer_id=payload.customer_id,
        follow_up_record_id=payload.follow_up_record_id,
    )
    reminder = Reminder(
        id=str(uuid4()),
        user_id=actor.id,
        customer_id=customer_id,
        follow_up_record_id=follow_up_record_id,
        title=payload.title,
        content=payload.content,
        remind_at=_utc(payload.remind_at),
        created_by=actor.id,
    )
    add_reminder(db, reminder)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="reminder_created",
        resource_type="reminder",
        resource_id=reminder.id,
        request_id=request_id,
        after_data=_reminder_audit_data(reminder),
    )
    _commit(db)
    return get_reminder_for_actor(db, actor=actor, reminder_id=reminder.id)


def update_reminder(
    db: Session,
    *,
    actor: User,
    reminder_id: str,
    payload: ReminderUpdate,
    request_id: str,
) -> Reminder:
    reminder = get_reminder_for_actor(db, actor=actor, reminder_id=reminder_id, for_update=True)
    if reminder.status != "pending":
        raise AppException("BUSINESS_RULE_VIOLATION", "只有待处理提醒可以编辑", status_code=422)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return reminder
    customer_id = updates.get("customer_id", reminder.customer_id)
    follow_up_record_id = updates.get("follow_up_record_id", reminder.follow_up_record_id)
    customer_id, follow_up_record_id = _resolve_reminder_links(
        db,
        actor=actor,
        customer_id=customer_id,
        follow_up_record_id=follow_up_record_id,
    )
    updates["customer_id"] = customer_id
    updates["follow_up_record_id"] = follow_up_record_id
    if "remind_at" in updates and updates["remind_at"] is not None:
        updates["remind_at"] = _utc(updates["remind_at"])
    before = _reminder_audit_data(reminder)
    for key, value in updates.items():
        setattr(reminder, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="reminder_updated",
        resource_type="reminder",
        resource_id=reminder.id,
        request_id=request_id,
        before_data=before,
        after_data=_reminder_audit_data(reminder),
    )
    _commit(db)
    return get_reminder_for_actor(db, actor=actor, reminder_id=reminder.id)


def complete_reminder(db: Session, *, actor: User, reminder_id: str, request_id: str) -> Reminder:
    return _change_reminder_status(
        db, actor=actor, reminder_id=reminder_id, status="completed", request_id=request_id
    )


def cancel_reminder(db: Session, *, actor: User, reminder_id: str, request_id: str) -> Reminder:
    return _change_reminder_status(
        db, actor=actor, reminder_id=reminder_id, status="cancelled", request_id=request_id
    )


def _change_reminder_status(
    db: Session,
    *,
    actor: User,
    reminder_id: str,
    status: str,
    request_id: str,
) -> Reminder:
    reminder = get_reminder_for_actor(db, actor=actor, reminder_id=reminder_id, for_update=True)
    if reminder.status != "pending":
        raise AppException(
            "BUSINESS_RULE_VIOLATION", "提醒已经处理，不能重复变更状态", status_code=422
        )
    now = datetime.now(UTC)
    before = _reminder_audit_data(reminder)
    reminder.status = status
    if status == "completed":
        reminder.completed_at = now
    else:
        reminder.cancelled_at = now
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"reminder_{status}",
        resource_type="reminder",
        resource_id=reminder.id,
        request_id=request_id,
        before_data=before,
        after_data=_reminder_audit_data(reminder),
    )
    _commit(db)
    return get_reminder_for_actor(db, actor=actor, reminder_id=reminder.id)


def follow_up_response(record: FollowUpRecord) -> dict:
    return {
        "id": record.id,
        "customer_id": record.customer_id,
        "contact_id": record.contact_id,
        "contact_name": record.contact.name if record.contact else None,
        "user_id": record.user_id,
        "user_name": record.user.display_name,
        "method": record.method,
        "content": record.content,
        "followed_at": record.followed_at,
        "result": record.result,
        "next_follow_up_at": record.next_follow_up_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def reminder_response(reminder: Reminder) -> dict:
    now = datetime.now(UTC)
    remind_at = _utc(reminder.remind_at)
    return {
        "id": reminder.id,
        "user_id": reminder.user_id,
        "user_name": reminder.user.display_name,
        "customer_id": reminder.customer_id,
        "customer_name": reminder.customer.name if reminder.customer else None,
        "follow_up_record_id": reminder.follow_up_record_id,
        "title": reminder.title,
        "content": reminder.content,
        "remind_at": remind_at,
        "status": reminder.status,
        "completed_at": reminder.completed_at,
        "cancelled_at": reminder.cancelled_at,
        "created_by": reminder.created_by,
        "created_by_name": reminder.creator.display_name,
        "created_at": reminder.created_at,
        "updated_at": reminder.updated_at,
        "is_overdue": reminder.status == "pending" and remind_at < now,
    }


def _follow_up_audit_data(value: FollowUpRecord | dict) -> dict:
    fields = {
        "customer_id",
        "contact_id",
        "user_id",
        "followed_at",
        "method",
        "content",
        "result",
        "next_follow_up_at",
    }
    if isinstance(value, FollowUpRecord):
        values = {field: getattr(value, field) for field in fields}
    else:
        values = {field: value.get(field) for field in fields if field in value}
    return {
        key: val.isoformat() if isinstance(val, datetime) else val for key, val in values.items()
    }


def _reminder_audit_data(value: Reminder | dict) -> dict:
    fields = {
        "user_id",
        "customer_id",
        "follow_up_record_id",
        "title",
        "content",
        "remind_at",
        "status",
        "completed_at",
        "cancelled_at",
    }
    if isinstance(value, Reminder):
        values = {field: getattr(value, field) for field in fields}
    else:
        values = {field: value.get(field) for field in fields if field in value}
    return {
        key: val.isoformat() if isinstance(val, datetime) else val for key, val in values.items()
    }
