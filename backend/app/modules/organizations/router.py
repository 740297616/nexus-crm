from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.organizations.repository import department_user_count
from app.modules.organizations.schema import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.modules.organizations.service import (
    create_department,
    delete_department,
    list_visible_departments,
    update_department,
)
from app.modules.roles.dependencies import require_permission

router = APIRouter(prefix="/departments", tags=["departments"])


def _tree(items: list, db: Session) -> list[dict]:
    nodes: dict[str, dict] = {
        item.id: {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "user_count": department_user_count(db, item.id),
            "children": [],
        }
        for item in items
    }
    roots: list[dict] = []
    for item in items:
        node = nodes[item.id]
        if item.parent_id in nodes:
            nodes[item.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return [DepartmentResponse.model_validate(root).model_dump(mode="json") for root in roots]


@router.get("", summary="List departments", response_model=ApiSuccess[PageData[DepartmentResponse]])
def get_departments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("departments:read")),
):
    items = list_visible_departments(db, current_user)
    return success_response(
        {"items": _tree(items, db), "total": len(items)}, request.state.request_id
    )


@router.post("", summary="Create department", response_model=ApiSuccess[DepartmentResponse])
def post_department(
    payload: DepartmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("departments:create")),
):
    department = create_department(
        db, payload=payload, actor=actor, request_id=request.state.request_id
    )
    response = DepartmentResponse.model_validate(department).model_dump(mode="json")
    response["user_count"] = 0
    return success_response(response, request.state.request_id, status_code=201)


@router.patch(
    "/{department_id}", summary="Update department", response_model=ApiSuccess[DepartmentResponse]
)
def patch_department(
    department_id: str,
    payload: DepartmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("departments:update")),
):
    department = update_department(
        db,
        department_id=department_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    response = DepartmentResponse.model_validate(department).model_dump(mode="json")
    response["user_count"] = department_user_count(db, department.id)
    return success_response(response, request.state.request_id)


@router.delete(
    "/{department_id}", summary="Delete empty department", response_model=ApiSuccess[dict]
)
def remove_department(
    department_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("departments:delete")),
):
    delete_department(
        db, department_id=department_id, actor=actor, request_id=request.state.request_id
    )
    return success_response({"status": "deleted"}, request.state.request_id)
