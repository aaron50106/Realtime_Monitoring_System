import io
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ and __package__.startswith("app."):
    from ..core.time_utils import TAIPEI_TZ, as_utc, to_utc_naive
    from ..database import get_db
    from ..models.user import User
    from ..schemas.analytics import (
        AnalyticsSummaryResponse,
        CategoryAggregateItem,
        CategoryAggregateResponse,
        TrendPoint,
        TrendResponse,
    )
    from ..services.analytics import get_by_category, get_records_for_export, get_summary, get_trend
    from .auth import get_current_user
else:
    from core.time_utils import TAIPEI_TZ, as_utc, to_utc_naive
    from database import get_db
    from models.user import User
    from schemas.analytics import (
        AnalyticsSummaryResponse,
        CategoryAggregateItem,
        CategoryAggregateResponse,
        TrendPoint,
        TrendResponse,
    )
    from services.analytics import get_by_category, get_records_for_export, get_summary, get_trend
    from api.auth import get_current_user

def _validate_time_range(
    start_time: datetime | None = Query(
        default=None, description="Inclusive start; offsets are converted to UTC. A timezone-free value means UTC."
    ),
    end_time: datetime | None = Query(
        default=None, description="Inclusive end; offsets are converted to UTC. A timezone-free value means UTC."
    ),
) -> None:
    if (
        start_time is not None
        and end_time is not None
        and to_utc_naive(start_time) > to_utc_naive(end_time)
    ):
        raise HTTPException(status_code=422, detail="start_time must be less than or equal to end_time")


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(_validate_time_range)],
)


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> AnalyticsSummaryResponse:
    _ = current_user
    data = await get_summary(db, category=category, start_time=start_time, end_time=end_time)
    return AnalyticsSummaryResponse(**data)


@router.get("/by-category", response_model=CategoryAggregateResponse)
async def analytics_by_category(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> CategoryAggregateResponse:
    _ = current_user
    items = await get_by_category(db, category=category, start_time=start_time, end_time=end_time)
    return CategoryAggregateResponse(
        items=[CategoryAggregateItem(**item) for item in items],
        total_categories=len(items),
    )


@router.get("/trend", response_model=TrendResponse)
async def analytics_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    granularity: Literal["minute", "hour", "day"] = Query(default="hour"),
    category: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> TrendResponse:
    _ = current_user
    points = await get_trend(
        db,
        granularity=granularity,
        category=category,
        start_time=start_time,
        end_time=end_time,
    )
    return TrendResponse(
        granularity=granularity,
        points=[TrendPoint(**point) for point in points],
    )


@router.get("/export/excel")
async def analytics_export_excel(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
):
    _ = current_user
    records = await get_records_for_export(
        db,
        category=category,
        start_time=start_time,
        end_time=end_time,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "analytics_records"

    ws.append(["id", "title", "value", "category", "timestamp", "is_alert", "creator_id", "timestamp_taipei"])
    for r in records:
        timestamp_utc = as_utc(r.timestamp)
        ws.append([
            r.id,
            r.title,
            r.value,
            r.category,
            timestamp_utc.isoformat(),
            r.is_alert,
            r.creator_id,
            timestamp_utc.astimezone(TAIPEI_TZ).isoformat(),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"analytics_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )