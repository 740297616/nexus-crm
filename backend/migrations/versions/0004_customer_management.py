"""Add customer management, ownership history, and customer permissions.

Revision ID: 0004_customer_management
Revises: 0003_organization_rbac
Create Date: 2026-11-15
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0004_customer_management"
down_revision: str | None = "0003_organization_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CUSTOMER_PERMISSIONS = (
    ("customers:menu", "客户管理菜单", "customers", "menu", "menu", "显示客户管理菜单"),
    ("customers:page", "客户管理页面", "customers", "page", "page", "访问客户管理页面"),
    ("customers:read", "查看客户", "customers", "read", "api", "查询客户和同名提醒"),
    ("customers:create", "创建客户", "customers", "create", "api", "创建客户档案"),
    ("customers:update", "编辑客户", "customers", "update", "api", "编辑客户档案"),
    ("customers:delete", "删除客户", "customers", "delete", "api", "软删除客户"),
    ("customers:assign", "分配客户", "customers", "assign", "api", "分配客户负责人"),
    ("customers:transfer", "转移客户", "customers", "transfer", "api", "转移客户负责人并记录原因"),
)


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_no", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("level", sa.String(length=1), server_default="C", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.CheckConstraint("level IN ('A', 'B', 'C', 'D')", name="ck_customers_level"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_no", name="uq_customers_customer_no"),
    )
    op.create_index("ix_customers_owner_status", "customers", ["owner_id", "status"])
    op.create_index("ix_customers_department_status", "customers", ["department_id", "status"])
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_deleted_at", "customers", ["deleted_at"])

    op.create_table(
        "customer_ownership_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("previous_owner_id", sa.String(length=36), nullable=True),
        sa.Column("previous_department_id", sa.String(length=36), nullable=True),
        sa.Column("new_owner_id", sa.String(length=36), nullable=False),
        sa.Column("new_department_id", sa.String(length=36), nullable=False),
        sa.Column("transferred_by", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('assigned', 'transferred')", name="ck_customer_history_action"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["previous_department_id"], ["departments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["previous_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transferred_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_ownership_history_customer_created",
        "customer_ownership_history",
        ["customer_id", "created_at"],
    )

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
        for code, name, resource, action, permission_type, description in CUSTOMER_PERMISSIONS
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
            "roles",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("code", sa.String),
            sa.column("description", sa.String),
            sa.column("data_scope", sa.String),
            sa.column("is_system", sa.Boolean),
        ),
        [
            {
                "id": _id("role:sales_manager"),
                "name": "销售主管",
                "code": "sales_manager",
                "description": "管理本人部门及下属部门范围内的客户和负责人分配。",
                "data_scope": "subtree",
                "is_system": True,
            },
            {
                "id": _id("role:sales"),
                "name": "销售",
                "code": "sales",
                "description": "管理本人负责的客户。",
                "data_scope": "self",
                "is_system": True,
            },
        ],
    )

    all_customer_codes = {code for code, *_ in CUSTOMER_PERMISSIONS}
    sales_manager_codes = all_customer_codes | {"dashboard:menu", "dashboard:page"}
    sales_codes = {
        "customers:menu",
        "customers:page",
        "customers:read",
        "customers:create",
        "customers:update",
        "dashboard:menu",
        "dashboard:page",
    }
    role_grants = {
        "system_admin": all_customer_codes,
        "sales_manager": sales_manager_codes,
        "sales": sales_codes,
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
    role_ids = [_id("role:sales_manager"), _id("role:sales")]
    permission_ids = [_id(code) for code, *_ in CUSTOMER_PERMISSIONS]
    user_roles = sa.table(
        "user_roles",
        sa.column("role_id", sa.String),
    )
    assignment_count = connection.scalar(
        sa.select(sa.func.count()).select_from(user_roles).where(user_roles.c.role_id.in_(role_ids))
    )
    if assignment_count:
        raise RuntimeError(
            "Cannot downgrade customer management while sales roles are assigned; "
            "reassign those users before retrying."
        )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.String),
        sa.column("permission_id", sa.String),
    )
    connection.execute(
        sa.delete(role_permissions).where(
            sa.or_(
                role_permissions.c.role_id.in_(role_ids),
                role_permissions.c.permission_id.in_(permission_ids),
            )
        )
    )
    connection.execute(
        sa.text("DELETE FROM roles WHERE id IN :role_ids").bindparams(
            sa.bindparam("role_ids", expanding=True)
        ),
        {"role_ids": role_ids},
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE id IN :permission_ids").bindparams(
            sa.bindparam("permission_ids", expanding=True)
        ),
        {"permission_ids": permission_ids},
    )

    op.drop_index(
        "ix_customer_ownership_history_customer_created", table_name="customer_ownership_history"
    )
    op.drop_table("customer_ownership_history")
    op.drop_index("ix_customers_deleted_at", table_name="customers")
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_index("ix_customers_department_status", table_name="customers")
    op.drop_index("ix_customers_owner_status", table_name="customers")
    op.drop_table("customers")
