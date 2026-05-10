"""한국 원유 수입 집중도(HHI) 분석 서비스 (한국석유공사 공공데이터 기반)

HHI (Herfindahl-Hirschman Index):
- 각 수입국의 시장 점유율(%)을 제곱하여 합산
- HHI > 2500: 고집중 → 지정학 리스크 고조
- 1500 < HHI < 2500: 중집중
- HHI < 1500: 저집중 → 수입처 다변화 양호
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, func

from app.core.database import Database
from app.models.base import get_session_factory
from app.models.oil_import import OilImport

logger = logging.getLogger(__name__)


class ImportConcentrationService:
    """한국 원유 수입 집중도 분석"""

    def __init__(self):
        self.db = Database()

    async def calculate_hhi(self, year: int | None = None) -> dict:
        """
        HHI를 산출하고 상위 수입국 목록을 반환한다.

        Args:
            year: 대상 연도. None이면 DB에서 최신 연도를 사용.

        Returns:
            {
                "year": 2024,
                "hhi": 2150.5,
                "risk_level": "medium",
                "top_countries": [
                    {"country": "사우디아라비아", "share_pct": 30.5, "volume": 140641},
                    ...
                ],
                "total_volume": 331025,
                "source": "knoc_public"
            }
        """
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 최신 연도 조회
            if year is None:
                result = await session.execute(
                    select(func.max(OilImport.year))
                )
                year = result.scalar()
                if year is None:
                    return {"error": "수입 데이터가 없습니다. CSV 적재를 먼저 실행하세요."}

            # 해당 연도의 국가별 수입량 조회
            result = await session.execute(
                select(OilImport.country, OilImport.import_volume, OilImport.import_value, OilImport.unit_price)
                .where(OilImport.year == year)
                .where(OilImport.import_volume.isnot(None))
                .where(OilImport.import_volume > 0)
                .order_by(OilImport.import_volume.desc())
            )
            rows = result.all()

            if not rows:
                return {"year": year, "hhi": 0, "risk_level": "unknown", "top_countries": [], "total_volume": 0}

            # 총 수입량 계산
            total_volume = sum(r.import_volume for r in rows)
            if total_volume == 0:
                return {"year": year, "hhi": 0, "risk_level": "unknown", "top_countries": [], "total_volume": 0}

            # HHI 산출 및 상위 국가 목록
            hhi = 0.0
            top_countries = []
            for r in rows:
                share_pct = (r.import_volume / total_volume) * 100
                hhi += share_pct ** 2
                top_countries.append({
                    "country": r.country,
                    "share_pct": round(share_pct, 2),
                    "volume": round(r.import_volume, 0),
                    "value": round(r.import_value, 0) if r.import_value else None,
                    "unit_price": round(r.unit_price, 2) if r.unit_price else None,
                })

            # 리스크 레벨 판정
            if hhi > 2500:
                risk_level = "high"
            elif hhi > 1500:
                risk_level = "medium"
            else:
                risk_level = "low"

            return {
                "year": year,
                "hhi": round(hhi, 1),
                "risk_level": risk_level,
                "top_countries": top_countries[:10],  # 상위 10개국
                "total_volume": round(total_volume, 0),
                "country_count": len(rows),
                "source": "knoc_public",
            }

    async def get_yearly_trend(self, start_year: int = 2010) -> list[dict]:
        """연도별 HHI 추이를 반환 (시계열 분석용)."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(func.distinct(OilImport.year))
                .where(OilImport.year >= start_year)
                .order_by(OilImport.year)
            )
            years = [r[0] for r in result.all()]

        trend = []
        for y in years:
            data = await self.calculate_hhi(year=y)
            if "error" not in data:
                trend.append({
                    "year": y,
                    "hhi": data["hhi"],
                    "risk_level": data["risk_level"],
                    "top_country": data["top_countries"][0]["country"] if data["top_countries"] else None,
                    "top_share_pct": data["top_countries"][0]["share_pct"] if data["top_countries"] else None,
                })

        return trend
