from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.auth.model import AuditLog, User
from app.modules.auth.security import hash_password
from app.modules.followups.model import FollowUpRecord, Reminder
from app.modules.organizations.model import Department
from app.modules.roles.model import Role
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_customer(client: TestClient, token: str, customer_no: str) -> dict:
    response = client.post(
        "/api/v1/customers",
        headers=_headers(token),
        json={"customer_no": customer_no, "name": f"客户 {customer_no}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _followup_identities(db_session: Session) -> dict[str, User | Department]:
    root = Department(id=str(uuid4()), name="跟进总部", is_active=True)
    child = Department(id=str(uuid4()), name="跟进一部", parent=root, is_active=True)
    outside = Department(id=str(uuid4()), name="跟进外部", is_active=True)
    db_session.add_all([root, child, outside])
    db_session.flush()
    roles = {role.code: role for role in db_session.scalars(select(Role)).all()}
    identities: dict[str, User | Department] = {
        "manager": User(
            id=str(uuid4()),
            username="follow-manager",
            password_hash=hash_password("FollowManager123!"),
            display_name="跟进主管",
            department=root,
            roles=[roles["sales_manager"]],
            status="active",
        ),
        "alice": User(
            id=str(uuid4()),
            username="follow-alice",
            password_hash=hash_password("FollowAlice123!"),
            display_name="跟进 Alice",
            department=child,
            roles=[roles["sales"]],
            status="active",
        ),
        "bob": User(
            id=str(uuid4()),
            username="follow-bob",
            password_hash=hash_password("FollowBob123!"),
            display_name="跟进 Bob",
            department=outside,
            roles=[roles["sales"]],
            status="active",
        ),
    }
    db_session.add_all(identities.values())
    db_session.commit()
    return {**identities, "root": root, "child": child, "outside": outside}


def test_follow_up_crud_scope_and_audit(client: TestClient, db_session: Session) -> None:
    identities = _followup_identities(db_session)
    alice_token = _login(client, "follow-alice", "FollowAlice123!")
    manager_token = _login(client, "follow-manager", "FollowManager123!")
    bob_token = _login(client, "follow-bob", "FollowBob123!")
    customer = _create_customer(client, alice_token, "FOLLOW-001")
    contacts_url = f"/api/v1/customers/{customer['id']}/contacts"
    contact = client.post(
        contacts_url,
        headers=_headers(alice_token),
        json={"name": "采购联系人"},
    ).json()["data"]
    followups_url = f"/api/v1/customers/{customer['id']}/follow-ups"
    invalid_contact = client.post(
        followups_url,
        headers=_headers(alice_token),
        json={
            "contact_id": str(uuid4()),
            "method": "phone",
            "content": "无效联系人",
            "followed_at": "2026-11-16T10:00:00+08:00",
        },
    )
    assert invalid_contact.status_code == 404
    created = client.post(
        followups_url,
        headers=_headers(alice_token),
        json={
            "contact_id": contact["id"],
            "method": "phone",
            "content": "确认了采购预算",
            "followed_at": "2026-11-16T10:00:00+08:00",
            "result": "客户会在本周反馈",
            "next_follow_up_at": "2026-11-20T10:00:00+08:00",
        },
    )
    assert created.status_code == 201, created.text
    record = created.json()["data"]
    assert record["user_id"] == identities["alice"].id
    assert client.get(followups_url, headers=_headers(alice_token)).json()["data"]["total"] == 1

    assert client.get(followups_url, headers=_headers(bob_token)).status_code == 404
    assert (
        client.get(f"{followups_url}/{record['id']}", headers=_headers(bob_token)).status_code
        == 404
    )

    updated = client.patch(
        f"{followups_url}/{record['id']}",
        headers=_headers(manager_token),
        json={"result": "已确认下周签约"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["result"] == "已确认下周签约"
    assert (
        db_session.scalar(
            select(AuditLog).where(
                AuditLog.resource_id == record["id"], AuditLog.action == "follow_up_updated"
            )
        )
        is not None
    )
    assert db_session.get(FollowUpRecord, record["id"]).user_id == identities["alice"].id

    manager_record = client.post(
        followups_url,
        headers=_headers(manager_token),
        json={
            "method": "wechat",
            "content": "主管补充了跟进意见",
            "followed_at": "2026-11-16T11:00:00+08:00",
        },
    ).json()["data"]
    denied = client.patch(
        f"{followups_url}/{manager_record['id']}",
        headers=_headers(alice_token),
        json={"result": "员工尝试修改主管记录"},
    )
    assert denied.status_code == 403


def test_reminder_due_overdue_status_and_scope(client: TestClient, db_session: Session) -> None:
    _followup_identities(db_session)
    alice_token = _login(client, "follow-alice", "FollowAlice123!")
    bob_token = _login(client, "follow-bob", "FollowBob123!")
    manager_token = _login(client, "follow-manager", "FollowManager123!")
    customer = _create_customer(client, alice_token, "REMINDER-001")
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created_past = client.post(
        "/api/v1/reminders",
        headers=_headers(alice_token),
        json={"title": "逾期回访", "remind_at": past, "customer_id": customer["id"]},
    )
    assert created_past.status_code == 201, created_past.text
    past_id = created_past.json()["data"]["id"]
    created_future = client.post(
        "/api/v1/reminders",
        headers=_headers(alice_token),
        json={"title": "明日回访", "remind_at": future},
    )
    assert created_future.status_code == 201, created_future.text
    future_id = created_future.json()["data"]["id"]

    mine = client.get("/api/v1/reminders/mine", headers=_headers(alice_token))
    assert mine.status_code == 200
    assert mine.json()["data"]["total"] == 2
    overdue = client.get("/api/v1/reminders/overdue", headers=_headers(alice_token))
    assert overdue.status_code == 200
    assert [item["id"] for item in overdue.json()["data"]["items"]] == [past_id]
    due = client.get("/api/v1/reminders/due", headers=_headers(alice_token))
    assert due.status_code == 200
    assert due.json()["data"]["total"] == 1

    assert (
        client.get(f"/api/v1/reminders/{past_id}", headers=_headers(bob_token)).status_code == 404
    )
    manager_list = client.get("/api/v1/reminders", headers=_headers(manager_token))
    assert manager_list.status_code == 200
    assert manager_list.json()["data"]["total"] == 2
    completed = client.post(f"/api/v1/reminders/{past_id}/complete", headers=_headers(alice_token))
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "completed"
    repeated = client.post(f"/api/v1/reminders/{past_id}/complete", headers=_headers(alice_token))
    assert repeated.status_code == 422
    cancelled = client.post(f"/api/v1/reminders/{future_id}/cancel", headers=_headers(alice_token))
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert db_session.scalar(select(Reminder).where(Reminder.id == future_id)).status == "cancelled"
