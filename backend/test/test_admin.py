import uuid

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
    return {"token": login.json()["access_token"], "username": username}


def _login(client, *, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_users_requires_admin_role(integration_client):
    user_auth = _register_and_login(integration_client, role="user")
    response = integration_client.get("/api/v1/admin/users", headers=_auth_headers(user_auth["token"]))
    assert response.status_code == 403


def test_admin_users_list_success(integration_client, create_user):
    admin = create_user(role="admin")
    admin_token = _login(integration_client, username=admin["username"], password=admin["password"])

    response = integration_client.get(
        f"/api/v1/admin/users?page=1&size=20&keyword={TEST_PREFIX}",
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


def test_admin_users_list_excludes_system_bot(integration_client, create_user):
    admin = create_user(role="admin")
    admin_token = _login(integration_client, username=admin["username"], password=admin["password"])

    response = integration_client.get(
        "/api/v1/admin/users?page=1&size=50",
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 200
    usernames = {item["username"] for item in response.json()["items"]}
    assert "system_bot" not in usernames


def test_admin_update_user_role_success(integration_client, create_user):
    admin = create_user(role="admin")
    target = create_user(role="user")
    admin_token = _login(integration_client, username=admin["username"], password=admin["password"])

    update = integration_client.patch(
        f"/api/v1/admin/users/{target['id']}/role",
        headers=_auth_headers(admin_token),
        json={"role": "viewer"},
    )
    assert update.status_code == 200
    assert update.json()["role"] == "viewer"


def test_admin_cannot_self_demote(integration_client, create_user):
    admin = create_user(role="admin")
    admin_token = _login(integration_client, username=admin["username"], password=admin["password"])

    update = integration_client.patch(
        f"/api/v1/admin/users/{admin['id']}/role",
        headers=_auth_headers(admin_token),
        json={"role": "user"},
    )
    assert update.status_code == 400
    assert update.json() == {"detail": "Admin cannot remove own admin role"}


def test_bootstrap_admin_conflict_when_human_admin_exists(integration_client, create_user):
    create_user(role="admin")
    payload = {
        "username": f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}",
        "email": f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}@example.com",
        "password": TEST_PASSWORD,
    }
    response = integration_client.post("/api/v1/admin/bootstrap", json=payload)
    assert response.status_code == 409
    assert response.json() == {"detail": "Admin user already exists"}
