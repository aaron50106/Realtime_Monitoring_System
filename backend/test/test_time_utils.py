from datetime import datetime, timedelta, timezone

import pytest

from app.core.time_utils import as_utc, to_utc_naive, utc_now_naive
from app.schemas.admin import AdminUserRead
from app.schemas.data_record import DataRecordRead


@pytest.mark.parametrize(
    "raw",
    [
        "2026-10-21T00:00:00+08:00",
        "2026-10-20T16:00:00Z",
        "2026-10-20T12:00:00-04:00",
        "2026-10-20T16:00:00",
    ],
)
def test_equivalent_timestamps_use_utc(raw):
    expected = datetime(2026, 10, 20, 16, tzinfo=timezone.utc)
    value = datetime.fromisoformat(raw)
    assert as_utc(value) == expected
    assert as_utc(value).utcoffset() == timedelta(0)
    assert to_utc_naive(value) == expected.replace(tzinfo=None)
    assert to_utc_naive(value).tzinfo is None

    record = DataRecordRead(
        id=1, title="test", value=10, category="Water_Level",
        timestamp=value, is_alert=False, creator_id=1,
    )
    parsed_record = DataRecordRead.model_validate({
        **record.model_dump(), "timestamp": raw,
    })
    assert parsed_record.timestamp == expected
    assert parsed_record.timestamp.utcoffset() == timedelta(0)

    admin_user = AdminUserRead.model_validate({
        "id": 1, "username": "test", "email": "test@example.com",
        "role": "user", "created_at": raw,
    })
    assert admin_user.created_at == expected
    assert admin_user.created_at.utcoffset() == timedelta(0)


def test_default_timestamp_is_current_naive_utc():
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    value = utc_now_naive()
    after = datetime.now(timezone.utc).replace(tzinfo=None)
    assert value.tzinfo is None
    assert before <= value <= after
