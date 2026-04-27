"""원유 재고 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OilInventory(Base):
    __tablename__ = "oil_inventory"
    __table_args__ = (
        UniqueConstraint("date", name="uq_oil_inventory_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    inventory_mbbl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
