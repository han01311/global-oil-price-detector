import re
with open('frontend/src/components/PriceChart/PriceChart.tsx', 'r') as f:
    content = f.read()

# Update context usage
content = content.replace(
    "const { setSelectedDate } = useDashboardContext();",
    "const { setSelectedDate, setSelectedDateRange } = useDashboardContext();"
)

# Update handleElementClick
old_click = """  const handleElementClick = (data: any) => {
    if (dragState.current.isPanning) return;
    if (data && (data.filterDate || data.date)) {
      setSelectedDate(data.filterDate || data.date);
      setTimeout(() => document.querySelector('.news-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }
  };"""

new_click = """  const handleElementClick = (data: any) => {
    if (dragState.current.isPanning) return;
    if (data) {
      if (interval !== 'day' && data.groupStartDate && data.groupEndDate) {
        setSelectedDateRange({ start: data.groupStartDate, end: data.groupEndDate });
      } else if (data.filterDate || data.date) {
        setSelectedDate(data.filterDate || data.date);
      }
      setTimeout(() => document.querySelector('.news-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }
  };"""

if old_click in content:
    content = content.replace(old_click, new_click)
    with open('frontend/src/components/PriceChart/PriceChart.tsx', 'w') as f:
        f.write(content)
    print("Patched handleElementClick")
else:
    print("old_click not found")

