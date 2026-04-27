"""거시경제 지표 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint("date", "source", name="uq_macro_indicators_date_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    fed_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dollar_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="fred")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
