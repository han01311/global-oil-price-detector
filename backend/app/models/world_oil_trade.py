"""세계 원유 수출입 물량 ORM 모델 (한국석유공사 공공데이터)"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorldOilTrade(Base):
    __tablename__ = "world_oil_trades"
    __table_args__ = (
        UniqueConstraint("exporter", "importer", "data_year", name="uq_world_oil_trades"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exporter: Mapped[str] = mapped_column(String(100), nullable=False)       # 수출국/지역
    importer: Mapped[str] = mapped_column(String(100), nullable=False)       # 수입국/지역
    volume_mt: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 백만 톤
    data_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2024)
    source: Mapped[str] = mapped_column(String(50), default="knoc_public")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
