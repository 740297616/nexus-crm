from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.roles.dependencies import require_permission
from app.modules.roles.schema import (
    PermissionResponse,
    RoleCreate,
    RolePermissionsUpdate,
    RoleResponse,
    RoleUpdate,
)
from app.modules.roles.service import (
    create_role,
    delete_role,
    list_permissions,
    list_roles,
    permission_response,
    role_response,
    update_role,
    update_role_permissions,
)

router = APIRouter(tags=["roles"])
roles_router = APIRouter(prefix="/roles")


@roles_router.get("", summary="List roles", response_model=ApiSuccess[PageData[RoleResponse]])
def get_roles(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    items = [role_response(role) for role in list_roles(db)]
    return success_response({"items": items, "total": len(items)}, request.state.request_id)


@roles_router.post("", summary="Create role", response_model=ApiSuccess[RoleResponse])
def post_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("roles:create")),
):
    role = create_role(db, payload=payload, actor=actor, request_id=request.state.request_id)
    return success_response(role_response(role), request.state.request_id, status_code=201)


@roles_router.patch(
    "/{role_id}", summary="Update custom role", response_model=ApiSuccess[RoleResponse]
)
def patch_role(
    role_id: str,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("roles:update")),
):
    role = update_role(
        db,
        role_id=role_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(role_response(role), request.state.request_id)


@roles_router.delete(
    "/{role_id}", summary="Delete unassigned custom role", response_model=ApiSuccess[dict]
)
def remove_role(
    role_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("roles:delete")),
):
    delete_role(db, role_id=role_id, actor=actor, request_id=request.state.request_id)
    return success_response({"status": "deleted"}, request.state.request_id)


@roles_router.put(
    "/{role_id}/permissions",
    summary="Replace role permissions",
    response_model=ApiSuccess[RoleResponse],
)
def put_role_permissions(
    role_id: str,
    payload: RolePermissionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("roles:assign_permissions")),
):
    role = update_role_permissions(
        db,
        role_id=role_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(role_response(role), request.state.request_id)


@router.get(
    "/permissions",
    summary="List permission catalog",
    response_model=ApiSuccess[PageData[PermissionResponse]],
)
def get_permissions(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("permissions:read")),
):
    items = [permission_response(permission) for permission in list_permissions(db)]
    return success_response({"items": items, "total": len(items)}, request.state.request_id)


router.include_router(roles_router)
