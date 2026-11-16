from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.audit import add_audit_log
from app.common.data_scope import DataScopeContext, data_scope_service
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.customers.excel import (
    ExcelParseError,
    build_customer_export,
    parse_customer_workbook,
)
from app.modules.customers.model import Customer, CustomerOwnershipHistory
from app.modules.customers.repository import (
    add_customer,
    add_ownership_history,
    customer_no_exists,
    existing_customer_name_keys,
    existing_customer_nos,
    find_name_duplicates,
    get_active_owner,
    get_active_owner_by_identifier,
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

    scope = _scope(db, actor)
    customer, owner = _build_customer_record(
        db,
        payload=payload,
        actor=actor,
        scope=scope,
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


def import_customers_from_excel(
    db: Session,
    *,
    actor: User,
    filename: str,
    content: bytes,
    request_id: str,
) -> dict:
    settings = get_settings()
    try:
        workbook = parse_customer_workbook(
            content,
            max_rows=settings.customer_import_max_rows,
        )
    except ExcelParseError as exc:
        raise AppException(
            exc.code,
            str(exc),
            status_code=413 if exc.code == "FILE_TOO_LARGE" else 400,
            details=exc.details,
        ) from exc

    errors: list[dict] = []
    warnings: list[dict] = []
    error_count = 0
    warning_count = 0
    report_limit = 1000

    def add_error(issue: dict) -> None:
        nonlocal error_count
        error_count += 1
        if len(errors) < report_limit:
            errors.append(issue)

    def add_warning(issue: dict) -> None:
        nonlocal warning_count
        warning_count += 1
        if len(warnings) < report_limit:
            warnings.append(issue)

    for header in workbook.ignored_headers:
        add_warning(
            _import_issue(
                row=1,
                field=header,
                code="UNSUPPORTED_COLUMN",
                message="未识别的列已忽略",
                value=header,
                severity="warning",
            )
        )

    scope = _scope(db, actor)
    candidates: list[tuple[int, CustomerCreate, str | None]] = []
    for row in workbook.rows:
        if row.formula_fields:
            add_error(
                _import_issue(
                    row=row.row_number,
                    field=", ".join(row.formula_fields),
                    code="FORMULA_NOT_ALLOWED",
                    message="不允许导入公式或可能触发公式执行的内容",
                    severity="error",
                )
            )
            continue
        values = row.values
        try:
            payload = CustomerCreate(
                customer_no=values.get("customer_no"),
                name=values.get("name"),
                source=values.get("source"),
                industry=values.get("industry"),
                level=values.get("level") or "C",
                status=values.get("status") or "active",
                phone=values.get("phone"),
                email=values.get("email"),
                address=values.get("address"),
                description=values.get("description"),
            )
        except ValidationError as exc:
            for detail in exc.errors():
                field = str(detail.get("loc", ["row"])[-1])
                add_error(
                    _import_issue(
                        row=row.row_number,
                        field=field,
                        code="FIELD_INVALID",
                        message=str(detail.get("msg", "字段值无效")),
                        value=_report_value(values.get(field)),
                        severity="error",
                    )
                )
            continue
        candidates.append(
            (row.row_number, payload, _optional_identifier(values.get("owner_username")))
        )

    existing_nos = existing_customer_nos(db, {payload.customer_no for _, payload, _ in candidates})
    existing_names = existing_customer_name_keys(
        db,
        name_keys={payload.name.casefold() for _, payload, _ in candidates},
        scope=scope,
    )
    seen_nos: set[str] = set()
    seen_names: set[str] = set()
    valid_candidates: list[tuple[int, CustomerCreate, User]] = []
    for row_number, payload, owner_identifier in candidates:
        if payload.customer_no in existing_nos or payload.customer_no in seen_nos:
            add_error(
                _import_issue(
                    row=row_number,
                    field="customer_no",
                    code="DUPLICATE_CUSTOMER_NO",
                    message="客户编号已存在或在本文件中重复",
                    value=payload.customer_no,
                    severity="error",
                )
            )
            continue
        seen_nos.add(payload.customer_no)

        name_key = payload.name.casefold()
        if name_key in existing_names or name_key in seen_names:
            add_warning(
                _import_issue(
                    row=row_number,
                    field="name",
                    code="DUPLICATE_CUSTOMER_NAME",
                    message="客户名称与已有或本次导入的客户重复，请后续人工确认",
                    value=payload.name,
                    severity="warning",
                )
            )
        seen_names.add(name_key)

        try:
            owner = _resolve_import_owner(
                db,
                actor=actor,
                scope=scope,
                identifier=owner_identifier,
            )
        except AppException as exc:
            add_error(
                _import_issue(
                    row=row_number,
                    field="owner_username",
                    code=exc.code,
                    message=exc.message,
                    value=owner_identifier,
                    severity="error",
                )
            )
            continue
        valid_candidates.append((row_number, payload, owner))

    imported_rows = 0
    for start in range(0, len(valid_candidates), settings.customer_import_batch_size):
        batch = valid_candidates[start : start + settings.customer_import_batch_size]
        try:
            _persist_import_batch(
                db,
                actor=actor,
                batch=batch,
                request_id=request_id,
                filename=filename,
            )
            imported_rows += len(batch)
        except IntegrityError:
            db.rollback()
            for row_number, payload, owner in batch:
                try:
                    customer = _build_customer_from_owner(payload, actor=actor, owner=owner)
                    db.add(customer)
                    _add_assignment_history_if_needed(
                        db,
                        customer=customer,
                        owner=owner,
                        actor=actor,
                    )
                    db.commit()
                    imported_rows += 1
                except IntegrityError:
                    db.rollback()
                    add_error(
                        _import_issue(
                            row=row_number,
                            field="customer_no",
                            code="DUPLICATE_CUSTOMER_NO",
                            message="客户编号在写入时发生冲突，请重试",
                            value=payload.customer_no,
                            severity="error",
                        )
                    )

    return {
        "filename": filename,
        "total_rows": len(workbook.rows),
        "imported_rows": imported_rows,
        "skipped_rows": len(workbook.rows) - imported_rows,
        "error_count": error_count,
        "warning_count": warning_count,
        "errors": errors,
        "warnings": warnings,
    }


def export_customers_for_actor(
    db: Session,
    *,
    actor: User,
    filters: CustomerListFilters,
    request_id: str,
) -> tuple[bytes, int]:
    settings = get_settings()
    items, total = list_customers_for_actor(
        db,
        actor=actor,
        filters=filters,
        page=1,
        page_size=settings.customer_export_max_rows,
    )
    if total > settings.customer_export_max_rows:
        raise AppException(
            "FILE_TOO_LARGE",
            f"导出记录超过上限（最多 {settings.customer_export_max_rows} 条）",
            status_code=413,
            details={"total": total, "max_rows": settings.customer_export_max_rows},
        )
    content = build_customer_export(items)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customers_exported",
        resource_type="customer_export",
        resource_id=request_id,
        request_id=request_id,
        after_data={
            "row_count": total,
            "filters": filters.model_dump(mode="json", exclude_none=True),
        },
    )
    db.commit()
    return content, total


def _build_customer_record(
    db: Session,
    *,
    payload: CustomerCreate,
    actor: User,
    scope: DataScopeContext,
) -> tuple[Customer, User]:
    owner_id = payload.owner_id or actor.id
    if owner_id != actor.id and not _actor_has_permission(db, actor, "customers:assign"):
        raise AppException("PERMISSION_DENIED", "没有为他人分配客户的权限", status_code=403)
    owner = _resolve_owner(db, actor=actor, scope=scope, owner_id=owner_id)
    return _build_customer_from_owner(payload, actor=actor, owner=owner), owner


def _build_customer_from_owner(payload: CustomerCreate, *, actor: User, owner: User) -> Customer:
    return Customer(
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


def _resolve_import_owner(
    db: Session,
    *,
    actor: User,
    scope: DataScopeContext,
    identifier: str | None,
) -> User:
    if identifier is None:
        return _resolve_owner(db, actor=actor, scope=scope, owner_id=actor.id)
    owner = get_active_owner_by_identifier(db, identifier)
    if owner is None or owner.department is None or not owner.department.is_active:
        raise AppException("RESOURCE_NOT_FOUND", "负责人不存在或不可用", status_code=404)
    if owner.id != actor.id and not _actor_has_permission(db, actor, "customers:assign"):
        raise AppException("PERMISSION_DENIED", "没有为他人分配客户的权限", status_code=403)
    data_scope_service.assert_department_access(scope, owner.department_id)
    return owner


def _persist_import_batch(
    db: Session,
    *,
    actor: User,
    batch: list[tuple[int, CustomerCreate, User]],
    request_id: str,
    filename: str,
) -> None:
    for _row_number, payload, owner in batch:
        customer = _build_customer_from_owner(payload, actor=actor, owner=owner)
        db.add(customer)
        _add_assignment_history_if_needed(db, customer=customer, owner=owner, actor=actor)
    add_audit_log(
        db,
        actor_id=actor.id,
        action="customers_imported",
        resource_type="customer_import",
        resource_id=request_id,
        request_id=request_id,
        after_data={"row_count": len(batch), "filename": filename},
    )
    db.commit()


def _add_assignment_history_if_needed(
    db: Session,
    *,
    customer: Customer,
    owner: User,
    actor: User,
) -> None:
    if owner.id == actor.id:
        return
    add_ownership_history(
        db,
        CustomerOwnershipHistory(
            id=str(uuid4()),
            customer_id=customer.id,
            action="assigned",
            new_owner_id=owner.id,
            new_department_id=owner.department_id,
            transferred_by=actor.id,
            reason="Excel 导入时指定负责人",
        ),
    )


def _import_issue(
    *,
    row: int,
    field: str | None,
    code: str,
    message: str,
    severity: str,
    value: object | None = None,
) -> dict:
    return {
        "row": row,
        "field": field,
        "code": code,
        "message": message,
        "value": _report_value(value),
        "severity": severity,
    }


def _optional_identifier(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _report_value(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)[:200]


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
