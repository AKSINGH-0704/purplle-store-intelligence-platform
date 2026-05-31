"""
API module — FastAPI service exposing all intelligence endpoints.

Responsibilities (Phase 4):
- Load events.json and CSV data into memory at startup (target < 2 seconds).
- Expose the following endpoints (all respond in < 500ms):

  GET /health
    Returns: status, timestamp, events_loaded, transactions_loaded,
    uptime_seconds, video_hashes, last_processing_time_seconds, config.

  GET /metrics
    Returns three sections: traffic (from video, 16-04-2026),
    sales (from CSV, 10-04-2026), operations (CAM_4 + CAM_5).

  GET /funnel
    Returns: entry_count, zone_visits, transaction_count, funnel_validation,
    disclaimer (aggregate only, different dates).

  GET /anomalies
    Returns list of all detected anomaly dicts with business_recommendation
    and triggered_at timestamps.

  GET /zone_metrics/{zone}
    Returns per-zone stats. Validates zone name; returns HTTP 404 with
    {"error": "Zone not found", "valid_zones": [...]} for invalid names.

  GET /events/sample
    Returns 10 raw events from events.json showing timestamped pipeline output.

  GET /dashboard
    Returns all data in a single call for Streamlit dashboard consumption.

- Implement structured JSON logging (timestamp, endpoint, response_time_ms,
  events_count) using Python's logging module.
- Expose last 50 log entries via /health response for System Health tab.
"""
