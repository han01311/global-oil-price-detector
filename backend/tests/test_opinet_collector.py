import pytest
from app.services.opinet_collector import OpinetCollector

@pytest.mark.asyncio
async def test_get_crude_prices():
    collector = OpinetCollector()
    df = await collector.get_crude_prices("2024-01-01", "2024-01-10")
    
    assert not df.empty
    assert 'dubai' in df.columns
    assert 'wti' in df.columns
    assert 'brent' in df.columns
    
    # Check if there are some non-null values
    assert df['dubai'].notna().sum() > 0
    assert df['wti'].notna().sum() > 0
    assert df['brent'].notna().sum() > 0
