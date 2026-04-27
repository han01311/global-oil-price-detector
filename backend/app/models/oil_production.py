"""원유 생산량 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OilProduction(Base):
    __tablename__ = "oil_production"
    __table_args__ = (
        UniqueConstraint("date", name="uq_oil_production_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    production_mbbl_d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
