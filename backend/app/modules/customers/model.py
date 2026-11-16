from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.auth.model import User
    from app.modules.organizations.model import Department


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("customer_no", name="uq_customers_customer_no"),
        CheckConstraint("level IN ('A', 'B', 'C', 'D')", name="ck_customers_level"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        Index("ix_customers_owner_status", "owner_id", "status"),
        Index("ix_customers_department_status", "department_id", "status"),
        Index("ix_customers_name", "name"),
        Index("ix_customers_deleted_at", "deleted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_no: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[str] = mapped_column(String(1), nullable=False, default="C", server_default="C")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="CURRENT_TIMESTAMP",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default="CURRENT_TIMESTAMP",
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    department: Mapped["Department"] = relationship("Department")
    ownership_history: Mapped[list["CustomerOwnershipHistory"]] = relationship(
        "CustomerOwnershipHistory",
        back_populates="customer",
        order_by="CustomerOwnershipHistory.created_at.desc()",
        passive_deletes=True,
    )


class CustomerOwnershipHistory(Base):
    __tablename__ = "customer_ownership_history"
    __table_args__ = (
        CheckConstraint("action IN ('assigned', 'transferred')", name="ck_customer_history_action"),
        Index("ix_customer_ownership_history_customer_created", "customer_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    previous_department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    new_owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    new_department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    transferred_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="CURRENT_TIMESTAMP",
        nullable=False,
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="ownership_history")
