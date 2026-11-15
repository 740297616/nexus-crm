from uuid import uuid4

import pytest
from app.modules.auth.model import User
from app.modules.auth.security import hash_password
from app.modules.organizations.model import Department
from app.modules.roles.model import Permission, Role
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def rbac_identities(db_session: Session) -> dict[str, User | Department]:
    root = Department(id=str(uuid4()), name="总部", is_active=True)
    child = Department(id=str(uuid4()), name="华东部", parent=root, is_active=True)
    db_session.add_all([root, child])
    db_session.flush()

    roles = {role.code: role for role in db_session.scalars(select(Role)).all()}
    admin = User(
        id=str(uuid4()),
        username="rbac-admin",
        email="rbac-admin@example.com",
        password_hash=hash_password("AdminPassword123!"),
        display_name="系统管理员",
        status="active",
        roles=[roles["system_admin"]],
    )
    manager = User(
        id=str(uuid4()),
        username="rbac-manager",
        email="rbac-manager@example.com",
        password_hash=hash_password("ManagerPassword123!"),
        display_name="部门主管",
        department=root,
        status="active",
        roles=[roles["department_manager"]],
    )
    employee = User(
        id=str(uuid4()),
        username="rbac-employee",
        email="rbac-employee@example.com",
        password_hash=hash_password("EmployeePassword123!"),
        display_name="普通员工",
        department=child,
        status="active",
        roles=[roles["employee"]],
    )
    db_session.add_all([admin, manager, employee])
    db_session.commit()
    return {
        "admin": admin,
        "manager": manager,
        "employee": employee,
        "root": root,
        "child": child,
    }


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_three_roles_have_distinct_menu_and_api_permissions(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    admin_token = login(client, "rbac-admin", "AdminPassword123!")
    manager_token = login(client, "rbac-manager", "ManagerPassword123!")
    employee_token = login(client, "rbac-employee", "EmployeePassword123!")

    admin_me = client.get("/api/v1/auth/me", headers=bearer(admin_token)).json()["data"]
    manager_me = client.get("/api/v1/auth/me", headers=bearer(manager_token)).json()["data"]
    employee_me = client.get("/api/v1/auth/me", headers=bearer(employee_token)).json()["data"]

    assert "system_admin" in admin_me["role_codes"]
    assert admin_me["data_scope"] == "all"
    assert {"users:menu", "departments:menu", "roles:menu"} <= set(admin_me["permission_codes"])
    assert "users:create" in admin_me["permission_codes"]

    assert "department_manager" in manager_me["role_codes"]
    assert manager_me["data_scope"] == "subtree"
    assert {"users:menu", "departments:menu", "roles:menu"} <= set(manager_me["permission_codes"])
    assert "users:create" not in manager_me["permission_codes"]

    assert "employee" in employee_me["role_codes"]
    assert employee_me["data_scope"] == "self"
    assert {"dashboard:menu", "dashboard:page"} <= set(employee_me["permission_codes"])
    assert not {"users:menu", "departments:menu", "roles:menu"} & set(
        employee_me["permission_codes"]
    )

    assert client.get("/api/v1/users", headers=bearer(admin_token)).status_code == 200
    assert client.get("/api/v1/users", headers=bearer(manager_token)).status_code == 200
    assert client.get("/api/v1/users", headers=bearer(employee_token)).status_code == 403
    assert client.get("/api/v1/roles", headers=bearer(employee_token)).status_code == 403


def test_department_manager_user_list_is_scoped_to_department_subtree(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    token = login(client, "rbac-manager", "ManagerPassword123!")
    response = client.get("/api/v1/users", headers=bearer(token))

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()["data"]["items"]}
    assert usernames == {"rbac-manager", "rbac-employee"}

    denied = client.get(f"/api/v1/users/{rbac_identities['admin'].id}", headers=bearer(token))
    assert denied.status_code == 404


def test_system_admin_can_create_users_and_department_but_employee_cannot(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    admin_token = login(client, "rbac-admin", "AdminPassword123!")
    employee_token = login(client, "rbac-employee", "EmployeePassword123!")
    employee_role = rbac_identities["employee"].roles[0]

    denied = client.post(
        "/api/v1/departments",
        json={"name": "无权创建"},
        headers=bearer(employee_token),
    )
    assert denied.status_code == 403

    department = client.post(
        "/api/v1/departments", json={"name": "产品部"}, headers=bearer(admin_token)
    )
    assert department.status_code == 201
    department_id = department.json()["data"]["id"]

    created = client.post(
        "/api/v1/users",
        headers=bearer(admin_token),
        json={
            "username": "created-employee",
            "email": "created-employee@example.com",
            "display_name": "新员工",
            "password": "NewEmployeePassword123!",
            "department_id": department_id,
            "role_ids": [employee_role.id],
        },
    )
    assert created.status_code == 201
    assert created.json()["data"]["role_codes"] == ["employee"]


def test_user_creation_cannot_be_used_to_bypass_role_assignment_permission(
    client: TestClient,
    db_session: Session,
    rbac_identities: dict[str, User | Department],
) -> None:
    create_only = Role(
        id=str(uuid4()),
        name="Account Creator",
        code="account_creator",
        data_scope="all",
        is_system=False,
        permissions=[
            db_session.scalar(select(Permission).where(Permission.code == "users:create"))
        ],
    )
    actor = rbac_identities["employee"]
    actor.roles = [create_only]
    db_session.commit()
    token = login(client, "rbac-employee", "EmployeePassword123!")
    employee_role = db_session.scalar(select(Role).where(Role.code == "employee"))

    response = client.post(
        "/api/v1/users",
        headers=bearer(token),
        json={
            "username": "privilege-escalation-attempt",
            "display_name": "Privilege Escalation",
            "password": "NewEmployeePassword123!",
            "role_ids": [employee_role.id],
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_custom_role_permission_configuration_and_system_role_protection(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    token = login(client, "rbac-admin", "AdminPassword123!")
    permissions = client.get("/api/v1/permissions", headers=bearer(token))
    assert permissions.status_code == 200
    permission_codes = {permission["code"] for permission in permissions.json()["data"]["items"]}
    assert {"users:menu", "users:page", "users:read"} <= permission_codes
    permission_types = {
        item["code"]: item["permission_type"] for item in permissions.json()["data"]["items"]
    }
    assert permission_types["users:menu"] == "menu"
    assert permission_types["users:page"] == "page"
    assert permission_types["users:read"] == "api"
    permission_id = next(
        item["id"] for item in permissions.json()["data"]["items"] if item["code"] == "users:read"
    )

    created = client.post(
        "/api/v1/roles",
        headers=bearer(token),
        json={"name": "只读审计员", "code": "read_only_auditor", "data_scope": "all"},
    )
    assert created.status_code == 201
    role = created.json()["data"]
    configured = client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=bearer(token),
        json={"permission_codes": ["users:read"]},
    )
    assert configured.status_code == 200
    assert configured.json()["data"]["permission_codes"] == ["users:read"]

    system_admin = rbac_identities["admin"].roles[0]
    forbidden = client.put(
        f"/api/v1/roles/{system_admin.id}/permissions",
        headers=bearer(token),
        json={"permission_codes": ["dashboard:page"]},
    )
    assert forbidden.status_code == 422

    unknown = client.post(
        "/api/v1/roles",
        headers=bearer(token),
        json={
            "name": "无效权限角色",
            "code": "invalid_permission_role",
            "permission_codes": ["not-a-real-permission"],
        },
    )
    assert unknown.status_code == 422
    assert permission_id

    deleted = client.delete(f"/api/v1/roles/{role['id']}", headers=bearer(token))
    assert deleted.status_code == 200
    protected_delete = client.delete(f"/api/v1/roles/{system_admin.id}", headers=bearer(token))
    assert protected_delete.status_code == 422


def test_department_cycle_is_rejected(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    token = login(client, "rbac-admin", "AdminPassword123!")
    root = rbac_identities["root"]
    child = rbac_identities["child"]
    response = client.patch(
        f"/api/v1/departments/{root.id}",
        headers=bearer(token),
        json={"parent_id": child.id},
    )
    assert response.status_code == 422


def test_disabling_user_revokes_refresh_token_and_blocks_access(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    admin_token = login(client, "rbac-admin", "AdminPassword123!")
    employee = rbac_identities["employee"]
    employee_tokens_response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "rbac-employee", "password": "EmployeePassword123!"},
    )
    tokens = employee_tokens_response.json()["data"]

    disabled = client.patch(
        f"/api/v1/users/{employee.id}/status",
        headers=bearer(admin_token),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == "disabled"
    assert client.get("/api/v1/auth/me", headers=bearer(tokens["access_token"])).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    reenabled = client.patch(
        f"/api/v1/users/{employee.id}/status",
        headers=bearer(admin_token),
        json={"status": "active"},
    )
    assert reenabled.status_code == 200
    old_access = client.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))
    assert old_access.status_code == 401
    assert old_access.json()["error"]["code"] == "TOKEN_INVALID"


def test_last_system_admin_cannot_disable_themselves(
    client: TestClient, rbac_identities: dict[str, User | Department]
) -> None:
    admin = rbac_identities["admin"]
    token = login(client, "rbac-admin", "AdminPassword123!")
    response = client.patch(
        f"/api/v1/users/{admin.id}/status",
        headers=bearer(token),
        json={"status": "disabled"},
    )
    assert response.status_code == 422


def test_non_system_admin_cannot_disable_system_admin_even_with_user_disable_permission(
    client: TestClient,
    db_session: Session,
    rbac_identities: dict[str, User | Department],
) -> None:
    manager = rbac_identities["manager"]
    disable_permission = db_session.scalar(
        select(Permission).where(Permission.code == "users:disable")
    )
    manager.roles[0].permissions.append(disable_permission)
    second_admin_role = db_session.scalar(select(Role).where(Role.code == "system_admin"))
    second_admin = User(
        id=str(uuid4()),
        username="second-system-admin",
        email="second-admin@example.com",
        password_hash=hash_password("SecondAdminPassword123!"),
        display_name="Second Admin",
        department_id=manager.department_id,
        status="active",
        roles=[second_admin_role],
    )
    db_session.add(second_admin)
    db_session.commit()
    manager_token = login(client, "rbac-manager", "ManagerPassword123!")

    response = client.patch(
        f"/api/v1/users/{second_admin.id}/status",
        headers=bearer(manager_token),
        json={"status": "disabled"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
