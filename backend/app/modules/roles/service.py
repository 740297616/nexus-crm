from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.common.audit import add_audit_log
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.roles.catalog import PERMISSION_CATALOG, ROLE_CATALOG
from app.modules.roles.model import Permission, Role
from app.modules.roles.repository import get_permission_codes_for_user
from app.modules.roles.schema import RoleCreate, RolePermissionsUpdate, RoleUpdate


def seed_default_rbac(db: Session) -> None:
    permissions: dict[str, Permission] = {}
    for definition in PERMISSION_CATALOG:
        permission = db.scalar(select(Permission).where(Permission.code == definition.code))
        if permission is None:
            permission = Permission(id=str(uuid4()), **definition.__dict__)
            db.add(permission)
        permissions[definition.code] = permission
    db.flush()

    for code, definition in ROLE_CATALOG.items():
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(
                id=str(uuid4()),
                code=code,
                name=definition["name"],
                description=definition["description"],
                data_scope=definition["data_scope"],
                is_system=True,
            )
            db.add(role)
            db.flush()
        existing_codes = {permission.code for permission in role.permissions}
        for permission_code in definition["permission_codes"]:
            if permission_code not in existing_codes:
                role.permissions.append(permissions[permission_code])
    db.commit()


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException("DUPLICATE_RESOURCE", "角色名称或代码已存在", status_code=409) from exc


def list_roles(db: Session) -> list[Role]:
    statement = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    return list(db.scalars(statement).all())


def list_permissions(db: Session) -> list[Permission]:
    return list(
        db.scalars(select(Permission).order_by(Permission.resource, Permission.action)).all()
    )


def get_role(db: Session, role_id: str) -> Role | None:
    statement = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    return db.scalar(statement)


def create_role(
    db: Session,
    *,
    payload: RoleCreate,
    actor: User,
    request_id: str,
) -> Role:
    permissions = list(
        db.scalars(select(Permission).where(Permission.code.in_(payload.permission_codes))).all()
    )
    if len(permissions) != len(set(payload.permission_codes)) or len(
        payload.permission_codes
    ) != len(set(payload.permission_codes)):
        raise AppException("BUSINESS_RULE_VIOLATION", "权限列表包含未知权限", status_code=422)
    if any(
        permission.code == "roles:assign_system" for permission in permissions
    ) and "roles:assign_system" not in get_permission_codes_for_user(db, actor.id):
        raise AppException("PERMISSION_DENIED", "不能授予系统管理员分配权限", status_code=403)
    role = Role(
        id=str(uuid4()),
        name=payload.name,
        code=payload.code,
        description=payload.description,
        data_scope=payload.data_scope,
        permissions=permissions,
    )
    db.add(role)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="role_created",
        resource_type="role",
        resource_id=role.id,
        request_id=request_id,
        after_data={"code": role.code, "permission_codes": payload.permission_codes},
    )
    _commit(db)
    return role


def update_role(
    db: Session,
    *,
    role_id: str,
    payload: RoleUpdate,
    actor: User,
    request_id: str,
) -> Role:
    role = get_role(db, role_id)
    if role is None:
        raise AppException("RESOURCE_NOT_FOUND", "角色不存在", status_code=404)
    if role.is_system:
        raise AppException("BUSINESS_RULE_VIOLATION", "系统角色不可修改", status_code=422)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is None:
        raise AppException("VALIDATION_ERROR", "角色名称不能为空", status_code=400)
    before = {key: getattr(role, key) for key in updates}
    for key, value in updates.items():
        setattr(role, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="role_updated",
        resource_type="role",
        resource_id=role.id,
        request_id=request_id,
        before_data=before,
        after_data=updates,
    )
    _commit(db)
    return role


def update_role_permissions(
    db: Session,
    *,
    role_id: str,
    payload: RolePermissionsUpdate,
    actor: User,
    request_id: str,
) -> Role:
    role = get_role(db, role_id)
    if role is None:
        raise AppException("RESOURCE_NOT_FOUND", "角色不存在", status_code=404)
    if role.is_system:
        raise AppException("BUSINESS_RULE_VIOLATION", "系统角色的权限不可修改", status_code=422)
    permissions = list(
        db.scalars(select(Permission).where(Permission.code.in_(payload.permission_codes))).all()
    )
    if len(permissions) != len(set(payload.permission_codes)) or len(
        payload.permission_codes
    ) != len(set(payload.permission_codes)):
        raise AppException("BUSINESS_RULE_VIOLATION", "权限列表包含未知权限", status_code=422)
    if (
        "roles:assign_system" in payload.permission_codes
        and "roles:assign_system" not in get_permission_codes_for_user(db, actor.id)
    ):
        raise AppException("PERMISSION_DENIED", "不能授予系统管理员分配权限", status_code=403)
    before_codes = sorted(permission.code for permission in role.permissions)
    role.permissions = permissions
    add_audit_log(
        db,
        actor_id=actor.id,
        action="role_permissions_changed",
        resource_type="role",
        resource_id=role.id,
        request_id=request_id,
        before_data={"permission_codes": before_codes},
        after_data={"permission_codes": sorted(payload.permission_codes)},
    )
    _commit(db)
    return role


def delete_role(db: Session, *, role_id: str, actor: User, request_id: str) -> None:
    role = get_role(db, role_id)
    if role is None:
        raise AppException("RESOURCE_NOT_FOUND", "角色不存在", status_code=404)
    if role.is_system:
        raise AppException("BUSINESS_RULE_VIOLATION", "系统角色不可删除", status_code=422)
    if role.users:
        raise AppException("BUSINESS_RULE_VIOLATION", "角色仍分配给用户，不能删除", status_code=422)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="role_deleted",
        resource_type="role",
        resource_id=role.id,
        request_id=request_id,
        before_data={"code": role.code, "name": role.name},
    )
    db.delete(role)
    _commit(db)


def role_response(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "data_scope": role.data_scope,
        "is_system": role.is_system,
        "permission_codes": sorted(permission.code for permission in role.permissions),
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


def permission_response(permission: Permission) -> dict:
    return {
        "id": permission.id,
        "code": permission.code,
        "name": permission.name,
        "resource": permission.resource,
        "action": permission.action,
        "permission_type": permission.permission_type,
        "description": permission.description,
    }
