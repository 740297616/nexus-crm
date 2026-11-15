"""Shared data-scope resolution and resource filtering.

The CRM modules use the same four scope values.  The persisted values remain
compatible with the project baseline (``all``, ``department``, ``subtree``
and ``self``), while the enum exposes the business names used in design
documents.  Resource repositories should call :meth:`DataScopeService.apply`
for every list, detail, write, aggregate and export query.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import Select, false, select, true
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.organizations.model import Department
from app.modules.roles.model import Role


class DataScope(StrEnum):
    """Canonical persisted values for role data scope."""

    SELF = "self"
    DEPARTMENT = "department"
    DEPARTMENT_AND_CHILDREN = "subtree"
    ALL = "all"

    @classmethod
    def from_value(cls, value: str | DataScope) -> DataScope:
        if isinstance(value, cls):
            return value
        aliases = {
            "SELF": cls.SELF,
            "DEPARTMENT": cls.DEPARTMENT,
            "DEPARTMENT_AND_CHILDREN": cls.DEPARTMENT_AND_CHILDREN,
            "SUBTREE": cls.DEPARTMENT_AND_CHILDREN,
            "ALL": cls.ALL,
            "department_and_children": cls.DEPARTMENT_AND_CHILDREN,
        }
        try:
            return cls(value)
        except ValueError:
            try:
                return aliases[value]
            except KeyError as exc:
                raise ValueError(f"Unsupported data scope: {value}") from exc


_SCOPE_PRIORITY: tuple[DataScope, ...] = (
    DataScope.ALL,
    DataScope.DEPARTMENT_AND_CHILDREN,
    DataScope.DEPARTMENT,
    DataScope.SELF,
)


@dataclass(frozen=True)
class DataScopeContext:
    """Effective scope for one authenticated user.

    ``department_ids`` is ``None`` for an unrestricted user.  For department
    and subtree scopes it contains the departments a resource may belong to.
    Self scope deliberately leaves it empty because ownership, rather than a
    department, is the governing condition.
    """

    user_id: str
    department_id: str | None
    scope: DataScope
    department_ids: frozenset[str] | None

    @property
    def scope_code(self) -> str:
        return self.scope.value

    @property
    def is_unrestricted(self) -> bool:
        return self.scope is DataScope.ALL

    def organization_department_ids(self) -> frozenset[str] | None:
        """Return departments visible when the resource itself is a department."""

        if self.scope is DataScope.ALL:
            return None
        if self.scope is DataScope.SELF:
            return frozenset({self.department_id}) if self.department_id else frozenset()
        return self.department_ids or frozenset()


class DataScopeService:
    """Resolve role scopes and apply one consistent resource predicate."""

    def get_effective_scope(self, db: Session, user: User | str) -> DataScope:
        return self.resolve(db, user).scope

    def get_effective_data_scope(self, db: Session, user: User | str) -> str:
        return self.resolve(db, user).scope_code

    def resolve(self, db: Session, user: User | str) -> DataScopeContext:
        user_id = user.id if isinstance(user, User) else user
        if isinstance(user, User):
            department_id = user.department_id
        else:
            department_id = db.scalar(select(User.department_id).where(User.id == user_id))
        if department_id is None and db.scalar(select(User.id).where(User.id == user_id)) is None:
            raise AppException("AUTH_REQUIRED", "用户不存在", status_code=401)

        role_scopes = db.scalars(
            select(Role.data_scope).select_from(User).join(User.roles).where(User.id == user_id)
        ).all()
        effective_scope = self.effective_scope(role_scopes)
        department_ids: frozenset[str] | None
        if effective_scope is DataScope.ALL:
            department_ids = None
        elif effective_scope is DataScope.DEPARTMENT_AND_CHILDREN:
            department_ids = frozenset(self._department_ids_in_subtree(db, department_id))
        elif effective_scope is DataScope.DEPARTMENT:
            department_ids = frozenset({department_id}) if department_id else frozenset()
        else:
            department_ids = frozenset()
        return DataScopeContext(
            user_id=user_id,
            department_id=department_id,
            scope=effective_scope,
            department_ids=department_ids,
        )

    @staticmethod
    def effective_scope(scopes: list[str] | tuple[str, ...] | set[str]) -> DataScope:
        normalized = {DataScope.from_value(scope) for scope in scopes}
        for candidate in _SCOPE_PRIORITY:
            if candidate in normalized:
                return candidate
        return DataScope.SELF

    @staticmethod
    def _department_ids_in_subtree(db: Session, root_id: str | None) -> set[str]:
        if root_id is None:
            return set()
        rows = db.execute(select(Department.id, Department.parent_id)).all()
        children: dict[str, list[str]] = {}
        for department_id, parent_id in rows:
            if parent_id is not None:
                children.setdefault(parent_id, []).append(department_id)
        result = {root_id}
        pending = [root_id]
        while pending:
            current = pending.pop()
            for child_id in children.get(current, []):
                if child_id not in result:
                    result.add(child_id)
                    pending.append(child_id)
        return result

    @staticmethod
    def _column(model: type[Any], field_name: str | None) -> Any:
        if field_name is None:
            return None
        return getattr(model, field_name, None)

    def condition(
        self,
        context: DataScopeContext,
        model: type[Any],
        *,
        owner_field: str | None = "owner_id",
        department_field: str | None = "department_id",
        creator_field: str | None = None,
    ) -> Any:
        """Build the SQL condition for a resource model.

        ``owner_field`` and ``creator_field`` are OR-ed for self scope.  A
        module may pass ``owner_field=None`` when a resource has no owner; the
        resulting predicate is false instead of accidentally returning all
        rows.
        """

        if context.scope is DataScope.ALL:
            return true()
        if context.scope is DataScope.SELF:
            ownership_columns = [
                column
                for column in (
                    self._column(model, owner_field),
                    self._column(model, creator_field),
                )
                if column is not None
            ]
            return _or_equal(ownership_columns, context.user_id) if ownership_columns else false()
        department_column = self._column(model, department_field)
        if department_column is None or not context.department_ids:
            return false()
        return department_column.in_(context.department_ids)

    def apply(
        self,
        statement: Select[Any],
        context: DataScopeContext,
        model: type[Any],
        *,
        owner_field: str | None = "owner_id",
        department_field: str | None = "department_id",
        creator_field: str | None = None,
    ) -> Select[Any]:
        """Apply the scope predicate to a SELECT statement."""

        return statement.where(
            self.condition(
                context,
                model,
                owner_field=owner_field,
                department_field=department_field,
                creator_field=creator_field,
            )
        )

    def can_access(
        self,
        record: Any,
        context: DataScopeContext,
        *,
        owner_field: str | None = "owner_id",
        department_field: str | None = "department_id",
        creator_field: str | None = None,
    ) -> bool:
        if context.scope is DataScope.ALL:
            return True
        if context.scope is DataScope.SELF:
            return any(
                getattr(record, field_name, None) == context.user_id
                for field_name in (owner_field, creator_field)
                if field_name is not None
            )
        if department_field is None:
            return False
        return getattr(record, department_field, None) in (context.department_ids or frozenset())

    def assert_access(
        self,
        record: Any | None,
        context: DataScopeContext,
        *,
        owner_field: str | None = "owner_id",
        department_field: str | None = "department_id",
        creator_field: str | None = None,
        message: str = "资源不存在",
    ) -> Any:
        """Return a visible record or hide an out-of-scope resource as 404."""

        if record is None or not self.can_access(
            record,
            context,
            owner_field=owner_field,
            department_field=department_field,
            creator_field=creator_field,
        ):
            raise AppException("RESOURCE_NOT_FOUND", message, status_code=404)
        return record

    def assert_department_access(
        self, context: DataScopeContext, department_id: str | None
    ) -> None:
        if context.scope is DataScope.ALL:
            return
        if department_id is None or department_id not in context.organization_department_ids():
            raise AppException("DATA_SCOPE_DENIED", "超出部门数据范围", status_code=403)


def _or_equal(columns: list[Any], value: str) -> Any:
    expression = columns[0] == value
    for column in columns[1:]:
        expression = expression | (column == value)
    return expression


data_scope_service = DataScopeService()


def get_scope_context(db: Session, user: User | str) -> DataScopeContext:
    """Functional entry point for modules that do not need the service object."""

    return data_scope_service.resolve(db, user)


def apply_data_scope(
    statement: Select[Any],
    context: DataScopeContext,
    model: type[Any],
    **kwargs: Any,
) -> Select[Any]:
    return data_scope_service.apply(statement, context, model, **kwargs)
