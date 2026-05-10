"""국가별 원유 수입 ORM 모델 (한국석유공사 공공데이터)"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OilImport(Base):
    __tablename__ = "oil_imports"
    __table_args__ = (
        UniqueConstraint("year", "country", name="uq_oil_imports_year_country"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    import_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # 천 배럴
    import_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # 천 달러
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)         # 달러/배럴
    source: Mapped[str] = mapped_column(String(50), default="knoc_public")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
