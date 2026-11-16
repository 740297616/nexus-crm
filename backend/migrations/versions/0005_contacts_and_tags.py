"""Add customer contacts, tags, and tag bindings.

Revision ID: 0005_contacts_and_tags
Revises: 0004_customer_management
Create Date: 2026-11-16
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0005_contacts_and_tags"
down_revision: str | None = "0004_customer_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("contacts:read", "查看联系人", "contacts", "read", "api", "查询客户联系人"),
    ("contacts:create", "创建联系人", "contacts", "create", "api", "创建客户联系人"),
    ("contacts:update", "编辑联系人", "contacts", "update", "api", "编辑客户联系人"),
    ("contacts:delete", "删除联系人", "contacts", "delete", "api", "软删除客户联系人"),
    (
        "contacts:set_primary",
        "设置主要联系人",
        "contacts",
        "set_primary",
        "api",
        "设置客户主要联系人",
    ),
    ("tags:read", "查看标签", "tags", "read", "api", "查询客户标签"),
    ("tags:create", "创建标签", "tags", "create", "api", "创建客户标签"),
    ("tags:update", "编辑标签", "tags", "update", "api", "编辑客户标签"),
    ("tags:delete", "删除标签", "tags", "delete", "api", "软删除客户标签"),
    ("tags:bind", "绑定标签", "tags", "bind", "api", "为客户绑定标签"),
    ("tags:unbind", "解绑标签", "tags", "unbind", "api", "移除客户标签"),
)


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("contact_method", sa.String(length=50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_contacts_name_not_blank"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_customer_active", "contacts", ["customer_id", "deleted_at"])
    op.create_index("ix_contacts_name", "contacts", ["name"])
    op.create_index(
        "uq_contacts_customer_primary_active",
        "contacts",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true AND deleted_at IS NULL"),
        sqlite_where=sa.text("is_primary = 1 AND deleted_at IS NULL"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("name_key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_key", name="uq_tags_name_key"),
    )
    op.create_index("ix_tags_deleted_at", "tags", ["deleted_at"])

    op.create_table(
        "customer_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "tag_id", name="uq_customer_tags_customer_tag"),
    )
    op.create_index("ix_customer_tags_tag_id", "customer_tags", ["tag_id"])

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

    permission_codes = {code for code, *_ in PERMISSIONS}
    role_grants = {
        "system_admin": permission_codes,
        "sales_manager": permission_codes,
        "sales": {
            "contacts:read",
            "contacts:create",
            "contacts:update",
            "contacts:delete",
            "contacts:set_primary",
            "tags:read",
            "tags:bind",
            "tags:unbind",
        },
    }
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.String),
            sa.column("permission_id", sa.String),
        ),
        [
            {"role_id": _id(f"role:{role_code}"), "permission_id": _id(permission_code)}
            for role_code, codes in role_grants.items()
            for permission_code in sorted(codes)
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

    op.drop_index("ix_customer_tags_tag_id", table_name="customer_tags")
    op.drop_table("customer_tags")
    op.drop_index("ix_tags_deleted_at", table_name="tags")
    op.drop_table("tags")
    op.drop_index("uq_contacts_customer_primary_active", table_name="contacts")
    op.drop_index("ix_contacts_name", table_name="contacts")
    op.drop_index("ix_contacts_customer_active", table_name="contacts")
    op.drop_table("contacts")
