"""Add dashboard statistics permission.

Revision ID: 0008_dashboard_statistics
Revises: 0007_followups_reminders
Create Date: 2026-11-16

The dashboard uses the existing CRM tables and therefore does not add a table.
This migration only adds the API permission and grants it to the built-in roles.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0008_dashboard_statistics"
down_revision: str | None = "0007_followups_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION = (
    "dashboard:read",
    "查看工作台统计",
    "dashboard",
    "read",
    "api",
    "查询工作台统计数据",
)


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    code, name, resource, action, permission_type, description = PERMISSION
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("id", sa.String),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("resource", sa.String),
            sa.column("action", sa.String),
            sa.column("permission_type", sa.String),
            sa.column("description", sa.String),
        ),
        [
            {
                "id": _id(code),
                "code": code,
                "name": name,
                "resource": resource,
                "action": action,
                "permission_type": permission_type,
                "description": description,
            }
        ],
    )
    role_codes = ("system_admin", "department_manager", "employee", "sales_manager", "sales")
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.String),
            sa.column("permission_id", sa.String),
        ),
        [
            {"role_id": _id(f"role:{role_code}"), "permission_id": _id(code)}
            for role_code in role_codes
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    code = PERMISSION[0]
    permission_id = _id(code)
    role_permissions = sa.table(
        "role_permissions",
        sa.column("permission_id", sa.String),
    )
    connection.execute(
        sa.delete(role_permissions).where(role_permissions.c.permission_id == permission_id)
    )
    permissions = sa.table("permissions", sa.column("id", sa.String))
    connection.execute(sa.delete(permissions).where(permissions.c.id == permission_id))
