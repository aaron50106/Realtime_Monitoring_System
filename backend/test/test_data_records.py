import uuid
from datetime import datetime, timezone

from conftest import TEST_PASSWORD, TEST_PREFIX


def _register_user_payload(role: str = "user") -> dict:
    username = f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": TEST_PASSWORD,
        "role": role,
    }


def _register_and_login(client, *, role: str = "user") -> dict:
    payload = _register_user_payload(role=role)
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"token": token, "user": payload}


def _login(client, *, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_record_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.post(
        "/api/v1/data-records",
        headers=_auth_headers(auth["token"]),
        json={"title": f"{TEST_PREFIX}cpu", "value": 65.5, "category": f"{TEST_PREFIX}system"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == f"{TEST_PREFIX}cpu"
    assert body["category"] == f"{TEST_PREFIX}system"
    assert body["is_alert"] is False
    assert body["creator_id"] > 0


def test_create_record_viewer_forbidden(integration_client):
    auth = _register_and_login(integration_client, role="viewer")
    response = integration_client.post(
        "/api/v1/data-records",
        headers=_auth_headers(auth["token"]),
        json={"title": f"{TEST_PREFIX}cpu", "value": 65.5, "category": f"{TEST_PREFIX}system"},
    )
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_list_records_with_pagination(integration_client):
    auth = _register_and_login(integration_client, role="user")
    headers = _auth_headers(auth["token"])

    for idx in range(2):
        create = integration_client.post(
            "/api/v1/data-records",
            headers=headers,
            json={
                "title": f"{TEST_PREFIX}cpu-{idx}",
                "value": 40 + idx,
                "category": f"{TEST_PREFIX}system",
            },
        )
        assert create.status_code == 201

    response = integration_client.get(
        f"/api/v1/data-records?page=1&size=20&category={TEST_PREFIX}system&sort_by=value&sort_order=desc",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["size"] == 20
    assert len(body["items"]) == 2


def test_get_record_not_found(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.get("/api/v1/data-records/999999", headers=_auth_headers(auth["token"]))
    assert response.status_code == 404
    assert response.json() == {"detail": "Data record not found"}


def test_update_record_owner_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    headers = _auth_headers(auth["token"])
    create = integration_client.post(
        "/api/v1/data-records",
        headers=headers,
        json={"title": f"{TEST_PREFIX}cpu", "value": 20.0, "category": f"{TEST_PREFIX}system"},
    )
    assert create.status_code == 201
    record_id = create.json()["id"]

    update = integration_client.put(
        f"/api/v1/data-records/{record_id}",
        headers=headers,
        json={"value": 91.2},
    )
    assert update.status_code == 200
    assert update.json()["value"] == 91.2
    assert update.json()["is_alert"] is True


def test_update_record_non_owner_forbidden(integration_client):
    owner = _register_and_login(integration_client, role="user")
    owner_headers = _auth_headers(owner["token"])
    create = integration_client.post(
        "/api/v1/data-records",
        headers=owner_headers,
        json={"title": f"{TEST_PREFIX}cpu", "value": 20.0, "category": f"{TEST_PREFIX}system"},
    )
    record_id = create.json()["id"]

    other = _register_and_login(integration_client, role="user")
    response = integration_client.put(
        f"/api/v1/data-records/{record_id}",
        headers=_auth_headers(other["token"]),
        json={"title": f"{TEST_PREFIX}changed"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Only creator or admin can update this record"}


def test_update_record_requires_payload_fields(integration_client):
    auth = _register_and_login(integration_client, role="user")
    headers = _auth_headers(auth["token"])
    create = integration_client.post(
        "/api/v1/data-records",
        headers=headers,
        json={"title": f"{TEST_PREFIX}cpu", "value": 20.0, "category": f"{TEST_PREFIX}system"},
    )
    record_id = create.json()["id"]

    response = integration_client.put(f"/api/v1/data-records/{record_id}", headers=headers, json={})
    assert response.status_code == 422


def test_delete_record_admin_success(integration_client, create_user):
    owner = _register_and_login(integration_client, role="user")
    create = integration_client.post(
        "/api/v1/data-records",
        headers=_auth_headers(owner["token"]),
        json={"title": f"{TEST_PREFIX}cpu", "value": 20.0, "category": f"{TEST_PREFIX}system"},
    )
    record_id = create.json()["id"]

    admin = create_user(role="admin")
    admin_token = _login(integration_client, username=admin["username"], password=admin["password"])

    delete = integration_client.delete(
        f"/api/v1/data-records/{record_id}",
        headers=_auth_headers(admin_token),
    )
    assert delete.status_code == 204


def test_import_json_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.post(
        "/api/v1/data-records/import/json",
        headers=_auth_headers(auth["token"]),
        json={
            "records": [
                {"title": f"{TEST_PREFIX}a", "value": 11.0, "category": f"{TEST_PREFIX}system"},
                {"title": f"{TEST_PREFIX}b", "value": 95.0, "category": f"{TEST_PREFIX}system"},
            ]
        },
    )

    assert response.status_code == 201
    assert response.json() == {"inserted_count": 2}


def test_import_json_viewer_forbidden(integration_client):
    auth = _register_and_login(integration_client, role="viewer")
    response = integration_client.post(
        "/api/v1/data-records/import/json",
        headers=_auth_headers(auth["token"]),
        json={"records": [{"title": f"{TEST_PREFIX}x", "value": 11.0, "category": f"{TEST_PREFIX}system"}]},
    )
    assert response.status_code == 403


def test_import_csv_success(integration_client):
    auth = _register_and_login(integration_client, role="user")
    csv_content = (
        "title,value,category,timestamp\n"
        f"{TEST_PREFIX}cpu,31.5,{TEST_PREFIX}system,2026-10-24T05:00:00+00:00\n"
        f"{TEST_PREFIX}ram,91.2,{TEST_PREFIX}system,2026-10-24T05:01:00+00:00\n"
    )
    response = integration_client.post(
        "/api/v1/data-records/import/csv",
        headers=_auth_headers(auth["token"]),
        files={"file": ("sample.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    assert response.json() == {"inserted_count": 2}


def test_import_csv_invalid_extension(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.post(
        "/api/v1/data-records/import/csv",
        headers=_auth_headers(auth["token"]),
        files={"file": ("sample.txt", "title,value,category\ncpu,5,system\n", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Please upload a CSV file"}


def test_import_csv_invalid_rows(integration_client):
    auth = _register_and_login(integration_client, role="user")
    csv_content = f"title,value,category\n{TEST_PREFIX}cpu,abc,{TEST_PREFIX}system\n"
    response = integration_client.post(
        "/api/v1/data-records/import/csv",
        headers=_auth_headers(auth["token"]),
        files={"file": ("sample.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "CSV contains invalid rows"


def test_import_csv_header_only(integration_client):
    auth = _register_and_login(integration_client, role="user")
    csv_content = "title,value,category\n"
    response = integration_client.post(
        "/api/v1/data-records/import/csv",
        headers=_auth_headers(auth["token"]),
        files={"file": ("sample.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "CSV has no data rows"}


def test_create_record_converts_input_timestamp_to_utc(integration_client):
    auth = _register_and_login(integration_client, role="user")
    response = integration_client.post(
        "/api/v1/data-records",
        headers=_auth_headers(auth["token"]),
        json={
            "title": f"{TEST_PREFIX}tz-check",
            "value": 66.1,
            "category": f"{TEST_PREFIX}tz-system",
            "timestamp": "2026-10-21T00:00:00+08:00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    parsed = datetime.fromisoformat(body["timestamp"])
    assert parsed == datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)


def test_list_records_converts_query_window_to_utc(integration_client):
    auth = _register_and_login(integration_client, role="user")
    headers = _auth_headers(auth["token"])
    category = f"{TEST_PREFIX}tz-query"
    created = integration_client.post(
        "/api/v1/data-records",
        headers=headers,
        json={
            "title": f"{TEST_PREFIX}tz-record",
            "value": 37.2,
            "category": category,
            "timestamp": "2026-10-21T00:30:00+08:00",
        },
    )
    assert created.status_code == 201

    listed = integration_client.get(
        "/api/v1/data-records",
        headers=headers,
        params={
            "page": 1,
            "size": 20,
            "category": category,
            "start_time": "2026-10-21T00:00:00+08:00",
            "end_time": "2026-10-21T00:59:59+08:00",
            "sort_by": "timestamp",
            "sort_order": "asc",
        },
    )

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == f"{TEST_PREFIX}tz-record"
