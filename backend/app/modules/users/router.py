from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.roles.dependencies import require_permission
from app.modules.users.schema import (
    UserCreate,
    UserResponse,
    UserRolesUpdate,
    UserStatusUpdate,
    UserUpdate,
)
from app.modules.users.service import (
    create_user,
    get_user_for_actor,
    list_users_for_actor,
    set_user_status,
    update_user,
    update_user_roles,
    user_response,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    summary="List users",
    response_model=ApiSuccess[PageData[UserResponse]],
)
def get_users(
    request: Request,
    search: str | None = Query(default=None, max_length=120),
    department_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:read")),
):
    users, total = list_users_for_actor(
        db,
        actor=actor,
        search=search,
        department_id=department_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {"items": [user_response(db, user) for user in users], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@router.post("", summary="Create user", response_model=ApiSuccess[UserResponse])
def post_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:create")),
):
    user = create_user(db, payload=payload, actor=actor, request_id=request.state.request_id)
    return success_response(user_response(db, user), request.state.request_id, status_code=201)


@router.get("/{user_id}", summary="Get user", response_model=ApiSuccess[UserResponse])
def get_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:read")),
):
    user = get_user_for_actor(db, actor=actor, user_id=user_id)
    return success_response(user_response(db, user), request.state.request_id)


@router.patch("/{user_id}", summary="Update user", response_model=ApiSuccess[UserResponse])
def patch_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:update")),
):
    user = update_user(
        db,
        user_id=user_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(user_response(db, user), request.state.request_id)


@router.patch(
    "/{user_id}/status", summary="Enable or disable user", response_model=ApiSuccess[UserResponse]
)
def patch_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:disable")),
):
    user = set_user_status(
        db,
        user_id=user_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(user_response(db, user), request.state.request_id)


@router.put(
    "/{user_id}/roles", summary="Replace user roles", response_model=ApiSuccess[UserResponse]
)
def put_user_roles(
    user_id: str,
    payload: UserRolesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users:assign_roles")),
):
    user = update_user_roles(
        db,
        user_id=user_id,
        role_ids=payload.role_ids,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(user_response(db, user), request.state.request_id)
