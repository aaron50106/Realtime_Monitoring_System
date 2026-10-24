import asyncio
import logging
import random
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if __package__ and __package__.startswith("app."):
    from ..config import Settings
    from ..core.security import hash_password
    from ..models.data_record import DataRecord
    from ..models.user import User, UserRole
    from .manager import ConnectionManager
else:
    from config import Settings
    from core.security import hash_password
    from models.data_record import DataRecord
    from models.user import User, UserRole
    from realtime.manager import ConnectionManager

logger = logging.getLogger(__name__)


class RealtimeService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        manager: ConnectionManager,
        interval_seconds: float = 5.0,
        batch_size: int = 2, # set to 2 for matching two type of data (water and temperature)
        alert_threshold: float = 80.0,
    ) -> None:
        self._session_factory = session_factory
        self._manager = manager
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._alert_threshold = alert_threshold
        self._settings = Settings()

        self._buffer: list[dict] = []
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._system_user_id: int | None = None
        self._last_flush_at = time.monotonic()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # Ensure the realtime service is started
    # This method will start the service if it is not already running
    async def ensure_started(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="realtime-generator")

    # Stop the realtime service if it is running
    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run_loop(self) -> None:
        logger.info("Realtime service started")
        last_water = None
        last_temp = None
    
        try:
            while not self._stop_event.is_set():
                last_water_level = last_water if last_water is not None else 50
                last_water_data = self._generate_water_level(last_value=last_water_level)
                self._buffer.append(last_water_data)
                last_water = last_water_data["value"]
                
                # Generate temperature point
                last_temp_degree = last_temp if last_temp is not None else 25
                last_temp_data = self._generate_temperature(last_value=last_temp_degree)
                last_temp = last_temp_data["value"]
                self._buffer.append(last_temp_data)

                await self._manager.broadcast(
                    {
                        "title": last_temp_data["title"],
                        "value": last_temp_data["value"],
                        "category": last_temp_data["category"],
                        "timestamp": last_temp_data["timestamp"].isoformat(),
                        "is_alert": last_temp_data["is_alert"],
                    }
                )

                await self._manager.broadcast(
                    {
                        "title": last_water_data["title"],
                        "value": last_water_data["value"],
                        "category": last_water_data["category"],
                        "timestamp": last_water_data["timestamp"].isoformat(),
                        "is_alert": last_water_data["is_alert"],
                    }
                )

                if len(self._buffer) >= self._batch_size:
                    await self._flush_buffer()

                await asyncio.sleep(self._interval_seconds)
        finally:
            if self._buffer:
                await self._flush_buffer()
            logger.info("Realtime service stopped")

    def _generate_water_level(self, last_value: float | None = None) -> dict:
        category = "Water_Level"
        if last_value is None:
            value = 50
        else:
            value = last_value + round(random.uniform(-5, 5), 2)
        now = datetime.now(timezone.utc)

        return {
            "title": f"{category}-sensor",
            "value": value,
            "category": category,
            "timestamp": now,
            "is_alert": value > self._alert_threshold,
        }

    def _generate_temperature(self, last_value: float | None = None) -> dict:
        category = "Temperature"
        if last_value is None:
            value = 25
        else:
            value = last_value + round(random.uniform(-1, 1), 2)
        now = datetime.now(timezone.utc)

        return {
            "title": f"{category}-sensor",
            "value": value,
            "category": category,
            "timestamp": now,
            "is_alert": value > self._alert_threshold,
        }

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return

        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush_at = time.monotonic()

        try:
            async with self._session_factory() as session:
                creator_id = await self._get_or_create_system_user_id(session)
                records = [
                    DataRecord(
                        title=item["title"],
                        value=item["value"],
                        category=item["category"],
                        timestamp=item["timestamp"],
                        is_alert=item["is_alert"],
                        creator_id=creator_id,
                    )
                    for item in batch
                ]
                session.add_all(records)
                await session.commit()
        except Exception:
            # If flushing the batch fails, put it back into the buffer to avoid data loss
            self._buffer = batch + self._buffer
            logger.exception("Failed to flush realtime batch into database")

    async def _get_or_create_system_user_id(self, session: AsyncSession) -> int:
        if self._system_user_id is not None:
            return self._system_user_id

        result = await session.execute(select(User).where(User.username == "system_bot"))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                username="system_bot",
                email="system_bot@example.local",
                password_hash=hash_password(self._settings.system_bot_password.get_secret_value()),
                role=UserRole.ADMIN.value,
            )
            session.add(user)
            await session.flush()

        self._system_user_id = user.id
        return self._system_user_id