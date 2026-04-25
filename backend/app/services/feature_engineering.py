import pandas as pd

class FeatureEngineer:
    """시계열 피처 엔지니어링 파이프라인"""

    def build_features(self, prices_df: pd.DataFrame,
                       macro_df: pd.DataFrame) -> pd.DataFrame:
        """원시 데이터를 ML 피처로 변환"""
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

        # 1. 가격 피처
        features["wti_price"] = df["wti"]
        features["brent_price"] = df["brent"]
        features["wti_brent_spread"] = df["wti"] - df["brent"]

        # 2. 이동평균
        for window in [5, 10, 20, 50]:
            features[f"wti_ma{window}"] = df["wti"].rolling(window).mean()
            features[f"wti_ma{window}_ratio"] = df["wti"] / features[f"wti_ma{window}"]

        # 3. 변동률
        for lag in [1, 5, 10, 20]:
            features[f"wti_return_{lag}d"] = df["wti"].pct_change(lag)

        # 4. 변동성 (rolling std)
        features["wti_vol_10d"] = df["wti"].pct_change().rolling(10).std()
        features["wti_vol_20d"] = df["wti"].pct_change().rolling(20).std()

        # 5. 거시경제 피처 (forward fill for frequency mismatch)
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

        # 6. 래깅 피처 (미래 정보 누출 방지)
        for col in ["fed_rate", "dollar_index"]:
            if col in features.columns:
                features[f"{col}_lag5"] = features[col].shift(5)

        # 7. 타겟 변수
        features["target_7d"] = df["wti"].shift(-7) / df["wti"] - 1
        features["target_30d"] = df["wti"].shift(-30) / df["wti"] - 1

        import numpy as np
        features.replace([float('inf'), float('-inf')], np.nan, inplace=True)
        return features.dropna().astype(float)

    def split_train_test(self, features_df: pd.DataFrame,
                         test_ratio: float = 0.2) -> tuple:
        """시계열 특성을 고려한 순차 분할 (랜덤 셔플 금지)"""
        split_idx = int(len(features_df) * (1 - test_ratio))
        train = features_df.iloc[:split_idx]
        test = features_df.iloc[split_idx:]
        return train, test
