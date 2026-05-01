"""파이프라인 작업 로그 ORM 모델"""
from typing import Optional

from sqlalchemy import Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # retry, bulk_classify, scheduled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")  # queued, running, completed, failed
    total_articles: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    article_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # 대상 기사 ID 목록
    results_detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # 개별 기사 처리 결과
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
