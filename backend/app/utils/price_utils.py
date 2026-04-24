import pandas as pd
from datetime import timedelta

def calculate_price_changes(prices_df: pd.DataFrame, event_date: str) -> dict:
    """
    Calculates price changes for WTI and Brent crude oil based on an event date.

    Args:
        prices_df: DataFrame with 'date', 'wti', and 'brent' columns.
        event_date: The date of the event in 'YYYY-MM-DD' format.

    Returns:
        A dictionary containing the percentage change over 1, 7, and 30 days.
    """
    if prices_df.empty:
        return {
            "wti_change_1d": None, "wti_change_7d": None, "wti_change_30d": None,
            "brent_change_1d": None, "brent_change_7d": None, "brent_change_30d": None,
        }

    df = prices_df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    try:
        event_dt = pd.to_datetime(event_date)
        # Find the closest available date for the event
        event_row_index = df.index.get_indexer([event_dt], method='nearest')[0]
        event_row = df.iloc[event_row_index]
    except (ValueError, IndexError):
        return {
            "wti_change_1d": None, "wti_change_7d": None, "wti_change_30d": None,
            "brent_change_1d": None, "brent_change_7d": None, "brent_change_30d": None,
        }

    changes = {}
    for period in [1, 7, 30]:
        past_dt = event_dt - timedelta(days=period)
        try:
            # Find the closest available date for the past period
            past_row_index = df.index.get_indexer([past_dt], method='nearest')[0]
            past_row = df.iloc[past_row_index]

            for oil_type in ['wti', 'brent']:
                key = f"{oil_type}_change_{period}d"
                current_price = event_row[oil_type]
                past_price = past_row[oil_type]

                if pd.notna(current_price) and pd.notna(past_price) and past_price != 0:
                    changes[key] = ((current_price - past_price) / past_price) * 100
                else:
                    changes[key] = None
        except (ValueError, IndexError):
             for oil_type in ['wti', 'brent']:
                changes[f"{oil_type}_change_{period}d"] = None

    return changes
