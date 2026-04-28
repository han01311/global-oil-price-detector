import re
with open('frontend/src/components/PriceChart/PriceChart.tsx', 'r') as f:
    content = f.read()

# Update aggregate signature
content = content.replace(
    "function aggregate(data: ChartDataPoint[], iv: Interval): ChartDataPoint[] {",
    "function aggregate(data: ChartDataPoint[], iv: Interval, rawCounts?: Record<string, number>): ChartDataPoint[] {"
)

# Update aggregate logic to sum rawCounts over the date range
old_agg_logic = """    const first = pts[0];
    const last = pts[pts.length - 1];
    const sumCount = pts.reduce((acc, curr) => acc + (curr.dbArticleCount || 0), 0);
    return { 
      ...last, 
      dbArticleCount: sumCount || undefined, 
      filterDate: k,
      groupStartDate: first.date,
      groupEndDate: last.date
    };"""

new_agg_logic = """    const first = pts[0];
    const last = pts[pts.length - 1];
    
    let sumCount = 0;
    if (rawCounts) {
      // iterate through dates from first to last using string comparison
      const startStr = first.date;
      const endStr = last.date;
      for (const [dateStr, count] of Object.entries(rawCounts)) {
        if (dateStr >= startStr && dateStr <= endStr) {
          sumCount += count;
        }
      }
    } else {
      sumCount = pts.reduce((acc, curr) => acc + (curr.dbArticleCount || 0), 0);
    }

    return { 
      ...last, 
      dbArticleCount: sumCount || undefined, 
      filterDate: k,
      groupStartDate: first.date,
      groupEndDate: last.date
    };"""

content = content.replace(old_agg_logic, new_agg_logic)

# Update usePriceData extraction
content = content.replace(
    "const { chartData, forecast, loading, error } = usePriceData('ALL');",
    "const { chartData, forecast, loading, error, rawNewsCounts } = usePriceData('ALL');"
)

# Update useMemo dependency
content = content.replace(
    "const aggData = useMemo(() => aggregate(chartData, interval), [chartData, interval]);",
    "const aggData = useMemo(() => aggregate(chartData, interval, rawNewsCounts), [chartData, interval, rawNewsCounts]);"
)

with open('frontend/src/components/PriceChart/PriceChart.tsx', 'w') as f:
    f.write(content)
print("Patched PriceChart.tsx")
