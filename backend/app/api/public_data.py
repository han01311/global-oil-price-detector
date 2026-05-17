"""공공데이터(data.go.kr) 전용 API 라우터

- 환율 조회 (한국수출입은행)
- 수입 집중도(HHI) 조회 (한국석유공사)
- 세계 원유 수출입 물량 조회 (한국석유공사)
- 활용 공공데이터 목록 (대회 심사용 메타데이터)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.core.config import settings
from app.services.exchange_rate_collector import ExchangeRateCollector
from app.services.import_concentration import ImportConcentrationService
from app.models.base import get_session_factory
from app.models.world_oil_trade import WorldOilTrade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/exchange-rate")
async def get_exchange_rate(date: Optional[str] = Query(None, description="조회 날짜 (YYYYMMDD)")):
    """최신 원/달러 환율 조회

    한국수출입은행 Open API (공공데이터)를 통해 매매기준율을 반환합니다.
    주말/공휴일에는 직전 영업일 캐시를 반환합니다.
    """
    collector = ExchangeRateCollector()
    result = await collector.get_exchange_rate(date)
    if result:
        return result
    return {"error": "환율 데이터를 가져올 수 없습니다.", "hint": "KOREAEXIM_API_KEY 설정을 확인하세요."}


@router.get("/import-concentration")
async def get_import_concentration(year: Optional[int] = Query(None, description="대상 연도")):
    """한국 원유 수입 집중도(HHI) 조회

    한국석유공사 공공데이터를 기반으로 수입 집중도(HHI)를 산출합니다.
    HHI > 2500: 고집중(지정학 리스크), 1500~2500: 중집중, < 1500: 저집중
    """
    service = ImportConcentrationService()
    return await service.calculate_hhi(year=year)


@router.get("/import-concentration/trend")
async def get_import_concentration_trend(start_year: int = Query(2010, description="시작 연도")):
    """연도별 수입 집중도(HHI) 추이"""
    service = ImportConcentrationService()
    return await service.get_yearly_trend(start_year=start_year)


@router.get("/world-oil-trade")
async def get_world_oil_trade(
    data_year: Optional[int] = Query(None, description="데이터 연도"),
    exporter: Optional[str] = Query(None, description="수출국 필터"),
    importer: Optional[str] = Query(None, description="수입국 필터"),
    top_n: int = Query(10, description="상위 N개 교역 흐름"),
):
    """세계 원유 수출입 물량 조회

    한국석유공사(KNOC) 공공데이터 기반 글로벌 원유 교역 매트릭스.
    21개 수출국 × 15개 수입국 물량(백만 톤).
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 데이터 연도 확인
        if data_year is None:
            result = await session.execute(select(func.max(WorldOilTrade.data_year)))
            data_year = result.scalar()
            if data_year is None:
                return {"error": "세계 교역 데이터가 없습니다. CSV 적재를 먼저 실행하세요."}

        # 기본 쿼리
        stmt = (
            select(WorldOilTrade)
            .where(WorldOilTrade.data_year == data_year)
            .where(WorldOilTrade.volume_mt.isnot(None))
            .where(WorldOilTrade.volume_mt > 0)
        )
        if exporter:
            stmt = stmt.where(WorldOilTrade.exporter == exporter)
        if importer:
            stmt = stmt.where(WorldOilTrade.importer == importer)

        stmt = stmt.order_by(WorldOilTrade.volume_mt.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()

        # 수출국별 총 수출량
        exporter_stmt = (
            select(
                WorldOilTrade.exporter,
                func.sum(WorldOilTrade.volume_mt).label("total_volume"),
            )
            .where(WorldOilTrade.data_year == data_year)
            .where(WorldOilTrade.volume_mt > 0)
            .group_by(WorldOilTrade.exporter)
            .order_by(func.sum(WorldOilTrade.volume_mt).desc())
        )
        exporter_result = await session.execute(exporter_stmt)
        exporter_totals = [
            {"exporter": r.exporter, "total_volume_mt": round(r.total_volume, 1)}
            for r in exporter_result.all()
        ]

        # 수입국별 총 수입량
        importer_stmt = (
            select(
                WorldOilTrade.importer,
                func.sum(WorldOilTrade.volume_mt).label("total_volume"),
            )
            .where(WorldOilTrade.data_year == data_year)
            .where(WorldOilTrade.volume_mt > 0)
            .group_by(WorldOilTrade.importer)
            .order_by(func.sum(WorldOilTrade.volume_mt).desc())
        )
        importer_result = await session.execute(importer_stmt)
        importer_totals = [
            {"importer": r.importer, "total_volume_mt": round(r.total_volume, 1)}
            for r in importer_result.all()
        ]

        # 상위 N개 교역 흐름
        top_flows = [
            {
                "exporter": r.exporter,
                "importer": r.importer,
                "volume_mt": round(r.volume_mt, 1),
            }
            for r in rows[:top_n]
        ]

        # 전체 교역량
        total_volume = sum(r.volume_mt for r in rows if r.volume_mt)

        return {
            "data_year": data_year,
            "total_volume_mt": round(total_volume, 1),
            "exporter_count": len(exporter_totals),
            "importer_count": len(importer_totals),
            "top_flows": top_flows,
            "exporters": exporter_totals,
            "importers": importer_totals,
            "source": "knoc_public",
        }


@router.get("/data-sources")
async def get_public_data_sources():
    """OilLens에서 활용 중인 공공데이터 목록 (대회 심사용 메타데이터)

    프로젝트에서 사용하는 모든 공공데이터의 출처, 유형, 활용 방식을 반환합니다.
    """
    return {
        "public_data_sources": [
            {
                "name": "한국수출입은행 현재환율 API",
                "provider": "한국수출입은행",
                "portal": "data.go.kr",
                "type": "Open API",
                "url": "https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C",
                "data_format": "JSON",
                "update_cycle": "매 영업일",
                "usage": "원/달러 매매기준율 → 원화 환산 유가, 거시경제 피처",
                "integrated": bool(settings.KOREAEXIM_API_KEY),
            },
            {
                "name": "한국석유공사 국내 원유수입 국가별",
                "provider": "한국석유공사(KNOC)",
                "portal": "data.go.kr",
                "type": "파일데이터 (CSV)",
                "url": "https://www.data.go.kr/data/15054606/fileData.do",
                "data_format": "CSV (EUC-KR)",
                "update_cycle": "연 1회",
                "usage": "수입 집중도(HHI) 산출 → 지정학 리스크 분석",
                "integrated": True,
            },
            {
                "name": "한국석유공사 세계 원유 수출입 물량",
                "provider": "한국석유공사(KNOC)",
                "portal": "data.go.kr",
                "type": "파일데이터 (CSV)",
                "url": "https://www.data.go.kr/data/15054611/fileData.do",
                "data_format": "CSV (EUC-KR)",
                "update_cycle": "연 1회",
                "usage": "글로벌 원유 교역 흐름 분석 → 수급 구조 시각화",
                "integrated": True,
            },
        ],
        "total_count": 3,
        "note": "모든 데이터는 대한민국 공공데이터포털(data.go.kr)에서 제공됩니다.",
    }
