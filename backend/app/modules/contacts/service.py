from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.contacts.model import Contact
from app.modules.contacts.repository import (
    add_contact,
    clear_primary_contacts,
    get_contact,
    list_contacts,
)
from app.modules.contacts.schema import ContactCreate, ContactUpdate
from app.modules.customers.service import get_customer_for_actor


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            "CONFLICT", "联系人状态发生并发冲突，请刷新后重试", status_code=409
        ) from exc


def list_contacts_for_actor(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    search: str | None,
    page: int,
    page_size: int,
    sort_order: str = "asc",
) -> tuple[list[Contact], int]:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    return list_contacts(
        db,
        customer_id=customer_id,
        search=search,
        offset=(page - 1) * page_size,
        limit=page_size,
        sort_order=sort_order,
    )


def get_contact_for_actor(
    db: Session, *, actor: User, customer_id: str, contact_id: str
) -> Contact:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = get_contact(db, customer_id=customer_id, contact_id=contact_id)
    if contact is None:
        raise AppException("RESOURCE_NOT_FOUND", "联系人不存在", status_code=404)
    return contact


def create_contact(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    payload: ContactCreate,
    request_id: str,
) -> Contact:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = Contact(
        id=str(uuid4()),
        customer_id=customer_id,
        name=payload.name,
        title=payload.title,
        phone=payload.phone,
        email=payload.email,
        contact_method=payload.contact_method,
        is_primary=payload.is_primary,
        remark=payload.remark,
        created_by=actor.id,
    )
    if contact.is_primary:
        clear_primary_contacts(db, customer_id=customer_id)
    add_contact(db, contact)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="contact_created",
        resource_type="contact",
        resource_id=contact.id,
        request_id=request_id,
        after_data=_contact_audit_data(contact),
    )
    _commit(db)
    return get_contact(db, customer_id=customer_id, contact_id=contact.id) or contact


def update_contact(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    contact_id: str,
    payload: ContactUpdate,
    request_id: str,
) -> Contact:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = get_contact(db, customer_id=customer_id, contact_id=contact_id, for_update=True)
    if contact is None:
        raise AppException("RESOURCE_NOT_FOUND", "联系人不存在", status_code=404)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return contact
    before = {key: getattr(contact, key) for key in updates}
    for key, value in updates.items():
        setattr(contact, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="contact_updated",
        resource_type="contact",
        resource_id=contact.id,
        request_id=request_id,
        before_data=_contact_audit_data(before),
        after_data=_contact_audit_data(updates),
    )
    _commit(db)
    return get_contact(db, customer_id=customer_id, contact_id=contact.id) or contact


def delete_contact(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    contact_id: str,
    request_id: str,
) -> None:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = get_contact(db, customer_id=customer_id, contact_id=contact_id, for_update=True)
    if contact is None:
        raise AppException("RESOURCE_NOT_FOUND", "联系人不存在", status_code=404)
    contact.deleted_at = datetime.now(UTC)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="contact_deleted",
        resource_type="contact",
        resource_id=contact.id,
        request_id=request_id,
        before_data=_contact_audit_data(contact),
        after_data={"deleted": True},
    )
    _commit(db)


def set_primary_contact(
    db: Session,
    *,
    actor: User,
    customer_id: str,
    contact_id: str,
    request_id: str,
) -> Contact:
    get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    contact = get_contact(db, customer_id=customer_id, contact_id=contact_id, for_update=True)
    if contact is None:
        raise AppException("RESOURCE_NOT_FOUND", "联系人不存在", status_code=404)
    if not contact.is_primary:
        clear_primary_contacts(db, customer_id=customer_id, except_id=contact.id)
        contact.is_primary = True
        add_audit_log(
            db,
            actor_id=actor.id,
            action="contact_primary_changed",
            resource_type="contact",
            resource_id=contact.id,
            request_id=request_id,
            after_data={"is_primary": True},
        )
        _commit(db)
    return get_contact(db, customer_id=customer_id, contact_id=contact.id) or contact


def contact_response(contact: Contact) -> dict:
    return {
        "id": contact.id,
        "customer_id": contact.customer_id,
        "name": contact.name,
        "title": contact.title,
        "phone": contact.phone,
        "email": contact.email,
        "contact_method": contact.contact_method,
        "is_primary": contact.is_primary,
        "remark": contact.remark,
        "created_by": contact.created_by,
        "created_by_name": contact.creator.display_name,
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
    }


def _contact_audit_data(value: Contact | dict) -> dict:
    if isinstance(value, Contact):
        values = {field: getattr(value, field) for field in _AUDIT_FIELDS}
    else:
        values = {field: value.get(field) for field in _AUDIT_FIELDS if field in value}
    return values


_AUDIT_FIELDS = {
    "name",
    "title",
    "phone",
    "email",
    "contact_method",
    "is_primary",
}
