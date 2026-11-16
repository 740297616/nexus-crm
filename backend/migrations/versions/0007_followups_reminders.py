"""Add customer follow-up records and reminders.

Revision ID: 0007_followups_reminders
Revises: 0006_customer_excel_io
Create Date: 2026-11-16
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0007_followups_reminders"
down_revision: str | None = "0006_customer_excel_io"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("follow_ups:menu", "跟进记录菜单", "follow_ups", "menu", "menu", "显示跟进记录入口"),
    ("follow_ups:page", "跟进记录页面", "follow_ups", "page", "page", "访问跟进记录页面"),
    ("follow_ups:read", "查看跟进记录", "follow_ups", "read", "api", "查看客户跟进记录"),
    ("follow_ups:create", "创建跟进记录", "follow_ups", "create", "api", "创建客户跟进记录"),
    ("follow_ups:update", "编辑跟进记录", "follow_ups", "update", "api", "编辑客户跟进记录"),
    ("reminders:menu", "提醒菜单", "reminders", "menu", "menu", "显示提醒入口"),
    ("reminders:page", "提醒页面", "reminders", "page", "page", "访问提醒页面"),
    ("reminders:read", "查看提醒", "reminders", "read", "api", "查看个人和范围内提醒"),
    ("reminders:create", "创建提醒", "reminders", "create", "api", "创建提醒"),
    ("reminders:update", "编辑提醒", "reminders", "update", "api", "编辑待办提醒"),
    ("reminders:complete", "完成提醒", "reminders", "complete", "api", "完成待办提醒"),
    ("reminders:cancel", "取消提醒", "reminders", "cancel", "api", "取消待办提醒"),
)


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"nexus-crm:{value}"))


def upgrade() -> None:
    op.create_table(
        "follow_up_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("followed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("result", sa.String(length=2000), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
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
            "method IN ('phone', 'visit', 'wechat', 'email', 'other')",
            name="ck_follow_up_records_method",
        ),
        sa.CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_follow_up_records_content_not_blank",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_follow_up_records_customer_time",
        "follow_up_records",
        ["customer_id", "followed_at"],
    )
    op.create_index(
        "ix_follow_up_records_user_time", "follow_up_records", ["user_id", "followed_at"]
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("follow_up_record_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_reminders_status",
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_reminders_title_not_blank"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["follow_up_record_id"], ["follow_up_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reminders_user_status_time", "reminders", ["user_id", "status", "remind_at"]
    )
    op.create_index("ix_reminders_customer_time", "reminders", ["customer_id", "remind_at"])

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
    role_grants = {
        "system_admin": {code for code, *_ in PERMISSIONS},
        "sales_manager": {code for code, *_ in PERMISSIONS},
        "sales": {
            "follow_ups:menu",
            "follow_ups:page",
            "follow_ups:read",
            "follow_ups:create",
            "follow_ups:update",
            "reminders:menu",
            "reminders:page",
            "reminders:read",
            "reminders:create",
            "reminders:update",
            "reminders:complete",
            "reminders:cancel",
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
    role_permissions = sa.table("role_permissions", sa.column("permission_id", sa.String))
    connection.execute(
        sa.delete(role_permissions).where(role_permissions.c.permission_id.in_(permission_ids))
    )
    permissions = sa.table("permissions", sa.column("id", sa.String))
    connection.execute(sa.delete(permissions).where(permissions.c.id.in_(permission_ids)))

    op.drop_index("ix_reminders_customer_time", table_name="reminders")
    op.drop_index("ix_reminders_user_status_time", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("ix_follow_up_records_user_time", table_name="follow_up_records")
    op.drop_index("ix_follow_up_records_customer_time", table_name="follow_up_records")
    op.drop_table("follow_up_records")
