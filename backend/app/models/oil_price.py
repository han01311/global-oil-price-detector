"""유가 데이터 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OilPrice(Base):
    __tablename__ = "oil_prices"
    __table_args__ = (
        UniqueConstraint("date", "source", name="uq_oil_prices_date_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    dubai: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wti: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="opinet")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
