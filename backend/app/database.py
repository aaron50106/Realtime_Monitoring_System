# database connection and session management for the FastAPI application
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
# AsyncSession : represents an asynchronous database session
# async_sessionmaker : factory for creating AsyncSession instances
# create_async_engine : create an asynchronous database engine

if __package__:
    from .config import Settings
else:
    from config import Settings

# lifespan function for managing the application's database connection lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    engine = create_async_engine(
        settings.database_url.get_secret_value(), # secret str --> str
        pool_pre_ping=True, # enable pool pre-ping to check connections before using them
        connect_args={"connect_timeout": 5}, # set the connection timeout to 5 seconds
    )
    # create the session factory and store it in the application's state
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        await engine.dispose()


# dependency for retrieving a database session from the request
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    # create a new session using the session factory and yield it
    async with session_factory() as session:
        yield session
