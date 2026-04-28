import re
with open('frontend/src/components/NewsExplorer/NewsExplorer.tsx', 'r') as f:
    content = f.read()

# Add fetchNewsByRange
content = content.replace(
    "import { fetchNewsByDate } from '../../services/api';",
    "import { fetchNewsByDate, fetchNewsByRange } from '../../services/api';"
)

# Add selectedDateRange to Context
content = content.replace(
    "const { selectedDate, setSelectedDate, setHighlightedCategory } = useDashboardContext();",
    "const { selectedDate, setSelectedDate, selectedDateRange, setSelectedDateRange, setHighlightedCategory } = useDashboardContext();"
)

# Update useEffect
old_useeffect = """  // 차트에서 날짜 클릭 시 DB에서 해당 날짜 기사를 로드
  useEffect(() => {
    if (selectedDate) {
      setActiveCategory('All');
      setDbLoading(true);
      fetchNewsByDate(selectedDate)
        .then(data => setDbArticles(data))
        .catch(err => {
          console.error('Failed to fetch articles by date:', err);
          setDbArticles([]);
        })
        .finally(() => setDbLoading(false));
    } else {
      setDbArticles([]);
    }
  }, [selectedDate]);"""

new_useeffect = """  // 차트에서 날짜/범위 클릭 시 DB에서 해당 기사를 로드
  useEffect(() => {
    if (selectedDate || selectedDateRange) {
      setActiveCategory('All');
      setDbLoading(true);
      const fetchPromise = selectedDateRange
        ? fetchNewsByRange(selectedDateRange.start, selectedDateRange.end)
        : fetchNewsByDate(selectedDate as string);
        
      fetchPromise
        .then(data => setDbArticles(data))
        .catch(err => {
          console.error('Failed to fetch articles:', err);
          setDbArticles([]);
        })
        .finally(() => setDbLoading(false));
    } else {
      setDbArticles([]);
    }
  }, [selectedDate, selectedDateRange]);"""

if old_useeffect in content:
    content = content.replace(old_useeffect, new_useeffect)

# Update targetArticles
content = content.replace(
    "const targetArticles = selectedDate ? dbArticles : articles;",
    "const targetArticles = (selectedDate || selectedDateRange) ? dbArticles : articles;"
)

# Update loading skeleton condition
content = content.replace(
    "if (selectedDate && dbLoading)",
    "if ((selectedDate || selectedDateRange) && dbLoading)"
)

# Update loading skeleton condition
content = content.replace(
    "if (!selectedDate && loading)",
    "if (!selectedDate && !selectedDateRange && loading)"
)

# Update Empty state messages
content = content.replace(
    "const emptyTitle = selectedDate",
    "const emptyTitle = (selectedDate || selectedDateRange)"
)

content = content.replace(
    "const emptyDesc = selectedDate",
    "const emptyDesc = (selectedDate || selectedDateRange)"
)

# Replace Date Chip JSX
old_chip = """      <div className="active-date-chip-container">
        {selectedDate ? (
          <div className="active-date-chip">
            <span>조회 날짜:</span>
            <strong>{selectedDate}</strong>
            <span className="active-date-count">({dbArticles.length}건)</span>
            <button className="clear-chip-button" onClick={() => setSelectedDate(null)} title="최신 뉴스로 돌아가기">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        ) : (
          <div className="active-date-chip default-state">"""

new_chip = """      <div className="active-date-chip-container">
        {(selectedDate || selectedDateRange) ? (
          <div className="active-date-chip">
            <span>조회 범위:</span>
            <strong>{selectedDateRange ? `${selectedDateRange.start} ~ ${selectedDateRange.end}` : selectedDate}</strong>
            <span className="active-date-count">({dbArticles.length}건)</span>
            <button className="clear-chip-button" onClick={() => { setSelectedDate(null); setSelectedDateRange(null); }} title="최신 뉴스로 돌아가기">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        ) : (
          <div className="active-date-chip default-state">"""

if old_chip in content:
    content = content.replace(old_chip, new_chip)

with open('frontend/src/components/NewsExplorer/NewsExplorer.tsx', 'w') as f:
    f.write(content)
print("Patched NewsExplorer")
