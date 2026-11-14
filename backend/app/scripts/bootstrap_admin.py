import os
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.common.audit import add_audit_log
from app.db.session import SessionLocal
from app.modules.auth.model import User
from app.modules.auth.security import hash_password
from app.modules.roles.model import Role


def bootstrap_admin() -> None:
    username = os.environ.get("INITIAL_ADMIN_USERNAME", "").strip()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    display_name = os.environ.get("INITIAL_ADMIN_DISPLAY_NAME", "").strip()
    email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip() or None
    if not username or not password or not display_name:
        raise SystemExit(
            "Set INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_PASSWORD and INITIAL_ADMIN_DISPLAY_NAME."
        )
    if len(password) < 12:
        raise SystemExit("INITIAL_ADMIN_PASSWORD must contain at least 12 characters.")

    with SessionLocal() as db:
        admin_role = db.scalar(select(Role).where(Role.code == "system_admin"))
        if admin_role is None:
            raise SystemExit("RBAC roles are missing; run `alembic upgrade head` first.")

        user = db.scalar(select(User).where(User.username == username))
        if user is not None:
            if admin_role not in user.roles:
                raise SystemExit("The requested username exists without the system_admin role.")
            print("Initial system administrator already exists; no changes made.")
            return

        existing_admin = db.scalar(
            select(User.id).join(User.roles).where(Role.code == "system_admin").limit(1)
        )
        if existing_admin is not None:
            raise SystemExit("A system administrator already exists; refusing to create another.")

        user = User(
            id=str(uuid4()),
            username=username,
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            status="active",
            roles=[admin_role],
        )
        db.add(user)
        db.flush()
        add_audit_log(
            db,
            actor_id=user.id,
            action="initial_system_admin_created",
            resource_type="user",
            resource_id=user.id,
            request_id="bootstrap",
            after_data={"username": user.username, "role_codes": [admin_role.code]},
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise SystemExit("Initial administrator conflicts with existing user data.") from exc
        print("Initial system administrator created.")


if __name__ == "__main__":
    bootstrap_admin()
