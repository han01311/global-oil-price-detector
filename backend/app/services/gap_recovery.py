from __future__ import annotations

"""
서비스 점검 — Gap Recovery Service
매일 정상적으로 데이터가 수집되고 있는지 일별로 확인하고,
누락된 날짜를 감지하여 복구한다.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.core.database import Database
from app.models.base import get_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Source definitions
# ──────────────────────────────────────────────

SOURCE_DEFS = [
    {
        "id": "opinet_prices",
        "label": "유가 (Opinet)",
        "icon": "⛽",
        "table": "oil_prices",
        "date_col": "date",
        "frequency": "weekday",  # 평일(월~금)마다 데이터 기대
        "check_days": 30,
        "lag_days": 1,
    },
    {
        "id": "eia_inventory",
        "label": "재고 (EIA)",
        "icon": "🛢",
        "table": "oil_inventory",
        "date_col": "date",
        "frequency": "weekly",  # 주 1회 (수요일)
        "check_days": 30,
        "lag_days": 14,
    },
    {
        "id": "eia_production",
        "label": "생산 (EIA)",
        "icon": "⛏",
        "table": "oil_production",
        "date_col": "date",
        "frequency": "weekly",
        "check_days": 30,
        "lag_days": 14,
    },
    {
        "id": "fred_macro",
        "label": "거시경제 (FRED)",
        "icon": "🏛",
        "table": "macro_indicators",
        "date_col": "date",
        "frequency": "weekly",
        "check_days": 30,
        "lag_days": 7,
    },
    {
        "id": "news",
        "label": "뉴스 (News)",
        "icon": "📰",
        "table": "news_articles",
        "date_col": "collected_at",
        "frequency": "daily",  # 매일 수집 기대
        "check_days": 30,
        "lag_days": 1,
    },
]


def _expected_dates(frequency: str, check_days: int) -> List[date]:
    """주어진 빈도에 따라 최근 check_days 동안의 '수집되었어야 하는 날짜' 리스트를 반환."""
    today = date.today()
    dates = []
    for i in range(check_days):
        d = today - timedelta(days=i)
        if frequency == "weekday":
            # 평일만 (월=0 ~ 금=4)
            if d.weekday() < 5:
                dates.append(d)
        elif frequency == "daily":
            dates.append(d)
        elif frequency == "weekly":
            # 매주 1회 — 해당 주에 최소 1건이 있으면 OK
            # 주의 시작일(월요일)만 대표로 기록
            monday = d - timedelta(days=d.weekday())
            if monday not in dates and monday <= today:
                dates.append(monday)
    return sorted(dates)


# ──────────────────────────────────────────────
# In-memory recovery state
# ──────────────────────────────────────────────

_recovery_state: Dict = {
    "is_running": False,
    "started_at": None,
    "sources": {},       # source_id -> { status, message, records }
    "completed_at": None,
}
_recovery_lock = asyncio.Lock()


def get_recovery_status() -> Dict:
    """현재 복구 진행 상태를 반환."""
    return dict(_recovery_state)


# ──────────────────────────────────────────────
# Diagnose
# ──────────────────────────────────────────────

async def diagnose() -> List[Dict]:
    """각 데이터 소스별 일별 수집 현황을 진단한다."""
    session_factory = get_session_factory()
    results = []
    today = date.today()

    async with session_factory() as session:
        for src in SOURCE_DEFS:
            try:
                date_col = src["date_col"]
                table = src["table"]
                check_days = src["check_days"]
                frequency = src["frequency"]

                # 1) 최근 check_days일 동안 데이터가 존재하는 날짜 목록 조회
                start_date = today - timedelta(days=check_days)
                start_str = start_date.isoformat()

                if date_col == "collected_at":
                    q = text(f"""
                        SELECT DISTINCT SUBSTRING({date_col}, 1, 10) as d
                        FROM {table}
                        WHERE {date_col} >= :start
                        ORDER BY d
                    """)
                else:
                    q = text(f"""
                        SELECT DISTINCT {date_col} as d
                        FROM {table}
                        WHERE {date_col} >= :start
                        ORDER BY d
                    """)

                rows = (await session.execute(q, {"start": start_str})).all()
                existing_dates = set()
                for row in rows:
                    val = row[0]
                    if isinstance(val, str):
                        existing_dates.add(datetime.strptime(val, "%Y-%m-%d").date())
                    elif isinstance(val, datetime):
                        existing_dates.add(val.date())
                    elif isinstance(val, date):
                        existing_dates.add(val)

                # 2) 기대 날짜 목록 생성
                expected = _expected_dates(frequency, check_days)

                # 3) 일별 상태 계산
                daily_status = []
                missing_dates = []

                for d in expected:
                    if frequency == "weekly":
                        # 해당 주(월~일) 중 데이터가 하나라도 있으면 OK
                        week_end = d + timedelta(days=6)
                        has_data = any(d <= ed <= week_end for ed in existing_dates)
                        label = f"{d.isoformat()} ~ {week_end.isoformat()}"
                    else:
                        has_data = d in existing_dates
                        label = d.isoformat()

                    # 각 소스별 발간 지연(Lag) 고려: 지연 기간 내의 날짜는 누락(missing)이 아닌 대기(pending)로 처리
                    lag_days = src.get("lag_days", 1)
                    is_pending_period = (today - d).days < lag_days
                    
                    if has_data:
                        status = "ok"
                    elif is_pending_period:
                        status = "pending"
                    else:
                        status = "missing"

                    daily_status.append({
                        "date": label,
                        "status": status,
                    })

                    if status == "missing":
                        missing_dates.append(label)

                # 4) 최신 날짜, 총 레코드 수
                if date_col == "collected_at":
                    latest_q = text(f"SELECT MAX({date_col}::date) FROM {table}")
                else:
                    latest_q = text(f"SELECT MAX({date_col}) FROM {table}")

                latest_row = (await session.execute(latest_q)).one_or_none()
                latest_date = None
                if latest_row and latest_row[0]:
                    val = latest_row[0]
                    if isinstance(val, str):
                        latest_date = datetime.strptime(val, "%Y-%m-%d").date()
                    elif isinstance(val, datetime):
                        latest_date = val.date()
                    elif isinstance(val, date):
                        latest_date = val

                count_row = (await session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )).one()
                total_records = count_row[0]

                # 5) 종합 상태 판정
                total_expected = len([d for d in daily_status if d["status"] != "pending"])
                total_ok = len([d for d in daily_status if d["status"] == "ok"])
                total_missing = len(missing_dates)

                if total_records == 0:
                    overall_status = "empty"
                elif total_missing == 0:
                    overall_status = "ok"
                elif total_missing <= 2:
                    overall_status = "warning"
                else:
                    overall_status = "gap"

                coverage_pct = round(total_ok / max(total_expected, 1) * 100, 1)

                results.append({
                    "id": src["id"],
                    "label": src["label"],
                    "icon": src["icon"],
                    "frequency": frequency,
                    "latest_date": latest_date.isoformat() if latest_date else None,
                    "total_records": total_records,
                    "status": overall_status,
                    "coverage_pct": coverage_pct,
                    "total_expected": total_expected,
                    "total_ok": total_ok,
                    "total_missing": total_missing,
                    "missing_dates": missing_dates,
                    "daily_status": daily_status,  # 일별 히트맵용
                })

            except Exception as e:
                logger.error(f"[GapRecovery] Diagnose error for {src['id']}: {e}")
                results.append({
                    "id": src["id"],
                    "label": src["label"],
                    "icon": src["icon"],
                    "frequency": src.get("frequency", "daily"),
                    "latest_date": None,
                    "total_records": 0,
                    "status": "error",
                    "coverage_pct": 0,
                    "total_expected": 0,
                    "total_ok": 0,
                    "total_missing": 0,
                    "missing_dates": [],
                    "daily_status": [],
                    "error": str(e)[:200],
                })

    return results


# ──────────────────────────────────────────────
# Recovery execution
# ──────────────────────────────────────────────

async def run_recovery(source_ids: List[str]) -> Dict:
    """선택한 소스들에 대해 누락 기간 데이터를 복구한다."""
    global _recovery_state

    async with _recovery_lock:
        if _recovery_state["is_running"]:
            return {"status": "error", "message": "이미 복구 작업이 진행 중입니다."}

        _recovery_state = {
            "is_running": True,
            "started_at": datetime.utcnow().isoformat(),
            "sources": {sid: {"status": "pending", "message": "대기 중", "records": 0} for sid in source_ids},
            "completed_at": None,
            "recent_logs": [],
        }

    # 백그라운드에서 실행
    asyncio.create_task(_execute_recovery(source_ids))
    return {"status": "started", "message": f"{len(source_ids)}개 소스 복구를 시작합니다."}


def _recovery_log(msg: str):
    """Add a log message to the recovery state"""
    global _recovery_state
    ts = datetime.utcnow().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    _recovery_state["recent_logs"].append(line)
    if len(_recovery_state["recent_logs"]) > 50:
        _recovery_state["recent_logs"] = _recovery_state["recent_logs"][-50:]
    logger.info(f"[GapRecovery] {msg}")

async def _execute_recovery(source_ids: List[str]):
    """실제 복구 로직 (백그라운드)."""
    global _recovery_state
    from app.services.data_collector import DataCollector
    from app.services.scheduler import collect_all_news, _log_collection

    collector = DataCollector()
    today = date.today()

    for sid in source_ids:
        _recovery_state["sources"][sid] = {"status": "running", "message": "수집 중...", "records": 0}
        _recovery_log(f"[{sid}] 복구 시작...")

        try:
            if sid == "opinet_prices":
                start = today - timedelta(days=60)
                result = await _log_collection("opinet", "recovery", collector.collect_prices, start.isoformat(), today.isoformat())
                count = len(result.prices) if result else 0
                _recovery_state["sources"][sid] = {
                    "status": "success",
                    "message": f"{count}건 유가 데이터 복구 완료",
                    "records": count,
                }
                _recovery_log(f"[{sid}] 완료: {count}건 데이터 수집됨")

            elif sid == "eia_inventory":
                start = today - timedelta(days=180)
                result = await _log_collection("eia_inventory", "recovery", collector.collect_inventory, start.isoformat(), today.isoformat())
                count = len(result) if result is not None and hasattr(result, '__len__') else 0
                _recovery_state["sources"][sid] = {
                    "status": "success",
                    "message": f"{count}건 재고 데이터 복구 완료",
                    "records": count,
                }
                _recovery_log(f"[{sid}] 완료: {count}건 데이터 수집됨")

            elif sid == "eia_production":
                start = today - timedelta(days=180)
                result = await _log_collection("eia_production", "recovery", collector.collect_production, start.isoformat(), today.isoformat())
                count = len(result) if result is not None and hasattr(result, '__len__') else 0
                _recovery_state["sources"][sid] = {
                    "status": "success",
                    "message": f"{count}건 생산 데이터 복구 완료",
                    "records": count,
                }
                _recovery_log(f"[{sid}] 완료: {count}건 데이터 수집됨")

            elif sid == "fred_macro":
                start = today - timedelta(days=180)
                result = await _log_collection("fred", "recovery", collector.collect_macro_data, start.isoformat(), today.isoformat())
                count = len(result.indicators) if result else 0
                _recovery_state["sources"][sid] = {
                    "status": "success",
                    "message": f"{count}건 거시경제 데이터 복구 완료",
                    "records": count,
                }
                _recovery_log(f"[{sid}] 완료: {count}건 데이터 수집됨")

            elif sid == "news":
                start = today - timedelta(days=10)
                _recovery_state["sources"][sid]["message"] = f"과거 10일치 뉴스 수집 + AI 분류 진행 중..."
                await collect_all_news(start.isoformat(), today.isoformat())
                _recovery_state["sources"][sid] = {
                    "status": "success",
                    "message": "과거 10일치 뉴스 수집 및 AI 분류 완료",
                    "records": 0,
                }
                _recovery_log(f"[{sid}] 완료: 과거 10일치 뉴스 복구 처리됨")

            else:
                _recovery_state["sources"][sid] = {
                    "status": "skipped",
                    "message": f"알 수 없는 소스: {sid}",
                    "records": 0,
                }
                _recovery_log(f"[{sid}] 알 수 없는 소스로 건너뜀")

        except Exception as e:
            _recovery_log(f"[{sid}] ERROR: 복구 실패 - {str(e)[:100]}")
            _recovery_state["sources"][sid] = {
                "status": "error",
                "message": str(e)[:300],
                "records": 0,
            }

    _recovery_state["is_running"] = False
    _recovery_state["completed_at"] = datetime.utcnow().isoformat()
    _recovery_log("모든 복구 작업 완료.")
