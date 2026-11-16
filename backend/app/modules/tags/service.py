from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.customers.service import get_customer_for_actor
from app.modules.tags.model import CustomerTag, Tag
from app.modules.tags.repository import (
    add_customer_tag,
    add_tag,
    delete_customer_tag,
    get_customer_tag,
    get_tag,
    list_customer_tags,
    list_tags,
    tag_name_exists,
)
from app.modules.tags.schema import TagBinding, TagCreate, TagUpdate


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException("DUPLICATE_RESOURCE", "标签或标签关系已存在", status_code=409) from exc


def list_tags_for_actor(db: Session, *, actor: User) -> list[Tag]:
    return list_tags(db)


def create_tag(db: Session, *, actor: User, payload: TagCreate, request_id: str) -> Tag:
    name_key = payload.name.casefold()
    if tag_name_exists(db, name_key):
        raise AppException("DUPLICATE_RESOURCE", "标签名称已存在", status_code=409)
    tag = Tag(
        id=str(uuid4()),
        name=payload.name,
        name_key=name_key,
        description=payload.description,
        created_by=actor.id,
    )
    add_tag(db, tag)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="tag_created",
        resource_type="tag",
        resource_id=tag.id,
        request_id=request_id,
        after_data=_tag_audit_data(tag),
    )
    _commit(db)
    return get_tag(db, tag.id) or tag


def update_tag(
    db: Session, *, actor: User, tag_id: str, payload: TagUpdate, request_id: str
) -> Tag:
    tag = get_tag(db, tag_id, for_update=True)
    if tag is None:
        raise AppException("RESOURCE_NOT_FOUND", "标签不存在", status_code=404)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name_key = updates["name"].casefold()
        if tag_name_exists(db, name_key, exclude_id=tag.id):
            raise AppException("DUPLICATE_RESOURCE", "标签名称已存在", status_code=409)
        tag.name_key = name_key
    before = {key: getattr(tag, key) for key in updates}
    for key, value in updates.items():
        setattr(tag, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="tag_updated",
        resource_type="tag",
        resource_id=tag.id,
        request_id=request_id,
        before_data={key: before[key] for key in ("name", "description") if key in before},
        after_data={key: updates[key] for key in ("name", "description") if key in updates},
    )
    _commit(db)
    return get_tag(db, tag.id) or tag


def delete_tag(db: Session, *, actor: User, tag_id: str, request_id: str) -> None:
    tag = get_tag(db, tag_id, for_update=True)
    if tag is None:
        raise AppException("RESOURCE_NOT_FOUND", "标签不存在", status_code=404)
    tag.deleted_at = datetime.now(UTC)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="tag_deleted",
        resource_type="tag",
        resource_id=tag.id,
        request_id=request_id,
        before_data=_tag_audit_data(tag),
        after_data={"deleted": True},
    )
    _commit(db)


def list_customer_tags_for_actor(
    db: Session, *, actor: User, customer_id: str
) -> list[CustomerTag]:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    return list_customer_tags(db, customer_id=customer_id)


def bind_tag(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    payload: TagBinding,
    request_id: str,
) -> CustomerTag:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    tag = get_tag(db, payload.tag_id)
    if tag is None:
        raise AppException("RESOURCE_NOT_FOUND", "标签不存在", status_code=404)
    if get_customer_tag(db, customer_id=customer_id, tag_id=tag.id) is not None:
        raise AppException("DUPLICATE_RESOURCE", "客户已绑定该标签", status_code=409)
    relation = CustomerTag(
        id=str(uuid4()), customer_id=customer_id, tag_id=tag.id, created_by=actor.id
    )
    add_customer_tag(db, relation)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customer_tag_bound",
        resource_type="customer",
        resource_id=customer_id,
        request_id=request_id,
        after_data={"tag_id": tag.id, "tag_name": tag.name},
    )
    _commit(db)
    return get_customer_tag(db, customer_id=customer_id, tag_id=tag.id) or relation


def unbind_tag(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    tag_id: str,
    request_id: str,
) -> None:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    relation = get_customer_tag(db, customer_id=customer_id, tag_id=tag_id, for_update=True)
    if relation is None:
        raise AppException("RESOURCE_NOT_FOUND", "客户未绑定该标签", status_code=404)
    delete_customer_tag(db, relation)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customer_tag_unbound",
        resource_type="customer",
        resource_id=customer_id,
        request_id=request_id,
        before_data={"tag_id": tag_id, "tag_name": relation.tag.name},
    )
    _commit(db)


def tag_response(tag: Tag) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "description": tag.description,
        "created_by": tag.created_by,
        "created_by_name": tag.creator.display_name,
        "created_at": tag.created_at.isoformat(),
        "updated_at": tag.updated_at.isoformat(),
    }


def customer_tag_response(relation: CustomerTag) -> dict:
    return {
        "id": relation.id,
        "customer_id": relation.customer_id,
        "tag_id": relation.tag_id,
        "tag_name": relation.tag.name,
        "tag_description": relation.tag.description,
        "created_by": relation.created_by,
        "created_at": relation.created_at.isoformat(),
    }


def _tag_audit_data(tag: Tag) -> dict:
    return {"name": tag.name, "description": tag.description}
