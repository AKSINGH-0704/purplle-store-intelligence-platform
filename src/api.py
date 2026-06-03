"""
API module -- FastAPI service exposing all intelligence endpoints.

Startup: pipeline_summary.json and events.json are loaded once into memory
at process start. All endpoints serve from the in-memory state. Rerunning
process_videos.py requires an API restart to pick up new data.

Endpoints:
  GET /health          -- System status, video hashes, log buffer, uptime
  GET /metrics         -- Traffic (video) + Sales (CSV) + Operations sections
  GET /funnel          -- 5-stage aggregate funnel with validation status
  GET /anomalies       -- List of triggered business anomalies
  GET /zone_metrics/{zone} -- Per-zone stats; 404 with valid_zones for unknown
  GET /events/sample   -- First 10 raw events from events.json
  GET /dashboard       -- All data in one call for Streamlit consumption

All responses < 500ms. CORS open for Streamlit dashboard communication.
"""
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.utils import LOG_BUFFER, get_logger

_log = get_logger(__name__)

# ── Paths (derived from this file's location: src/api.py -> project root) ─────
_ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUMMARY_PATH = os.path.join(_ROOT, "events", "pipeline_summary.json")
_EVENTS_PATH  = os.path.join(_ROOT, "events", "events.json")

# All valid zone names and their source cameras. Used for zone_metrics routing
# and 404 error responses. Derived from zones.json camera assignments.
_VALID_ZONES: Dict[str, str] = {
    "main_floor": "CAM_2",
    "skincare":   "CAM_1",
    "billing":    "CAM_5",
    "entrance":   "CAM_3",
    "warehouse":  "CAM_4",
}

# Mutable startup state. Populated by lifespan(); read by all endpoints.
_state: Dict[str, Any] = {}


# ── Startup helpers ────────────────────────────────────────────────────────────

def _load_events(path: str) -> list:
    """Load an NDJSON events file into a flat list of dicts."""
    if not os.path.exists(path):
        return []
    events: list = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _compute_zone_totals(events: list) -> dict:
    """
    Derive total_dwell_seconds per zone directly from zone_dwell events.
    Option (b): exact sum, not avg * count approximation.
    Returns {zone_name: float} for all zones with at least one qualifying event.
    """
    totals: Dict[str, float] = {}
    for e in events:
        if e.get("event_type") == "zone_dwell":
            zone = e.get("zone")
            if zone:
                totals[zone] = totals.get(zone, 0.0) + float(e.get("dwell_seconds", 0))
    return {zone: round(total, 2) for zone, total in totals.items()}


# ── Application lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load pipeline outputs into memory once at startup. Fail loudly if missing."""
    if not os.path.exists(_SUMMARY_PATH):
        raise FileNotFoundError(
            f"pipeline_summary.json not found at {_SUMMARY_PATH}. "
            "Run 'python process_videos.py' first to generate pipeline outputs."
        )

    with open(_SUMMARY_PATH, encoding="utf-8") as f:
        _state["summary"] = json.load(f)

    events = _load_events(_EVENTS_PATH)
    _state["events"]      = events
    _state["zone_totals"] = _compute_zone_totals(events)
    _state["started_at"]  = time.time()
    _state["ingested_event_ids"] = set()

    _log.info(
        "API startup complete: events=%d zone_totals=%s",
        len(events),
        list(_state["zone_totals"].keys()),
    )
    yield
    # No teardown required.


# ── Application setup ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Purplle Store Intelligence Platform",
    description=(
        "Retail analytics API for Brigade Road store. "
        "Metrics derived from 5 camera feeds (16-04-2026) and POS transaction "
        "data (10-04-2026). Datasets are different dates; no individual-level "
        "matching is performed. Restart required after rerunning process_videos.py."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    """Log every request with endpoint, status, response time, and event count."""
    t0 = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    events_count = (
        _state.get("summary", {}).get("event_counts", {}).get("total", 0)
    )
    _log.info(
        "endpoint=%s status=%d response_time_ms=%.1f events_count=%d",
        request.url.path,
        response.status_code,
        elapsed_ms,
        events_count,
    )
    return response


# ── Private response builders ──────────────────────────────────────────────────
# Extracted so both the individual endpoint AND /dashboard can call them
# without code duplication.

def _metrics_data() -> dict:
    """Assemble the three-section metrics response."""
    summary = _state["summary"]
    csv     = summary.get("csv_analytics", {})
    counts  = summary.get("event_counts", {})
    staff   = summary.get("staff_filter_summary", {})
    funnel  = summary.get("funnel", {})
    return {
        "traffic": {
            "data_date":    "16-04-2026",
            "total_events": counts.get("total", 0),
            "event_counts": counts.get("by_type", {}),
            "staff_filter": {
                "staff_filtered_count":   staff.get("staff_filtered_count", 0),
                "cam3_staff_track_count": staff.get("cam3_staff_track_count", 0),
                "cam5_staff_track_count": staff.get("cam5_staff_track_count", 0),
            },
        },
        "sales": {
            "data_date":               "10-04-2026",
            "transactions":            csv.get("transactions", 0),
            "gmv":                     csv.get("gmv", 0),
            "nmv":                     csv.get("nmv", 0),
            "avg_basket_depth":        csv.get("avg_basket_depth", 0),
            "top_categories":          csv.get("top_categories", []),
            "category_distribution":   csv.get("category_distribution", {}),
            "brand_split":             csv.get("brand_split", {}),
            "salesperson_performance": csv.get("salesperson_performance", []),
            "promotion_effectiveness": csv.get("promotion_effectiveness", []),
            "hourly_revenue":          csv.get("hourly_revenue", {}),
        },
        "operations": {
            "warehouse_motion_events": counts.get("by_type", {}).get("warehouse_motion", 0),
            "anomalies_triggered":     len(summary.get("anomalies", [])),
            "funnel_validation":       funnel.get("funnel_validation", "unknown"),
            "funnel_validation_notes": funnel.get("validation_notes", []),
        },
    }


def _health_data() -> dict:
    """Assemble the health response (omits log_buffer for /dashboard compactness)."""
    summary = _state["summary"]
    meta    = summary.get("processing_metadata", {})
    snap    = meta.get("config_snapshot", {})
    return {
        "status":              "ok",
        "events_loaded":       summary.get("event_counts", {}).get("total", 0),
        "video_hashes":        summary.get("video_hashes", {}),
        "validation_warnings": summary.get("validation_warnings", []),
        "last_run": {
            "run_at":            meta.get("run_at"),
            "total_elapsed_sec": meta.get("total_elapsed_sec"),
            "quick_mode":        meta.get("quick_mode"),
            "cam4_override":     snap.get("cam4_override"),
        },
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """System status: uptime, event counts, video hashes, last pipeline run, log buffer."""
    data = _health_data()
    data["timestamp"]           = datetime.now(tz=timezone.utc).isoformat()
    data["uptime_seconds"]      = round(time.time() - _state["started_at"], 1)
    data["transactions_loaded"] = (
        _state["summary"].get("csv_analytics", {}).get("transactions", 0)
    )
    data["log_buffer"] = list(LOG_BUFFER)
    return data


@app.get("/metrics")
def metrics():
    """Traffic (video, 16-04-2026) + Sales (POS CSV, 10-04-2026) + Operations."""
    return _metrics_data()


@app.get("/funnel")
def funnel():
    """5-stage aggregate customer funnel with monotonicity validation and disclaimer."""
    return _state["summary"].get("funnel", {})


@app.get("/anomalies")
def anomalies():
    """List of triggered business anomalies with business_recommendation and triggered_at."""
    return _state["summary"].get("anomalies", [])


@app.get("/zone_metrics/{zone}")
def zone_metrics(zone: str):
    """Per-zone statistics. Returns HTTP 404 with valid_zones list for unknown zones."""
    if zone not in _VALID_ZONES:
        raise HTTPException(
            status_code=404,
            detail={
                "error":       "zone not found",
                "valid_zones": sorted(_VALID_ZONES.keys()),
            },
        )

    camera      = _VALID_ZONES[zone]
    summary     = _state["summary"]
    funnel_data = summary.get("funnel", {})
    zone_visits = funnel_data.get("zone_visits", {})
    avg_dwell   = funnel_data.get("avg_dwell_seconds", {})
    zone_totals = _state.get("zone_totals", {})
    counts_type = summary.get("event_counts", {}).get("by_type", {})

    if zone in ("main_floor", "skincare", "billing"):
        return {
            "zone":                zone,
            "camera":              camera,
            "visit_count":         zone_visits.get(zone, 0),
            "avg_dwell_seconds":   avg_dwell.get(zone, 0.0),
            "total_dwell_seconds": zone_totals.get(zone, 0.0),
            "data_source":         "zone_dwell events",
        }

    if zone == "entrance":
        return {
            "zone":                       zone,
            "camera":                     camera,
            "entry_count_staff_filtered": funnel_data.get("entry_count", 0),
            "entry_count_raw":            counts_type.get("crossing_entry", 0),
            "exit_count_raw":             counts_type.get("crossing_exit", 0),
            "data_source":                "crossing_entry/crossing_exit events",
            "note": (
                "Q3 Partial Pass: real-world crossing sensitivity unverified "
                "on available footage. Crossing mechanics are validated synthetically."
            ),
        }

    # warehouse
    return {
        "zone":               zone,
        "camera":             camera,
        "motion_event_count": counts_type.get("warehouse_motion", 0),
        "data_source":        "warehouse_motion events",
    }


@app.get("/events/sample")
def events_sample():
    """First 10 raw events from events.json for pipeline integrity verification."""
    return _state.get("events", [])[:10]


@app.get("/dashboard")
def dashboard():
    """All analytics in one call. Designed for Streamlit dashboard consumption."""
    summary = _state["summary"]
    return {
        "funnel":      summary.get("funnel", {}),
        "anomalies":   summary.get("anomalies", []),
        "metrics":     _metrics_data(),
        "health":      _health_data(),
        "zone_totals": _state.get("zone_totals", {}),
    }


# ── Acceptance-gate endpoints ──────────────────────────────────────────────────

@app.post("/events/ingest")
def events_ingest(events: List[Any] = Body(...)):
    """Ingest a batch of up to 500 events. Idempotent by event_id.
    Returns accepted_count and rejected_count. Never returns 5xx for malformed events."""
    if not isinstance(events, list):
        events = [events]

    batch = events[:500]
    seen: set = _state.get("ingested_event_ids", set())
    accepted, rejected, errors = 0, 0, []

    for i, event in enumerate(batch):
        try:
            if not isinstance(event, dict):
                rejected += 1
                errors.append({"index": i, "reason": "not a JSON object"})
                continue
            eid = event.get("event_id")
            if not eid:
                rejected += 1
                errors.append({"index": i, "reason": "missing event_id"})
                continue
            if eid in seen:
                rejected += 1
                errors.append({"index": i, "reason": "duplicate event_id", "event_id": str(eid)})
                continue
            seen.add(eid)
            accepted += 1
        except Exception as exc:
            rejected += 1
            errors.append({"index": i, "reason": str(exc)})

    return {
        "accepted_count": accepted,
        "rejected_count": rejected,
        "total":          len(batch),
        "errors":         errors,
    }


@app.get("/stores/{store_id}/metrics")
def store_metrics(store_id: str):
    """Store-scoped metrics. Reuses pipeline analytics.
    Acceptance gate: GET /stores/STORE_BLR_002/metrics must return valid JSON."""
    data = _metrics_data()
    data["store_id"] = store_id
    return data


@app.get("/stores/{store_id}/funnel")
def store_funnel(store_id: str):
    """Store-scoped aggregate funnel. Part B scoring endpoint."""
    data = dict(_state["summary"].get("funnel", {}))
    data["store_id"] = store_id
    return data


@app.get("/stores/{store_id}/anomalies")
def store_anomalies(store_id: str):
    """Store-scoped anomalies. Part B scoring endpoint."""
    return {
        "store_id":  store_id,
        "anomalies": _state["summary"].get("anomalies", []),
    }


@app.get("/stores/{store_id}/heatmap")
def store_heatmap(store_id: str):
    """Zone visit frequency + avg dwell normalised 0-100.
    data_confidence='low' when fewer than 20 sessions (per challenge spec)."""
    funnel = _state["summary"].get("funnel", {})
    visits = funnel.get("zone_visits", {})
    dwell  = funnel.get("avg_dwell_seconds", {})
    total_sessions = sum(visits.values())
    max_v = max(visits.values(), default=1)
    max_d = max(dwell.values(), default=1)
    zones: Dict[str, Any] = {}
    for zone in sorted(set(list(visits.keys()) + list(dwell.keys()))):
        zones[zone] = {
            "visit_frequency_normalised": round(visits.get(zone, 0) / max_v * 100),
            "avg_dwell_normalised":       round(dwell.get(zone, 0) / max_d * 100),
            "visit_count":                visits.get(zone, 0),
            "avg_dwell_seconds":          dwell.get(zone, 0.0),
        }
    return {
        "store_id":        store_id,
        "zones":           zones,
        "data_confidence": "low" if total_sessions < 20 else "ok",
        "session_count":   total_sessions,
    }
