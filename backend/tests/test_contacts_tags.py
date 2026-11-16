from uuid import uuid4

import pytest
from app.modules.auth.model import AuditLog, User
from app.modules.auth.security import hash_password
from app.modules.contacts.model import Contact
from app.modules.customers.model import Customer
from app.modules.organizations.model import Department
from app.modules.roles.model import Role
from app.modules.tags.model import CustomerTag
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.fixture
def contact_identities(db_session: Session) -> dict[str, User | Department]:
    root = Department(id=str(uuid4()), name="联系人总部", is_active=True)
    child = Department(id=str(uuid4()), name="联系人一部", parent=root, is_active=True)
    outside = Department(id=str(uuid4()), name="联系人外部", is_active=True)
    db_session.add_all([root, child, outside])
    db_session.flush()
    roles = {role.code: role for role in db_session.scalars(select(Role)).all()}
    identities = {
        "admin": User(
            id=str(uuid4()),
            username="contact-admin",
            password_hash=hash_password("ContactAdmin123!"),
            display_name="联系人管理员",
            department=root,
            roles=[roles["system_admin"]],
            status="active",
        ),
        "manager": User(
            id=str(uuid4()),
            username="contact-manager",
            password_hash=hash_password("ContactManager123!"),
            display_name="联系人主管",
            department=root,
            roles=[roles["sales_manager"]],
            status="active",
        ),
        "alice": User(
            id=str(uuid4()),
            username="contact-alice",
            password_hash=hash_password("ContactAlice123!"),
            display_name="联系人 Alice",
            department=child,
            roles=[roles["sales"]],
            status="active",
        ),
        "bob": User(
            id=str(uuid4()),
            username="contact-bob",
            password_hash=hash_password("ContactBob123!"),
            display_name="联系人 Bob",
            department=child,
            roles=[roles["sales"]],
            status="active",
        ),
        "eve": User(
            id=str(uuid4()),
            username="contact-eve",
            password_hash=hash_password("ContactEve123!"),
            display_name="联系人 Eve",
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
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_customer(client: TestClient, token: str, customer_no: str, name: str) -> dict:
    response = client.post(
        "/api/v1/customers",
        headers=_headers(token),
        json={"customer_no": customer_no, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_contact_crud_primary_search_and_audit(
    client: TestClient,
    db_session: Session,
    contact_identities: dict[str, User | Department],
) -> None:
    alice_token = _login(client, "contact-alice", "ContactAlice123!")
    customer = _create_customer(client, alice_token, "CONTACT-001", "Contact Customer")
    base_url = f"/api/v1/customers/{customer['id']}/contacts"

    first = client.post(
        base_url,
        headers=_headers(alice_token),
        json={
            "name": "张经理",
            "title": "采购负责人",
            "phone": "13800000001",
            "email": "zhang@example.com",
            "contact_method": "微信",
            "is_primary": True,
            "remark": "首要联系人",
        },
    )
    assert first.status_code == 201, first.text
    first_data = first.json()["data"]
    second = client.post(
        base_url,
        headers=_headers(alice_token),
        json={"name": "李总", "title": "总经理", "is_primary": True},
    )
    assert second.status_code == 201, second.text
    second_data = second.json()["data"]
    assert second_data["is_primary"] is True

    listed = client.get(f"{base_url}?search=采购", headers=_headers(alice_token))
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["id"] == first_data["id"]

    detail = client.get(f"{base_url}/{first_data['id']}", headers=_headers(alice_token))
    assert detail.status_code == 200
    assert detail.json()["data"]["created_by"] == contact_identities["alice"].id

    updated = client.patch(
        f"{base_url}/{first_data['id']}",
        headers=_headers(alice_token),
        json={"title": "采购总监", "phone": "13800000002"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "采购总监"

    promoted = client.post(f"{base_url}/{first_data['id']}/primary", headers=_headers(alice_token))
    assert promoted.status_code == 200
    assert promoted.json()["data"]["is_primary"] is True
    refreshed_second = client.get(f"{base_url}/{second_data['id']}", headers=_headers(alice_token))
    assert refreshed_second.json()["data"]["is_primary"] is False

    removed = client.delete(f"{base_url}/{second_data['id']}", headers=_headers(alice_token))
    assert removed.status_code == 200
    assert (
        client.get(f"{base_url}/{second_data['id']}", headers=_headers(alice_token)).status_code
        == 404
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.resource_id == first_data["id"],
                AuditLog.action.in_(
                    ["contact_created", "contact_updated", "contact_primary_changed"]
                ),
            )
        )
        >= 3
    )


def test_contacts_and_tags_obey_customer_scope_and_permissions(
    client: TestClient,
    contact_identities: dict[str, User | Department],
    user: User,
) -> None:
    alice_token = _login(client, "contact-alice", "ContactAlice123!")
    bob_token = _login(client, "contact-bob", "ContactBob123!")
    employee_token = _login(client, "alice", "CorrectPassword123!")
    alice_customer = _create_customer(client, alice_token, "SCOPE-CONTACT-001", "Alice Customer")
    bob_customer = _create_customer(client, bob_token, "SCOPE-CONTACT-002", "Bob Customer")
    bob_contacts = f"/api/v1/customers/{bob_customer['id']}/contacts"

    bob_contact = client.post(
        bob_contacts,
        headers=_headers(bob_token),
        json={"name": "Bob Contact"},
    )
    assert bob_contact.status_code == 201
    contact_id = bob_contact.json()["data"]["id"]
    alice_contacts = f"/api/v1/customers/{alice_customer['id']}/contacts"
    assert client.get(bob_contacts, headers=_headers(alice_token)).status_code == 404
    assert (
        client.get(f"{bob_contacts}/{contact_id}", headers=_headers(alice_token)).status_code == 404
    )
    assert (
        client.post(
            bob_contacts, headers=_headers(alice_token), json={"name": "Cross Scope"}
        ).status_code
        == 404
    )
    assert client.get(alice_contacts, headers=_headers(employee_token)).status_code == 403
    assert client.get("/api/v1/tags", headers=_headers(employee_token)).status_code == 403
    assert client.get("/api/v1/customers", headers=_headers(employee_token)).status_code == 403
    assert user.id != contact_identities["alice"].id


def test_tag_crud_binding_filter_and_deleted_customer_relationships(
    client: TestClient,
    db_session: Session,
    contact_identities: dict[str, User | Department],
) -> None:
    manager_token = _login(client, "contact-manager", "ContactManager123!")
    alice_token = _login(client, "contact-alice", "ContactAlice123!")
    admin_token = _login(client, "contact-admin", "ContactAdmin123!")
    customer = _create_customer(client, alice_token, "TAG-001", "Tagged Customer")
    customer_tags_url = f"/api/v1/customers/{customer['id']}/tags"

    created = client.post(
        "/api/v1/tags",
        headers=_headers(manager_token),
        json={"name": "重点客户", "description": "重点跟进"},
    )
    assert created.status_code == 201, created.text
    tag = created.json()["data"]
    duplicate = client.post(
        "/api/v1/tags", headers=_headers(manager_token), json={"name": " 重点客户 "}
    )
    assert duplicate.status_code == 409
    updated_tag = client.patch(
        f"/api/v1/tags/{tag['id']}",
        headers=_headers(manager_token),
        json={"description": "重点客户跟进"},
    )
    assert updated_tag.status_code == 200, updated_tag.text
    assert updated_tag.json()["data"]["description"] == "重点客户跟进"

    bound = client.post(
        customer_tags_url,
        headers=_headers(alice_token),
        json={"tag_id": tag["id"]},
    )
    assert bound.status_code == 201, bound.text
    repeated = client.post(
        customer_tags_url,
        headers=_headers(alice_token),
        json={"tag_id": tag["id"]},
    )
    assert repeated.status_code == 409
    listed = client.get(customer_tags_url, headers=_headers(alice_token))
    assert listed.status_code == 200
    assert listed.json()["data"][0]["tag_name"] == "重点客户"

    filtered = client.get(f"/api/v1/customers?tag_id={tag['id']}", headers=_headers(alice_token))
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 1

    contact_url = f"/api/v1/customers/{customer['id']}/contacts"
    contact = client.post(contact_url, headers=_headers(alice_token), json={"name": "保留联系人"})
    assert contact.status_code == 201
    relation_id = bound.json()["data"]["id"]

    deleted = client.delete(f"/api/v1/customers/{customer['id']}", headers=_headers(admin_token))
    assert deleted.status_code == 200
    assert client.get(contact_url, headers=_headers(admin_token)).status_code == 404
    assert client.get(customer_tags_url, headers=_headers(admin_token)).status_code == 404
    assert db_session.get(Contact, contact.json()["data"]["id"]) is not None
    assert db_session.get(CustomerTag, relation_id) is not None
    assert db_session.get(Customer, customer["id"]).deleted_at is not None

    tag_deleted = client.delete(f"/api/v1/tags/{tag['id']}", headers=_headers(manager_token))
    assert tag_deleted.status_code == 200
    assert all(
        item["id"] != tag["id"]
        for item in client.get("/api/v1/tags", headers=_headers(manager_token)).json()["data"]
    )
