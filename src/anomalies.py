"""
Anomalies module — five business anomaly detectors.

Responsibilities (Phase 3):
All five anomalies use video data only. No anomaly crosses datasets.

Anomaly 1 — Extended Zone Occupancy:
  A track dwelling in CAM_1 (skincare) or CAM_5 (billing) for > 15 minutes
  continuously. Computed within one camera. Recommendation: customer may need
  assistance or may be experiencing decision fatigue.

Anomaly 2 — Queue Buildup at Billing:
  CAM_5 occupancy exceeds queue_occupancy_threshold (default 2) simultaneously
  for > queue_duration_threshold_seconds (default 300s) continuously.
  Recommendation: consider opening additional checkout lane.

Anomaly 3 — Unusual Warehouse Activity:
  CAM_4 background subtraction detects motion outside configurable expected
  time window. Recommendation: investigate unscheduled warehouse access.

Anomaly 4 — Zone Abandonment:
  Entry at CAM_3 but no subsequent zone visit at CAM_1 or CAM_2 within
  zone_abandonment_window_seconds (default 300s). Computed only for entries in
  the first 70% of the processing window to prevent false positives from
  truncated observation. Recommendation: review entrance experience or signage.

Anomaly 5 — Repeat Zone Visits:
  A track enters the same product zone > repeat_visit_threshold (default 3)
  times in one session, each visit requiring >= min_dwell_for_visit_seconds
  (default 10s). Two-second pass-throughs excluded. Recommendation: customer
  may be undecided; review product display and pricing.

Each anomaly returns:
  {type, severity, message, business_recommendation, triggered_at (ISO8601)}.
"""
