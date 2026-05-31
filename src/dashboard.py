"""
Dashboard module — Streamlit 5-tab retail intelligence dashboard.

Responsibilities (Phase 5):
- Fetch all data from the FastAPI backend via:
    API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
  This allows local development (localhost default) and Docker operation
  (API_BASE_URL=http://api:8000 set in docker-compose.yml).
- Apply @st.cache_data(ttl=60) on the API fetch function to prevent repeated
  calls on tab switches (Streamlit reruns the full script on every interaction).

Tab 1 — Executive Overview:
  KPI cards: total entries (staff-filtered), avg dwell time, zone visits,
  total GMV, transaction count. Timeline chart of entries per hour.

Tab 2 — Customer Journey (Aggregate):
  Funnel chart with five stages and conversion percentages. Clear label:
  "Aggregate zone counts, no individual tracking." Traffic-Sales Alignment
  panel visually separated with disclaimer: "Traffic from 16-04-2026,
  sales from 10-04-2026. Alignment is illustrative only."

Tab 3 — Zone Intelligence:
  Per-zone breakdown: visit count, avg dwell, peak time. Zone popularity
  heatmap. Store layout image with zone markers overlaid from zones.json
  if coordinates are available (Phase 0 TODO resolved by Phase 2).

Tab 4 — Revenue Intelligence:
  Total transactions, GMV, NMV. Top categories by revenue. Private Brand vs
  External Brand split. Salesperson performance table. Promotion effectiveness
  chart. Time-of-day revenue curve.

Tab 5 — Operational Intelligence and System Health:
  CAM_4 warehouse activity timeline. Restocking events. Queue alerts from
  CAM_5. Crowding events. Funnel validation result. Staff movements detected.
  Events loaded count and source. Video hash fingerprint. Last processing
  timestamp and duration. API status. Recent log entries (last 50).
"""
