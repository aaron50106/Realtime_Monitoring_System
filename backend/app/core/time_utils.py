from datetime import datetime, timedelta, timezone


TAIPEI_TZ = timezone(timedelta(hours=8))


def as_utc(value: datetime) -> datetime:
    """Treat naive API/DB datetimes as UTC, never as the host's local time."""
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_utc_naive(value: datetime) -> datetime:
    return as_utc(value).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
