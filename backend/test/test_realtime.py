import uuid
from datetime import datetime, timezone

from app.main import app
from app.models.user import UserRole
from conftest import TEST_PASSWORD, TEST_PREFIX


def _register_and_login(client, *, role: str = "user") -> dict:
    username = f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": TEST_PASSWORD,
        "role": role,
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    return {"username": username, "token": login.json()["access_token"]}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_realtime_status_authenticated(integration_client):
    auth = _register_and_login(integration_client)
    response = integration_client.get("/api/v1/realtime/status", headers=_auth_headers(auth["token"]))

    assert response.status_code == 200
    body = response.json()
    assert "running" in body
    assert "connected_clients" in body
    assert body["current_user"] == auth["username"]


def test_websocket_stream_and_database_persistence(integration_client, create_user):
    auth = _register_and_login(integration_client)
    service = app.state.realtime_service

    service._interval_seconds = 0.01
    service._batch_size = 1

    realtime_creator = create_user(role=UserRole.ADMIN.value, username=f"{TEST_PREFIX}rtbot")

    async def fake_creator(_session):
        return realtime_creator["id"]

    service._get_or_create_system_user_id = fake_creator

    def fake_generate_water_level(last_value=None):
        value = 77.7 if last_value is None else round(last_value + 0.5, 2)
        return {
            "title": f"{TEST_PREFIX}realtime-water-sensor",
            "value": value,
            "category": f"{TEST_PREFIX}realtime",
            "timestamp": datetime.now(timezone.utc),
            "is_alert": False,
        }

    def fake_generate_temperature(last_value=None):
        value = 25.5 if last_value is None else round(last_value + 0.2, 2)
        return {
            "title": f"{TEST_PREFIX}realtime-temp-sensor",
            "value": value,
            "category": f"{TEST_PREFIX}realtime",
            "timestamp": datetime.now(timezone.utc),
            "is_alert": False,
        }

    service._generate_water_level = fake_generate_water_level
    service._generate_temperature = fake_generate_temperature

    with integration_client.websocket_connect(f"/api/v1/ws/realtime?token={auth['token']}") as ws:
        connected = ws.receive_json()
        assert connected["event"] == "connected"
        ws.send_text("ping")
        payload = ws.receive_json()
        assert payload["category"] == f"{TEST_PREFIX}realtime"
        assert payload["title"] in {
            f"{TEST_PREFIX}realtime-water-sensor",
            f"{TEST_PREFIX}realtime-temp-sensor",
        }

    persisted = integration_client.get(
        f"/api/v1/data-records?category={TEST_PREFIX}realtime&page=1&size=20",
        headers=_auth_headers(auth["token"]),
    )
    assert persisted.status_code == 200
    body = persisted.json()
    assert body["total"] >= 1
    returned_titles = {item["title"] for item in body["items"]}
    assert f"{TEST_PREFIX}realtime-water-sensor" in returned_titles
    assert f"{TEST_PREFIX}realtime-temp-sensor" in returned_titles
