"""뉴스 기사 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_classified: Mapped[int] = mapped_column(Integer, default=0) # 0: unclassified, 1: classified, -1: failed
    classification_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    classification_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    hold_status: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # 0: 정상, 1: 보류, 2: 수동입력

