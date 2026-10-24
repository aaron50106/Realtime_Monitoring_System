from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if __package__ and __package__.startswith("app."):
    from ..core.time_utils import as_utc
else:
    from core.time_utils import as_utc

# Schemas for data record operations (create, update, response, list, import)
class DataRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid") # Forbid extra fields not defined in the model

    title: str = Field(min_length=1, max_length=100, description="The title of the data record")
    value: float
    category: str = Field(min_length=1, max_length=50)
    timestamp: datetime | None = None # Optional timestamp, defaults to None if not provided

class DataRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid") # Forbid extra fields not defined in the model

    title: str | None = Field(default=None, min_length=1, max_length=100)
    value: float | None = None
    category: str | None = Field(default=None, min_length=1, max_length=50)
    timestamp: datetime | None = None
    is_alert: bool | None = None

    @model_validator(mode="after") # after model initialization
    def validate_at_least_one_field(self):
        if(
            self.title is None and
            self.value is None and
            self.category is None and
            self.timestamp is None and
            self.is_alert is None
        ):
            raise ValueError("At least one field must be provided")
        return self

class DataRecordRead(BaseModel):
    # Auto detect fields from object attributes when creating the model instance
    model_config = ConfigDict(from_attributes=True) 

    id: int
    title: str
    value: float
    category: str
    timestamp: datetime
    is_alert: bool
    creator_id: int

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp_to_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

# Schema for listing data records with pagination
class DataRecordListResponse(BaseModel):
    items: list[DataRecordRead]
    page: int
    size: int
    total: int
    total_pages: int

# Schema for importing data records from JSON
class DataRecordImportJsonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[DataRecordCreate] = Field(min_length=1, max_length=1000)

# Schema for the response after importing data records
class DataRecordImportResponse(BaseModel):
    inserted_count: int