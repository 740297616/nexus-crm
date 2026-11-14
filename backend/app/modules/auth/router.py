from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.responses import success_response
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schema import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    UserResponse,
)
from app.modules.auth.security import login_rate_limiter, token_service
from app.modules.auth.service import AuthService
from app.modules.roles.repository import get_permission_codes_for_user, get_role_codes_for_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(db: Session) -> AuthService:
    return AuthService(db, token_service=token_service, rate_limiter=login_rate_limiter)


def _request_context(request: Request) -> dict[str, str | None]:
    return {
        "request_id": request.state.request_id,
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.post("/login", response_model=None, summary="Log in")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    context = _request_context(request)
    tokens = _service(db).login(
        identifier=payload.identifier,
        password=payload.password,
        **context,
    )
    return success_response(tokens.model_dump(), context["request_id"] or "")


@router.post("/refresh", response_model=None, summary="Rotate refresh token")
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    context = _request_context(request)
    tokens = _service(db).refresh(refresh_token=payload.refresh_token, **context)
    return success_response(tokens.model_dump(), context["request_id"] or "")


@router.post("/logout", response_model=None, summary="Log out")
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)):
    context = _request_context(request)
    _service(db).logout(refresh_token=payload.refresh_token, **context)
    return success_response({"status": "logged_out"}, context["request_id"] or "")


@router.get("/me", response_model=None, summary="Get current user")
def me(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(
        {
            **UserResponse.model_validate(user).model_dump(mode="json"),
            "role_codes": get_role_codes_for_user(db, user.id),
            "permission_codes": sorted(get_permission_codes_for_user(db, user.id)),
        },
        request.state.request_id,
    )


@router.post("/change-password", response_model=None, summary="Change password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    context = _request_context(request)
    _service(db).change_password(
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        **context,
    )
    return success_response({"status": "password_changed"}, context["request_id"] or "")
