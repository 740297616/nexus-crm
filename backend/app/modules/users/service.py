from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.auth.repository import revoke_user_refresh_tokens
from app.modules.auth.security import hash_password
from app.modules.organizations.repository import get_department_ids_in_subtree
from app.modules.roles.repository import (
    get_effective_data_scope,
    get_permission_codes_for_user,
    get_role_codes_for_user,
)
from app.modules.users.repository import get_roles, get_user, list_users
from app.modules.users.schema import UserCreate, UserStatusUpdate, UserUpdate


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException("DUPLICATE_RESOURCE", "用户名或邮箱已存在", status_code=409) from exc


def _visible_user_scope(db: Session, actor: User) -> tuple[set[str] | None, str | None]:
    scope = get_effective_data_scope(db, actor.id)
    if scope == "all":
        return None, None
    if scope == "self" or actor.department_id is None:
        return None, actor.id
    if scope == "subtree":
        return get_department_ids_in_subtree(db, actor.department_id), None
    return {actor.department_id}, None


def _assert_department_scope(db: Session, actor: User, department_id: str | None) -> None:
    scope = get_effective_data_scope(db, actor.id)
    if scope == "all":
        return
    if department_id is None:
        raise AppException("DATA_SCOPE_DENIED", "只能管理授权部门中的用户", status_code=403)
    if scope == "subtree":
        permitted = (
            get_department_ids_in_subtree(db, actor.department_id) if actor.department_id else set()
        )
    else:
        permitted = {actor.department_id} if actor.department_id else set()
    if department_id not in permitted:
        raise AppException("DATA_SCOPE_DENIED", "超出部门数据范围", status_code=403)


def list_users_for_actor(
    db: Session,
    *,
    actor: User,
    search: str | None,
    department_id: str | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    visible_ids, self_user_id = _visible_user_scope(db, actor)
    if department_id is not None and visible_ids is not None and department_id not in visible_ids:
        raise AppException("DATA_SCOPE_DENIED", "超出部门数据范围", status_code=403)
    items, total = list_users(
        db,
        search=search,
        department_id=department_id,
        visible_department_ids=visible_ids,
        self_user_id=self_user_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return items, total


def get_user_for_actor(db: Session, *, actor: User, user_id: str) -> User:
    visible_ids, self_user_id = _visible_user_scope(db, actor)
    user = get_user(db, user_id)
    if user is None:
        raise AppException("RESOURCE_NOT_FOUND", "用户不存在", status_code=404)
    if self_user_id is not None and user.id != self_user_id:
        raise AppException("RESOURCE_NOT_FOUND", "用户不存在", status_code=404)
    if visible_ids is not None and user.department_id not in visible_ids:
        raise AppException("RESOURCE_NOT_FOUND", "用户不存在", status_code=404)
    return user


def create_user(
    db: Session,
    *,
    payload: UserCreate,
    actor: User,
    request_id: str,
) -> User:
    _assert_department_scope(db, actor, payload.department_id)
    if payload.department_id is not None:
        from app.modules.organizations.repository import get_department

        department = get_department(db, payload.department_id)
        if department is None or not department.is_active:
            raise AppException("RESOURCE_NOT_FOUND", "部门不存在或已停用", status_code=404)
    roles = get_roles(db, payload.role_ids)
    if len(roles) != len(set(payload.role_ids)) or len(payload.role_ids) != len(
        set(payload.role_ids)
    ):
        raise AppException("BUSINESS_RULE_VIOLATION", "角色列表包含未知角色", status_code=422)
    actor_permissions = get_permission_codes_for_user(db, actor.id)
    if "users:assign_roles" not in actor_permissions:
        raise AppException("PERMISSION_DENIED", "没有分配用户角色的权限", status_code=403)
    if (
        any(role.code == "system_admin" for role in roles)
        and "roles:assign_system" not in actor_permissions
    ):
        raise AppException(
            "PERMISSION_DENIED", "只有系统管理员可以分配系统管理员角色", status_code=403
        )

    user = User(
        id=str(uuid4()),
        username=payload.username,
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        department_id=payload.department_id,
        status="active",
        roles=roles,
    )
    db.add(user)
    db.flush()
    add_audit_log(
        db,
        actor_id=actor.id,
        action="user_created",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        after_data={
            "username": user.username,
            "department_id": user.department_id,
            "role_codes": [r.code for r in roles],
        },
    )
    _commit(db)
    return get_user(db, user.id) or user


def update_user(
    db: Session,
    *,
    user_id: str,
    payload: UserUpdate,
    actor: User,
    request_id: str,
) -> User:
    user = get_user_for_actor(db, actor=actor, user_id=user_id)
    updates = payload.model_dump(exclude_unset=True)
    if "department_id" in updates:
        _assert_department_scope(db, actor, updates["department_id"])
        if updates["department_id"] is not None:
            from app.modules.organizations.repository import get_department

            department = get_department(db, updates["department_id"])
            if department is None or not department.is_active:
                raise AppException("RESOURCE_NOT_FOUND", "部门不存在或已停用", status_code=404)
    before = {key: getattr(user, key) for key in updates}
    for key, value in updates.items():
        setattr(user, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="user_updated",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        before_data=before,
        after_data=updates,
    )
    _commit(db)
    return get_user(db, user.id) or user


def set_user_status(
    db: Session,
    *,
    user_id: str,
    payload: UserStatusUpdate,
    actor: User,
    request_id: str,
) -> User:
    user = get_user_for_actor(db, actor=actor, user_id=user_id)
    if payload.status == "disabled":
        if user.id == actor.id:
            raise AppException("BUSINESS_RULE_VIOLATION", "不能禁用当前登录账号", status_code=422)
        target_is_system_admin = "system_admin" in get_role_codes_for_user(db, user.id)
        if target_is_system_admin and "roles:assign_system" not in get_permission_codes_for_user(
            db, actor.id
        ):
            raise AppException(
                "PERMISSION_DENIED", "只有系统管理员可以停用系统管理员账号", status_code=403
            )
        if target_is_system_admin:
            from sqlalchemy import select

            from app.modules.auth.model import User as UserModel
            from app.modules.roles.model import Role as RoleModel

            other_admin = db.scalar(
                select(UserModel.id)
                .join(UserModel.roles)
                .where(
                    RoleModel.code == "system_admin",
                    UserModel.status == "active",
                    UserModel.id != user.id,
                )
                .limit(1)
            )
            if not other_admin:
                raise AppException(
                    "BUSINESS_RULE_VIOLATION", "至少保留一个启用的系统管理员", status_code=422
                )
    before_status = user.status
    user.status = payload.status
    if payload.status == "disabled":
        user.auth_version += 1
        revoke_user_refresh_tokens(db, user.id)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="user_disabled" if payload.status == "disabled" else "user_enabled",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        before_data={"status": before_status},
        after_data={"status": payload.status},
    )
    _commit(db)
    return get_user(db, user.id) or user


def update_user_roles(
    db: Session,
    *,
    user_id: str,
    role_ids: list[str],
    actor: User,
    request_id: str,
) -> User:
    user = get_user_for_actor(db, actor=actor, user_id=user_id)
    roles = get_roles(db, role_ids)
    if len(roles) != len(set(role_ids)) or len(role_ids) != len(set(role_ids)):
        raise AppException("BUSINESS_RULE_VIOLATION", "角色列表包含未知角色", status_code=422)
    actor_permissions = get_permission_codes_for_user(db, actor.id)
    current_role_codes = get_role_codes_for_user(db, user.id)
    if (
        any(role.code == "system_admin" for role in roles)
        and "roles:assign_system" not in actor_permissions
    ):
        raise AppException(
            "PERMISSION_DENIED", "只有系统管理员可以分配系统管理员角色", status_code=403
        )
    if "system_admin" in current_role_codes and "roles:assign_system" not in actor_permissions:
        raise AppException(
            "PERMISSION_DENIED", "只有系统管理员可以修改系统管理员角色", status_code=403
        )
    if "system_admin" in current_role_codes and not any(
        role.code == "system_admin" for role in roles
    ):
        from sqlalchemy import select

        from app.modules.auth.model import User as UserModel
        from app.modules.roles.model import Role as RoleModel

        other_admins = db.scalar(
            select(UserModel.id)
            .join(UserModel.roles)
            .where(
                RoleModel.code == "system_admin",
                UserModel.status == "active",
                UserModel.id != user.id,
            )
            .limit(1)
        )
        if not other_admins:
            raise AppException(
                "BUSINESS_RULE_VIOLATION", "至少保留一个启用的系统管理员", status_code=422
            )
    before_codes = sorted(current_role_codes)
    user.roles = roles
    add_audit_log(
        db,
        actor_id=actor.id,
        action="user_roles_changed",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        before_data={"role_codes": before_codes},
        after_data={"role_codes": sorted(role.code for role in roles)},
    )
    _commit(db)
    return get_user(db, user.id) or user


def user_response(db: Session, user: User) -> dict:
    from app.modules.roles.repository import get_role_codes_for_user

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "status": user.status,
        "role_codes": get_role_codes_for_user(db, user.id),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
