from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ and __package__.startswith("app."):
    from ..core.time_utils import TAIPEI_TZ, as_utc, to_utc_naive
    from ..models.data_record import DataRecord
else:
    from core.time_utils import TAIPEI_TZ, as_utc, to_utc_naive
    from models.data_record import DataRecord


Granularity = Literal["minute", "hour", "day"]


def build_filters(
    *,
    category: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list:
    filters = []
    if category is not None:
        filters.append(DataRecord.category == category)
    if start_time is not None:
        filters.append(DataRecord.timestamp >= to_utc_naive(start_time))
    if end_time is not None:
        filters.append(DataRecord.timestamp <= to_utc_naive(end_time))
    return filters


async def get_summary(
    db: AsyncSession,
    *,
    category: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
) -> dict:
    filters = build_filters(category=category, start_time=start_time, end_time=end_time)

    stmt = select(
        func.count(DataRecord.id),
        func.avg(DataRecord.value),
        func.min(DataRecord.value),
        func.max(DataRecord.value),
    )
    if filters:
        stmt = stmt.where(*filters)

    total_count, avg_value, min_value, max_value = (await db.execute(stmt)).one()

    return {
        "total_count": int(total_count or 0),
        "avg_value": float(avg_value) if avg_value is not None else None,
        "min_value": float(min_value) if min_value is not None else None,
        "max_value": float(max_value) if max_value is not None else None,
    }


async def get_by_category(
    db: AsyncSession,
    *,
    category: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[dict]:
    filters = build_filters(category=category, start_time=start_time, end_time=end_time)

    stmt = select(
        DataRecord.category,
        func.count(DataRecord.id),
        func.avg(DataRecord.value),
        func.min(DataRecord.value),
        func.max(DataRecord.value),
        func.sum(DataRecord.value),
    ).group_by(DataRecord.category).order_by(DataRecord.category.asc())

    if filters:
        stmt = stmt.where(*filters)

    rows = (await db.execute(stmt)).all()

    return [
        {
            "category": row[0],
            "count": int(row[1] or 0),
            "avg_value": float(row[2]) if row[2] is not None else None,
            "min_value": float(row[3]) if row[3] is not None else None,
            "max_value": float(row[4]) if row[4] is not None else None,
            "sum_value": float(row[5]) if row[5] is not None else None,
        }
        for row in rows
    ]


def _bucket_expression(granularity: Granularity):
    # Fixed offsets work without loading MariaDB's named timezone tables.
    taipei_timestamp = func.convert_tz(DataRecord.timestamp, "+00:00", "+08:00")
    if granularity == "minute":
        return func.date_format(taipei_timestamp, "%Y-%m-%d %H:%i:00")
    if granularity == "hour":
        return func.date_format(taipei_timestamp, "%Y-%m-%d %H:00:00")
    return func.date_format(taipei_timestamp, "%Y-%m-%d 00:00:00")


async def get_trend(
    db: AsyncSession,
    *,
    granularity: Granularity,
    category: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[dict]:
    filters = build_filters(category=category, start_time=start_time, end_time=end_time)
    bucket_expr = _bucket_expression(granularity).label("bucket")

    stmt = select(
        bucket_expr,
        func.count(DataRecord.id),
        func.avg(DataRecord.value),
        func.min(DataRecord.value),
        func.max(DataRecord.value),
    ).group_by(bucket_expr).order_by(bucket_expr.asc())

    if filters:
        stmt = stmt.where(*filters)

    rows = (await db.execute(stmt)).all()

    return [
        {
            "bucket": as_utc(datetime.fromisoformat(row[0]).replace(tzinfo=TAIPEI_TZ)),
            "count": int(row[1] or 0),
            "avg_value": float(row[2]) if row[2] is not None else None,
            "min_value": float(row[3]) if row[3] is not None else None,
            "max_value": float(row[4]) if row[4] is not None else None,
        }
        for row in rows
    ]


async def get_records_for_export(
    db: AsyncSession,
    *,
    category: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
):
    filters = build_filters(category=category, start_time=start_time, end_time=end_time)
    stmt = select(DataRecord).order_by(DataRecord.timestamp.asc())
    if filters:
        stmt = stmt.where(*filters)

    result = await db.execute(stmt)
    return result.scalars().all()