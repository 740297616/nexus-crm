from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.modules.auth.model import AuditLog, RefreshToken, User


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    return db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_refresh_token(db: Session, token_id: str) -> RefreshToken | None:
    return db.get(RefreshToken, token_id)


def add_refresh_token(
    db: Session,
    *,
    token_id: str,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(token)
    return token


def revoke_user_refresh_tokens(db: Session, user_id: str, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=current)
    )
    return result.rowcount


def add_audit_log(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    resource_id: str | None,
    request_id: str,
    ip_address: str | None,
    user_agent: str | None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        id=str(uuid4()),
        actor_user_id=actor_user_id,
        action=action,
        resource_type="auth",
        resource_id=resource_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        before_data=before_data,
        after_data=after_data,
    )
    db.add(audit_log)
    return audit_log
