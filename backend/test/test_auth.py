import uuid

from app.config import Settings
from app.core.security import create_access_token
from conftest import TEST_PREFIX, TEST_PASSWORD


def _register_payload(role: str = "user") -> dict:
    username = f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": TEST_PASSWORD,
        "role": role,
    }


def _register_and_login(client, *, role: str = "user") -> dict:
    payload = _register_payload(role=role)
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"token": token, "user": payload}


def test_register_success(integration_client):
    payload = _register_payload(role="user")
    response = integration_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == payload["username"]
    assert body["email"] == payload["email"]
    assert body["role"] == payload["role"]
    assert "id" in body


def test_register_duplicate_username_or_email(integration_client):
    payload = _register_payload(role="user")
    first = integration_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    duplicate = integration_client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Username or email already exists"}


def test_register_rejects_admin_role(integration_client):
    payload = _register_payload(role="admin")
    response = integration_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin registration is not allowed"}


def test_login_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    assert auth["token"]


def test_login_invalid_credentials(integration_client):
    payload = _register_payload(role="user")
    register = integration_client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201

    response = integration_client.post(
        "/api/v1/auth/login",
        json={"username": payload["username"], "password": "wrongpass123"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_me_requires_bearer_token(integration_client):
    response = integration_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == auth["user"]["username"]
    assert body["email"] == auth["user"]["email"]
    assert body["role"] == "user"


def test_me_invalid_token(integration_client):
    response = integration_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


def test_me_user_not_found(integration_client):
    settings = Settings(_env_file=None)
    token = create_access_token(
        subject="99999999",
        role="user",
        secret_key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )

    response = integration_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}
