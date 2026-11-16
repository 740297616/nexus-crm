from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.followups.schema import (
    FollowUpCreate,
    FollowUpListFilters,
    FollowUpResponse,
    FollowUpUpdate,
    ReminderCreate,
    ReminderListFilters,
    ReminderResponse,
    ReminderUpdate,
)
from app.modules.followups.service import (
    cancel_reminder,
    complete_reminder,
    create_follow_up,
    create_reminder,
    follow_up_response,
    get_follow_up_for_actor,
    get_reminder_for_actor,
    list_follow_ups_for_actor,
    list_reminders_for_actor,
    reminder_response,
    update_follow_up,
    update_reminder,
)
from app.modules.roles.dependencies import require_permission

follow_up_router = APIRouter(prefix="/customers/{customer_id}/follow-ups", tags=["follow-ups"])
reminder_router = APIRouter(prefix="/reminders", tags=["reminders"])


def _follow_up_filters(
    search: str | None = Query(default=None, max_length=200),
    method: str | None = Query(default=None, pattern="^(phone|visit|wechat|email|other)$"),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> FollowUpListFilters:
    return FollowUpListFilters.model_validate(
        {
            "search": search,
            "method": method,
            "from_at": from_at,
            "to_at": to_at,
            "sort_order": sort_order,
        }
    )


@follow_up_router.get(
    "",
    summary="List customer follow-up records",
    description="Permission: follow_ups:read. The parent customer is resolved through data scope.",
    response_model=ApiSuccess[PageData[FollowUpResponse]],
)
def get_follow_ups(
    customer_id: str,
    request: Request,
    filters: FollowUpListFilters = Depends(_follow_up_filters),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("follow_ups:read")),
):
    items, total = list_follow_ups_for_actor(
        db,
        actor=actor,
        customer_id=customer_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {"items": [follow_up_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@follow_up_router.post(
    "",
    summary="Create customer follow-up record",
    description=(
        "Permission: follow_ups:create. The authenticated user is recorded as the follow-up owner."
    ),
    response_model=ApiSuccess[FollowUpResponse],
    status_code=201,
)
def post_follow_up(
    customer_id: str,
    payload: FollowUpCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("follow_ups:create")),
):
    record = create_follow_up(
        db,
        actor=actor,
        customer_id=customer_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(follow_up_response(record), request.state.request_id, status_code=201)


@follow_up_router.get(
    "/{record_id}",
    summary="Get customer follow-up record",
    description="Permission: follow_ups:read. Out-of-scope records return 404.",
    response_model=ApiSuccess[FollowUpResponse],
)
def get_follow_up(
    customer_id: str,
    record_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("follow_ups:read")),
):
    record = get_follow_up_for_actor(db, actor=actor, customer_id=customer_id, record_id=record_id)
    return success_response(follow_up_response(record), request.state.request_id)


@follow_up_router.patch(
    "/{record_id}",
    summary="Update customer follow-up record",
    description=(
        "Permission: follow_ups:update. Self-scope users may update only their own records."
    ),
    response_model=ApiSuccess[FollowUpResponse],
)
def patch_follow_up(
    customer_id: str,
    record_id: str,
    payload: FollowUpUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("follow_ups:update")),
):
    record = update_follow_up(
        db,
        actor=actor,
        customer_id=customer_id,
        record_id=record_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(follow_up_response(record), request.state.request_id)


@reminder_router.get(
    "",
    summary="List reminders",
    description="Permission: reminders:read. Results are filtered by the actor's reminder scope.",
    response_model=ApiSuccess[PageData[ReminderResponse]],
)
def get_reminders(
    request: Request,
    status: str | None = Query(default=None, pattern="^(pending|completed|cancelled)$"),
    customer_id: str | None = Query(default=None),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:read")),
):
    filters = ReminderListFilters(status=status, customer_id=customer_id, sort_order=sort_order)
    items, total = list_reminders_for_actor(
        db, actor=actor, filters=filters, page=page, page_size=page_size
    )
    return success_response(
        {"items": [reminder_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@reminder_router.get(
    "/mine",
    summary="List my reminders",
    description="Permission: reminders:read. Returns the authenticated user's personal todo list.",
    response_model=ApiSuccess[PageData[ReminderResponse]],
)
def get_my_reminders(
    request: Request,
    status: str | None = Query(default=None, pattern="^(pending|completed|cancelled)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:read")),
):
    filters = ReminderListFilters(status=status, sort_order=sort_order)
    items, total = list_reminders_for_actor(
        db,
        actor=actor,
        filters=filters,
        page=page,
        page_size=page_size,
        mine_only=True,
    )
    return success_response(
        {"items": [reminder_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@reminder_router.get(
    "/due",
    summary="List due reminders",
    description=(
        "Permission: reminders:read. Returns pending reminders due at or before current UTC time."
    ),
    response_model=ApiSuccess[PageData[ReminderResponse]],
)
def get_due_reminders(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:read")),
):
    filters = ReminderListFilters(status="pending", sort_order="asc")
    items, total = list_reminders_for_actor(
        db, actor=actor, filters=filters, page=page, page_size=page_size, due=True
    )
    return success_response(
        {"items": [reminder_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@reminder_router.get(
    "/overdue",
    summary="List overdue reminders",
    description=(
        "Permission: reminders:read. Returns pending reminders strictly before current UTC time."
    ),
    response_model=ApiSuccess[PageData[ReminderResponse]],
)
def get_overdue_reminders(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:read")),
):
    filters = ReminderListFilters(status="pending", sort_order="asc")
    items, total = list_reminders_for_actor(
        db, actor=actor, filters=filters, page=page, page_size=page_size, overdue=True
    )
    return success_response(
        {"items": [reminder_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@reminder_router.post(
    "",
    summary="Create reminder",
    description="Permission: reminders:create. New reminders belong to the authenticated user.",
    response_model=ApiSuccess[ReminderResponse],
    status_code=201,
)
def post_reminder(
    payload: ReminderCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:create")),
):
    reminder = create_reminder(
        db, actor=actor, payload=payload, request_id=request.state.request_id
    )
    return success_response(reminder_response(reminder), request.state.request_id, status_code=201)


@reminder_router.get(
    "/{reminder_id}",
    summary="Get reminder",
    description="Permission: reminders:read. Out-of-scope reminders return 404.",
    response_model=ApiSuccess[ReminderResponse],
)
def get_one_reminder(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:read")),
):
    reminder = get_reminder_for_actor(db, actor=actor, reminder_id=reminder_id)
    return success_response(reminder_response(reminder), request.state.request_id)


@reminder_router.patch(
    "/{reminder_id}",
    summary="Update reminder",
    description="Permission: reminders:update. Only pending reminders can be edited.",
    response_model=ApiSuccess[ReminderResponse],
)
def patch_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:update")),
):
    reminder = update_reminder(
        db,
        actor=actor,
        reminder_id=reminder_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(reminder_response(reminder), request.state.request_id)


@reminder_router.post(
    "/{reminder_id}/complete",
    summary="Complete reminder",
    description="Permission: reminders:complete. Only pending reminders can be completed.",
    response_model=ApiSuccess[ReminderResponse],
)
def post_complete_reminder(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:complete")),
):
    reminder = complete_reminder(
        db, actor=actor, reminder_id=reminder_id, request_id=request.state.request_id
    )
    return success_response(reminder_response(reminder), request.state.request_id)


@reminder_router.post(
    "/{reminder_id}/cancel",
    summary="Cancel reminder",
    description="Permission: reminders:cancel. Only pending reminders can be cancelled.",
    response_model=ApiSuccess[ReminderResponse],
)
def post_cancel_reminder(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("reminders:cancel")),
):
    reminder = cancel_reminder(
        db, actor=actor, reminder_id=reminder_id, request_id=request.state.request_id
    )
    return success_response(reminder_response(reminder), request.state.request_id)
