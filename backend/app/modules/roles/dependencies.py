from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import AppException
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.roles.repository import get_permission_codes_for_user


def require_permission(permission_code: str) -> Callable:
    def permission_dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        permission_codes = get_permission_codes_for_user(db, current_user.id)
        if permission_code not in permission_codes:
            raise AppException("PERMISSION_DENIED", "没有执行此操作的权限", status_code=403)
        return current_user

    return permission_dependency
