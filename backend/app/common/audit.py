from uuid import uuid4

from sqlalchemy.orm import Session

from app.modules.auth.model import AuditLog


def add_audit_log(
    db: Session,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    request_id: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            id=str(uuid4()),
            actor_user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            before_data=before_data,
            after_data=after_data,
        )
    )
