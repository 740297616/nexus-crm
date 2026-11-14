from datetime import UTC, datetime, timedelta

import jwt
from app.core.config import get_settings
from app.modules.auth.model import AuditLog, RefreshToken
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def login(client: TestClient, identifier: str = "alice", password: str = "CorrectPassword123!"):
    return client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )


def test_correct_login_and_current_user(client: TestClient, user) -> None:
    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]
    assert "$argon2id$" in user.password_hash

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['data']['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "alice"


def test_wrong_password_and_unknown_user_are_indistinguishable(client: TestClient, user) -> None:
    wrong_password = login(client, password="WrongPassword123!")
    unknown_user = login(client, identifier="unknown")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert unknown_user.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert wrong_password.json()["error"]["message"] == unknown_user.json()["error"]["message"]


def test_access_token_expiry_is_rejected(client: TestClient, user) -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": user.id,
            "jti": "expired-access",
            "iat": datetime.now(UTC) - timedelta(minutes=2),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "token_type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_refresh_rotates_and_reuse_revokes_all_tokens(
    client: TestClient, user, db_session: Session
) -> None:
    first = login(client).json()["data"]
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})

    assert rotated.status_code == 200
    second = rotated.json()["data"]
    assert second["refresh_token"] != first["refresh_token"]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "TOKEN_INVALID"

    second_after_reuse = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert second_after_reuse.status_code == 401
    assert db_session.scalar(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))) is None
    assert (
        db_session.scalar(select(AuditLog).where(AuditLog.action == "refresh_token_reuse_detected"))
        is not None
    )


def test_logout_invalidates_refresh_token(client: TestClient, user) -> None:
    tokens = login(client).json()["data"]
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 200

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401
    assert refresh.json()["error"]["code"] == "TOKEN_INVALID"


def test_change_password_revokes_sessions_and_allows_new_password(client: TestClient, user) -> None:
    tokens = login(client).json()["data"]
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": "CorrectPassword123!", "new_password": "NewPassword123!"},
    )
    assert changed.status_code == 200

    old_refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert old_refresh.status_code == 401
    old_access = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert old_access.status_code == 401
    assert old_access.json()["error"]["code"] == "TOKEN_INVALID"

    assert login(client, password="CorrectPassword123!").status_code == 401
    assert login(client, password="NewPassword123!").status_code == 200


def test_auth_audit_logs_do_not_contain_password_or_refresh_token(
    client: TestClient, user, db_session: Session
) -> None:
    tokens = login(client).json()["data"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": "CorrectPassword123!", "new_password": "NewPassword123!"},
    )

    logs = db_session.scalars(select(AuditLog)).all()
    serialized = repr([(log.before_data, log.after_data) for log in logs])
    assert "CorrectPassword123!" not in serialized
    assert "NewPassword123!" not in serialized
    assert tokens["refresh_token"] not in serialized


def test_unauthenticated_access_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_failed_login_limit_returns_rate_limited(client: TestClient, user) -> None:
    for _ in range(5):
        response = login(client, identifier="rate-limited-user", password="wrong")
        assert response.status_code == 401

    blocked = login(client, identifier="rate-limited-user", password="wrong")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
