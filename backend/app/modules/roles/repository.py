from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.data_scope import data_scope_service
from app.modules.auth.model import User
from app.modules.roles.model import Permission, Role


def get_permission_codes_for_user(db: Session, user_id: str) -> set[str]:
    statement = (
        select(Permission.code)
        .select_from(User)
        .join(User.roles)
        .join(Role.permissions)
        .where(User.id == user_id)
    )
    return set(db.scalars(statement).all())


def get_role_codes_for_user(db: Session, user_id: str) -> list[str]:
    statement = (
        select(Role.code)
        .select_from(User)
        .join(User.roles)
        .where(User.id == user_id)
        .order_by(Role.code)
    )
    return list(db.scalars(statement).all())


def get_roles_for_user(db: Session, user_id: str) -> list[Role]:
    statement = (
        select(Role)
        .select_from(User)
        .join(User.roles)
        .where(User.id == user_id)
        .order_by(Role.name)
    )
    return list(db.scalars(statement).all())


def get_effective_data_scope(db: Session, user_id: str) -> str:
    """Backward-compatible scalar API backed by the shared scope service."""

    return data_scope_service.get_effective_data_scope(db, user_id)
