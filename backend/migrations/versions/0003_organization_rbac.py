"""Create organization and RBAC models and seed standard role templates.

Revision ID: 0003_organization_rbac
Revises: 0002_authentication
Create Date: 2026-11-14
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import context, op

revision: str = "0003_organization_rbac"
down_revision: str | None = "0002_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("dashboard:menu", "工作台菜单", "dashboard", "menu", "menu", "显示工作台菜单"),
    ("dashboard:page", "工作台页面", "dashboard", "page", "page", "访问工作台页面"),
    ("users:menu", "用户管理菜单", "users", "menu", "menu", "显示用户管理菜单"),
    ("users:page", "用户管理页面", "users", "page", "page", "访问用户管理页面"),
    ("users:read", "查看用户", "users", "read", "api", "查询用户列表和详情"),
    ("users:create", "创建用户", "users", "create", "api", "创建员工账号"),
    ("users:update", "编辑用户", "users", "update", "api", "修改员工信息"),
    ("users:disable", "启用或禁用用户", "users", "disable", "api", "修改用户启用状态"),
    ("users:assign_roles", "分配用户角色", "users", "assign_roles", "api", "分配用户角色"),
    ("departments:menu", "部门管理菜单", "departments", "menu", "menu", "显示部门管理菜单"),
    ("departments:page", "部门管理页面", "departments", "page", "page", "访问部门管理页面"),
    ("departments:read", "查看部门", "departments", "read", "api", "查询部门组织树"),
    ("departments:create", "创建部门", "departments", "create", "api", "创建组织部门"),
    ("departments:update", "编辑部门", "departments", "update", "api", "修改部门信息"),
    ("departments:delete", "删除部门", "departments", "delete", "api", "删除空部门"),
    ("roles:menu", "角色管理菜单", "roles", "menu", "menu", "显示角色管理菜单"),
    ("roles:page", "角色管理页面", "roles", "page", "page", "访问角色管理页面"),
    ("roles:read", "查看角色", "roles", "read", "api", "查询角色和权限目录"),
    ("roles:create", "创建角色", "roles", "create", "api", "创建自定义角色"),
    ("roles:update", "编辑角色", "roles", "update", "api", "修改自定义角色"),
    ("roles:delete", "删除角色", "roles", "delete", "api", "删除未分配的自定义角色"),
    (
        "roles:assign_permissions",
        "配置角色权限",
        "roles",
        "assign_permissions",
        "api",
        "配置自定义角色权限",
    ),
    (
        "roles:assign_system",
        "分配系统管理员",
        "roles",
        "assign_system",
        "api",
        "授予系统管理员角色",
    ),
    ("permissions:read", "查看权限目录", "permissions", "read", "api", "查询权限目录"),
)

MANAGER_PERMISSIONS = (
    "dashboard:menu",
    "dashboard:page",
    "users:menu",
    "users:page",
    "users:read",
    "departments:menu",
    "departments:page",
    "departments:read",
    "roles:menu",
    "roles:page",
    "roles:read",
    "permissions:read",
)
EMPLOYEE_PERMISSIONS = ("dashboard:menu", "dashboard:page")


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.ForeignKeyConstraint(["parent_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "name", name="uq_departments_parent_name"),
    )
    op.create_index("ix_departments_parent_id", "departments", ["parent_id"], unique=False)
    op.create_index(
        "uq_departments_root_name",
        "departments",
        ["name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
        sqlite_where=sa.text("parent_id IS NULL"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("data_scope", sa.String(length=20), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        sa.CheckConstraint(
            "data_scope IN ('self', 'department', 'subtree', 'all')", name="ck_roles_data_scope"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("permission_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "permission_type IN ('menu', 'page', 'api')", name="ck_permissions_type"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_resource", "permissions", ["resource"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_index(
        "ix_role_permissions_permission_id", "role_permissions", ["permission_id"], unique=False
    )
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_users_department_id_departments",
                "departments",
                ["department_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    else:
        op.create_foreign_key(
            "fk_users_department_id_departments",
            "users",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    permissions_rows = [
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
        permissions_rows,
    )

    role_definitions = (
        ("system_admin", "系统管理员", "管理所有组织、账号和权限配置。", "all"),
        (
            "department_manager",
            "部门主管",
            "查看本部门及下属部门的用户、组织和角色配置。",
            "subtree",
        ),
        ("employee", "普通员工", "访问工作台，不具备组织和账号管理权限。", "self"),
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
                "id": _id(f"role:{code}"),
                "name": name,
                "code": code,
                "description": description,
                "data_scope": scope,
                "is_system": True,
            }
            for code, name, description, scope in role_definitions
        ],
    )

    permission_codes = {code for code, *_ in PERMISSIONS}
    role_grants = {
        "system_admin": permission_codes,
        "department_manager": set(MANAGER_PERMISSIONS),
        "employee": set(EMPLOYEE_PERMISSIONS),
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
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_users_department_id_departments", type_="foreignkey")
    else:
        op.drop_constraint("fk_users_department_id_departments", "users", type_="foreignkey")
    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_permissions_resource", table_name="permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index("uq_departments_root_name", table_name="departments")
    op.drop_index("ix_departments_parent_id", table_name="departments")
    op.drop_table("departments")
    op.drop_column("users", "auth_version")
