from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.organizations.model import Department
from app.modules.organizations.repository import (
    department_user_count,
    get_department,
    get_department_ids_in_subtree,
    list_departments,
)
from app.modules.organizations.schema import DepartmentCreate, DepartmentUpdate
from app.modules.roles.repository import get_effective_data_scope


def visible_department_ids(db: Session, current_user: User) -> set[str] | None:
    scope = get_effective_data_scope(db, current_user.id)
    if scope == "all":
        return None
    if current_user.department_id is None:
        return set()
    if scope == "subtree":
        return get_department_ids_in_subtree(db, current_user.department_id)
    return {current_user.department_id}


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException("DUPLICATE_RESOURCE", "部门名称已存在", status_code=409) from exc


def _assert_no_cycle(db: Session, department_id: str, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if department_id == parent_id or parent_id in get_department_ids_in_subtree(db, department_id):
        raise AppException(
            "BUSINESS_RULE_VIOLATION", "部门不能移动到自身或其下属部门", status_code=422
        )


def _assert_sibling_name_available(
    db: Session,
    *,
    name: str,
    parent_id: str | None,
    exclude_id: str | None = None,
) -> None:
    statement = select(Department.id).where(Department.name == name)
    statement = statement.where(
        Department.parent_id.is_(None) if parent_id is None else Department.parent_id == parent_id
    )
    if exclude_id is not None:
        statement = statement.where(Department.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise AppException("DUPLICATE_RESOURCE", "同级部门名称已存在", status_code=409)


def create_department(
    db: Session,
    *,
    payload: DepartmentCreate,
    actor: User,
    request_id: str,
) -> Department:
    _assert_sibling_name_available(db, name=payload.name, parent_id=payload.parent_id)
    if payload.parent_id and get_department(db, payload.parent_id) is None:
        raise AppException("RESOURCE_NOT_FOUND", "上级部门不存在", status_code=404)
    department = Department(id=str(uuid4()), **payload.model_dump())
    db.add(department)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="department_created",
        resource_type="department",
        resource_id=department.id,
        request_id=request_id,
        after_data={"name": department.name, "parent_id": department.parent_id},
    )
    _commit(db)
    return department


def update_department(
    db: Session,
    *,
    department_id: str,
    payload: DepartmentUpdate,
    actor: User,
    request_id: str,
) -> Department:
    department = get_department(db, department_id)
    if department is None:
        raise AppException("RESOURCE_NOT_FOUND", "部门不存在", status_code=404)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is None:
        raise AppException("VALIDATION_ERROR", "部门名称不能为空", status_code=400)
    next_name = updates.get("name", department.name)
    next_parent_id = updates.get("parent_id", department.parent_id)
    if "name" in updates or "parent_id" in updates:
        _assert_sibling_name_available(
            db,
            name=next_name,
            parent_id=next_parent_id,
            exclude_id=department.id,
        )
    if "parent_id" in updates:
        _assert_no_cycle(db, department_id, updates["parent_id"])
        if updates["parent_id"] and get_department(db, updates["parent_id"]) is None:
            raise AppException("RESOURCE_NOT_FOUND", "上级部门不存在", status_code=404)
    before = {key: getattr(department, key) for key in updates}
    for key, value in updates.items():
        setattr(department, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="department_updated",
        resource_type="department",
        resource_id=department.id,
        request_id=request_id,
        before_data=before,
        after_data=updates,
    )
    _commit(db)
    return department


def delete_department(db: Session, *, department_id: str, actor: User, request_id: str) -> None:
    department = get_department(db, department_id)
    if department is None:
        raise AppException("RESOURCE_NOT_FOUND", "部门不存在", status_code=404)
    has_children = db.scalar(
        select(Department.id).where(Department.parent_id == department_id).limit(1)
    )
    if has_children or department_user_count(db, department_id):
        raise AppException("BUSINESS_RULE_VIOLATION", "部门仍包含下级部门或用户", status_code=422)
    db.delete(department)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="department_deleted",
        resource_type="department",
        resource_id=department.id,
        request_id=request_id,
        before_data={"name": department.name, "parent_id": department.parent_id},
    )
    _commit(db)


def list_visible_departments(db: Session, current_user: User) -> list[Department]:
    visible_ids = visible_department_ids(db, current_user)
    departments = list_departments(db)
    if visible_ids is None:
        return departments
    return [department for department in departments if department.id in visible_ids]
