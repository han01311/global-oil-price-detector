import re
with open('frontend/src/hooks/usePriceData.ts', 'r') as f:
    content = f.read()

# Update useMemo return
old_return = """    return {
      chartData: Array.from(chartDataMap.values()),
      newsMarkers: processedNewsMarkers,
      dbNewsMarkers: processedDBMarkers,
    };
  }, [history, forecast, news, newsDateCounts]);

  return { chartData, newsMarkers, dbNewsMarkers, forecast, loading, error };"""

new_return = """    const rawNewsCounts: Record<string, number> = {};
    dateCountMap.forEach((val, key) => { rawNewsCounts[key] = val; });

    return {
      chartData: Array.from(chartDataMap.values()),
      newsMarkers: processedNewsMarkers,
      dbNewsMarkers: processedDBMarkers,
      rawNewsCounts,
    };
  }, [history, forecast, news, newsDateCounts]);

  return { chartData, newsMarkers, dbNewsMarkers, rawNewsCounts, forecast, loading, error };"""

content = content.replace(old_return, new_return)

# Also update the hook destruction line to include rawNewsCounts
content = content.replace(
    "  const { chartData, newsMarkers, dbNewsMarkers } = useMemo(() => {",
    "  const { chartData, newsMarkers, dbNewsMarkers, rawNewsCounts } = useMemo(() => {"
)

with open('frontend/src/hooks/usePriceData.ts', 'w') as f:
    f.write(content)
print("Patched usePriceData.ts")
