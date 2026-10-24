from pathlib import Path
import runpy
from unittest.mock import AsyncMock, MagicMock

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.main import app, get_db


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+asyncmy://test:test@127.0.0.1:3307/test",
    )
    # Ignore any local .env; unit tests use fake configuration only.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://test_user:test_pass@127.0.0.1:3307/test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters-long")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("SYSTEM_BOT_PASSWORD", "test-system-bot-password")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = AsyncMock(spec=AsyncSession)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok!!"}


def test_database_health_connected(client, db_session):
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"database": "connected"}
    db_session.connection.assert_awaited_once_with()


@pytest.mark.parametrize(
    "error",
    [
        OperationalError(None, None, Exception("fake-sensitive-connection-detail")),
        OSError("fake-sensitive-connection-detail"),
        TimeoutError("fake-sensitive-connection-detail"),
    ],
)
def test_database_health_unavailable(client, db_session, caplog, error):
    db_session.connection.side_effect = error
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "fake-sensitive-connection-detail" not in response.text
    assert "fake-sensitive-connection-detail" not in caplog.text
    assert "Database health check failed" in caplog.text
    assert client.get("/health").json() == {"status": "ok!!"}


def test_swagger_and_openapi(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text
    schema = client.get("/openapi.json").json()
    assert "/health" in schema["paths"]
    assert "200" in schema["paths"]["/health/db"]["get"]["responses"]
    assert "503" in schema["paths"]["/health/db"]["get"]["responses"]


def test_original_script_entrypoint(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "app" / "main.py"
    monkeypatch.syspath_prepend(str(script.parent))
    run_server = MagicMock()
    monkeypatch.setattr(uvicorn, "run", run_server)
    runpy.run_path(str(script), run_name="__main__")
    run_server.assert_called_once()
    assert run_server.call_args.kwargs == {
        "host": "127.0.0.1",
        "port": 8000,
        "ws": "websockets-sansio",
    }
    script_app = run_server.call_args.args[0]
    assert "/health/db" in script_app.openapi()["paths"]
