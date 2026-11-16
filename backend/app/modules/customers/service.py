from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.common.data_scope import DataScopeContext, data_scope_service
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.customers.model import Customer, CustomerOwnershipHistory
from app.modules.customers.repository import (
    add_customer,
    add_ownership_history,
    customer_no_exists,
    find_name_duplicates,
    get_active_owner,
    get_customer,
    list_assignable_users,
    list_customers,
    list_ownership_history,
)
from app.modules.customers.schema import (
    CustomerAssign,
    CustomerCreate,
    CustomerListFilters,
    CustomerTransfer,
    CustomerUpdate,
)
from app.modules.roles.repository import get_permission_codes_for_user


def _scope(db: Session, actor: User) -> DataScopeContext:
    return data_scope_service.resolve(db, actor)


def _actor_has_permission(db: Session, actor: User, permission_code: str) -> bool:
    return permission_code in get_permission_codes_for_user(db, actor.id)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            "DUPLICATE_RESOURCE", "客户编号已存在或客户数据与现有记录冲突", status_code=409
        ) from exc


def _resolve_owner(
    db: Session,
    *,
    actor: User,
    scope: DataScopeContext,
    owner_id: str,
) -> User:
    owner = get_active_owner(db, owner_id)
    if owner is None or owner.department is None or not owner.department.is_active:
        raise AppException("RESOURCE_NOT_FOUND", "负责人不存在或不可用", status_code=404)
    data_scope_service.assert_department_access(scope, owner.department_id)
    return owner


def list_customers_for_actor(
    db: Session,
    *,
    actor: User,
    filters: CustomerListFilters,
    page: int,
    page_size: int,
) -> tuple[list[Customer], int]:
    scope = _scope(db, actor)
    if filters.department_id:
        data_scope_service.assert_department_access(scope, filters.department_id)
    if filters.owner_id:
        owner = get_active_owner(db, filters.owner_id)
        if owner is None:
            raise AppException("RESOURCE_NOT_FOUND", "负责人不存在", status_code=404)
        if not scope.is_unrestricted:
            data_scope_service.assert_department_access(scope, owner.department_id)
    return list_customers(
        db,
        scope=scope,
        filters=filters,
        offset=(page - 1) * page_size,
        limit=page_size,
    )


def get_customer_for_actor(db: Session, *, actor: User, customer_id: str) -> Customer:
    customer = get_customer(db, customer_id, scope=_scope(db, actor))
    if customer is None:
        raise AppException("RESOURCE_NOT_FOUND", "客户不存在", status_code=404)
    return customer


def get_customer_detail_for_actor(db: Session, *, actor: User, customer_id: str) -> dict:
    customer = get_customer_for_actor(db, actor=actor, customer_id=customer_id)
    return customer_response(
        db,
        customer,
        ownership_history=list_ownership_history(db, customer.id),
    )


def create_customer(
    db: Session,
    *,
    payload: CustomerCreate,
    actor: User,
    request_id: str,
) -> Customer:
    if customer_no_exists(db, payload.customer_no):
        raise AppException("DUPLICATE_RESOURCE", "客户编号已存在", status_code=409)

    owner_id = payload.owner_id or actor.id
    if owner_id != actor.id and not _actor_has_permission(db, actor, "customers:assign"):
        raise AppException("PERMISSION_DENIED", "没有为他人分配客户的权限", status_code=403)
    scope = _scope(db, actor)
    owner = _resolve_owner(db, actor=actor, scope=scope, owner_id=owner_id)
    customer = Customer(
        id=str(uuid4()),
        customer_no=payload.customer_no,
        name=payload.name,
        owner_id=owner.id,
        department_id=owner.department_id,
        source=payload.source,
        industry=payload.industry,
        level=payload.level,
        status=payload.status,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        description=payload.description,
        created_by=actor.id,
    )
    add_customer(db, customer)
    if owner.id != actor.id:
        add_ownership_history(
            db,
            CustomerOwnershipHistory(
                id=str(uuid4()),
                customer_id=customer.id,
                action="assigned",
                new_owner_id=owner.id,
                new_department_id=owner.department_id,
                transferred_by=actor.id,
                reason="客户创建时指定负责人",
            ),
        )
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customer_created",
        resource_type="customer",
        resource_id=customer.id,
        request_id=request_id,
        after_data=_customer_audit_data(customer),
    )
    _commit(db)
    return get_customer(db, customer.id, scope=scope) or customer


def update_customer(
    db: Session,
    *,
    customer_id: str,
    payload: CustomerUpdate,
    actor: User,
    request_id: str,
) -> Customer:
    customer = get_customer(db, customer_id, scope=_scope(db, actor), for_update=True)
    if customer is None:
        raise AppException("RESOURCE_NOT_FOUND", "客户不存在", status_code=404)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and not updates["name"]:
        raise AppException("VALIDATION_ERROR", "客户名称不能为空", status_code=400)
    before = {key: getattr(customer, key) for key in updates}
    for key, value in updates.items():
        setattr(customer, key, value)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customer_updated",
        resource_type="customer",
        resource_id=customer.id,
        request_id=request_id,
        before_data=_customer_change_audit_data(before),
        after_data=_customer_change_audit_data(updates),
    )
    _commit(db)
    return get_customer(db, customer.id, scope=_scope(db, actor)) or customer


def soft_delete_customer(
    db: Session,
    *,
    customer_id: str,
    actor: User,
    request_id: str,
) -> None:
    customer = get_customer(db, customer_id, scope=_scope(db, actor), for_update=True)
    if customer is None:
        raise AppException("RESOURCE_NOT_FOUND", "客户不存在", status_code=404)
    customer.deleted_at = datetime.now(UTC)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customer_deleted",
        resource_type="customer",
        resource_id=customer.id,
        request_id=request_id,
        before_data=_customer_audit_data(customer),
        after_data={"deleted": True},
    )
    _commit(db)


def assign_customer(
    db: Session,
    *,
    customer_id: str,
    payload: CustomerAssign,
    actor: User,
    request_id: str,
) -> Customer:
    return _change_owner(
        db,
        customer_id=customer_id,
        owner_id=payload.owner_id,
        reason=payload.reason,
        action="assigned",
        actor=actor,
        request_id=request_id,
    )


def transfer_customer(
    db: Session,
    *,
    customer_id: str,
    payload: CustomerTransfer,
    actor: User,
    request_id: str,
) -> Customer:
    return _change_owner(
        db,
        customer_id=customer_id,
        owner_id=payload.owner_id,
        reason=payload.reason,
        action="transferred",
        actor=actor,
        request_id=request_id,
    )


def _change_owner(
    db: Session,
    *,
    customer_id: str,
    owner_id: str,
    reason: str | None,
    action: str,
    actor: User,
    request_id: str,
) -> Customer:
    scope = _scope(db, actor)
    customer = get_customer(db, customer_id, scope=scope, for_update=True)
    if customer is None:
        raise AppException("RESOURCE_NOT_FOUND", "客户不存在", status_code=404)
    owner = _resolve_owner(db, actor=actor, scope=scope, owner_id=owner_id)
    if customer.owner_id == owner.id and customer.department_id == owner.department_id:
        raise AppException("BUSINESS_RULE_VIOLATION", "客户已由该负责人负责", status_code=422)

    previous_owner_id = customer.owner_id
    previous_department_id = customer.department_id
    customer.owner_id = owner.id
    customer.department_id = owner.department_id
    add_ownership_history(
        db,
        CustomerOwnershipHistory(
            id=str(uuid4()),
            customer_id=customer.id,
            action=action,
            previous_owner_id=previous_owner_id,
            previous_department_id=previous_department_id,
            new_owner_id=owner.id,
            new_department_id=owner.department_id,
            transferred_by=actor.id,
            reason=reason,
        ),
    )
    add_audit_log(
        db,
        actor_id=actor.id,
        action=f"customer_{action}",
        resource_type="customer",
        resource_id=customer.id,
        request_id=request_id,
        before_data={
            "owner_id": previous_owner_id,
            "department_id": previous_department_id,
        },
        after_data={
            "owner_id": owner.id,
            "department_id": owner.department_id,
        },
    )
    _commit(db)
    return get_customer(db, customer.id, scope=_scope(db, actor)) or customer


def check_customer_name(
    db: Session,
    *,
    actor: User,
    name: str,
    exclude_id: str | None = None,
) -> dict:
    matches, count = find_name_duplicates(
        db,
        name=name.strip(),
        scope=_scope(db, actor),
        exclude_id=exclude_id,
    )
    return {
        "has_duplicates": count > 0,
        "matches": [
            {
                "id": customer.id,
                "customer_no": customer.customer_no,
                "name": customer.name,
                "owner_name": customer.owner.display_name,
            }
            for customer in matches
        ],
    }


def list_assignable_users_for_actor(db: Session, *, actor: User) -> list[User]:
    return list_assignable_users(db, scope=_scope(db, actor))


def customer_response(
    db: Session,
    customer: Customer,
    *,
    ownership_history: list[dict] | None = None,
) -> dict:
    response = {
        "id": customer.id,
        "customer_no": customer.customer_no,
        "name": customer.name,
        "owner_id": customer.owner_id,
        "owner_name": customer.owner.display_name,
        "department_id": customer.department_id,
        "department_name": customer.department.name,
        "source": customer.source,
        "industry": customer.industry,
        "level": customer.level,
        "status": customer.status,
        "phone": customer.phone,
        "email": customer.email,
        "address": customer.address,
        "description": customer.description,
        "created_by": customer.created_by,
        "created_by_name": customer.creator.display_name,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
    }
    if ownership_history is not None:
        response["ownership_history"] = ownership_history
    return response


def _customer_audit_data(customer: Customer) -> dict:
    return {
        "customer_no": customer.customer_no,
        "name": customer.name,
        "owner_id": customer.owner_id,
        "department_id": customer.department_id,
        "source": customer.source,
        "industry": customer.industry,
        "level": customer.level,
        "status": customer.status,
        "phone": _mask_phone(customer.phone),
        "email": _mask_email(customer.email),
    }


def _customer_change_audit_data(changes: dict) -> dict:
    allowed_fields = {
        "name",
        "source",
        "industry",
        "level",
        "status",
        "phone",
        "email",
        "address",
        "description",
    }
    result = {"changed_fields": sorted(changes.keys())}
    for key, value in changes.items():
        if key not in allowed_fields:
            continue
        if key == "phone":
            result[key] = _mask_phone(value)
        elif key == "email":
            result[key] = _mask_email(value)
        elif key not in {"address", "description"}:
            result[key] = value
    return result


def _mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = "".join(character for character in value if character.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


def _mask_email(value: str | None) -> str | None:
    if not value:
        return value
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    return f"{local[:1]}***@{domain}"
