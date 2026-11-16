from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

from app.modules.auth.model import User
from app.modules.auth.security import hash_password
from app.modules.customers.model import Customer
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


def _dashboard_identities(db_session: Session) -> dict[str, User | Department]:
    root = Department(id=str(uuid4()), name="统计总部", is_active=True)
    child = Department(id=str(uuid4()), name="统计一部", parent=root, is_active=True)
    outside = Department(id=str(uuid4()), name="统计外部", is_active=True)
    db_session.add_all([root, child, outside])
    db_session.flush()
    roles = {role.code: role for role in db_session.scalars(select(Role)).all()}
    manager = User(
        id=str(uuid4()),
        username="dashboard-manager",
        password_hash=hash_password("DashboardManager123!"),
        display_name="统计主管",
        department=root,
        roles=[roles["sales_manager"]],
        status="active",
    )
    employee = User(
        id=str(uuid4()),
        username="dashboard-employee",
        password_hash=hash_password("DashboardEmployee123!"),
        display_name="统计员工",
        department=child,
        roles=[roles["sales"]],
        status="active",
    )
    outside_user = User(
        id=str(uuid4()),
        username="dashboard-outside",
        password_hash=hash_password("DashboardOutside123!"),
        display_name="外部员工",
        department=outside,
        roles=[roles["sales"]],
        status="active",
    )
    db_session.add_all([manager, employee, outside_user])
    db_session.commit()
    return {
        "root": root,
        "child": child,
        "outside": outside,
        "manager": manager,
        "employee": employee,
        "outside_user": outside_user,
    }


def test_dashboard_summary_uses_database_aggregates_and_scope(
    client: TestClient, db_session: Session
) -> None:
    identities = _dashboard_identities(db_session)
    today = datetime.now(UTC).date()
    day_one = datetime.combine(today - timedelta(days=2), time(10), tzinfo=UTC)
    day_two = datetime.combine(today - timedelta(days=1), time(11), tzinfo=UTC)
    month_start = datetime.combine(today.replace(day=1), time.min, tzinfo=UTC)
    manager = identities["manager"]
    employee = identities["employee"]
    outside_user = identities["outside_user"]
    customer_in_scope = Customer(
        id=str(uuid4()),
        customer_no="DASH-001",
        name="统计范围内客户",
        owner_id=employee.id,
        department_id=identities["child"].id,
        source="referral",
        level="A",
        status="active",
        created_by=employee.id,
        created_at=day_one,
        updated_at=day_one,
    )
    customer_at_root = Customer(
        id=str(uuid4()),
        customer_no="DASH-002",
        name="统计总部客户",
        owner_id=manager.id,
        department_id=identities["root"].id,
        source="website",
        level="B",
        status="active",
        created_by=manager.id,
        created_at=day_two,
        updated_at=day_two,
    )
    customer_outside = Customer(
        id=str(uuid4()),
        customer_no="DASH-003",
        name="统计范围外客户",
        owner_id=outside_user.id,
        department_id=identities["outside"].id,
        source="partner",
        level="C",
        status="active",
        created_by=outside_user.id,
        created_at=day_two,
        updated_at=day_two,
    )
    deleted_customer = Customer(
        id=str(uuid4()),
        customer_no="DASH-004",
        name="已删除客户",
        owner_id=employee.id,
        department_id=identities["child"].id,
        source="referral",
        level="D",
        status="active",
        created_by=employee.id,
        created_at=day_two,
        updated_at=day_two,
        deleted_at=day_two,
    )
    db_session.add_all([customer_in_scope, customer_at_root, customer_outside, deleted_customer])
    db_session.flush()
    db_session.add_all(
        [
            FollowUpRecord(
                id=str(uuid4()),
                customer_id=customer_in_scope.id,
                user_id=employee.id,
                followed_at=month_start + timedelta(days=1, hours=2),
                method="phone",
                content="范围内跟进",
                result="已联系",
            ),
            FollowUpRecord(
                id=str(uuid4()),
                customer_id=customer_at_root.id,
                user_id=manager.id,
                followed_at=day_two,
                method="visit",
                content="主管跟进",
                result=None,
            ),
            FollowUpRecord(
                id=str(uuid4()),
                customer_id=customer_outside.id,
                user_id=outside_user.id,
                followed_at=day_two,
                method="wechat",
                content="范围外跟进",
                result=None,
            ),
        ]
    )
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Reminder(
                id=str(uuid4()),
                user_id=employee.id,
                customer_id=customer_in_scope.id,
                title="今日待办",
                remind_at=datetime.combine(today, time(12), tzinfo=UTC),
                created_by=employee.id,
            ),
            Reminder(
                id=str(uuid4()),
                user_id=employee.id,
                customer_id=customer_in_scope.id,
                title="已逾期",
                remind_at=now - timedelta(hours=2),
                created_by=employee.id,
            ),
            Reminder(
                id=str(uuid4()),
                user_id=outside_user.id,
                customer_id=customer_outside.id,
                title="外部待办",
                remind_at=datetime.combine(today, time(12), tzinfo=UTC),
                created_by=outside_user.id,
            ),
        ]
    )
    db_session.commit()

    manager_token = _login(client, "dashboard-manager", "DashboardManager123!")
    employee_token = _login(client, "dashboard-employee", "DashboardEmployee123!")
    start = today.replace(day=1).isoformat()
    end = today.isoformat()
    manager_response = client.get(
        f"/api/v1/dashboard/summary?start_date={start}&end_date={end}",
        headers=_headers(manager_token),
    )
    assert manager_response.status_code == 200, manager_response.text
    manager_data = manager_response.json()["data"]
    assert manager_data["management"]["customer_total"] == 2
    manager_sources = {
        item["source"]
        for item in manager_data["management"]["customer_source_distribution"]
    }
    assert manager_sources == {
        "referral",
        "website",
    }
    assert sum(item["count"] for item in manager_data["management"]["customer_new_trend"]) == 2
    assert sum(item["count"] for item in manager_data["management"]["follow_up_trend"]) == 2
    assert {item["customer_name"] for item in manager_data["personal"]["recent_follow_ups"]} == {
        "统计范围内客户",
        "统计总部客户",
    }

    employee_response = client.get(
        f"/api/v1/dashboard/summary?start_date={start}&end_date={end}",
        headers=_headers(employee_token),
    )
    assert employee_response.status_code == 200, employee_response.text
    employee_data = employee_response.json()["data"]
    assert employee_data["personal"]["my_customer_total"] == 1
    assert employee_data["personal"]["current_month_follow_up_count"] == 1
    assert employee_data["personal"]["today_pending_reminder_count"] == 2
    assert employee_data["personal"]["overdue_reminder_count"] == 2
    assert employee_data["management"]["customer_total"] == 1
    assert sum(item["count"] for item in employee_data["management"]["follow_up_trend"]) == 1
    assert {item["customer_name"] for item in employee_data["personal"]["recent_follow_ups"]} == {
        "统计范围内客户"
    }


def test_dashboard_summary_rejects_invalid_or_excessive_ranges(
    client: TestClient, db_session: Session
) -> None:
    identities = _dashboard_identities(db_session)
    token = _login(client, identities["employee"].username, "DashboardEmployee123!")
    invalid = client.get(
        "/api/v1/dashboard/summary?start_date=2026-11-20&end_date=2026-11-19",
        headers=_headers(token),
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    excessive = client.get(
        "/api/v1/dashboard/summary?start_date=2024-01-01&end_date=2026-01-01",
        headers=_headers(token),
    )
    assert excessive.status_code == 400
    assert excessive.json()["error"]["code"] == "VALIDATION_ERROR"
