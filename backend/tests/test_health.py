from app.main import app
from fastapi.testclient import TestClient


def test_healthz_returns_standard_success_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok"}
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_api_meta_is_available_under_v1_prefix() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json()["data"]["phase"] == "4"
