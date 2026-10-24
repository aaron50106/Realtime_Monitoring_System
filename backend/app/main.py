import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
import pydantic
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

if __package__:
    from .database import get_db, lifespan
    from .api.auth import router as auth_router
    from .api.admin import router as admin_router
    from .api.data_records import router as data_records_router
    from .api.realtime import router as realtime_router
    from .realtime.manager import ConnectionManager
    from .realtime.service import RealtimeService
    from .config import Settings
    from .api.analytics import router as analytics_router
else:
    from database import get_db, lifespan
    from api.auth import router as auth_router
    from api.admin import router as admin_router
    from api.data_records import router as data_records_router
    from api.realtime import router as realtime_router
    from realtime.manager import ConnectionManager
    from config import Settings
    from api.analytics import router as analytics_router
    from realtime.service import RealtimeService

logger = logging.getLogger(__name__)

# Pydantic models 
class HealthCheckResponse(pydantic.BaseModel):
    status: str


class DatabaseHealthResponse(pydantic.BaseModel):
    database: str

@asynccontextmanager
async def realtime_lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with lifespan(app): # Use the original database lifespan as the base context manager
        settings = Settings()
        app.state.realtime_manager = ConnectionManager()
        app.state.realtime_service = RealtimeService(
            session_factory=app.state.session_factory,
            manager=app.state.realtime_manager,
        )
        # Start the realtime service to begin generating and broadcasting data points as system started
        if settings.realtime_auto_start:
            await app.state.realtime_service.ensure_started() 
        try:
            yield
        finally:
            await app.state.realtime_service.stop()

app = FastAPI(
    title = "即時資料分析與監控系統-Aaron",
    version = "0.1.0",
    lifespan=realtime_lifespan, # Use the realtime lifespan which includes the database lifespan as well
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(data_records_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")

@app.get('/health', tags=["system"])
async def health_check() -> HealthCheckResponse:
    """Check if the system is running"""
    return HealthCheckResponse(status="ok!!")


@app.get(
    '/health/db',
    tags=["system"],
    responses={503: {"description": "Database unavailable"}},
)
async def database_health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseHealthResponse:
    """Check database connectivity without running an application SQL query."""
    try:
        await db.connection()
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        logger.warning("Database health check failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return DatabaseHealthResponse(database="connected")



def start_app():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, ws="websockets-sansio")

if __name__ == "__main__":
    start_app()