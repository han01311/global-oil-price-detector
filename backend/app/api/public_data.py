"""공공데이터(data.go.kr) 전용 API 라우터

- 환율 조회 (한국수출입은행)
- 수입 집중도(HHI) 조회 (한국석유공사)
- 활용 공공데이터 목록 (대회 심사용 메타데이터)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.core.config import settings
from app.services.exchange_rate_collector import ExchangeRateCollector
from app.services.import_concentration import ImportConcentrationService

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
                "usage": "글로벌 원유 교역 흐름 분석 → 수급 시그널 보강",
                "integrated": True,
            },
        ],
        "total_count": 3,
        "note": "모든 데이터는 대한민국 공공데이터포털(data.go.kr)에서 제공됩니다.",
    }
