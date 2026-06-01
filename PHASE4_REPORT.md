# PHASE 4 REPORT -- API Development

Phase: 4 -- API Development
Status: COMPLETE (single checkpoint)
Started: 2026-06-01
Completed: 2026-06-01
Commit: TBD
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## Objective

Expose all pipeline analytics through a FastAPI service on port 8000.
All endpoints respond in < 500ms. Data is loaded once at startup from
precomputed pipeline outputs. No computation at request time.

---

## Checkpoint Status

| # | Checkpoint | Files | Status | Result |
|---|-----------|-------|--------|--------|
| 4 | FastAPI endpoints | src/api.py | **COMPLETE** | 18/18 validation checks pass |

---

## Architecture Decision -- Option C (Startup Load)

**API loads `pipeline_summary.json` and `events.json` once at startup and serves
all responses from the in-memory state. Rerunning `process_videos.py` requires
an API restart to pick up new data.**

This is the approved design (Option C). Rationale:
- Fastest possible response times (sub-millisecond in-process; <500ms from network)
- Simplest architecture: no recomputation per request, no repeated disk I/O
- Matches the precomputed-analytics design established in Phase 3
- Most suitable for a hackathon demo where `docker compose up` is the primary path

`process_videos.py` is the regeneration path. The API is the serving path.
These are deliberately separated. Restart behavior is documented in the API
description and will be documented in README.md (Phase 7).

### Startup data loading

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Raises FileNotFoundError (not sys.exit) if pipeline outputs are absent
    with open(_SUMMARY_PATH) as f:
        _state["summary"] = json.load(f)          # pipeline_summary.json
    events = _load_events(_EVENTS_PATH)            # events.json (51 events)
    _state["events"]      = events
    _state["zone_totals"] = _compute_zone_totals(events)  # derived at startup
    _state["started_at"]  = time.time()
    yield
```

`_state` is a module-level dict. All 7 endpoints read from it with no file I/O.

---

## What was implemented

**`src/api.py`** -- FastAPI service replacing the Phase 0 placeholder

### Configuration

| Item | Value |
|------|-------|
| Framework | FastAPI 0.115.0 |
| Server | uvicorn[standard] |
| Port | 8000 |
| CORS | allow_origins=["*"], allow_methods=["GET"] |
| Startup pattern | `@asynccontextmanager lifespan` (modern; replaces deprecated `on_event`) |
| Startup failure | Raises `FileNotFoundError` -- FastAPI exits cleanly with traceback |

### Endpoint map

| Endpoint | Response source | Status code on error |
|----------|----------------|---------------------|
| `GET /health` | `_state["summary"]` + LOG_BUFFER + `time.time()` | n/a |
| `GET /metrics` | `_metrics_data()` helper | n/a |
| `GET /funnel` | `_state["summary"]["funnel"]` direct | n/a |
| `GET /anomalies` | `_state["summary"]["anomalies"]` direct | n/a |
| `GET /zone_metrics/{zone}` | `_state["summary"]["funnel"]` + `_state["zone_totals"]` | 404 for unknown zone |
| `GET /events/sample` | `_state["events"][:10]` | n/a |
| `GET /dashboard` | `_metrics_data()` + `_health_data()` + funnel + anomalies | n/a |

### Key implementation notes

**`total_dwell_seconds` in `/zone_metrics`:** Derived directly from `zone_dwell`
events at startup via `_compute_zone_totals()` (Option b: exact sum, not
`avg * count` approximation). Result for current footage:
- main_floor: 130.8s (5 visits)
- skincare: 66.4s (2 visits)
- billing: 54.03s (2 visits)

**`/zone_metrics/entrance`:** Returns both staff-filtered (`entry_count_staff_filtered`)
and raw (`entry_count_raw`, `exit_count_raw`) crossing counts. Current footage: all
zeros (CAM_3 Q3 Partial Pass). Note field explains the limitation explicitly.

**`/zone_metrics/warehouse`:** Returns `motion_event_count=2` derived from
`event_counts["by_type"]["warehouse_motion"]`. Genuine events captured at t=92.3s
via the CAM_4 full-video override (Decision 21).

**`/dashboard`:** Returns all four sections (funnel, anomalies, metrics, health)
in one call for Streamlit consumption. Omits `log_buffer` from the health sub-dict
to keep the response compact; dashboard reads it separately from `/health`.

**HTTP middleware:** Every request is logged via `_log.info()` with endpoint,
status code, `response_time_ms`, and `events_count`. Entries accumulate in
`LOG_BUFFER` (deque maxlen=50) and are returned by `/health`.

**`_metrics_data()` and `_health_data()`:** Private helper functions called by
both their respective individual endpoints and by `/dashboard`. No duplicated logic.

### Sample responses (from 18/18 validation run)

**`GET /health`**
```json
{
  "status": "ok",
  "events_loaded": 51,
  "transactions_loaded": 24,
  "uptime_seconds": 0.4,
  "timestamp": "2026-06-01T17:45:38+00:00",
  "last_run": {
    "run_at": "2026-06-01T17:29:17+00:00",
    "total_elapsed_sec": 142.6,
    "quick_mode": false,
    "cam4_override": "full_video"
  },
  "video_hashes": {
    "CAM_1": "8ca666cd17bdd329...",
    "CAM_2": "28914b2447af5155...",
    "CAM_3": "7f552b1b243c4270...",
    "CAM_4": "b58a8a45be006313...",
    "CAM_5": "4d2ad25fd6300e41..."
  },
  "validation_warnings": [],
  "log_buffer": [ ...last 50 structured log entries... ]
}
```

**`GET /zone_metrics/main_floor`** -- Option b total_dwell confirmed
```json
{
  "zone": "main_floor",
  "camera": "CAM_2",
  "visit_count": 5,
  "avg_dwell_seconds": 26.16,
  "total_dwell_seconds": 130.8,
  "data_source": "zone_dwell events"
}
```

**`GET /zone_metrics/invalid`** -- HTTP 404
```json
{
  "detail": {
    "error": "zone not found",
    "valid_zones": ["billing", "entrance", "main_floor", "skincare", "warehouse"]
  }
}
```

**`GET /anomalies`** -- 1 triggered (warehouse activity at t=92.3s)
```json
[
  {
    "type": "unusual_warehouse_activity",
    "severity": "warning",
    "message": "2 warehouse motion frame(s) detected; 2 classified as sustained restocking.",
    "business_recommendation": "Verify this was a scheduled restocking operation...",
    "triggered_at": "2026-06-01T17:29:16+00:00",
    "camera": "CAM_4",
    "zone": "warehouse"
  }
]
```

---

## Validation results

```
18/18 checks passed -- ALL PASS

[PASS] API startup: lifespan populated _state (events=51, zone_totals keys=3)
[PASS] GET /health: 200, status='ok'
[PASS] GET /health: all 8 required keys present with correct types
[PASS] GET /health: video_hashes has 5 entries (one per camera)
[PASS] GET /metrics: 200 with traffic/sales/operations sections + data_dates
[PASS] GET /metrics: gmv=44920.0  nmv=34831.74
[PASS] GET /funnel: funnel_validation='warning', disclaimer present
[PASS] GET /anomalies: 1 anomaly, all 6 required keys present
[PASS] GET /zone_metrics/main_floor: visit=5 avg=26.16s total=130.8s
[PASS] GET /zone_metrics/skincare: visit=2 avg=33.2s total=66.4s
[PASS] GET /zone_metrics/billing: visit=2 avg=27.02s total=54.03s
[PASS] GET /zone_metrics/entrance: staff_filtered=0 raw_entry=0 raw_exit=0
[PASS] GET /zone_metrics/warehouse: motion_event_count=2
[PASS] GET /zone_metrics/invalid: 404 with valid_zones list
[PASS] GET /events/sample: 10 events, first event_type=zone_entry
[PASS] GET /dashboard: all 4 sections present with correct sub-structure
[PASS] Response times: all < 500ms; slowest=/health at 0.9ms
[PASS] GET /dashboard: log_buffer absent from health sub-dict (by design)
```

**Response time target: < 500ms. Actual: < 1ms per endpoint (in-process via TestClient).**
Network overhead from Docker or localhost will add latency but will remain well
under 500ms for all endpoints given the in-memory response architecture.

---

## Phase 4 Completion Gate

- [x] All 7 endpoints implemented and respond correctly
- [x] All responses < 500ms
- [x] `/health` returns video hashes, config, log buffer, uptime
- [x] `/zone_metrics/{zone}` returns 404 with valid_zones for unknown zone
- [x] Structured JSON logging via LOG_BUFFER; accessible at `/health`
- [x] CORS enabled for Streamlit dashboard communication
- [x] Startup raises exception (not sys.exit) on missing pipeline outputs
- [x] 18/18 validation checks pass

**Phase 4 completion gate: PASSED.**
