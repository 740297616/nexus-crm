from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.modules.contacts.model import Contact


def list_contacts(
    db: Session,
    *,
    customer_id: str,
    search: str | None,
    offset: int,
    limit: int,
    sort_order: str = "asc",
) -> tuple[list[Contact], int]:
    statement = _with_details(select(Contact)).where(Contact.customer_id == customer_id)
    count_statement = (
        select(func.count())
        .select_from(Contact)
        .where(
            Contact.customer_id == customer_id,
            Contact.deleted_at.is_(None),
        )
    )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        condition = or_(
            Contact.name.ilike(pattern),
            Contact.title.ilike(pattern),
            Contact.phone.ilike(pattern),
            Contact.email.ilike(pattern),
            Contact.contact_method.ilike(pattern),
        )
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    order = Contact.created_at.asc() if sort_order == "asc" else Contact.created_at.desc()
    total = int(db.scalar(count_statement) or 0)
    items = list(
        db.scalars(
            statement.order_by(Contact.is_primary.desc(), order, Contact.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return items, total


def get_contact(
    db: Session,
    *,
    customer_id: str,
    contact_id: str,
    for_update: bool = False,
) -> Contact | None:
    statement = _with_details(select(Contact)).where(
        Contact.id == contact_id,
        Contact.customer_id == customer_id,
    )
    if for_update:
        statement = statement.with_for_update(of=Contact)
    return db.scalar(statement)


def clear_primary_contacts(db: Session, *, customer_id: str, except_id: str | None = None) -> None:
    statement = (
        update(Contact)
        .where(Contact.customer_id == customer_id, Contact.deleted_at.is_(None))
        .values(is_primary=False)
    )
    if except_id is not None:
        statement = statement.where(Contact.id != except_id)
    db.execute(statement)


def add_contact(db: Session, contact: Contact) -> None:
    db.add(contact)
    db.flush()


def _with_details(statement: Select[Any]) -> Select[Any]:
    return statement.options(joinedload(Contact.creator)).where(Contact.deleted_at.is_(None))
