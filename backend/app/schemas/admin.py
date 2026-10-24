from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

if __package__ and __package__.startswith("app."):
    from ..core.time_utils import as_utc
else:
    from core.time_utils import as_utc

AdminRole = Literal["admin", "user", "viewer"]


class BootstrapAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at_to_utc(cls, value: datetime) -> datetime:
        return as_utc(value)


class AdminUsersListResponse(BaseModel):
    items: list[AdminUserRead]
    page: int
    size: int
    total: int
    total_pages: int


class AdminUserRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AdminRole
