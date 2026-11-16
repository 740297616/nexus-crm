from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.tags.model import CustomerTag, Tag


def list_tags(db: Session) -> list[Tag]:
    return list(db.scalars(_with_details(select(Tag)).order_by(func.lower(Tag.name), Tag.id)).all())


def get_tag(db: Session, tag_id: str, *, for_update: bool = False) -> Tag | None:
    statement = _with_details(select(Tag)).where(Tag.id == tag_id)
    if for_update:
        statement = statement.with_for_update(of=Tag)
    return db.scalar(statement)


def tag_name_exists(db: Session, name_key: str, *, exclude_id: str | None = None) -> bool:
    statement = select(Tag.id).where(Tag.name_key == name_key, Tag.deleted_at.is_(None))
    if exclude_id is not None:
        statement = statement.where(Tag.id != exclude_id)
    return db.scalar(statement.limit(1)) is not None


def add_tag(db: Session, tag: Tag) -> None:
    db.add(tag)
    db.flush()


def list_customer_tags(db: Session, *, customer_id: str) -> list[CustomerTag]:
    statement = (
        select(CustomerTag)
        .options(joinedload(CustomerTag.tag), joinedload(CustomerTag.creator))
        .join(Tag, CustomerTag.tag_id == Tag.id)
        .where(CustomerTag.customer_id == customer_id, Tag.deleted_at.is_(None))
        .order_by(func.lower(Tag.name), CustomerTag.id)
    )
    return list(db.scalars(statement).all())


def get_customer_tag(
    db: Session, *, customer_id: str, tag_id: str, for_update: bool = False
) -> CustomerTag | None:
    statement = (
        select(CustomerTag)
        .options(joinedload(CustomerTag.tag), joinedload(CustomerTag.creator))
        .join(Tag, CustomerTag.tag_id == Tag.id)
        .where(CustomerTag.customer_id == customer_id, CustomerTag.tag_id == tag_id)
    )
    if for_update:
        statement = statement.with_for_update(of=CustomerTag)
    return db.scalar(statement)


def add_customer_tag(db: Session, relation: CustomerTag) -> None:
    db.add(relation)
    db.flush()


def delete_customer_tag(db: Session, relation: CustomerTag) -> None:
    db.delete(relation)
    db.flush()


def _with_details(statement: Select[Any]) -> Select[Any]:
    return statement.options(joinedload(Tag.creator)).where(Tag.deleted_at.is_(None))
