from __future__ import annotations

import hashlib
import secrets
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import AppException

password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _secret(self) -> str:
        if not self.settings.jwt_secret_key:
            raise RuntimeError("JWT_SECRET_KEY is not configured")
        return self.settings.jwt_secret_key

    def _encode(
        self,
        subject: str,
        token_type: str,
        expires_delta: timedelta,
        additional_claims: dict[str, Any] | None = None,
    ) -> tuple[str, str, datetime]:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + expires_delta
        token_id = str(uuid4())
        payload: dict[str, Any] = {
            "sub": subject,
            "jti": token_id,
            "iat": issued_at,
            "exp": expires_at,
            "token_type": token_type,
        }
        if additional_claims:
            payload.update(additional_claims)
        return (
            jwt.encode(payload, self._secret(), algorithm=self.settings.jwt_algorithm),
            token_id,
            expires_at,
        )

    def create_access_token(self, subject: str, auth_version: int = 0) -> tuple[str, datetime]:
        token, _, expires_at = self._encode(
            subject,
            "access",
            timedelta(minutes=self.settings.access_token_expire_minutes),
            {"ver": auth_version},
        )
        return token, expires_at

    def create_refresh_token(self, subject: str) -> tuple[str, str, datetime]:
        return self._encode(
            subject,
            "refresh",
            timedelta(days=self.settings.refresh_token_expire_days),
        )

    def decode(self, token: str, expected_type: str, *, verify_exp: bool = True) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._secret(),
                algorithms=[self.settings.jwt_algorithm],
                options={"verify_exp": verify_exp},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AppException("TOKEN_EXPIRED", "令牌已过期", status_code=401) from exc
        except jwt.InvalidTokenError as exc:
            raise AppException("TOKEN_INVALID", "令牌无效", status_code=401) from exc

        if payload.get("token_type") != expected_type or not payload.get("sub"):
            raise AppException("TOKEN_INVALID", "令牌无效", status_code=401)
        return payload


class LoginRateLimiter:
    """Process-local failed-login limiter; deploy one app worker per limiter scope."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)
        self._locked_until: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def is_blocked(self, key: str, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        with self._lock:
            locked_until = self._locked_until.get(key)
            return bool(locked_until and locked_until > current)

    def register_failure(self, key: str, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        threshold = current - timedelta(seconds=self.settings.login_window_seconds)
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= threshold:
                attempts.popleft()
            attempts.append(current)
            if len(attempts) >= self.settings.login_max_attempts:
                self._locked_until[key] = current + timedelta(
                    seconds=self.settings.login_lockout_seconds
                )

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
            self._locked_until.pop(key, None)


token_service = TokenService()
login_rate_limiter = LoginRateLimiter()


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(48)
