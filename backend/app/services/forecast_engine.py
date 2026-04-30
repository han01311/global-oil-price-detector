import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import List, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add project root to path to allow direct script execution
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services.feature_engineering import FeatureEngineer
from app.services.data_collector import DataCollector
from app.schemas.forecast import ForecastResult, FactorBreakdown, CrudeForecast

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CRUDE_TYPES = ["dubai", "brent", "wti"]


def _resolve_ml_dir() -> Path:
    """Resolve ML artifact directory independent of the process cwd."""
    backend_dir = Path(__file__).resolve().parents[2]
    candidates = [
        backend_dir / "ml",
        backend_dir / "backend" / "ml",
    ]
    for candidate in candidates:
        report = candidate / "training_report.json"
        model_dir = candidate / "models"
        if report.exists() and any(model_dir.glob("xgb_*_7d.joblib")):
            return candidate
    return candidates[0]


class ForecastEngine:
    """XGBoost-based oil price forecasting engine — 유종별 독립 모델 지원."""

    _ML_DIR = _resolve_ml_dir()
    MODEL_DIR = _ML_DIR / "models"
    REPORT_PATH = _ML_DIR / "training_report.json"

    def __init__(self):
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        # Per-crude models: {"wti": {"7d": model, "30d": model}, ...}
        self.models: Dict[str, Dict[str, object]] = {}
        self.training_report = None

    def _model_path(self, crude: str, horizon: str) -> Path:
        return self.MODEL_DIR / f"xgb_{crude}_{horizon}.joblib"

    def _load_models(self):
        """Loads all trained models and training report from disk."""
        if self.REPORT_PATH.exists():
            with open(self.REPORT_PATH, 'r') as f:
                self.training_report = json.load(f)
        else:
            raise FileNotFoundError("Training report not found. Please run the training script first.")

        for crude in CRUDE_TYPES:
            self.models[crude] = {}
            for horizon in ["7d", "30d"]:
                path = self._model_path(crude, horizon)
                if path.exists():
                    self.models[crude][horizon] = joblib.load(path)
                else:
                    # Fallback: try loading legacy WTI-only models
                    legacy_path = self.MODEL_DIR / f"xgb_{horizon}.joblib"
                    if crude == "wti" and legacy_path.exists():
                        self.models[crude][horizon] = joblib.load(legacy_path)
                    else:
                        logging.warning(f"Model not found: {path}. Will skip {crude}/{horizon}.")
                        self.models[crude][horizon] = None

    def _get_feature_cols(self, features_df: pd.DataFrame) -> list:
        """Get feature columns (exclude all target columns)."""
        return [c for c in features_df.columns if not c.startswith("target_")]

    def train(self, features_df: pd.DataFrame) -> dict:
        """Trains models for all crude types and evaluates them."""
        if features_df.empty:
            raise ValueError("Features DataFrame cannot be empty.")

        train, test = FeatureEngineer().split_train_test(features_df)
        feature_cols = self._get_feature_cols(train)

        all_metrics = {}

        for crude in CRUDE_TYPES:
            target_7d = f"target_{crude}_7d"
            target_30d = f"target_{crude}_30d"

            # Skip if target columns don't exist (e.g., missing Dubai data)
            if target_7d not in train.columns or target_30d not in train.columns:
                logging.warning(f"Skipping {crude}: target columns not found in features.")
                continue

            X_train, X_test = train[feature_cols], test[feature_cols]

            # --- 7-day model ---
            y_train_7d, y_test_7d = train[target_7d], test[target_7d]
            model_7d = xgb.XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                early_stopping_rounds=10,
            )
            model_7d.fit(X_train, y_train_7d, eval_set=[(X_test, y_test_7d)], verbose=False)

            # --- 30-day model ---
            y_train_30d, y_test_30d = train[target_30d], test[target_30d]
            model_30d = xgb.XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                early_stopping_rounds=10,
            )
            model_30d.fit(X_train, y_train_30d, eval_set=[(X_test, y_test_30d)], verbose=False)

            # --- Save models ---
            joblib.dump(model_7d, self._model_path(crude, "7d"))
            joblib.dump(model_30d, self._model_path(crude, "30d"))

            # --- Evaluation ---
            preds_7d = model_7d.predict(X_test)
            preds_30d = model_30d.predict(X_test)

            all_metrics[crude] = {
                "rmse_7d": float(np.sqrt(mean_squared_error(y_test_7d, preds_7d))),
                "mae_7d": float(mean_absolute_error(y_test_7d, preds_7d)),
                "rmse_30d": float(np.sqrt(mean_squared_error(y_test_30d, preds_30d))),
                "mae_30d": float(mean_absolute_error(y_test_30d, preds_30d)),
            }

            logging.info(f"[{crude.upper()}] RMSE_7d={all_metrics[crude]['rmse_7d']:.4f}, RMSE_30d={all_metrics[crude]['rmse_30d']:.4f}")

        # Feature importance from WTI 7d model (primary)
        wti_7d_path = self._model_path("wti", "7d")
        feature_importance_map = {}
        if wti_7d_path.exists():
            wti_model = joblib.load(wti_7d_path)
            importances = wti_model.feature_importances_
            for col, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
                feature_importance_map[col] = float(imp)

        # Legacy compatibility: top-level metrics use WTI
        wti_metrics = all_metrics.get("wti", {})

        return {
            "rmse_7d": wti_metrics.get("rmse_7d", 0),
            "mae_7d": wti_metrics.get("mae_7d", 0),
            "rmse_30d": wti_metrics.get("rmse_30d", 0),
            "mae_30d": wti_metrics.get("mae_30d", 0),
            "metrics_by_crude": all_metrics,
            "feature_columns": feature_cols,
            "feature_importance": dict(feature_importance_map),
            "data_range": {
                "start": features_df.index.min().strftime('%Y-%m-%d'),
                "end": features_df.index.max().strftime('%Y-%m-%d')
            },
            "samples": len(features_df)
        }

    def predict(self, current_features: pd.DataFrame, crude_type: str = "wti") -> dict:
        """Predicts price changes for a specific crude type."""
        if not self.models:
            self._load_models()

        # Ensure columns are in the same order as during training
        feature_cols = self.training_report.get('feature_columns')
        if feature_cols:
            current_features = current_features[feature_cols]

        crude_models = self.models.get(crude_type, {})
        model_7d = crude_models.get("7d")
        model_30d = crude_models.get("30d")

        # Fallback to WTI models if specific crude model not available
        if model_7d is None:
            model_7d = self.models.get("wti", {}).get("7d")
        if model_30d is None:
            model_30d = self.models.get("wti", {}).get("30d")

        if model_7d is None or model_30d is None:
            raise FileNotFoundError(f"Models for {crude_type} not found.")

        pred_7d = model_7d.predict(current_features)[0]
        pred_30d = model_30d.predict(current_features)[0]

        # Get RMSE from report
        metrics_by_crude = self.training_report.get("metrics_by_crude", {})
        crude_metrics = metrics_by_crude.get(crude_type, {})

        return {
            "baseline_change_7d": float(pred_7d),
            "baseline_change_30d": float(pred_30d),
            "model_rmse_7d": crude_metrics.get("rmse_7d", self.training_report.get("rmse_7d")),
            "model_rmse_30d": crude_metrics.get("rmse_30d", self.training_report.get("rmse_30d")),
        }


class NewsAdjuster:
    """뉴스 기반 유가 보정 로직 — 학술 근거 기반 개선 (v3)

    개선사항:
    1. Temporal Decay: 거래일(Trading Day) 기반 시간 감쇠
    2. Semantic Deduplication: 의미적 중복 제거
    3. Volatility Regime: 변동성 국면 인식
    4. Price Absorption: 시장 반영도 체크
    5. Market Gap Awareness: 휴장 기간 기사 누적/상쇄 처리
    """

    # 시간 감쇠 반감기 (거래일 단위) — 카테고리별 차등 적용
    DECAY_HALF_LIFE = {
        "geopolitics": 5.0,
        "supply": 3.0,
        "demand": 3.0,
        "macro": 4.0,
        "policy": 4.0,
        "default": 2.5,
    }

    VOL_LOW_PCTILE = 0.30
    VOL_HIGH_PCTILE = 0.70

    VOL_REGIME_MULTIPLIER = {
        "low": 0.7,
        "normal": 1.0,
        "high": 1.5,
    }

    DEDUP_SIMILARITY_THRESHOLD = 0.85

    # ──────────────────────────────────────────────
    # 보완 5: 시장 공백 인식 (Market Gap Awareness)
    # ──────────────────────────────────────────────

    @staticmethod
    def _count_trading_days(start_dt: datetime, end_dt: datetime) -> float:
        """두 시점 사이의 거래일(주말 제외) 수를 계산.
        주말에 시장이 닫혀있는 동안의 시간은 경과일에서 제외하여
        비거래일 기사의 영향력이 부당하게 감쇠되지 않도록 합니다.
        """
        if end_dt <= start_dt:
            return 0.0

        from datetime import timedelta
        trading_seconds = 0.0
        current = start_dt

        while current < end_dt:
            # 하루 단위로 순회
            next_day = min(current + timedelta(days=1), end_dt)
            if current.weekday() < 5:  # 월(0)~금(4)만 거래일
                trading_seconds += (next_day - current).total_seconds()
            current = next_day

        return trading_seconds / 86400

    @staticmethod
    def _is_market_open(dt: datetime) -> bool:
        """해당 시점이 거래일(월~금)인지 판별."""
        return dt.weekday() < 5

    def _classify_market_gap_articles(self, articles: List[Dict]) -> tuple:
        """기사를 '거래일 발행'과 '시장 공백(비거래일) 발행'으로 분류.

        비거래일 기사들은 다음 거래일에 일괄 반영되어야 하며,
        같은 공백 기간 내에서 상반된 방향의 기사는 서로 상쇄됩니다.
        """
        trading_articles = []
        gap_articles = []

        for a in articles:
            pub_at = a.get("article", {}).get("published_at", "") or a.get("published_at", "")
            try:
                pub_date = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                if self._is_market_open(pub_date):
                    trading_articles.append(a)
                else:
                    gap_articles.append(a)
            except (ValueError, TypeError):
                trading_articles.append(a)  # 파싱 실패 시 거래일 기사로 취급

        return trading_articles, gap_articles

    def _calculate_gap_net_score(self, gap_articles: List[Dict],
                                 crude_type: str) -> Dict:
        """시장 공백 기간 기사들의 순(Net) 영향도를 계산.

        경우의 수:
        1. 모두 같은 방향 → 누적 합산 (강화 효과)
        2. 상반된 방향 → 상쇄 후 순 효과만 반영
        3. 완전 상쇄 → 영향도 0 (시장에 실제 변동 없을 것으로 예측)

        추가로, 같은 공백 내 늦게 나온 기사가 앞 기사를 '덮어쓰는' 효과도 반영합니다.
        (예: 토요일에 전쟁 위기설 → 일요일에 협상 타결 → 월요일엔 안정)
        """
        if not gap_articles:
            return {"net_score": 0, "net_weight": 0, "gap_count": 0,
                    "bullish_count": 0, "bearish_count": 0, "cancelled_ratio": 0.0}

        # 발행 시간순 정렬 (늦은 기사가 더 최신 상황 반영)
        sorted_articles = sorted(gap_articles, key=lambda a: (
            a.get("article", {}).get("published_at", "") or a.get("published_at", "")
        ))

        bullish_score = 0.0
        bearish_score = 0.0
        bullish_weight = 0.0
        bearish_weight = 0.0
        bullish_count = 0
        bearish_count = 0

        for idx, a in enumerate(sorted_articles):
            score = self._extract_crude_score(a, crude_type)
            confidence = a.get("confidence", 0.8)

            # 시간순 가중: 공백 내 늦은 기사일수록 더 최신 상황 반영
            recency_boost = 1.0 + (idx / max(len(sorted_articles), 1)) * 0.3

            w = confidence * recency_boost

            if score > 0:
                bullish_score += score * w
                bullish_weight += w
                bullish_count += 1
            elif score < 0:
                bearish_score += abs(score) * w
                bearish_weight += w
                bearish_count += 1

        # 상쇄 계산: 강한 쪽에서 약한 쪽을 차감
        total_magnitude = bullish_score + bearish_score
        if total_magnitude == 0:
            cancelled_ratio = 1.0
            net_score = 0
            net_weight = 0
        else:
            net_score = (bullish_score - bearish_score)
            # 상쇄율: 약한 쪽이 강한 쪽을 얼마나 깎았는지 (0=상쇄 없음, 1=완전 상쇄)
            cancelled_ratio = min(bullish_score, bearish_score) / (total_magnitude / 2)
            net_weight = max(bullish_weight, bearish_weight) - min(bullish_weight, bearish_weight) * 0.5

        return {
            "net_score": net_score,
            "net_weight": max(net_weight, 0.001),
            "gap_count": len(gap_articles),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "cancelled_ratio": cancelled_ratio,
        }

    def _extract_crude_score(self, article: Dict, crude_type: str) -> float:
        """기사에서 특정 유종의 영향 점수를 추출."""
        impact_by_crude = article.get("impact_by_crude", {})
        if crude_type in impact_by_crude:
            crude_impact = impact_by_crude[crude_type]
            if isinstance(crude_impact, dict):
                return crude_impact.get("score", 0)
            return crude_impact.score if hasattr(crude_impact, 'score') else 0
        return article.get("impact_score", 0)

    async def calculate_adjustment(self, classified_articles: List[Dict],
                                    similar_events: List[Dict],
                                    crude_type: str = "wti",
                                    recent_prices: Optional[List[float]] = None,
                                    historical_volatilities: Optional[List[float]] = None) -> Dict:
        """뉴스 분석 결과를 기반으로 특정 유종의 보정값 산출 (v3 — 시장 공백 인식)"""
        relevant_articles = [a for a in classified_articles if a.get("is_relevant")]

        # 보완 1: 의미적 중복 제거
        deduped_articles = self._deduplicate_articles(relevant_articles)
        dedup_ratio = len(deduped_articles) / max(len(relevant_articles), 1)

        # 보완 5: 거래일/비거래일 기사 분류
        trading_articles, gap_articles = self._classify_market_gap_articles(deduped_articles)
        gap_result = self._calculate_gap_net_score(gap_articles, crude_type)

        # ── 거래일 기사: 거래일 기반 시간 감쇠 적용 ──
        weighted_score = 0.0
        total_weight = 0.0

        for a in trading_articles:
            decay_weight = self._temporal_decay_weight(a)
            score = self._extract_crude_score(a, crude_type)
            confidence = a.get("confidence", 0.8)
            w = confidence * decay_weight
            weighted_score += score * w
            total_weight += w

        # ── 비거래일 기사: 상쇄/누적 후 순 효과를 감쇠 없이 합산 ──
        if gap_result["gap_count"] > 0:
            weighted_score += gap_result["net_score"]
            total_weight += gap_result["net_weight"]

        article_count = len(deduped_articles)
        avg_sentiment = weighted_score / max(total_weight, 0.001)

        # 2. 유사 과거 사례 기반 보정
        similar_adjustment = self._calculate_similar_adjustment(similar_events, crude_type)

        # 3. 최종 보정값 = 감성 + 유사 사례
        sentiment_adjustment = self._sentiment_to_pct(avg_sentiment)
        raw_adjustment = 0.4 * sentiment_adjustment + 0.6 * similar_adjustment

        # 보완 3: 변동성 국면 보정
        vol_regime = self._detect_volatility_regime(historical_volatilities)
        vol_multiplier = self.VOL_REGIME_MULTIPLIER.get(vol_regime, 1.0)
        regime_adjusted = raw_adjustment * vol_multiplier

        # 보완 4: 시장 반영도 보정
        absorption_factor = self._calculate_absorption(recent_prices, regime_adjusted)
        news_adjustment = regime_adjusted * absorption_factor

        # 4. 불확실성 — 상쇄율이 높으면 불확실성 증가
        uncertainty = self._calculate_uncertainty(deduped_articles, crude_type)
        if gap_result["cancelled_ratio"] > 0.3:
            uncertainty *= (1 + gap_result["cancelled_ratio"] * 0.5)

        return {
            "news_adjustment_pct": news_adjustment,
            "sentiment_component": avg_sentiment,
            "similar_component": similar_adjustment,
            "uncertainty_factor": uncertainty,
            "article_count": article_count,
            "dedup_ratio": dedup_ratio,
            "volatility_regime": vol_regime,
            "vol_multiplier": vol_multiplier,
            "absorption_factor": absorption_factor,
            "dominant_category": self._get_dominant_category(deduped_articles, crude_type),
            "market_gap_info": {
                "gap_article_count": gap_result["gap_count"],
                "bullish_count": gap_result["bullish_count"],
                "bearish_count": gap_result["bearish_count"],
                "net_score": gap_result["net_score"],
                "cancelled_ratio": round(gap_result["cancelled_ratio"], 2),
            },
        }

    # ──────────────────────────────────────────────
    # 보완 1: 시간 감쇠 (거래일 기반 Temporal Decay)
    # 학술 근거: Exponential Decay + Trading Day Calendar
    # ──────────────────────────────────────────────

    def _temporal_decay_weight(self, article: Dict) -> float:
        """기사의 발행 시점에 따른 시간 감쇠 가중치 계산.

        v3 개선: 달력일이 아닌 거래일(Trading Day) 기준으로 경과일을 계산.
        주말/공휴일에 시장이 닫혀있는 시간은 경과일에서 제외되므로,
        금요일 밤~일요일에 나온 기사도 월요일에 감쇠 없이 온전한 가중치를 유지.
        """
        published_at = article.get("article", {}).get("published_at", "")
        if not published_at:
            published_at = article.get("published_at", "")

        try:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            trading_days_ago = self._count_trading_days(pub_date, now)
        except (ValueError, TypeError):
            trading_days_ago = 0

        trading_days_ago = max(0, trading_days_ago)

        category = article.get("category", "default")
        half_life = self.DECAY_HALF_LIFE.get(category, self.DECAY_HALF_LIFE["default"])

        decay_lambda = np.log(2) / half_life
        return float(np.exp(-decay_lambda * trading_days_ago))

    # ──────────────────────────────────────────────
    # 보완 2: 의미적 중복 제거 (Semantic Deduplication)
    # 학술 근거: BERT/LLM embedding + cosine similarity threshold
    # ──────────────────────────────────────────────

    def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """같은 사건을 보도한 기사들을 그룹으로 묶고, 그룹별 대표 1개만 남김.
        
        임베딩 기반 유사도를 계산할 수 없는 경우 (ChromaDB 미연결 등),
        제목 기반 간이 유사도로 폴백합니다.
        """
        if len(articles) <= 1:
            return articles

        # 제목 추출
        titles = []
        for a in articles:
            article_info = a.get("article", {})
            title = article_info.get("title", "") if isinstance(article_info, dict) else ""
            titles.append(title.lower().strip())

        # 간이 유사도 기반 클러스터링 (단어 집합 자카드 유사도)
        clusters: List[List[int]] = []
        clustered = set()

        for i in range(len(articles)):
            if i in clustered:
                continue
            cluster = [i]
            clustered.add(i)
            words_i = set(titles[i].split())

            for j in range(i + 1, len(articles)):
                if j in clustered:
                    continue
                words_j = set(titles[j].split())
                if not words_i or not words_j:
                    continue
                # 자카드 유사도
                intersection = len(words_i & words_j)
                union = len(words_i | words_j)
                similarity = intersection / union if union > 0 else 0

                if similarity >= 0.5:  # 단어의 50% 이상 겹치면 같은 이벤트로 판정
                    cluster.append(j)
                    clustered.add(j)
            clusters.append(cluster)

        # 각 클러스터에서 신뢰도가 가장 높은 기사 1개를 대표로 선정
        deduped = []
        for cluster in clusters:
            best_idx = max(cluster, key=lambda idx: articles[idx].get("confidence", 0))
            representative = dict(articles[best_idx])
            # 보도량(클러스터 크기)을 메타데이터로 기록
            representative["_cluster_size"] = len(cluster)
            deduped.append(representative)

        return deduped

    # ──────────────────────────────────────────────
    # 보완 3: 변동성 국면 인식 (Volatility Regime Detection)
    # 학술 근거: GARCH 변동성 클러스터링 (Bollerslev, 1986)
    # ──────────────────────────────────────────────

    def _detect_volatility_regime(self, historical_volatilities: Optional[List[float]]) -> str:
        """최근 변동성을 역사적 분포와 비교하여 현재 국면을 분류.
        
        고변동 국면: 같은 뉴스라도 시장 반응이 크므로 보정치 확대
        저변동 국면: 시장이 둔감하므로 보정치 축소
        """
        if not historical_volatilities or len(historical_volatilities) < 20:
            return "normal"

        current_vol = historical_volatilities[-1]
        sorted_vols = sorted(historical_volatilities)
        n = len(sorted_vols)

        low_threshold = sorted_vols[int(n * self.VOL_LOW_PCTILE)]
        high_threshold = sorted_vols[int(n * self.VOL_HIGH_PCTILE)]

        if current_vol <= low_threshold:
            return "low"
        elif current_vol >= high_threshold:
            return "high"
        return "normal"

    # ──────────────────────────────────────────────
    # 보완 4: 시장 반영도 체크 (Price Absorption)
    # 학술 근거: 효율적 시장 가설(EMH) 실증적 변형
    # ──────────────────────────────────────────────

    def _calculate_absorption(self, recent_prices: Optional[List[float]],
                               expected_adjustment: float) -> float:
        """시장이 이미 뉴스를 얼마나 반영했는지 측정.
        
        최근 7일간 실제 가격 변동과 뉴스 기반 예상 변동을 비교하여,
        이미 반영된 부분은 추가 보정에서 제외합니다.
        
        반환값: 0.0 ~ 1.0 (0이면 완전히 반영됨, 1이면 전혀 반영 안 됨)
        """
        if not recent_prices or len(recent_prices) < 2 or abs(expected_adjustment) < 0.001:
            return 1.0  # 데이터 부족 시 보정치 그대로 적용

        # 최근 7일간 실제 가격 변동률
        actual_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]

        # 뉴스가 예고한 방향과 실제 변동 방향이 같은지 확인
        if np.sign(expected_adjustment) == np.sign(actual_change):
            # 같은 방향으로 움직임 → 일부 이미 반영됨
            absorption_ratio = min(abs(actual_change) / abs(expected_adjustment), 1.0)
            # 남은 미반영 비율 (최소 20%는 유지 — 모멘텀 효과)
            remaining = max(1.0 - absorption_ratio, 0.2)
            return remaining
        else:
            # 반대 방향으로 움직임 → 아직 전혀 반영 안 됨 + 추가 반발 가능
            return 1.0

    # ──────────────────────────────────────────────
    # 기존 유틸리티 메서드 (유지)
    # ──────────────────────────────────────────────

    def _sentiment_to_pct(self, score: float) -> float:
        """감성 스코어(-5~+5)를 변동률(%)로 변환"""
        if score == 0:
            return 0.0
        # 비선형 매핑: score ±1 → ±0.4%, ±3 → ±2.3%, ±5 → ±5%
        return np.sign(score) * (abs(score) / 5) ** 1.5 * 0.05

    def _calculate_similar_adjustment(self, events: List[Dict], crude_type: str = "wti") -> float:
        """유사 사례의 유종별 유가 변동률 가중 평균"""
        total_weight = 0
        weighted_sum = 0
        
        change_key = f"{crude_type}_change_7d"
        fallback_key = "wti_change_7d"
        
        for event in events:
            similarity = event.get("similarity", 0)
            change = event.get(change_key) or event.get(fallback_key)
            
            if change is not None and similarity > 0.5:
                change_decimal = change / 100.0
                weighted_sum += change_decimal * similarity
                total_weight += similarity
                
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_uncertainty(self, articles: List[Dict], crude_type: str = "wti") -> float:
        """뉴스 의견 분산으로 불확실성 계산 — 유종별"""
        scores = []
        for a in articles:
            impact_by_crude = a.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    scores.append(crude_impact.get("score", 0))
                else:
                    scores.append(crude_impact.score if hasattr(crude_impact, 'score') else 0)
            else:
                scores.append(a.get("impact_score", 0))

        if len(scores) < 2:
            return 0.005
        
        std_dev = np.std(scores)
        normalized_std = std_dev / 5.0
        return normalized_std * 0.02

    def _get_dominant_category(self, articles: List[Dict], crude_type: str = "wti") -> Optional[str]:
        """가장 영향력 있는 카테고리 식별 — 유종별"""
        category_impacts = Counter()
        for article in articles:
            category = article.get("category")
            impact_by_crude = article.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    impact = abs(crude_impact.get("score", 0))
                else:
                    impact = abs(crude_impact.score) if hasattr(crude_impact, 'score') else 0
            else:
                impact = abs(article.get("impact_score", 0))
            if category:
                category_impacts[category] += impact
        
        if not category_impacts:
            return None
        return category_impacts.most_common(1)[0][0]

    def _calculate_factor_breakdown(self, articles: List[Dict], crude_type: str = "wti") -> List[Dict]:
        """카테고리별 기여도 계산 — 유종별"""
        category_contributions = Counter()
        category_counts = Counter()
        total_weighted_score = 0

        for article in articles:
            if not article.get("is_relevant"):
                continue
            impact_by_crude = article.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    score = crude_impact.get("score", 0)
                else:
                    score = crude_impact.score if hasattr(crude_impact, 'score') else 0
            else:
                score = article.get("impact_score", 0)

            confidence = article.get("confidence", 1.0)
            weighted = score * confidence
            total_weighted_score += weighted

            category = article.get("category")
            if category:
                category_contributions[category] += weighted
                category_counts[category] += 1

        if total_weighted_score == 0:
            return []

        breakdown = []
        sentiment_total_pct = self._sentiment_to_pct(total_weighted_score / max(1, len(articles)))
        
        for category, total_score in category_contributions.items():
            contribution_pct = (total_score / total_weighted_score) * sentiment_total_pct * 0.4
            breakdown.append({
                "category": category,
                "contribution": contribution_pct,
                "article_count": category_counts[category]
            })
        return breakdown


class HybridForecaster:
    """하이브리드 유가 추정기 — 유종별 독립 추정 지원"""

    def __init__(self, engine: ForecastEngine, adjuster: NewsAdjuster):
        self.engine = engine
        self.adjuster = adjuster

    async def forecast(self, current_prices: Dict[str, float],
                       current_features: pd.DataFrame,
                       classified_articles: List[Dict],
                       similar_events: List[Dict],
                       data_as_of: str = "") -> ForecastResult:
        """유종별 독립 추정 밴드 산출"""

        forecasts_by_crude = {}

        for crude in CRUDE_TYPES:
            price = current_prices.get(crude)
            if price is None or pd.isna(price):
                continue

            try:
                baseline = self.engine.predict(current_features, crude_type=crude)
            except FileNotFoundError:
                logging.warning(f"No model for {crude}, skipping.")
                continue

            adjustment = await self.adjuster.calculate_adjustment(
                classified_articles, similar_events, crude_type=crude
            )

            final_change_7d = (1 + baseline["baseline_change_7d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
            estimated_7d = price * (1 + final_change_7d)
            band_7d = baseline["model_rmse_7d"] + adjustment["uncertainty_factor"]

            final_change_30d = (1 + baseline["baseline_change_30d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
            estimated_30d = price * (1 + final_change_30d)
            band_30d = baseline["model_rmse_30d"] + adjustment["uncertainty_factor"]

            forecasts_by_crude[crude] = CrudeForecast(
                crude_type=crude,
                current_price=price,
                estimated_7d=estimated_7d,
                estimated_7d_high=estimated_7d * (1 + band_7d),
                estimated_7d_low=estimated_7d * (1 - band_7d),
                estimated_30d=estimated_30d,
                estimated_30d_high=estimated_30d * (1 + band_30d),
                estimated_30d_low=estimated_30d * (1 - band_30d),
                baseline_change_7d=baseline["baseline_change_7d"],
                baseline_change_30d=baseline["baseline_change_30d"],
                news_adjustment_pct=adjustment["news_adjustment_pct"],
                confidence=max(0, 1 - (band_7d * 2)),
                dominant_factor=adjustment["dominant_category"],
            )

        # Primary result uses WTI for backward compatibility
        wti = forecasts_by_crude.get("wti")
        if wti is None:
            # Use first available crude
            wti = next(iter(forecasts_by_crude.values())) if forecasts_by_crude else None

        if wti is None:
            raise ValueError("No crude type could be forecasted.")

        # Factor breakdown using WTI
        factor_breakdown_data = self.adjuster._calculate_factor_breakdown(
            [a for a in classified_articles if a.get("is_relevant")],
            crude_type="wti"
        )

        wti_adj = await self.adjuster.calculate_adjustment(
            classified_articles, similar_events, crude_type="wti"
        )
        is_extreme = abs(wti_adj["news_adjustment_pct"]) >= 0.05 or wti.confidence < 0.3

        return ForecastResult(
            current_price=wti.current_price,
            estimated_7d=wti.estimated_7d,
            estimated_7d_high=wti.estimated_7d_high,
            estimated_7d_low=wti.estimated_7d_low,
            estimated_30d=wti.estimated_30d,
            estimated_30d_high=wti.estimated_30d_high,
            estimated_30d_low=wti.estimated_30d_low,
            baseline_change_7d=wti.baseline_change_7d,
            baseline_change_30d=wti.baseline_change_30d,
            news_adjustment_pct=wti.news_adjustment_pct,
            confidence=wti.confidence,
            dominant_factor=wti.dominant_factor,
            extreme_volatility_warning=is_extreme,
            factor_breakdown=[FactorBreakdown(**fb) for fb in factor_breakdown_data],
            forecasts_by_crude=forecasts_by_crude,
            data_as_of=data_as_of,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


async def run_training():
    """The main training pipeline script."""
    logging.info("Starting model training pipeline...")

    # 1. Data Collection
    logging.info("Collecting historical data...")
    collector = DataCollector()
    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=5)
    
    prices_history = await collector.collect_prices(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    macro_history = await collector.collect_macro_data(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    prices_df = pd.DataFrame([p.model_dump() for p in prices_history.prices])
    macro_df = pd.DataFrame([i.model_dump() for i in macro_history.indicators])
    
    if prices_df.empty or macro_df.empty:
        logging.error("Failed to collect sufficient data for training.")
        return

    # 2. Feature Engineering
    logging.info("Building features...")
    feature_engineer = FeatureEngineer()
    features_df = feature_engineer.build_features(prices_df, macro_df)

    # 3. Model Training
    logging.info("Training XGBoost models for all crude types...")
    engine = ForecastEngine()
    metrics = engine.train(features_df)

    # 4. Save Report
    logging.info("Saving training report...")
    report = {
        "trained_at": datetime.now().isoformat(),
        "data_range": f"{metrics['data_range']['start']} ~ {metrics['data_range']['end']}",
        "samples": metrics['samples'],
        "rmse_7d": metrics['rmse_7d'],
        "mae_7d": metrics['mae_7d'],
        "rmse_30d": metrics['rmse_30d'],
        "mae_30d": metrics['mae_30d'],
        "metrics_by_crude": metrics.get('metrics_by_crude', {}),
        "feature_columns": metrics['feature_columns'],
        "top_features": dict(list(metrics['feature_importance'].items())[:10]),
    }

    with open(engine.REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    logging.info(f"Training complete. Report saved to {engine.REPORT_PATH}")
    for crude, m in metrics.get('metrics_by_crude', {}).items():
        logging.info(f"[{crude.upper()}] RMSE_7d={m['rmse_7d']:.4f}, RMSE_30d={m['rmse_30d']:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forecast Engine Training Script")
    parser.add_argument("--train", action="store_true", help="Run the model training pipeline.")
    args = parser.parse_args()

    if args.train:
        import asyncio
        asyncio.run(run_training())
    else:
        print("Use --train flag to run the training pipeline.")
