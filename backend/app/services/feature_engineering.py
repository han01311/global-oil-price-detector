import pandas as pd
import numpy as np

CRUDE_TYPES = ["wti", "brent", "dubai"]


class FeatureEngineer:
    """시계열 피처 엔지니어링 파이프라인 (유종별 독립 피처 지원)"""

    def build_features(self, prices_df: pd.DataFrame,
                       macro_df: pd.DataFrame) -> pd.DataFrame:
        """원시 데이터를 ML 피처로 변환 — 유종별 독립 피처 포함"""
        # Ensure dataframes are sorted by date and have datetime index
        prices_df['date'] = pd.to_datetime(prices_df['date'])
        prices_df = prices_df.sort_values('date').set_index('date')
        
        if not macro_df.empty and 'date' in macro_df.columns:
            macro_df['date'] = pd.to_datetime(macro_df['date'])
            macro_df = macro_df.sort_values('date').set_index('date')
            df = prices_df.join(macro_df, how='left')
        else:
            df = prices_df.copy()
            for col in ['fed_rate', 'dollar_index', 'yield_spread']:
                df[col] = 0.0

        # Create a new dataframe for features to avoid modifying the original
        features = pd.DataFrame(index=df.index)

        # 1. 유종별 가격 피처
        for crude in CRUDE_TYPES:
            if crude in df.columns:
                features[f"{crude}_price"] = df[crude]
            else:
                features[f"{crude}_price"] = np.nan

        # 2. 유종 간 스프레드 (cross-crude spreads)
        if "wti" in df.columns and "brent" in df.columns:
            features["wti_brent_spread"] = df["wti"] - df["brent"]
        if "dubai" in df.columns and "brent" in df.columns:
            features["dubai_brent_spread"] = df["dubai"] - df["brent"]
        if "wti" in df.columns and "dubai" in df.columns:
            features["wti_dubai_spread"] = df["wti"] - df["dubai"]

        # 3. 유종별 이동평균
        for crude in CRUDE_TYPES:
            if crude not in df.columns:
                continue
            for window in [5, 10, 20, 50]:
                ma_col = f"{crude}_ma{window}"
                features[ma_col] = df[crude].rolling(window).mean()
                features[f"{crude}_ma{window}_ratio"] = df[crude] / features[ma_col]

        # 4. 유종별 변동률
        for crude in CRUDE_TYPES:
            if crude not in df.columns:
                continue
            for lag in [1, 5, 10, 20]:
                features[f"{crude}_return_{lag}d"] = df[crude].pct_change(lag)

        # 5. 유종별 변동성 (rolling std)
        for crude in CRUDE_TYPES:
            if crude not in df.columns:
                continue
            features[f"{crude}_vol_10d"] = df[crude].pct_change().rolling(10).std()
            features[f"{crude}_vol_20d"] = df[crude].pct_change().rolling(20).std()

        # 6. 거시경제 피처 (forward fill for frequency mismatch)
        if "fed_rate" in df.columns:
            features["fed_rate"] = df["fed_rate"].ffill().fillna(0.0)
        else:
            features["fed_rate"] = 0.0
            
        if "dollar_index" in df.columns:
            features["dollar_index"] = df["dollar_index"].ffill().fillna(0.0)
        else:
            features["dollar_index"] = 0.0
            
        if "yield_spread" in df.columns:
            features["yield_spread"] = df["yield_spread"].ffill().fillna(0.0)
        else:
            features["yield_spread"] = 0.0

        # 7. 래깅 피처 (미래 정보 누출 방지)
        for col in ["fed_rate", "dollar_index"]:
            if col in features.columns:
                features[f"{col}_lag5"] = features[col].shift(5)

        # 8. 유종별 타겟 변수
        for crude in CRUDE_TYPES:
            if crude in df.columns:
                features[f"target_{crude}_7d"] = df[crude].shift(-7) / df[crude] - 1
                features[f"target_{crude}_30d"] = df[crude].shift(-30) / df[crude] - 1

        # Legacy target columns (backward compat — used by existing WTI-only model)
        if "wti" in df.columns:
            features["target_7d"] = features.get("target_wti_7d", np.nan)
            features["target_30d"] = features.get("target_wti_30d", np.nan)

        features.replace([float('inf'), float('-inf')], np.nan, inplace=True)
        return features.dropna().astype(float)

    def split_train_test(self, features_df: pd.DataFrame,
                         test_ratio: float = 0.2) -> tuple:
        """시계열 특성을 고려한 순차 분할 (랜덤 셔플 금지)"""
        split_idx = int(len(features_df) * (1 - test_ratio))
        train = features_df.iloc[:split_idx]
        test = features_df.iloc[split_idx:]
        return train, test

