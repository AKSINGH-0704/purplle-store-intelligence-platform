# PHASE 5 REPORT -- Dashboard

Phase: 5 -- Dashboard
Status: COMPLETE (single checkpoint)
Started: 2026-06-01
Completed: 2026-06-01
Commit: TBD
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## Objective

5-tab Streamlit dashboard consuming the FastAPI backend. Optimised for judge
comprehension and demo flow.

---

## Checkpoint Status

| # | Checkpoint | Files | Status | Result |
|---|-----------|-------|--------|--------|
| 5 | Streamlit dashboard | src/dashboard.py | **COMPLETE** | 17/17 validation checks pass |

---

## Architecture

```
API_BASE_URL env var (default: http://localhost:8000)
      |
      +-- fetch_dashboard() @st.cache_data(ttl=60) --> GET /dashboard
      |     Returns: funnel, anomalies, metrics, health, zone_totals
      |
      +-- fetch_health()    @st.cache_data(ttl=60) --> GET /health
            Returns: status, uptime, events_loaded, log_buffer, video_hashes
```

Two cached API calls. All 5 tabs read from the same in-memory objects.
No additional API calls per tab or per metric. Cache TTL=60s.

**API failure handling:** `requests.RequestException` is caught in both fetch
functions; they return `{}` on failure. The caller checks and calls `st.error()`
followed by `st.stop()` to prevent partial render.

---

## Tab Structure

| Tab | Title | Primary data source | Key visuals |
|-----|-------|---------------------|-------------|
| 1 | Executive Overview | metrics.sales + metrics.traffic | 8 st.metric cards, hourly revenue bar chart |
| 2 | Customer Journey | funnel + zone_totals | go.Funnel (stages 2-4), st.warning for funnel state |
| 3 | Zone Intelligence | funnel + zone_totals | 2 horizontal bar charts, per-zone metric cards |
| 4 | Revenue Intelligence | metrics.sales | 4 charts + promotions table |
| 5 | System Health | anomalies + health + funnel | Anomaly cards, video hash table, log entries |

---

## Key Design Decisions

### Tab 1 -- Executive Overview

Two clearly labelled KPI sections (no warning boxes):

- **Video Analytics -- 16-04-2026:** Zone Visits (9), Avg Dwell (28.8s),
  Events Captured (51), Anomalies Detected (1)
- **POS Data -- 10-04-2026:** GMV (Rs 44,920), NMV (Rs 34,832),
  Transactions (24), Avg Basket (4.88 items)

Hourly revenue bar chart (12:00-21:00). Peak hour highlighted.
Top performer note as `st.caption`.

### Tab 2 -- Customer Journey

Funnel rendered as **Plotly go.Funnel for stages 2-4 only**
(Main Floor -> Skincare -> Billing: 5 -> 2 -> 2). Entry count (0) and
Transactions (24) shown as separate st.metric cards with explanatory
st.info() boxes above and below the funnel. This avoids the misleading
0 -> 5 expansion and 2 -> 24 widening that would occur in a single
5-stage funnel with this data.

`st.warning()` for `funnel_validation == "warning"` (fires on current footage).
Full disclaimer (531 chars) always visible in a bordered st.warning() box.

### Tab 3 -- Zone Intelligence

`total_dwell_seconds` consumed directly from `data["zone_totals"]` which
comes from the API's `/dashboard` endpoint. This is the exact value computed
server-side by `_compute_zone_totals()` which sums `dwell_seconds` from
zone_dwell events (Option b -- no recomputation in the dashboard).

Values: main_floor=130.8s, skincare=66.4s, billing=54.03s.

Note: the `zone_totals` key was added to the `/dashboard` response as part
of this checkpoint to enable exact total_dwell consumption without requiring
additional per-zone API calls.

### Tab 4 -- Revenue Intelligence

Four Plotly charts: category GMV bar, brand split donut pie, salesperson NMV
horizontal bar, hourly revenue bar. Promotions dataframe (9 rows). Most
chart-dense tab -- primary judge-facing showcase for POS analytics quality.

### Tab 5 -- System Health

Anomaly cards rendered as `st.warning()` (severity=warning) or `st.info()`
(severity=info). Current footage: 1 anomaly fires (unusual_warehouse_activity).
Video fingerprints in st.dataframe. Pipeline run provenance (elapsed, mode,
cam4 override). Recent log entries from LOG_BUFFER.

---

## total_dwell_seconds Implementation Note

The self-audit in the pre-commit report described two things that appeared
contradictory:
- "Total dwell derived from events (Option b)"
- "total_dwell = avg_dwell * visit_count"

Clarification: Option b is implemented **server-side** in `src/api.py`
via `_compute_zone_totals()`, which sums `dwell_seconds` from zone_dwell
events at startup. This is the authoritative value.

The initial dashboard code recomputed `avg * count` on the client side
(a dashboard-level approximation). This was corrected before commit:
- `src/api.py`: `zone_totals` added to `/dashboard` response
- `src/dashboard.py`: `total_dwell = data.get("zone_totals", {})` -- direct API value

Verified exact match: all three zones match `/zone_metrics/{zone}` to the cent
(billing: dashboard=54.03s, zone_metrics=54.03s -- not 54.04s from avg*count).

---

## Validation results

```
17/17 checks passed -- ALL PASS (structural; no browser driver required)

[PASS] dashboard.py exists at src/dashboard.py
[PASS] valid Python syntax
[PASS] API_BASE_URL environment variable used
[PASS] @st.cache_data(ttl=60) caching decorator
[PASS] Tab 'Executive Overview' present
[PASS] Tab 'Customer Journey' present
[PASS] Tab 'Zone Intelligence' present
[PASS] Tab 'Revenue Intelligence' present
[PASS] Tab 'System Health' present
[PASS] Plotly go.Funnel + plotly.graph_objects import
[PASS] st.warning() conditional on funnel_validation == 'warning'
[PASS] 17 st.metric() calls (KPI cards)
[PASS] fetch_dashboard and fetch_health defined and called
[PASS] requests.RequestException graceful failure handling
[PASS] st.error() fallback for API unavailability
[PASS] st.stop() prevents partial render after error
[PASS] fetch_dashboard() as single data source for all tabs
```

Phase 4 validator: 18/18 still pass after api.py modification (zone_totals
key is additive; no existing checks affected).

---

## Phase 5 Completion Gate

- [x] All 5 tabs implemented
- [x] Single cached /dashboard call per 60s TTL
- [x] Plotly funnel chart (stages 2-4)
- [x] st.warning() for funnel WARNING state
- [x] Funnel disclaimer always visible (Tab 2)
- [x] Source labels for video vs POS data (Tab 1)
- [x] total_dwell_seconds from API exact value (Option b, server-side)
- [x] API failure: requests.RequestException + st.error() + st.stop()
- [x] Video hash fingerprints visible in Tab 5
- [x] Recent log entries visible in Tab 5
- [x] 17/17 structural validation checks pass

**Phase 5 completion gate: PASSED.**
