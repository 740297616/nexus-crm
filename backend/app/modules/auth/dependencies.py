from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import AppException
from app.modules.auth.repository import get_user_by_id
from app.modules.auth.security import token_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException("AUTH_REQUIRED", "请先登录", status_code=401)
    payload = token_service.decode(credentials.credentials, "access")
    user = get_user_by_id(db, str(payload["sub"]))
    if user is None or user.status != "active":
        raise AppException("AUTH_REQUIRED", "请先登录", status_code=401)
    if payload.get("ver", 0) != user.auth_version:
        raise AppException("TOKEN_INVALID", "令牌已失效", status_code=401)
    return user
