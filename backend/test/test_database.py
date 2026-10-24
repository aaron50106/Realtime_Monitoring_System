import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app import database
from app.config import Settings


@pytest.fixture(autouse=True)
def jwt_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://test_user:test_pass@127.0.0.1:3307/test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters-long")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("SYSTEM_BOT_PASSWORD", "test-system-bot-password")


@pytest.mark.parametrize("fail_during_lifespan", [False, True])
def test_engine_lifecycle(monkeypatch, fail_during_lifespan):
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+asyncmy://test:test@127.0.0.1:3307/test",
    )
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://test_user:test_pass@127.0.0.1:3307/test")
    engine = MagicMock()
    engine.dispose = AsyncMock()
    create_engine = MagicMock(return_value=engine)
    create_factory = MagicMock()
    monkeypatch.setattr(database, "create_async_engine", create_engine)
    monkeypatch.setattr(database, "async_sessionmaker", create_factory)
    app = FastAPI()

    async def run():
        async with database.lifespan(app):
            assert app.state.session_factory is create_factory.return_value
            if fail_during_lifespan:
                raise RuntimeError("test shutdown")

    if fail_during_lifespan:
        with pytest.raises(RuntimeError, match="test shutdown"):
            asyncio.run(run())
    else:
        asyncio.run(run())

    assert create_engine.call_args.kwargs["pool_pre_ping"] is True
    assert create_engine.call_args.kwargs["connect_args"]["connect_timeout"] == 5
    create_factory.assert_called_once_with(engine, expire_on_commit=False)
    engine.dispose.assert_awaited_once_with()


@pytest.mark.parametrize("fail_during_request", [False, True])
def test_get_db_closes_session(fail_during_request):
    app = FastAPI()
    session = AsyncMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    app.state.session_factory = MagicMock(return_value=session)
    request = Request({"type": "http", "app": app})

    async def run():
        dependency = database.get_db(request)
        assert await anext(dependency) is session
        if fail_during_request:
            with pytest.raises(RuntimeError, match="test request"):
                await dependency.athrow(RuntimeError("test request"))
        else:
            await dependency.aclose()

    asyncio.run(run())
    session.__aexit__.assert_awaited_once()


def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url",
    ["not-a-url-fake-secret", "mysql+pymysql://user:fake-secret@localhost/db"],
)
def test_settings_reject_invalid_urls_without_exposing_input(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "fake-secret" not in str(error.value)


def test_settings_environment_overrides_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=mysql+asyncmy://user:pass@localhost/file\n"
        "JWT_SECRET_KEY=file-secret\n"
        "MARIADB_DATABASE=file\n",
        encoding="utf-8",
    )
    environment_url = "mysql+asyncmy://env:fake@localhost/env"
    environment_url = "mysql+asyncmy://env_user:env_pass@localhost/env"
    monkeypatch.setenv("DATABASE_URL", environment_url)
    settings = Settings(_env_file=env_file)
    assert settings.database_url.get_secret_value() == environment_url
    assert environment_url not in repr(settings)
