from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.common.data_scope import DataScopeContext, data_scope_service
from app.modules.auth.model import User
from app.modules.customers.model import Customer, CustomerOwnershipHistory
from app.modules.customers.schema import CustomerListFilters
from app.modules.organizations.model import Department


def list_customers(
    db: Session,
    *,
    scope: DataScopeContext,
    filters: CustomerListFilters,
    offset: int,
    limit: int,
) -> tuple[list[Customer], int]:
    statement = _with_customer_details(select(Customer))
    count_statement = select(func.count()).select_from(Customer)
    statement = _apply_customer_scope(statement, scope)
    count_statement = _apply_customer_scope(count_statement, scope)
    statement, count_statement = _apply_filters(statement, count_statement, filters)

    order_column = {
        "created_at": Customer.created_at,
        "updated_at": Customer.updated_at,
        "customer_no": Customer.customer_no,
        "name": Customer.name,
        "level": Customer.level,
        "status": Customer.status,
    }[filters.sort_by]
    order = order_column.asc() if filters.sort_order == "asc" else order_column.desc()
    total = int(db.scalar(count_statement) or 0)
    customers = list(
        db.scalars(statement.order_by(order, Customer.id).offset(offset).limit(limit)).all()
    )
    return customers, total


def get_customer(
    db: Session,
    customer_id: str,
    *,
    scope: DataScopeContext,
    for_update: bool = False,
) -> Customer | None:
    statement = _with_customer_details(select(Customer)).where(Customer.id == customer_id)
    statement = _apply_customer_scope(statement, scope)
    if for_update:
        statement = statement.with_for_update(of=Customer)
    return db.scalar(statement)


def customer_no_exists(db: Session, customer_no: str) -> bool:
    return (
        db.scalar(select(Customer.id).where(Customer.customer_no == customer_no).limit(1))
        is not None
    )


def find_name_duplicates(
    db: Session,
    *,
    name: str,
    scope: DataScopeContext,
    exclude_id: str | None = None,
    limit: int = 5,
) -> tuple[list[Customer], int]:
    normalized_name = func.lower(func.trim(Customer.name)) == name.strip().casefold()
    statement = _with_customer_details(select(Customer)).where(normalized_name)
    count_statement = select(func.count()).select_from(Customer).where(normalized_name)
    statement = _apply_customer_scope(statement, scope)
    count_statement = _apply_customer_scope(count_statement, scope)
    if exclude_id is not None:
        statement = statement.where(Customer.id != exclude_id)
        count_statement = count_statement.where(Customer.id != exclude_id)
    total = int(db.scalar(count_statement) or 0)
    customers = list(db.scalars(statement.order_by(Customer.created_at.desc()).limit(limit)).all())
    return customers, total


def list_assignable_users(db: Session, *, scope: DataScopeContext) -> list[User]:
    statement = (
        select(User)
        .options(joinedload(User.department))
        .join(Department, User.department_id == Department.id)
        .where(User.status == "active", Department.is_active.is_(True))
    )
    statement = data_scope_service.apply(
        statement,
        scope,
        User,
        owner_field="id",
        department_field="department_id",
    )
    return list(db.scalars(statement.order_by(User.display_name, User.id)).all())


def get_active_owner(db: Session, owner_id: str) -> User | None:
    statement = (
        select(User)
        .options(joinedload(User.department))
        .where(User.id == owner_id, User.status == "active")
    )
    return db.scalar(statement)


def list_ownership_history(db: Session, customer_id: str) -> list[dict[str, Any]]:
    from sqlalchemy.orm import aliased

    previous_owner = aliased(User)
    new_owner = aliased(User)
    assigned_by = aliased(User)
    previous_department = aliased(Department)
    new_department = aliased(Department)
    statement = (
        select(
            CustomerOwnershipHistory,
            previous_owner.display_name.label("previous_owner_name"),
            previous_department.name.label("previous_department_name"),
            new_owner.display_name.label("new_owner_name"),
            new_department.name.label("new_department_name"),
            assigned_by.display_name.label("transferred_by_name"),
        )
        .outerjoin(previous_owner, CustomerOwnershipHistory.previous_owner_id == previous_owner.id)
        .outerjoin(
            previous_department,
            CustomerOwnershipHistory.previous_department_id == previous_department.id,
        )
        .join(new_owner, CustomerOwnershipHistory.new_owner_id == new_owner.id)
        .join(new_department, CustomerOwnershipHistory.new_department_id == new_department.id)
        .join(assigned_by, CustomerOwnershipHistory.transferred_by == assigned_by.id)
        .where(CustomerOwnershipHistory.customer_id == customer_id)
        .order_by(CustomerOwnershipHistory.created_at.desc(), CustomerOwnershipHistory.id.desc())
    )
    rows = db.execute(statement).all()
    return [
        {
            "id": history.id,
            "action": history.action,
            "previous_owner_id": history.previous_owner_id,
            "previous_owner_name": previous_owner_name,
            "previous_department_id": history.previous_department_id,
            "new_owner_id": history.new_owner_id,
            "new_owner_name": new_owner_name,
            "new_department_id": history.new_department_id,
            "new_department_name": new_department_name,
            "transferred_by": history.transferred_by,
            "transferred_by_name": transferred_by_name,
            "reason": history.reason,
            "created_at": history.created_at,
        }
        for (
            history,
            previous_owner_name,
            _previous_department_name,
            new_owner_name,
            new_department_name,
            transferred_by_name,
        ) in rows
    ]


def add_customer(db: Session, customer: Customer) -> None:
    db.add(customer)
    db.flush()


def add_ownership_history(db: Session, history: CustomerOwnershipHistory) -> None:
    db.add(history)
    db.flush()


def _with_customer_details(statement: Select[Any]) -> Select[Any]:
    return statement.options(
        joinedload(Customer.owner),
        joinedload(Customer.department),
        joinedload(Customer.creator),
    ).where(Customer.deleted_at.is_(None))


def _apply_customer_scope(statement: Select[Any], scope: DataScopeContext) -> Select[Any]:
    return data_scope_service.apply(statement, scope, Customer).where(Customer.deleted_at.is_(None))


def _apply_filters(
    statement: Select[Any],
    count_statement: Select[Any],
    filters: CustomerListFilters,
) -> tuple[Select[Any], Select[Any]]:
    conditions = []
    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        conditions.append(
            or_(
                Customer.customer_no.ilike(pattern),
                Customer.name.ilike(pattern),
                Customer.phone.ilike(pattern),
                Customer.email.ilike(pattern),
            )
        )
    if filters.source:
        conditions.append(Customer.source == filters.source.strip())
    if filters.industry:
        conditions.append(Customer.industry == filters.industry.strip())
    if filters.level:
        conditions.append(Customer.level == filters.level)
    if filters.status:
        conditions.append(Customer.status == filters.status)
    if filters.owner_id:
        conditions.append(Customer.owner_id == filters.owner_id)
    if filters.department_id:
        conditions.append(Customer.department_id == filters.department_id)
    if filters.created_from:
        start = datetime.combine(filters.created_from, time.min, tzinfo=UTC)
        conditions.append(Customer.created_at >= start)
    if filters.created_to:
        end = datetime.combine(filters.created_to + timedelta(days=1), time.min, tzinfo=UTC)
        conditions.append(Customer.created_at < end)
    for condition in conditions:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    return statement, count_statement
