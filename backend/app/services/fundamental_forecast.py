"""펀더멘탈 분석 모델 (Method B) — 수급 기반 유가 예측

학술/산업 근거:
- EIA Short-Term Energy Outlook (STEO) 방법론
- Supply-Demand Balance → Inventory proxy
- Mean Reversion (Ornstein-Uhlenbeck process)
- Seasonal Decomposition
- Dollar-Oil Inverse Correlation

이 모델은 XGBoost(Method A)와는 완전히 다른 데이터와 접근 방식을 사용합니다.
- Method A: 가격 파생 지표(이동평균, 변동성 등) → ML 패턴 인식
- Method B: 실물 시장 데이터(재고, 생산, 계절) → 경제학적 수급 분석
"""

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.database import Database

logger = logging.getLogger(__name__)

CRUDE_TYPES = ["dubai", "wti", "brent"]


class FundamentalForecastEngine:
    """EIA 방법론을 참고한 수급 기반 유가 예측 엔진.

    5개의 독립적인 시그널을 과거 데이터에서 산출하고,
    각 시그널의 역사적 적중률에 비례하여 가중 합산합니다.
    """

    def __init__(self):
        self.db = Database()

    async def forecast(self, current_prices: Dict[str, float]) -> Dict:
        """유종별 7일 전망치를 수급 기반으로 산출.

        Returns:
            {
                "forecasts_by_crude": {
                    "wti": { "current_price", "estimated_7d", "signals", ... },
                    ...
                },
                "method": "fundamental",
                "generated_at": "..."
            }
        """
        await self.db.connect()

        # 과거 데이터 로드
        prices_df = await self._load_prices()
        inventory_df = await self._load_inventory()
        production_df = await self._load_production()
        macro_df = await self._load_macro()

        from datetime import datetime, timezone
        forecasts_by_crude = {}

        for crude in CRUDE_TYPES:
            price = current_prices.get(crude)
            if price is None or pd.isna(price):
                continue

            if crude not in prices_df.columns or prices_df[crude].dropna().empty:
                continue

            price_series = prices_df[crude].dropna()

            # 5개 시그널 산출
            signals = {}

            signals["inventory"] = self._inventory_signal(inventory_df, price_series)
            signals["production"] = self._production_signal(production_df, price_series)
            signals["seasonal"] = self._seasonal_signal(price_series)
            signals["mean_reversion"] = self._mean_reversion_signal(price_series, price)
            signals["dollar"] = self._dollar_signal(macro_df, price_series)

            # 가중 합산 (각 시그널의 신뢰도에 비례)
            total_change, signal_details = self._weighted_combine(signals)

            estimated_7d = price * (1 + total_change)

            # inf/NaN 방어 함수 (JSON 직렬화 오류 방지)
            def _safe(v: float, fallback: float = 0.0) -> float:
                try:
                    fv = float(v)
                    return round(fv, 2) if math.isfinite(fv) else fallback
                except (TypeError, ValueError):
                    return fallback

            # 불확실성 밴드: 시그널 분산 기반
            signal_values = [s["change"] for s in signal_details if s["change"] is not None]
            if len(signal_values) >= 2:
                band = float(np.std(signal_values)) * 1.5
                if band != band:
                    band = 0.03
            else:
                band = 0.03  # 기본 3%

            forecasts_by_crude[crude] = {
                "crude_type": crude,
                "current_price": _safe(price),
                "estimated_7d": _safe(estimated_7d),
                "estimated_7d_high": _safe(estimated_7d * (1 + band)),
                "estimated_7d_low": _safe(estimated_7d * (1 - band)),
                "total_change_pct": _safe(total_change * 100),
                "signals": signal_details,
                "confidence": self._calculate_confidence(signal_details),
            }

        return {
            "forecasts_by_crude": forecasts_by_crude,
            "method": "fundamental",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ──────────────────────────────────────────────
    # 시그널 1: 재고 변화율 (Inventory Signal)
    # 근거: EIA — 재고 변화는 수급 균형의 대리 지표
    # ──────────────────────────────────────────────

    def _inventory_signal(self, inventory_df: pd.DataFrame,
                           price_series: pd.Series) -> Dict:
        """최근 4주간 재고 변화 추세로부터 유가 방향성 추론.

        재고 감소 → 수요 > 공급 → 가격 상승 압력
        재고 증가 → 공급 > 수요 → 가격 하락 압력
        """
        result = {"name": "재고 변화", "change": None, "confidence": 0.0, "detail": "데이터 부족"}

        if inventory_df.empty or len(inventory_df) < 4:
            return result

        # 최근 4주 재고 변화율
        recent = inventory_df.tail(4)
        inv_values = recent["inventory_mbbl"].values
        if inv_values[0] == 0:
            return result

        weekly_change_rate = (inv_values[-1] - inv_values[0]) / inv_values[0]

        # 과거 데이터에서 유사한 재고 변화율 시기의 7일 유가 변동 조회
        historical_response = self._lookup_historical_price_response(
            price_series, inventory_df, "inventory_mbbl",
            current_rate=weekly_change_rate, lookback_weeks=4
        )

        if historical_response is not None:
            result["change"] = historical_response["avg_change"]
            result["confidence"] = historical_response["confidence"]
            result["detail"] = (
                f"재고 {'감소' if weekly_change_rate < 0 else '증가'} 중 "
                f"({weekly_change_rate*100:+.1f}%) → "
                f"과거 유사 시기 7일 변동: {historical_response['avg_change']*100:+.1f}% "
                f"(사례 {historical_response['sample_count']}건)"
            )
        else:
            # 과거 데이터 부족 시 간이 추정
            # 재고 1% 감소 → 유가 약 0.5% 상승 (경험적 역상관)
            estimated = -weekly_change_rate * 0.5
            result["change"] = max(min(estimated, 0.05), -0.05)  # 상한 5%
            result["confidence"] = 0.3
            result["detail"] = f"재고 변화 {weekly_change_rate*100:+.1f}% → 간이 추정 적용"

        return result

    # ──────────────────────────────────────────────
    # 시그널 2: 생산량 추세 (Production Signal)
    # 근거: EIA — 미국 셰일오일 생산은 가격에 민감
    # ──────────────────────────────────────────────

    def _production_signal(self, production_df: pd.DataFrame,
                            price_series: pd.Series) -> Dict:
        """최근 4주 생산량 추세에서 공급 방향성 추론."""
        result = {"name": "생산량 추세", "change": None, "confidence": 0.0, "detail": "데이터 부족"}

        if production_df.empty or len(production_df) < 4:
            return result

        recent = production_df.tail(4)
        prod_values = recent["production_mbbl_d"].values
        if prod_values[0] == 0:
            return result

        weekly_change_rate = (prod_values[-1] - prod_values[0]) / prod_values[0]

        historical_response = self._lookup_historical_price_response(
            price_series, production_df, "production_mbbl_d",
            current_rate=weekly_change_rate, lookback_weeks=4
        )

        if historical_response is not None:
            result["change"] = historical_response["avg_change"]
            result["confidence"] = historical_response["confidence"]
            result["detail"] = (
                f"생산량 {'증가' if weekly_change_rate > 0 else '감소'} 중 "
                f"({weekly_change_rate*100:+.2f}%) → "
                f"과거 유사 시기 7일 변동: {historical_response['avg_change']*100:+.1f}%"
            )
        else:
            # 생산 증가 → 공급 증가 → 가격 하락 압력
            estimated = -weekly_change_rate * 0.3
            result["change"] = max(min(estimated, 0.03), -0.03)
            result["confidence"] = 0.3
            result["detail"] = f"생산량 변화 {weekly_change_rate*100:+.2f}% → 간이 추정 적용"

        return result

    # ──────────────────────────────────────────────
    # 시그널 3: 계절적 패턴 (Seasonal Factor)
    # 근거: Seasonal Decomposition — 수요의 계절성
    # ──────────────────────────────────────────────

    def _seasonal_signal(self, price_series: pd.Series) -> Dict:
        """현재 월의 역사적 평균 7일 수익률 계산.

        여름(6~8월): 드라이빙 시즌 → 수요 증가 → 상승 경향
        겨울(11~1월): 난방유 시즌 → 수요 증가 → 상승 경향
        봄(3~5월): 정유소 정비 시즌 → 가격 약세 경향
        """
        result = {"name": "계절 패턴", "change": None, "confidence": 0.0, "detail": "데이터 부족"}

        if len(price_series) < 252:  # 최소 1년치
            return result

        current_month = date.today().month

        # 과거 데이터에서 같은 월의 7일 수익률 수집
        returns_7d = price_series.pct_change(7)
        same_month_returns = []

        for idx in returns_7d.index:
            try:
                if hasattr(idx, 'month') and idx.month == current_month:
                    val = returns_7d.loc[idx]
                    if not pd.isna(val):
                        same_month_returns.append(float(val))
            except (AttributeError, TypeError):
                continue

        if len(same_month_returns) < 5:
            return result

        avg_return = float(np.mean(same_month_returns))
        std_return = float(np.std(same_month_returns))

        # 신뢰도: 표준편차가 작을수록 패턴이 일관적
        confidence = max(0.2, min(0.8, 1.0 - std_return * 10))

        month_names = {
            1: "1월", 2: "2월", 3: "3월", 4: "4월", 5: "5월", 6: "6월",
            7: "7월", 8: "8월", 9: "9월", 10: "10월", 11: "11월", 12: "12월"
        }

        result["change"] = avg_return
        result["confidence"] = confidence
        result["detail"] = (
            f"{month_names[current_month]} 역사적 평균 7일 수익률: {avg_return*100:+.2f}% "
            f"(표준편차 {std_return*100:.2f}%, 사례 {len(same_month_returns)}건)"
        )
        return result

    # ──────────────────────────────────────────────
    # 시그널 4: 평균 회귀 (Mean Reversion)
    # 근거: Ornstein-Uhlenbeck process — 원자재 가격의 평균 회귀 성질
    # ──────────────────────────────────────────────

    def _mean_reversion_signal(self, price_series: pd.Series,
                                current_price: float) -> Dict:
        """현재 가격의 50일 MA 이탈도로부터 회귀 압력 추론.

        가격이 MA 위로 크게 벗어남 → 하락 회귀 압력
        가격이 MA 아래로 크게 벗어남 → 상승 회귀 압력
        """
        result = {"name": "평균 회귀", "change": None, "confidence": 0.0, "detail": "데이터 부족"}

        if len(price_series) < 50:
            return result

        ma50 = float(price_series.tail(50).mean())
        if ma50 == 0:
            return result

        deviation = (current_price - ma50) / ma50  # 이탈 비율

        # 과거 데이터에서 비슷한 이탈도일 때의 7일 수익률 조회
        ma50_series = price_series.rolling(50).mean()
        deviation_series = (price_series - ma50_series) / ma50_series
        returns_7d = price_series.pct_change(7).shift(-7)  # 7일 후 수익률

        # 현재와 비슷한 이탈도(±2% 범위)의 과거 사례 수집
        similar_mask = (deviation_series >= deviation - 0.02) & (deviation_series <= deviation + 0.02)
        similar_returns = returns_7d[similar_mask].dropna()

        if len(similar_returns) >= 5:
            avg_return = float(similar_returns.mean())
            result["change"] = avg_return
            result["confidence"] = min(0.7, len(similar_returns) / 50)
            result["detail"] = (
                f"현재 50일 MA 대비 {deviation*100:+.1f}% 이탈 → "
                f"과거 유사 시기 7일 변동: {avg_return*100:+.2f}% "
                f"(사례 {len(similar_returns)}건)"
            )
        else:
            # 간이 추정: 이탈의 10%가 7일 내 회귀
            estimated = -deviation * 0.10
            result["change"] = max(min(estimated, 0.03), -0.03)
            result["confidence"] = 0.25
            result["detail"] = f"50일 MA 대비 {deviation*100:+.1f}% 이탈 → 간이 회귀 추정"

        return result

    # ──────────────────────────────────────────────
    # 시그널 5: 달러 영향 (Dollar Correlation)
    # 근거: 학술적으로 잘 알려진 유가-달러 역상관 관계
    # ──────────────────────────────────────────────

    def _dollar_signal(self, macro_df: pd.DataFrame,
                        price_series: pd.Series) -> Dict:
        """최근 달러 인덱스 변화와 유가의 역상관 관계 분석."""
        result = {"name": "달러 영향", "change": None, "confidence": 0.0, "detail": "데이터 부족"}

        if macro_df.empty or "dollar_index" not in macro_df.columns:
            return result

        dollar = macro_df["dollar_index"].dropna()
        if len(dollar) < 10:
            return result

        # 최근 7일간 달러 변화율
        recent_dollar = dollar.tail(7)
        if len(recent_dollar) < 2 or recent_dollar.iloc[0] == 0:
            return result

        dollar_change = (recent_dollar.iloc[-1] - recent_dollar.iloc[0]) / recent_dollar.iloc[0]

        # 과거 데이터에서 비슷한 달러 변화율 시기의 유가 반응 조회
        dollar_returns = dollar.pct_change(7)
        price_returns = price_series.pct_change(7)

        # 날짜 인덱스 정렬 및 공통 구간 추출 — 양쪽 인덱스를 안전하게 합집합
        # (중복 인덱스 방지를 위해 groupby mean 사용)
        dollar_returns = dollar_returns.groupby(level=0).mean()
        price_returns = price_returns.groupby(level=0).mean()

        combined_index = dollar_returns.index.union(price_returns.index)
        dollar_reindexed = dollar_returns.reindex(combined_index)
        price_reindexed = price_returns.reindex(combined_index)

        aligned = pd.DataFrame({
            "dollar_ret": dollar_reindexed,
            "price_ret": price_reindexed
        }).dropna()

        if len(aligned) < 20:
            # 간이 추정: 달러-유가 역상관 계수 약 -0.5
            estimated = -dollar_change * 0.5
            result["change"] = max(min(estimated, 0.03), -0.03)
            result["confidence"] = 0.3
            result["detail"] = f"달러 {dollar_change*100:+.2f}% 변화 → 간이 역상관 추정"
            return result

        # 비슷한 달러 변화율(±1% 범위) 시기의 유가 반응
        similar_mask = (
            (aligned["dollar_ret"] >= dollar_change - 0.01) &
            (aligned["dollar_ret"] <= dollar_change + 0.01)
        )
        similar_price_returns = aligned.loc[similar_mask, "price_ret"]

        if len(similar_price_returns) >= 3:
            avg_return = float(similar_price_returns.mean())
            result["change"] = avg_return
            result["confidence"] = min(0.6, len(similar_price_returns) / 30)
            result["detail"] = (
                f"달러 {dollar_change*100:+.2f}% 변화 → "
                f"과거 유사 시기 유가 반응: {avg_return*100:+.2f}% "
                f"(사례 {len(similar_price_returns)}건)"
            )
        else:
            # 전체 상관계수 기반 추정
            correlation = float(aligned["dollar_ret"].corr(aligned["price_ret"]))
            estimated = dollar_change * correlation
            result["change"] = max(min(estimated, 0.03), -0.03)
            result["confidence"] = 0.35
            result["detail"] = (
                f"달러 {dollar_change*100:+.2f}% 변화, "
                f"역사적 상관계수: {correlation:.2f} → 추정 반영"
            )

        # 원/달러 환율 보조 정보 (공공데이터)
        if "krw_usd" in macro_df.columns:
            krw = macro_df["krw_usd"].dropna()
            if len(krw) >= 2:
                krw_latest = krw.iloc[-1]
                if len(krw) >= 7 and krw.iloc[-7] != 0:
                    krw_change = (krw.iloc[-1] - krw.iloc[-7]) / krw.iloc[-7]
                    result["detail"] += f" | 원/달러: {krw_latest:,.0f}원 ({krw_change*100:+.1f}%)"
                else:
                    result["detail"] += f" | 원/달러: {krw_latest:,.0f}원"

        return result

    # ──────────────────────────────────────────────
    # 가중 합산 및 유틸리티
    # ──────────────────────────────────────────────

    def _weighted_combine(self, signals: Dict) -> Tuple[float, List[Dict]]:
        """5개 시그널을 신뢰도 기반으로 가중 합산.

        각 시그널의 confidence가 높을수록 최종 결과에 더 큰 비중을 차지합니다.
        """
        total_weight = 0
        weighted_sum = 0
        details = []

        for key, signal in signals.items():
            change = signal.get("change")
            confidence = signal.get("confidence", 0)

            # NaN/inf → None 정리
            if change is not None:
                try:
                    fchange = float(change)
                    change = fchange if math.isfinite(fchange) else None
                except (TypeError, ValueError):
                    change = None
            if isinstance(confidence, float) and not math.isfinite(confidence):
                confidence = 0.0

            details.append({
                "signal_id": key,
                "name": signal.get("name", key),
                "change": change,
                "confidence": round(float(confidence), 2),
                "detail": signal.get("detail", ""),
                "weight": 0,  # 아래에서 계산
            })

            if change is not None and confidence > 0:
                weighted_sum += change * confidence
                total_weight += confidence

        # 가중치 비율 계산 (UI 표시용)
        if total_weight > 0:
            total_change = weighted_sum / total_weight
            # NaN 방어
            if total_change != total_change:
                total_change = 0.0
            for d in details:
                if d["change"] is not None and d["confidence"] > 0:
                    d["weight"] = round(d["confidence"] / total_weight, 2)
        else:
            total_change = 0.0

        # 극단값 클리핑: 7일 예측에서 ±10% 이상은 비현실적
        total_change = max(min(total_change, 0.10), -0.10)

        return total_change, details

    def _calculate_confidence(self, signal_details: List[Dict]) -> float:
        """종합 신뢰도 산출.

        활성 시그널이 많을수록, 시그널 간 방향이 일치할수록 신뢰도 상승.
        """
        active_signals = [s for s in signal_details if s["change"] is not None]
        if not active_signals:
            return 0.1

        # 활성 시그널 비율 (5개 중 몇 개가 유효한지)
        active_ratio = len(active_signals) / 5

        # 방향 일치도
        directions = [np.sign(s["change"]) for s in active_signals if s["change"] != 0]
        if directions:
            agreement = abs(sum(directions)) / len(directions)
        else:
            agreement = 0.5

        confidence = (active_ratio * 0.4 + agreement * 0.6)
        return round(min(max(confidence, 0.1), 0.95), 2)

    def _lookup_historical_price_response(
        self, price_series: pd.Series, indicator_df: pd.DataFrame,
        indicator_col: str, current_rate: float, lookback_weeks: int = 4
    ) -> Optional[Dict]:
        """과거 유사 지표 변화율 시기의 실제 유가 반응을 조회.

        예: "재고가 이 속도로 줄었던 과거 시기들에서, 7일 후 유가가 평균 몇 % 변했는가?"
        """
        if len(indicator_df) < 10 or len(price_series) < 50:
            return None

        # 지표의 4주간 변화율 시계열 생성
        indicator_values = indicator_df.set_index("date")[indicator_col]
        indicator_change = indicator_values.pct_change(lookback_weeks)

        # 유가 7일 수익률
        price_returns_7d = price_series.pct_change(7).shift(-7)

        # 공통 날짜 정렬
        aligned = pd.DataFrame({
            "indicator_change": indicator_change,
            "price_return": price_returns_7d
        }).dropna()

        if len(aligned) < 5:
            return None

        # 현재와 비슷한 지표 변화율(±50% 범위)의 과거 사례
        tolerance = max(abs(current_rate) * 0.5, 0.005)
        similar_mask = (
            (aligned["indicator_change"] >= current_rate - tolerance) &
            (aligned["indicator_change"] <= current_rate + tolerance)
        )
        similar = aligned.loc[similar_mask, "price_return"]

        if len(similar) < 3:
            return None

        return {
            "avg_change": float(similar.mean()),
            "std_change": float(similar.std()),
            "sample_count": len(similar),
            "confidence": min(0.7, len(similar) / 20),
        }

    # ──────────────────────────────────────────────
    # 데이터 로드
    # ──────────────────────────────────────────────

    async def _load_prices(self) -> pd.DataFrame:
        """유가 시계열 로드 (최대 20년)"""
        end = date.today()
        start = end - timedelta(days=365 * 20)
        rows = await self.db.get_oil_prices(start.isoformat(), end.isoformat(), limit=10000)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        # 날짜 중복 제거 (마지막 값 유지)
        df = df.drop_duplicates(subset="date", keep="last")
        df = df.set_index("date")
        return df[["dubai", "wti", "brent"]].apply(pd.to_numeric, errors="coerce")

    async def _load_inventory(self) -> pd.DataFrame:
        """원유 재고 데이터 로드 (최대 20년)"""
        rows = await self.db.get_oil_inventory(limit=1500)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["inventory_mbbl"] = pd.to_numeric(df["inventory_mbbl"], errors="coerce")
        return df.sort_values("date").reset_index(drop=True)

    async def _load_production(self) -> pd.DataFrame:
        """원유 생산량 데이터 로드 (최대 20년)"""
        end = date.today()
        start = end - timedelta(days=365 * 20)
        try:
            rows = await self.db.get_oil_production_range(start.isoformat(), end.isoformat(), limit=1500)
        except Exception:
            rows = []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["production_mbbl_d"] = pd.to_numeric(df["production_mbbl_d"], errors="coerce")
        return df.sort_values("date").reset_index(drop=True)

    async def _load_macro(self) -> pd.DataFrame:
        """거시경제 지표 로드 (최대 20년)"""
        end = date.today()
        start = end - timedelta(days=365 * 20)
        rows = await self.db.get_macro_indicators(start.isoformat(), end.isoformat(), limit=10000)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        # 날짜+지표명 중복 제거
        if "indicator" in df.columns:
            df = df.drop_duplicates(subset=["date", "indicator"], keep="last")
            # 넓은 형식으로 피벗
            df = df.pivot(index="date", columns="indicator", values="value")
            df.columns.name = None
        else:
            df = df.drop_duplicates(subset="date", keep="last")
            df = df.set_index("date")
        for col in ["dollar_index", "fed_rate"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col] = df[col].ffill().bfill()
        return df
