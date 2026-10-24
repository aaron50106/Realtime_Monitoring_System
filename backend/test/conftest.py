import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.core.security import hash_password
from app.main import app
from app.models.data_record import DataRecord
from app.models.user import User, UserRole

TEST_PREFIX = "itest_"
TEST_PASSWORD = "StrongPass123!"

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters-long")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("SYSTEM_BOT_PASSWORD", "test-system-bot-password")


@pytest.fixture(scope="session")
def integration_settings():
    return Settings()


@pytest.fixture(scope="session")
def integration_db_url(integration_settings):
    return integration_settings.database_url.get_secret_value()


@pytest.fixture(scope="session")
def integration_session_factory(integration_db_url):
    engine = create_async_engine(
        integration_db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        asyncio.run(engine.dispose())


async def _cleanup_test_rows(session_factory: async_sessionmaker):
    async with session_factory() as session:
        result = await session.execute(
            select(User.id).where(
                or_(
                    User.username.like(f"{TEST_PREFIX}%"),
                    User.email.like(f"{TEST_PREFIX}%"),
                )
            )
        )
        prefixed_user_ids = list(result.scalars().all())

        if prefixed_user_ids:
            await session.execute(
                delete(DataRecord).where(DataRecord.creator_id.in_(prefixed_user_ids))
            )

        await session.execute(
            delete(DataRecord).where(
                or_(
                    DataRecord.title.like(f"{TEST_PREFIX}%"),
                    DataRecord.category.like(f"{TEST_PREFIX}%"),
                )
            )
        )
        await session.execute(
            delete(User).where(
                or_(
                    User.username.like(f"{TEST_PREFIX}%"),
                    User.email.like(f"{TEST_PREFIX}%"),
                )
            )
        )
        await session.commit()


@pytest.fixture
def clean_test_data(integration_session_factory):
    asyncio.run(_cleanup_test_rows(integration_session_factory))
    try:
        yield
    finally:
        asyncio.run(_cleanup_test_rows(integration_session_factory))


@pytest.fixture
def integration_client(monkeypatch, clean_test_data, integration_db_url):
    monkeypatch.setenv("DATABASE_URL", integration_db_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters-long")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("SYSTEM_BOT_PASSWORD", "test-system-bot-password")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def create_user(integration_session_factory):
    def _create(
        *,
        role: str = UserRole.USER.value,
        username: str | None = None,
        password: str = TEST_PASSWORD,
    ) -> dict:
        name = username or f"{TEST_PREFIX}{uuid.uuid4().hex[:10]}"
        email = f"{name}@example.com"

        async def _insert():
            async with integration_session_factory() as session:
                user = User(
                    username=name,
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "password": password,
                    "role": user.role,
                }

        return asyncio.run(_insert())

    return _create
