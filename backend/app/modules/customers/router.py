from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.customers.schema import (
    CustomerAssign,
    CustomerAssigneeResponse,
    CustomerCreate,
    CustomerDetailResponse,
    CustomerListFilters,
    CustomerNameCheckResponse,
    CustomerResponse,
    CustomerTransfer,
    CustomerUpdate,
)
from app.modules.customers.service import (
    assign_customer,
    check_customer_name,
    create_customer,
    customer_response,
    get_customer_detail_for_actor,
    list_assignable_users_for_actor,
    list_customers_for_actor,
    soft_delete_customer,
    transfer_customer,
    update_customer,
)
from app.modules.roles.dependencies import require_permission

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "",
    summary="List customers",
    description=(
        "Permission: customers:read. Results and total are filtered by the actor's data scope."
    ),
    response_model=ApiSuccess[PageData[CustomerResponse]],
)
def get_customers(
    request: Request,
    search: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=80),
    industry: str | None = Query(default=None, max_length=100),
    level: str | None = Query(default=None, pattern="^[ABCD]$"),
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    owner_id: str | None = None,
    department_id: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort_by: str = Query(
        default="created_at",
        pattern="^(created_at|updated_at|customer_no|name|level|status)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:read")),
):
    filters = CustomerListFilters(
        search=search,
        source=source,
        industry=industry,
        level=level,
        status=status,
        owner_id=owner_id,
        department_id=department_id,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items, total = list_customers_for_actor(
        db,
        actor=actor,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {"items": [customer_response(db, customer) for customer in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@router.get(
    "/name-check",
    summary="Check for visible customers with the same name",
    description=(
        "Permission: customers:read. Checks only non-deleted customers visible to the actor."
    ),
    response_model=ApiSuccess[CustomerNameCheckResponse],
)
def get_customer_name_check(
    request: Request,
    name: str = Query(min_length=1, max_length=200),
    exclude_id: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:read")),
):
    result = check_customer_name(db, actor=actor, name=name, exclude_id=exclude_id)
    return success_response(result, request.state.request_id)


@router.get(
    "/assignees",
    summary="List eligible customer owners",
    description=(
        "Permission: customers:assign. Returns active users in the actor's department scope."
    ),
    response_model=ApiSuccess[list[CustomerAssigneeResponse]],
)
def get_customer_assignees(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:assign")),
):
    users = list_assignable_users_for_actor(db, actor=actor)
    items = [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "department_id": user.department_id,
            "department_name": user.department.name,
        }
        for user in users
    ]
    return success_response(items, request.state.request_id)


@router.post(
    "",
    summary="Create customer",
    description=(
        "Permission: customers:create. A caller may choose another owner only with "
        "customers:assign."
    ),
    response_model=ApiSuccess[CustomerResponse],
    status_code=201,
)
def post_customer(
    payload: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:create")),
):
    customer = create_customer(
        db,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(
        customer_response(db, customer), request.state.request_id, status_code=201
    )


@router.get(
    "/{customer_id}",
    summary="Get customer detail",
    description=(
        "Permission: customers:read. An out-of-scope customer is returned as RESOURCE_NOT_FOUND."
    ),
    response_model=ApiSuccess[CustomerDetailResponse],
)
def get_customer(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:read")),
):
    return success_response(
        get_customer_detail_for_actor(db, actor=actor, customer_id=customer_id),
        request.state.request_id,
    )


@router.patch(
    "/{customer_id}",
    summary="Update customer",
    description=(
        "Permission: customers:update. The scoped customer query also protects ID-based access."
    ),
    response_model=ApiSuccess[CustomerResponse],
)
def patch_customer(
    customer_id: str,
    payload: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:update")),
):
    customer = update_customer(
        db,
        customer_id=customer_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(customer_response(db, customer), request.state.request_id)


@router.delete(
    "/{customer_id}",
    summary="Soft-delete customer",
    description=(
        "Permission: customers:delete. The customer is retained and hidden from normal queries."
    ),
    response_model=ApiSuccess[dict],
)
def delete_customer(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:delete")),
):
    soft_delete_customer(
        db,
        customer_id=customer_id,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response({"status": "deleted"}, request.state.request_id)


@router.post(
    "/{customer_id}/assign",
    summary="Assign customer owner",
    description=(
        "Permission: customers:assign. The owner and department change is stored in history "
        "and audit logs."
    ),
    response_model=ApiSuccess[CustomerDetailResponse],
)
def post_customer_assignment(
    customer_id: str,
    payload: CustomerAssign,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:assign")),
):
    assign_customer(
        db,
        customer_id=customer_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(
        get_customer_detail_for_actor(db, actor=actor, customer_id=customer_id),
        request.state.request_id,
    )


@router.post(
    "/{customer_id}/transfer",
    summary="Transfer customer owner",
    description=(
        "Permission: customers:transfer. A reason, ownership history, and audit log are required."
    ),
    response_model=ApiSuccess[CustomerDetailResponse],
)
def post_customer_transfer(
    customer_id: str,
    payload: CustomerTransfer,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:transfer")),
):
    transfer_customer(
        db,
        customer_id=customer_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return success_response(
        get_customer_detail_for_actor(db, actor=actor, customer_id=customer_id),
        request.state.request_id,
    )
