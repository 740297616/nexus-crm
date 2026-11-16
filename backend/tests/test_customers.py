from uuid import uuid4

import pytest
from app.modules.auth.model import AuditLog, User
from app.modules.auth.security import hash_password
from app.modules.customers.model import Customer, CustomerOwnershipHistory
from app.modules.organizations.model import Department
from app.modules.roles.model import Role
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def customer_identities(db_session: Session) -> dict[str, User | Department]:
    root = Department(id=str(uuid4()), name="客户范围总部", is_active=True)
    child = Department(id=str(uuid4()), name="客户范围一部", parent=root, is_active=True)
    outside = Department(id=str(uuid4()), name="客户范围外部", is_active=True)
    db_session.add_all([root, child, outside])
    db_session.flush()
    roles = {role.code: role for role in db_session.scalars(select(Role)).all()}

    identities = {
        "admin": User(
            id=str(uuid4()),
            username="customer-admin",
            password_hash=hash_password("CustomerAdmin123!"),
            display_name="CRM 管理员",
            department=root,
            roles=[roles["system_admin"]],
            status="active",
        ),
        "manager": User(
            id=str(uuid4()),
            username="customer-manager",
            password_hash=hash_password("CustomerManager123!"),
            display_name="销售主管",
            department=root,
            roles=[roles["sales_manager"]],
            status="active",
        ),
        "alice": User(
            id=str(uuid4()),
            username="customer-alice",
            password_hash=hash_password("CustomerAlice123!"),
            display_name="Alice 销售",
            department=child,
            roles=[roles["sales"]],
            status="active",
        ),
        "bob": User(
            id=str(uuid4()),
            username="customer-bob",
            password_hash=hash_password("CustomerBob123!"),
            display_name="Bob 销售",
            department=child,
            roles=[roles["sales"]],
            status="active",
        ),
        "eve": User(
            id=str(uuid4()),
            username="customer-eve",
            password_hash=hash_password("CustomerEve123!"),
            display_name="Eve 外部销售",
            department=outside,
            roles=[roles["sales"]],
            status="active",
        ),
    }
    db_session.add_all(identities.values())
    db_session.commit()
    return {**identities, "root": root, "child": child, "outside": outside}


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_customer(
    client: TestClient,
    token: str,
    customer_no: str,
    name: str,
    **fields: object,
) -> dict:
    response = client.post(
        "/api/v1/customers",
        headers=_headers(token),
        json={"customer_no": customer_no, "name": name, **fields},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_customer_crud_filters_permissions_and_soft_delete(
    client: TestClient,
    db_session: Session,
    customer_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")
    admin_token = _login(client, "customer-admin", "CustomerAdmin123!")

    created = _create_customer(
        client,
        alice_token,
        " acme-001 ",
        " Acme North ",
        source="referral",
        industry="software",
        level="A",
        phone="+852 1234 5678",
        description="Initial account",
    )
    assert created["customer_no"] == "ACME-001"
    assert created["created_by"] == created["owner_id"] == customer_identities["alice"].id

    updated = client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=_headers(alice_token),
        json={"status": "inactive", "description": "On hold"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "inactive"

    invalid_email = client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=_headers(alice_token),
        json={"email": "not-an-email"},
    )
    assert invalid_email.status_code == 400
    null_status = client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=_headers(alice_token),
        json={"status": None},
    )
    assert null_status.status_code == 400

    filtered = client.get(
        "/api/v1/customers?search=acme&industry=software&level=A&status=inactive&page=1&page_size=1",
        headers=_headers(alice_token),
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 1
    assert len(filtered.json()["data"]["items"]) == 1

    removed = client.delete(f"/api/v1/customers/{created['id']}", headers=_headers(admin_token))
    assert removed.status_code == 200
    assert removed.json()["data"]["status"] == "deleted"
    assert (
        client.get(f"/api/v1/customers/{created['id']}", headers=_headers(admin_token)).status_code
        == 404
    )
    assert (
        client.get("/api/v1/customers", headers=_headers(admin_token)).json()["data"]["total"] == 0
    )

    stored = db_session.get(Customer, created["id"])
    assert stored is not None and stored.deleted_at is not None
    audit_actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.resource_id == created["id"])
        ).all()
    )
    assert {"customer_created", "customer_updated", "customer_deleted"} <= audit_actions


def test_customer_no_is_normalized_and_globally_unique_including_soft_deleted(
    client: TestClient,
    customer_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")
    admin_token = _login(client, "customer-admin", "CustomerAdmin123!")
    customer = _create_customer(client, alice_token, "Unique-100", "Unique Customer")

    duplicate = client.post(
        "/api/v1/customers",
        headers=_headers(admin_token),
        json={"customer_no": "unique-100", "name": "Different Name"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_RESOURCE"

    deleted = client.delete(f"/api/v1/customers/{customer['id']}", headers=_headers(alice_token))
    assert deleted.status_code == 403
    deleted_by_admin = client.delete(
        f"/api/v1/customers/{customer['id']}", headers=_headers(admin_token)
    )
    assert deleted_by_admin.status_code == 200

    reused = client.post(
        "/api/v1/customers",
        headers=_headers(admin_token),
        json={"customer_no": "UNIQUE-100", "name": "Reused Number"},
    )
    assert reused.status_code == 409


def test_customer_creation_keeps_creator_separate_from_assigned_owner(
    client: TestClient,
    customer_identities: dict[str, User | Department],
) -> None:
    manager_token = _login(client, "customer-manager", "CustomerManager123!")
    customer = _create_customer(
        client,
        manager_token,
        "OWNER-001",
        "Assigned at Creation",
        owner_id=customer_identities["alice"].id,
    )

    assert customer["owner_id"] == customer_identities["alice"].id
    assert customer["created_by"] == customer_identities["manager"].id
    assert customer["created_by"] != customer["owner_id"]

    detail = client.get(
        f"/api/v1/customers/{customer['id']}", headers=_headers(manager_token)
    ).json()["data"]
    assert len(detail["ownership_history"]) == 1
    assert detail["ownership_history"][0]["action"] == "assigned"
    assert detail["ownership_history"][0]["new_owner_id"] == customer_identities["alice"].id


def test_customer_audit_masks_contact_fields_and_omits_free_text(
    client: TestClient,
    db_session: Session,
    customer_identities: dict[str, User | Department],
) -> None:
    token = _login(client, "customer-alice", "CustomerAlice123!")
    customer = _create_customer(
        client,
        token,
        "AUDIT-001",
        "Audit Customer",
        phone="+852 9123 4567",
        email="private.contact@example.com",
    )

    response = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=_headers(token),
        json={
            "phone": "+852 9876 5432",
            "email": "new.private@example.com",
            "address": "Sensitive street address",
            "description": "Sensitive free-text note",
        },
    )
    assert response.status_code == 200

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.resource_id == customer["id"], AuditLog.action == "customer_updated"
        )
    )
    assert audit is not None
    assert audit.before_data is not None and audit.after_data is not None
    assert audit.before_data["phone"] == "***4567"
    assert audit.after_data["phone"] == "***5432"
    assert audit.before_data["email"] == "p***@example.com"
    assert audit.after_data["email"] == "n***@example.com"
    assert {"address", "description"} <= set(audit.after_data["changed_fields"])
    assert "address" not in audit.after_data and "description" not in audit.after_data
    serialized = str(audit.before_data) + str(audit.after_data)
    assert "Sensitive street address" not in serialized
    assert "Sensitive free-text note" not in serialized
    assert "new.private@example.com" not in serialized


def test_data_scope_blocks_list_detail_update_delete_and_id_enumeration(
    client: TestClient,
    customer_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")
    bob_token = _login(client, "customer-bob", "CustomerBob123!")
    manager_token = _login(client, "customer-manager", "CustomerManager123!")
    admin_token = _login(client, "customer-admin", "CustomerAdmin123!")
    eve_token = _login(client, "customer-eve", "CustomerEve123!")

    alice_customer = _create_customer(client, alice_token, "SCOPE-001", "Alice Record")
    bob_customer = _create_customer(client, bob_token, "SCOPE-002", "Bob Record")
    outside_customer = _create_customer(client, eve_token, "SCOPE-003", "Outside Record")

    alice_list = client.get("/api/v1/customers", headers=_headers(alice_token)).json()["data"]
    assert [item["id"] for item in alice_list["items"]] == [alice_customer["id"]]
    assert alice_list["total"] == 1

    forbidden_detail = client.get(
        f"/api/v1/customers/{bob_customer['id']}", headers=_headers(alice_token)
    )
    assert forbidden_detail.status_code == 404
    assert forbidden_detail.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert (
        client.patch(
            f"/api/v1/customers/{bob_customer['id']}",
            headers=_headers(alice_token),
            json={"name": "Hijacked"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/customers/{outside_customer['id']}", headers=_headers(manager_token)
        ).status_code
        == 404
    )

    manager_ids = {
        item["id"]
        for item in client.get("/api/v1/customers", headers=_headers(manager_token)).json()["data"][
            "items"
        ]
    }
    assert manager_ids == {alice_customer["id"], bob_customer["id"]}
    admin_ids = {
        item["id"]
        for item in client.get("/api/v1/customers", headers=_headers(admin_token)).json()["data"][
            "items"
        ]
    }
    assert admin_ids == {alice_customer["id"], bob_customer["id"], outside_customer["id"]}


def test_name_check_warns_only_for_visible_records_without_blocking_create(
    client: TestClient,
    customer_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")
    bob_token = _login(client, "customer-bob", "CustomerBob123!")
    manager_token = _login(client, "customer-manager", "CustomerManager123!")

    _create_customer(client, alice_token, "NAME-001", "Same Name Ltd")
    _create_customer(client, bob_token, "NAME-002", " same name ltd ")

    alice_check = client.get(
        "/api/v1/customers/name-check?name=Same%20Name%20Ltd", headers=_headers(alice_token)
    )
    assert alice_check.status_code == 200
    assert alice_check.json()["data"]["has_duplicates"] is True
    assert len(alice_check.json()["data"]["matches"]) == 1

    manager_check = client.get(
        "/api/v1/customers/name-check?name=same%20name%20ltd",
        headers=_headers(manager_token),
    )
    assert len(manager_check.json()["data"]["matches"]) == 2

    allowed_duplicate = _create_customer(client, alice_token, "NAME-003", "Same Name Ltd")
    assert allowed_duplicate["id"]


def test_assignment_and_transfer_keep_history_and_audit_in_scope(
    client: TestClient,
    db_session: Session,
    customer_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")
    manager_token = _login(client, "customer-manager", "CustomerManager123!")
    eve_token = _login(client, "customer-eve", "CustomerEve123!")
    customer = _create_customer(client, alice_token, "MOVE-001", "Move Me")

    denied = client.post(
        f"/api/v1/customers/{customer['id']}/transfer",
        headers=_headers(alice_token),
        json={"owner_id": customer_identities["bob"].id, "reason": "Coverage change"},
    )
    assert denied.status_code == 403

    outside_scope = client.post(
        f"/api/v1/customers/{customer['id']}/transfer",
        headers=_headers(manager_token),
        json={"owner_id": customer_identities["eve"].id, "reason": "Outside scope"},
    )
    assert outside_scope.status_code == 403

    missing_reason = client.post(
        f"/api/v1/customers/{customer['id']}/transfer",
        headers=_headers(manager_token),
        json={"owner_id": customer_identities["bob"].id},
    )
    assert missing_reason.status_code == 400

    transferred = client.post(
        f"/api/v1/customers/{customer['id']}/transfer",
        headers=_headers(manager_token),
        json={"owner_id": customer_identities["bob"].id, "reason": "Territory coverage"},
    )
    assert transferred.status_code == 200, transferred.text
    body = transferred.json()["data"]
    assert body["owner_id"] == customer_identities["bob"].id
    history = body["ownership_history"]
    assert len(history) == 1
    assert history[0]["action"] == "transferred"
    assert history[0]["previous_owner_id"] == customer_identities["alice"].id
    assert history[0]["new_owner_id"] == customer_identities["bob"].id
    assert history[0]["reason"] == "Territory coverage"

    assigned = client.post(
        f"/api/v1/customers/{customer['id']}/assign",
        headers=_headers(manager_token),
        json={"owner_id": customer_identities["alice"].id, "reason": "Rebalanced"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["data"]["ownership_history"][0]["action"] == "assigned"

    events = list(
        db_session.scalars(
            select(CustomerOwnershipHistory).where(
                CustomerOwnershipHistory.customer_id == customer["id"]
            )
        ).all()
    )
    assert {event.action for event in events} == {"assigned", "transferred"}
    audit_actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.resource_id == customer["id"])
        ).all()
    )
    assert {"customer_created", "customer_transferred", "customer_assigned"} <= audit_actions
    assert (
        client.get(f"/api/v1/customers/{customer['id']}", headers=_headers(eve_token)).status_code
        == 404
    )


def test_customer_permissions_and_assignee_list_are_scope_limited(
    client: TestClient,
    customer_identities: dict[str, User | Department],
    user: User,
) -> None:
    employee_token = _login(client, "alice", "CorrectPassword123!")
    manager_token = _login(client, "customer-manager", "CustomerManager123!")
    alice_token = _login(client, "customer-alice", "CustomerAlice123!")

    assert client.get("/api/v1/customers", headers=_headers(employee_token)).status_code == 403
    assert (
        client.get("/api/v1/customers/assignees", headers=_headers(alice_token)).status_code == 403
    )

    manager_assignees = client.get("/api/v1/customers/assignees", headers=_headers(manager_token))
    assert manager_assignees.status_code == 200
    visible_ids = {item["id"] for item in manager_assignees.json()["data"]}
    assert visible_ids == {
        customer_identities["admin"].id,
        customer_identities["manager"].id,
        customer_identities["alice"].id,
        customer_identities["bob"].id,
    }
