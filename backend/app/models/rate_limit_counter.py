"""Rate Limit 카운터 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        UniqueConstraint("source", "date", name="uq_rate_limit_source_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    last_request_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
