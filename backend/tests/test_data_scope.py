from uuid import uuid4

import pytest
from app.common.data_scope import DataScope, DataScopeContext, data_scope_service
from app.core.exceptions import AppException
from app.modules.auth.model import User
from app.modules.auth.security import hash_password
from app.modules.organizations.model import Department
from app.modules.roles.model import Role
from app.modules.users.repository import get_user
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.fixture
def scope_identities(db_session: Session) -> dict[str, User | Department | list[str]]:
    root = Department(id=str(uuid4()), name="范围总部")
    child = Department(id=str(uuid4()), name="范围子部门", parent=root)
    sibling = Department(id=str(uuid4()), name="范围兄弟部门")
    db_session.add_all([root, child, sibling])

    roles = {
        scope: Role(
            id=str(uuid4()),
            name=f"范围角色-{scope}",
            code=f"scope_{scope}",
            data_scope=scope,
            is_system=False,
        )
        for scope in ("all", "department", "subtree", "self")
    }
    db_session.add_all(roles.values())
    db_session.flush()

    actors = {
        "all": User(
            id=str(uuid4()),
            username="scope-all",
            password_hash=hash_password("ScopePassword123!"),
            display_name="全部范围用户",
            department=root,
            roles=[roles["all"]],
        ),
        "department": User(
            id=str(uuid4()),
            username="scope-department",
            password_hash=hash_password("ScopePassword123!"),
            display_name="本部门范围用户",
            department=root,
            roles=[roles["department"]],
        ),
        "subtree": User(
            id=str(uuid4()),
            username="scope-subtree",
            password_hash=hash_password("ScopePassword123!"),
            display_name="下属范围用户",
            department=root,
            roles=[roles["subtree"]],
        ),
        "self": User(
            id=str(uuid4()),
            username="scope-self",
            password_hash=hash_password("ScopePassword123!"),
            display_name="本人范围用户",
            department=root,
            roles=[roles["self"]],
        ),
    }
    resources = [
        User(
            id=str(uuid4()),
            username="resource-root",
            password_hash="unused",
            display_name="总部资源",
            department=root,
        ),
        User(
            id=str(uuid4()),
            username="resource-child",
            password_hash="unused",
            display_name="子部门资源",
            department=child,
        ),
        User(
            id=str(uuid4()),
            username="resource-sibling",
            password_hash="unused",
            display_name="兄弟部门资源",
            department=sibling,
        ),
    ]
    db_session.add_all([*actors.values(), *resources])
    db_session.commit()
    return {
        **actors,
        "root": root,
        "child": child,
        "sibling": sibling,
        "resources": [resource.id for resource in resources],
    }


def _resource_ids(identity: dict[str, User | Department | list[str]]) -> list[str]:
    return list(identity["resources"])  # type: ignore[arg-type]


def _scoped_ids(
    db: Session,
    actor: User,
    resource_ids: list[str],
) -> set[str]:
    context = data_scope_service.resolve(db, actor)
    statement = select(User).where(User.id.in_(resource_ids))
    statement = data_scope_service.apply(statement, context, User, owner_field="id")
    return {record.id for record in db.scalars(statement).all()}


def test_all_four_scopes_filter_list_detail_statistic_and_export_queries(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    resource_ids = _resource_ids(scope_identities)
    assert _scoped_ids(db_session, scope_identities["all"], resource_ids) == set(resource_ids)  # type: ignore[arg-type]
    assert _scoped_ids(db_session, scope_identities["department"], resource_ids) == {
        resource_ids[0]
    }  # type: ignore[arg-type]
    assert _scoped_ids(db_session, scope_identities["subtree"], resource_ids) == {
        resource_ids[0],
        resource_ids[1],
    }  # type: ignore[arg-type]
    assert _scoped_ids(db_session, scope_identities["self"], resource_ids) == set()  # type: ignore[arg-type]

    context = data_scope_service.resolve(db_session, scope_identities["department"])  # type: ignore[arg-type]
    detail = db_session.get(User, resource_ids[1])
    with pytest.raises(AppException) as denied:
        data_scope_service.assert_access(detail, context, owner_field="id")
    assert denied.value.code == "RESOURCE_NOT_FOUND"

    base = select(User.id).where(User.id.in_(resource_ids))
    count_query = select(func.count()).select_from(User).where(User.id.in_(resource_ids))
    scoped_count = data_scope_service.apply(count_query, context, User, owner_field="id")
    assert db_session.scalar(scoped_count) == 1

    export_query = data_scope_service.apply(base, context, User, owner_field="id")
    assert set(db_session.scalars(export_query).all()) == {resource_ids[0]}


def test_self_scope_blocks_id_enumeration_through_scoped_repository(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    actor = scope_identities["self"]
    resource_ids = _resource_ids(scope_identities)
    context = data_scope_service.resolve(db_session, actor)  # type: ignore[arg-type]
    assert get_user(db_session, resource_ids[0], scope=context) is None


def test_effective_scope_uses_the_widest_role_and_accepts_design_aliases() -> None:
    assert data_scope_service.effective_scope({"self", "department"}) is DataScope.DEPARTMENT
    assert (
        data_scope_service.effective_scope({"SELF", "DEPARTMENT_AND_CHILDREN"})
        is DataScope.DEPARTMENT_AND_CHILDREN
    )
    assert DataScope.from_value("ALL") is DataScope.ALL
    assert DataScope.from_value("department_and_children") is DataScope.DEPARTMENT_AND_CHILDREN


def test_user_inherits_the_widest_scope_from_multiple_roles(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    actor = scope_identities["self"]
    department_role = db_session.scalar(select(Role).where(Role.code == "scope_department"))
    actor.roles.append(department_role)  # type: ignore[union-attr]
    db_session.commit()

    context = data_scope_service.resolve(db_session, actor)  # type: ignore[arg-type]
    assert context.scope is DataScope.DEPARTMENT


def test_department_move_recomputes_subtree_visibility(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    actor = scope_identities["subtree"]
    sibling = scope_identities["sibling"]
    resource_ids = _resource_ids(scope_identities)

    before = _scoped_ids(db_session, actor, resource_ids)  # type: ignore[arg-type]
    assert resource_ids[0] in before and resource_ids[1] in before

    actor.department_id = sibling.id  # type: ignore[union-attr]
    db_session.commit()
    after = _scoped_ids(db_session, actor, resource_ids)  # type: ignore[arg-type]
    assert after == {resource_ids[2]}


def test_department_scope_checks_department_targets(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    actor = scope_identities["department"]
    root = scope_identities["root"]
    child = scope_identities["child"]
    context = data_scope_service.resolve(db_session, actor)  # type: ignore[arg-type]
    data_scope_service.assert_department_access(context, root.id)  # type: ignore[union-attr]
    with pytest.raises(AppException) as denied:
        data_scope_service.assert_department_access(context, child.id)  # type: ignore[union-attr]
    assert denied.value.code == "DATA_SCOPE_DENIED"


def test_scope_context_is_explicit_and_stable(
    db_session: Session,
    scope_identities: dict[str, User | Department | list[str]],
) -> None:
    context = data_scope_service.resolve(db_session, scope_identities["subtree"])  # type: ignore[arg-type]
    assert isinstance(context, DataScopeContext)
    assert context.scope is DataScope.DEPARTMENT_AND_CHILDREN
    assert context.department_ids == frozenset(
        {scope_identities["root"].id, scope_identities["child"].id}  # type: ignore[union-attr]
    )
