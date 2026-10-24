from datetime import datetime

from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    total_count: int
    avg_value: float | None
    min_value: float | None
    max_value: float | None


class CategoryAggregateItem(BaseModel):
    category: str
    count: int
    avg_value: float | None
    min_value: float | None
    max_value: float | None
    sum_value: float | None


class CategoryAggregateResponse(BaseModel):
    items: list[CategoryAggregateItem]
    total_categories: int


class TrendPoint(BaseModel):
    bucket: datetime = Field(
        description="UTC bucket start (ISO 8601); buckets follow Taiwan time (UTC+8), including local midnight for day."
    )
    count: int
    avg_value: float | None
    min_value: float | None
    max_value: float | None


class TrendResponse(BaseModel):
    granularity: str
    points: list[TrendPoint]