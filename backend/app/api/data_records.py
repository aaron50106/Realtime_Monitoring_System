import csv
import io
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ and __package__.startswith("app."):
    from ..core.time_utils import to_utc_naive, utc_now_naive
    from ..database import get_db
    from ..models.data_record import DataRecord
    from ..models.user import User, UserRole
    from ..schemas.data_record import (
        DataRecordCreate,
        DataRecordImportJsonRequest,
        DataRecordImportResponse,
        DataRecordListResponse,
        DataRecordRead,
        DataRecordUpdate,
    )
    from .auth import get_current_user, require_role

else:
    from core.time_utils import to_utc_naive, utc_now_naive
    from database import get_db
    from models.data_record import DataRecord
    from models.user import User, UserRole
    from schemas.data_record import (
        DataRecordCreate,
        DataRecordImportJsonRequest,
        DataRecordImportResponse,
        DataRecordListResponse,
        DataRecordRead,
        DataRecordUpdate,
    )
    from api.auth import get_current_user, require_role

router = APIRouter(prefix="/data-records", tags=["data-records"])

SortBy = Literal["timestamp", "value", "title", "category"]
SortOrder = Literal["asc", "desc"]

ALERT_THRESHOLD = 80.0


def _compute_alert(value: float) -> bool:
    return value > ALERT_THRESHOLD


def _can_manage_record(record: DataRecord, user: User) -> bool:
    return user.role == UserRole.ADMIN.value or record.creator_id == user.id

async def _get_record_or_404(db: AsyncSession, record_id: int) -> DataRecord:
    result = await db.execute(select(DataRecord).where(DataRecord.id == record_id))
    record = result.scalar_one_or_none() # scalar_one_or_none returns the first result or None if no rows are found
    if record is None:
        raise HTTPException(status_code=404, detail="Data record not found")
    return record

# Create a new data record
@router.post("", response_model=DataRecordRead, status_code=status.HTTP_201_CREATED)
async def create_data_record(
    payload: DataRecordCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN.value, UserRole.USER.value)),
    ],
) -> DataRecordRead:
    record_kwargs = {
        "title": payload.title,
        "value": payload.value,
        "category": payload.category,
        "is_alert": _compute_alert(payload.value),
        "creator_id": current_user.id,
        "timestamp": to_utc_naive(payload.timestamp) if payload.timestamp is not None else utc_now_naive(),
    }

    record = DataRecord(**record_kwargs)
    db.add(record)
    await db.commit() # Commit the new record to the database
    await db.refresh(record) # Refresh the record instance with the latest data from the database
    return DataRecordRead.model_validate(record) # Return the validated data record response to fronte

# List data records with optional filtering, sorting, and pagination
@router.get("", response_model=DataRecordListResponse)
async def list_data_records(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    sort_by: SortBy = Query(default="timestamp"),
    sort_order: SortOrder = Query(default="desc"),
) -> DataRecordListResponse:
    normalized_start_time = to_utc_naive(start_time) if start_time is not None else None
    normalized_end_time = to_utc_naive(end_time) if end_time is not None else None

    if (
        normalized_start_time is not None
        and normalized_end_time is not None
        and normalized_start_time > normalized_end_time
    ):
        raise HTTPException(status_code=422, detail="start_time must be less than or equal to end_time")

    filters = []
    if category is not None:
        filters.append(DataRecord.category == category)
    if normalized_start_time is not None:
        filters.append(DataRecord.timestamp >= normalized_start_time)
    if normalized_end_time is not None:
        filters.append(DataRecord.timestamp <= normalized_end_time)

    count_stmt = select(func.count()).select_from(DataRecord)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    sort_column = {
        "timestamp": DataRecord.timestamp,
        "value": DataRecord.value,
        "title": DataRecord.title,
        "category": DataRecord.category,
    }[sort_by]
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    stmt = select(DataRecord)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(order_clause).offset((page - 1) * size).limit(size)

    result = await db.execute(stmt)
    records = result.scalars().all()

    total_pages = (total + size - 1) // size if total > 0 else 0
    return DataRecordListResponse(
        items=[DataRecordRead.model_validate(item) for item in records], # Validate each data record for the response
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{record_id}", response_model=DataRecordRead)
async def get_data_record(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DataRecordRead:
    record = await _get_record_or_404(db, record_id)
    return DataRecordRead.model_validate(record)


@router.put("/{record_id}", response_model=DataRecordRead)
async def update_data_record(
    record_id: int,
    payload: DataRecordUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN.value, UserRole.USER.value)),
    ],
) -> DataRecordRead:
    record = await _get_record_or_404(db, record_id)

    if not _can_manage_record(record, current_user):
        raise HTTPException(status_code=403, detail="Only creator or admin can update this record")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("timestamp") is not None:
        update_data["timestamp"] = to_utc_naive(update_data["timestamp"])

    if "value" in update_data and "is_alert" not in update_data:
        update_data["is_alert"] = _compute_alert(update_data["value"])

    for field, value in update_data.items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return DataRecordRead.model_validate(record)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_record(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN.value, UserRole.USER.value)),
    ],
) -> Response:
    record = await _get_record_or_404(db, record_id)

    if not _can_manage_record(record, current_user):
        raise HTTPException(status_code=403, detail="Only creator or admin can delete this record")

    await db.delete(record)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import/json", response_model=DataRecordImportResponse, status_code=status.HTTP_201_CREATED)
async def import_data_records_json(
    payload: DataRecordImportJsonRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN.value, UserRole.USER.value)),
    ],
) -> DataRecordImportResponse:
    for item in payload.records:
        record_kwargs = {
            "title": item.title,
            "value": item.value,
            "category": item.category,
            "is_alert": _compute_alert(item.value),
            "creator_id": current_user.id,
            "timestamp": to_utc_naive(item.timestamp) if item.timestamp is not None else utc_now_naive(),
        }
        db.add(DataRecord(**record_kwargs))

    await db.commit()
    return DataRecordImportResponse(inserted_count=len(payload.records))


@router.post("/import/csv", response_model=DataRecordImportResponse, status_code=status.HTTP_201_CREATED)
async def import_data_records_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN.value, UserRole.USER.value)),
    ],
    file: UploadFile = File(...),
) -> DataRecordImportResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from None

    reader = csv.DictReader(io.StringIO(text))
    required_headers = {"title", "value", "category"}
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header is missing")

    normalized_headers = {h.strip() for h in reader.fieldnames if h is not None}
    if not required_headers.issubset(normalized_headers):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain headers: title,value,category (optional timestamp)",
        )

    records: list[DataRecord] = []
    row_errors: list[dict] = []

    for row_number, row in enumerate(reader, start=2):
        payload_dict = {
            "title": (row.get("title") or "").strip(),
            "value": row.get("value"),
            "category": (row.get("category") or "").strip(),
            "timestamp": (row.get("timestamp") or "").strip() or None,
        }

        try:
            item = DataRecordCreate.model_validate(payload_dict)
        except ValidationError as exc:
            row_errors.append({"row": row_number, "errors": exc.errors()})
            continue

        record_kwargs = {
            "title": item.title,
            "value": item.value,
            "category": item.category,
            "is_alert": _compute_alert(item.value),
            "creator_id": current_user.id,
            "timestamp": to_utc_naive(item.timestamp) if item.timestamp is not None else utc_now_naive(),
        }
        records.append(DataRecord(**record_kwargs))

    if row_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "CSV contains invalid rows", "errors": row_errors[:20]},
        )

    if not records:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    db.add_all(records)
    await db.commit()
    return DataRecordImportResponse(inserted_count=len(records))