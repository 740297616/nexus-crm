from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.roles.dependencies import require_permission
from app.modules.tags.schema import (
    CustomerTagResponse,
    TagBinding,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.modules.tags.service import (
    bind_tag,
    create_tag,
    customer_tag_response,
    delete_tag,
    list_customer_tags_for_actor,
    list_tags_for_actor,
    tag_response,
    unbind_tag,
    update_tag,
)

router = APIRouter(tags=["tags"])


@router.get(
    "/tags",
    summary="List active customer tags",
    response_model=ApiSuccess[list[TagResponse]],
)
def get_tags(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:read")),
):
    return success_response(
        [tag_response(tag) for tag in list_tags_for_actor(db, actor=actor)],
        request.state.request_id,
    )


@router.post(
    "/tags",
    summary="Create customer tag",
    response_model=ApiSuccess[TagResponse],
    status_code=201,
)
def post_tag(
    payload: TagCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:create")),
):
    tag = create_tag(db, actor=actor, payload=payload, request_id=request.state.request_id)
    return success_response(tag_response(tag), request.state.request_id, status_code=201)


@router.patch(
    "/tags/{tag_id}",
    summary="Update customer tag",
    response_model=ApiSuccess[TagResponse],
)
def patch_tag(
    tag_id: str,
    payload: TagUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:update")),
):
    tag = update_tag(
        db, actor=actor, tag_id=tag_id, payload=payload, request_id=request.state.request_id
    )
    return success_response(tag_response(tag), request.state.request_id)


@router.delete(
    "/tags/{tag_id}",
    summary="Soft-delete customer tag",
    response_model=ApiSuccess[dict],
)
def remove_tag(
    tag_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:delete")),
):
    delete_tag(db, actor=actor, tag_id=tag_id, request_id=request.state.request_id)
    return success_response({"status": "deleted"}, request.state.request_id)


@router.get(
    "/customers/{customer_id}/tags",
    summary="List tags bound to a customer",
    response_model=ApiSuccess[list[CustomerTagResponse]],
)
def get_customer_tags(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:read")),
):
    relations = list_customer_tags_for_actor(db, actor=actor, customer_id=customer_id)
    return success_response(
        [customer_tag_response(relation) for relation in relations], request.state.request_id
    )


@router.post(
    "/customers/{customer_id}/tags",
    summary="Bind a tag to a customer",
    response_model=ApiSuccess[CustomerTagResponse],
    status_code=201,
)
def post_customer_tag(
    customer_id: str,
    payload: TagBinding,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:bind")),
):
    relation = bind_tag(
        db,
        actor=actor,
        customer_id=customer_id,
        payload=payload,
        request_id=request.state.request_id,
    )
    return success_response(
        customer_tag_response(relation), request.state.request_id, status_code=201
    )


@router.delete(
    "/customers/{customer_id}/tags/{tag_id}",
    summary="Unbind a tag from a customer",
    response_model=ApiSuccess[dict],
)
def delete_customer_tag(
    customer_id: str,
    tag_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tags:unbind")),
):
    unbind_tag(
        db,
        actor=actor,
        customer_id=customer_id,
        tag_id=tag_id,
        request_id=request.state.request_id,
    )
    return success_response({"status": "unbound"}, request.state.request_id)
