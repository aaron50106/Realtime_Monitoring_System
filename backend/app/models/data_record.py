from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

class DataRecord(Base):
    __tablename__ = "data_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_alert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    creator = relationship("User", back_populates="records")