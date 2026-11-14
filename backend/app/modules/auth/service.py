from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.auth.repository import (
    add_audit_log,
    add_refresh_token,
    get_refresh_token,
    get_user_by_id,
    get_user_by_identifier,
    revoke_user_refresh_tokens,
)
from app.modules.auth.schema import TokenResponse
from app.modules.auth.security import (
    LoginRateLimiter,
    TokenService,
    hash_password,
    token_digest,
    verify_password,
)


class AuthService:
    def __init__(
        self,
        db: Session,
        *,
        token_service: TokenService,
        rate_limiter: LoginRateLimiter,
    ) -> None:
        self.db = db
        self.token_service = token_service
        self.rate_limiter = rate_limiter

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _is_expired(value: datetime, now: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value <= now

    def _commit(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def _audit(
        self,
        *,
        actor_user_id: str | None,
        action: str,
        resource_id: str | None,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
        after_data: dict | None = None,
    ) -> None:
        add_audit_log(
            self.db,
            actor_user_id=actor_user_id,
            action=action,
            resource_id=resource_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            after_data=after_data,
        )

    def _issue_tokens(self, user: User) -> TokenResponse:
        access_token, _ = self.token_service.create_access_token(user.id)
        refresh_token, refresh_id, refresh_expires_at = self.token_service.create_refresh_token(
            user.id
        )
        add_refresh_token(
            self.db,
            token_id=refresh_id,
            user_id=user.id,
            token_hash=token_digest(refresh_token),
            expires_at=refresh_expires_at,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.token_service.settings.access_token_expire_minutes * 60,
        )

    def login(
        self,
        *,
        identifier: str,
        password: str,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        rate_key = f"{ip_address or 'unknown'}:{identifier.casefold()}"
        if self.rate_limiter.is_blocked(rate_key):
            self._audit(
                actor_user_id=None,
                action="login_rate_limited",
                resource_id=None,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._commit()
            raise AppException("RATE_LIMITED", "登录尝试过于频繁，请稍后再试", status_code=429)

        user = get_user_by_identifier(self.db, identifier)
        valid_credentials = bool(user and verify_password(password, user.password_hash))
        if not valid_credentials or user.status != "active":
            self.rate_limiter.register_failure(rate_key)
            self._audit(
                actor_user_id=user.id if user else None,
                action="login_failed",
                resource_id=user.id if user else None,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                after_data={"reason": "invalid_credentials"},
            )
            self._commit()
            raise AppException("AUTH_INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)

        self.rate_limiter.reset(rate_key)
        tokens = self._issue_tokens(user)
        user.last_login_at = self._now()
        self._audit(
            actor_user_id=user.id,
            action="login_succeeded",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._commit()
        return tokens

    def refresh(
        self,
        *,
        refresh_token: str,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        payload = self.token_service.decode(refresh_token, "refresh")
        refresh_id = str(payload["jti"])
        user_id = str(payload["sub"])
        stored_token = get_refresh_token(self.db, refresh_id)
        now = self._now()

        if (
            stored_token is None
            or stored_token.user_id != user_id
            or stored_token.token_hash != token_digest(refresh_token)
        ):
            raise AppException("TOKEN_INVALID", "Refresh Token 无效", status_code=401)

        if stored_token.revoked_at is not None:
            revoke_user_refresh_tokens(self.db, user_id, now)
            self._audit(
                actor_user_id=user_id,
                action="refresh_token_reuse_detected",
                resource_id=user_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._commit()
            raise AppException("TOKEN_INVALID", "Refresh Token 已失效", status_code=401)

        if self._is_expired(stored_token.expires_at, now):
            stored_token.revoked_at = now
            self._audit(
                actor_user_id=user_id,
                action="refresh_token_expired",
                resource_id=user_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._commit()
            raise AppException("TOKEN_EXPIRED", "Refresh Token 已过期", status_code=401)

        user = get_user_by_id(self.db, user_id)
        if user is None or user.status != "active":
            stored_token.revoked_at = now
            self._audit(
                actor_user_id=user_id,
                action="refresh_rejected_disabled_user",
                resource_id=user_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._commit()
            raise AppException("ACCOUNT_DISABLED", "账号不可用", status_code=401)

        stored_token.revoked_at = now
        stored_token.last_used_at = now
        tokens = self._issue_tokens(user)
        new_payload = self.token_service.decode(tokens.refresh_token, "refresh")
        stored_token.replaced_by_id = str(new_payload["jti"])
        self._audit(
            actor_user_id=user.id,
            action="refresh_token_rotated",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._commit()
        return tokens

    def logout(
        self,
        *,
        refresh_token: str,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        try:
            payload = self.token_service.decode(refresh_token, "refresh", verify_exp=False)
        except AppException as exc:
            if exc.code in {"TOKEN_INVALID", "TOKEN_EXPIRED"}:
                return
            raise

        refresh_id = str(payload["jti"])
        user_id = str(payload["sub"])
        stored_token = get_refresh_token(self.db, refresh_id)
        if stored_token is None or stored_token.token_hash != token_digest(refresh_token):
            return
        if stored_token.revoked_at is None:
            stored_token.revoked_at = self._now()
            self._audit(
                actor_user_id=user_id,
                action="logout",
                resource_id=user_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._commit()

    def current_user(self, user_id: str) -> User:
        user = get_user_by_id(self.db, user_id)
        if user is None or user.status != "active":
            raise AppException("AUTH_REQUIRED", "请先登录", status_code=401)
        return user

    def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            self._audit(
                actor_user_id=user.id,
                action="password_change_failed",
                resource_id=user.id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                after_data={"reason": "invalid_current_password"},
            )
            self._commit()
            raise AppException("AUTH_INVALID_CREDENTIALS", "当前密码错误", status_code=401)
        if verify_password(new_password, user.password_hash):
            raise AppException(
                "BUSINESS_RULE_VIOLATION", "新密码不能与当前密码相同", status_code=422
            )

        user.password_hash = hash_password(new_password)
        revoke_user_refresh_tokens(self.db, user.id)
        self._audit(
            actor_user_id=user.id,
            action="password_changed",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._commit()
