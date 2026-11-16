from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess, PageData
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.contacts.schema import ContactCreate, ContactResponse, ContactUpdate
from app.modules.contacts.service import (
    contact_response,
    create_contact,
    delete_contact,
    get_contact_for_actor,
    list_contacts_for_actor,
    set_primary_contact,
    update_contact,
)
from app.modules.roles.dependencies import require_permission

router = APIRouter(prefix="/customers/{customer_id}/contacts", tags=["contacts"])


@router.get(
    "",
    summary="List customer contacts",
    description=(
        "Permission: contacts:read. The parent customer is resolved through the actor's data scope."
    ),
    response_model=ApiSuccess[PageData[ContactResponse]],
)
def get_contacts(
    customer_id: str,
    request: Request,
    search: str | None = Query(default=None, max_length=200),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:read")),
):
    items, total = list_contacts_for_actor(
        db,
        actor=actor,
        customer_id=customer_id,
        search=search,
        page=page,
        page_size=page_size,
        sort_order=sort_order,
    )
    return success_response(
        {"items": [contact_response(item) for item in items], "total": total},
        request.state.request_id,
        meta={
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@router.post(
    "",
    summary="Create customer contact",
    description="Permission: contacts:create. The contact is created only for a visible customer.",
    response_model=ApiSuccess[ContactResponse],
    status_code=201,
)
def post_contact(
    customer_id: str,
    payload: ContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:create")),
):
    contact = create_contact(
        db,
        actor=actor,
        customer_id=customer_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(contact_response(contact), request.state.request_id, status_code=201)


@router.get(
    "/{contact_id}",
    summary="Get customer contact",
    description="Permission: contacts:read. An out-of-scope customer or contact returns 404.",
    response_model=ApiSuccess[ContactResponse],
)
def get_contact(
    customer_id: str,
    contact_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:read")),
):
    contact = get_contact_for_actor(db, actor=actor, customer_id=customer_id, contact_id=contact_id)
    return success_response(contact_response(contact), request.state.request_id)


@router.patch(
    "/{contact_id}",
    summary="Update customer contact",
    description="Permission: contacts:update. The contact remains under its original customer.",
    response_model=ApiSuccess[ContactResponse],
)
def patch_contact(
    customer_id: str,
    contact_id: str,
    payload: ContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:update")),
):
    contact = update_contact(
        db,
        actor=actor,
        customer_id=customer_id,
        contact_id=contact_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(contact_response(contact), request.state.request_id)


@router.delete(
    "/{contact_id}",
    summary="Soft-delete customer contact",
    description="Permission: contacts:delete. Contact history remains stored but hidden.",
    response_model=ApiSuccess[dict],
)
def remove_contact(
    customer_id: str,
    contact_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:delete")),
):
    delete_contact(
        db,
        actor=actor,
        customer_id=customer_id,
        contact_id=contact_id,
        request_id=request.state.request_id,
    )
    return success_response({"status": "deleted"}, request.state.request_id)


@router.post(
    "/{contact_id}/primary",
    summary="Set primary customer contact",
    description=(
        "Permission: contacts:set_primary. Setting one contact primary automatically demotes "
        "the previous primary contact."
    ),
    response_model=ApiSuccess[ContactResponse],
)
def make_primary_contact(
    customer_id: str,
    contact_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("contacts:set_primary")),
):
    contact = set_primary_contact(
        db,
        actor=actor,
        customer_id=customer_id,
        contact_id=contact_id,
        request_id=request.state.request_id,
    )
    return success_response(contact_response(contact), request.state.request_id)
