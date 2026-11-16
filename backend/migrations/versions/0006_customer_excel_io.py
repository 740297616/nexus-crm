"""Add customer Excel import and export permissions.

Revision ID: 0006_customer_excel_io
Revises: 0005_contacts_and_tags
Create Date: 2026-11-16
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0006_customer_excel_io"
down_revision: str | None = "0005_contacts_and_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    (
        "customers:import",
        "导入客户",
        "customers",
        "import",
        "api",
        "从 Excel 批量导入客户",
    ),
    (
        "customers:export",
        "导出客户",
        "customers",
        "export",
        "api",
        "按数据权限导出客户",
    ),
)


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    permission_rows = [
        {
            "id": _id(code),
            "code": code,
            "name": name,
            "resource": resource,
            "action": action,
            "permission_type": permission_type,
            "description": description,
        }
        for code, name, resource, action, permission_type, description in PERMISSIONS
    ]
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
        permission_rows,
    )
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.String),
            sa.column("permission_id", sa.String),
        ),
        [
            {"role_id": _id(f"role:{role_code}"), "permission_id": _id(permission_code)}
            for role_code in ("system_admin", "sales_manager", "sales")
            for permission_code, *_ in PERMISSIONS
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    permission_ids = [_id(code) for code, *_ in PERMISSIONS]
    role_permissions = sa.table(
        "role_permissions",
        sa.column("permission_id", sa.String),
    )
    connection.execute(
        sa.delete(role_permissions).where(role_permissions.c.permission_id.in_(permission_ids))
    )
    permissions = sa.table("permissions", sa.column("id", sa.String))
    connection.execute(sa.delete(permissions).where(permissions.c.id.in_(permission_ids)))
