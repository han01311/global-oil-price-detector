from datetime import datetime, timezone
import json
response_json = {"impact_score": 1, "impact_summary": "test"}
raw_impact = response_json.pop("impact_by_crude", {})
impact_by_crude = {}
for crude_type in ["dubai", "wti", "brent"]:
    overall_score = response_json.get("impact_score", 0)
    direction = "bullish" if overall_score > 0 else ("bearish" if overall_score < 0 else "neutral")
    impact_by_crude[crude_type] = {"direction": direction, "score": overall_score, "rationale": "test"}

result_data = {
    "impact_by_crude": impact_by_crude,
    **response_json
}
print(result_data)
