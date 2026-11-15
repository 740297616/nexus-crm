from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.common.data_scope import DataScopeContext, data_scope_service
from app.modules.auth.model import User
from app.modules.organizations.model import Department
from app.modules.roles.model import Role


def list_users(
    db: Session,
    *,
    search: str | None,
    department_id: str | None,
    scope: DataScopeContext,
    offset: int,
    limit: int,
) -> tuple[list[User], int]:
    statement = select(User).options(selectinload(User.roles), selectinload(User.department))
    count_statement = select(func.count()).select_from(User)
    statement = data_scope_service.apply(statement, scope, User, owner_field="id")
    count_statement = data_scope_service.apply(count_statement, scope, User, owner_field="id")
    if department_id is not None:
        statement = statement.where(User.department_id == department_id)
        count_statement = count_statement.where(User.department_id == department_id)
    if search:
        query = f"%{search.strip()}%"
        condition = or_(
            User.username.ilike(query), User.display_name.ilike(query), User.email.ilike(query)
        )
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = int(db.scalar(count_statement) or 0)
    items = list(
        db.scalars(statement.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    )
    return items, total


def get_user(db: Session, user_id: str, *, scope: DataScopeContext | None = None) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.department))
        .where(User.id == user_id)
    )
    if scope is not None:
        statement = data_scope_service.apply(statement, scope, User, owner_field="id")
    return db.scalar(statement)


def get_roles(db: Session, role_ids: list[str]) -> list[Role]:
    return list(db.scalars(select(Role).where(Role.id.in_(set(role_ids)))).all())


def get_department_name(db: Session, department_id: str | None) -> str | None:
    if department_id is None:
        return None
    return db.scalar(select(Department.name).where(Department.id == department_id))
