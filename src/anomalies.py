"""
Anomalies module — five business anomaly detectors.

All five anomalies use video data only. No anomaly crosses datasets.
Anomalies fire only when detector thresholds are genuinely exceeded.
No anomaly is emitted for entry_count=0 or billing>entries — these are
known consequences of CAM_3 Q3 Partial Pass status (footage limitation,
not a detection failure). See funnel.py for monotonicity validation.

Anomaly 1 — Extended Zone Occupancy (CAM_1, CAM_5):
  A track dwelling in skincare (CAM_1) or billing (CAM_5) for >=
  _EXTENDED_DWELL_THRESHOLD_SECONDS (15 min). CAM_5 staff-filtered.
  Threshold is a module constant (not in config.json); "15 minutes" is
  from the master plan. Consistent with the module constant pattern
  established in entry_counter.py and staff_filter.py.

Anomaly 2 — Queue Buildup at Billing (CAM_5):
  CAM_5 occupancy exceeds queue_occupancy_threshold (default 2) for >=
  queue_duration_threshold_seconds (default 300s) continuously.
  Occupancy reconstructed from zone_entry + zone_exit event timeline.

Anomaly 3 — Unusual Warehouse Activity (CAM_4):
  Any warehouse_motion event triggers this anomaly. Wall-clock time is
  not available from frame timestamps (video timestamps are seconds from
  recording start, not time-of-day), so "outside configurable expected
  time window" from the master plan cannot be computed without recording
  metadata. Any detected motion is flagged as operational intelligence —
  the operator should verify it was a scheduled restocking operation.
  See decisions_log.txt Decision 20.

Anomaly 4 — Zone Abandonment (CAM_3 -> CAM_1/CAM_2):
  Entry at CAM_3 (non-staff) with no subsequent zone_dwell at CAM_1 or
  CAM_2 within zone_abandonment_window_seconds. Only entries in the first
  70% of the observation window are checked to avoid false positives from
  truncated footage.

Anomaly 5 — Repeat Zone Visits (CAM_1, CAM_2, CAM_5):
  A track visits the same zone > repeat_visit_threshold (default 3) times,
  each visit qualifying with dwell_seconds >= min_dwell_for_visit_seconds
  (default 10s). CAM_5 staff-filtered.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

from src.utils import get_logger

_log = get_logger(__name__)

# Extended dwell threshold: "15 minutes" from master plan.
# Not in config.json — this is a calibration detail, consistent with
# the module constant pattern (entry_counter._AMBIGUOUS_MIN_DY, etc.).
_EXTENDED_DWELL_THRESHOLD_SECONDS = 900  # 15 minutes


def _iso(event: dict) -> str:
    """Return processed_at from event, or a UTC timestamp if absent."""
    return event.get("processed_at", datetime.now(tz=timezone.utc).isoformat())


def run_anomalies(
    events: list,
    staff_result: dict,
    config: dict,
) -> List[dict]:
    """Run all five anomaly detectors over the event stream.

    Args:
        events: All events loaded from events.json into memory (list of dicts).
                Caller owns the load — this function performs no file I/O.
        staff_result: Dict returned by run_staff_filter().
        config: Loaded config.json dict.

    Returns:
        List of anomaly dicts. Empty list if no thresholds are exceeded.
        Each anomaly dict:
          {
              "type":                    str,
              "severity":                "warning" | "info",
              "message":                 str,
              "business_recommendation": str,
              "triggered_at":            str,  # ISO8601 from event.processed_at
              "camera":                  str,
              "zone":                    str,
          }
    """
    staff_cam3: frozenset = staff_result.get("staff_track_ids", {}).get("CAM_3", frozenset())
    staff_cam5: frozenset = staff_result.get("staff_track_ids", {}).get("CAM_5", frozenset())

    min_dwell       = float(config.get("min_dwell_for_visit_seconds", 10))
    queue_threshold = int(config.get("queue_occupancy_threshold", 2))
    queue_duration  = float(config.get("queue_duration_threshold_seconds", 300))
    abandon_window  = float(config.get("zone_abandonment_window_seconds", 300))
    repeat_threshold = int(config.get("repeat_visit_threshold", 3))

    triggered: List[dict] = []

    # ── Anomaly 1: Extended zone occupancy ───────────────────────────────────
    # zone_dwell in CAM_1 (skincare) or CAM_5 (billing, staff-filtered)
    # where dwell_seconds >= _EXTENDED_DWELL_THRESHOLD_SECONDS.
    for e in events:
        if e.get("event_type") != "zone_dwell":
            continue
        cam = e.get("camera")
        if cam not in ("CAM_1", "CAM_5"):
            continue
        tid = e.get("track_id")
        if cam == "CAM_5" and tid in staff_cam5:
            continue
        dwell = float(e.get("dwell_seconds", 0.0))
        if dwell >= _EXTENDED_DWELL_THRESHOLD_SECONDS:
            zone = e.get("zone", cam)
            triggered.append({
                "type":     "extended_dwell",
                "severity": "warning",
                "message":  (
                    f"Track {tid} dwelled in {zone} ({cam}) for "
                    f"{dwell:.0f}s (threshold: {_EXTENDED_DWELL_THRESHOLD_SECONDS}s)."
                ),
                "business_recommendation": (
                    "Customer may need assistance or be experiencing decision fatigue. "
                    "Consider proactive staff engagement in this zone."
                ),
                "triggered_at": _iso(e),
                "camera":       cam,
                "zone":         zone,
            })
            _log.info(
                "Anomaly 1 (extended_dwell): cam=%s zone=%s tid=%d dwell=%.0fs",
                cam, zone, tid, dwell,
            )

    # ── Anomaly 2: Queue buildup at billing ───────────────────────────────────
    # Reconstruct CAM_5 occupancy from zone_entry / zone_exit timeline.
    # Fires when occupancy > queue_threshold continuously for >= queue_duration.
    timeline = []
    for e in events:
        if e.get("camera") != "CAM_5":
            continue
        tid = e.get("track_id")
        if tid in staff_cam5:
            continue
        if e.get("event_type") == "zone_entry":
            timeline.append((float(e["timestamp_seconds"]), +1, e))
        elif e.get("event_type") == "zone_exit":
            timeline.append((float(e["timestamp_seconds"]), -1, e))
    timeline.sort(key=lambda x: x[0])

    occupancy = 0
    buildup_start = None
    buildup_event = None
    for ts, delta, ev in timeline:
        occupancy += delta
        if occupancy > queue_threshold and buildup_start is None:
            buildup_start = ts
            buildup_event = ev
        elif occupancy <= queue_threshold and buildup_start is not None:
            duration = ts - buildup_start
            if duration >= queue_duration:
                zone = buildup_event.get("zone", "billing")
                triggered.append({
                    "type":     "queue_buildup",
                    "severity": "warning",
                    "message":  (
                        f"Billing queue exceeded {queue_threshold} persons for "
                        f"{duration:.0f}s (threshold: {queue_duration:.0f}s)."
                    ),
                    "business_recommendation": (
                        "Consider opening an additional checkout lane or "
                        "calling extra staff to assist at billing."
                    ),
                    "triggered_at": _iso(buildup_event),
                    "camera":       "CAM_5",
                    "zone":         zone,
                })
                _log.info("Anomaly 2 (queue_buildup): duration=%.0fs", duration)
            buildup_start = None
            buildup_event = None

    # Handle case where high occupancy persists to end of footage
    if buildup_start is not None and timeline:
        last_ts = timeline[-1][0]
        duration = last_ts - buildup_start
        if duration >= queue_duration:
            zone = buildup_event.get("zone", "billing")
            triggered.append({
                "type":     "queue_buildup",
                "severity": "warning",
                "message":  (
                    f"Billing queue exceeded {queue_threshold} persons for "
                    f"{duration:.0f}s to end of footage "
                    f"(threshold: {queue_duration:.0f}s)."
                ),
                "business_recommendation": (
                    "Consider opening an additional checkout lane or "
                    "calling extra staff to assist at billing."
                ),
                "triggered_at": _iso(buildup_event),
                "camera":       "CAM_5",
                "zone":         zone,
            })
            _log.info(
                "Anomaly 2 (queue_buildup): duration=%.0fs (persists to end of footage)",
                duration,
            )

    # ── Anomaly 3: Unusual warehouse activity ─────────────────────────────────
    # Any warehouse_motion event is flagged. Wall-clock time is unavailable
    # from frame timestamps, so hour-of-day filtering is not possible.
    # Decision 20: reframed from "outside expected hours" to "operational alert."
    warehouse_events = [e for e in events if e.get("event_type") == "warehouse_motion"]
    restocking_events = [e for e in warehouse_events if e.get("is_restocking_event", False)]

    if warehouse_events:
        first_ev = min(warehouse_events, key=lambda e: float(e.get("timestamp_seconds", 0)))
        n_motion  = len(warehouse_events)
        n_restock = len(restocking_events)
        severity  = "warning" if n_restock > 0 else "info"
        triggered.append({
            "type":     "unusual_warehouse_activity",
            "severity": severity,
            "message":  (
                f"{n_motion} warehouse motion frame(s) detected; "
                f"{n_restock} classified as sustained restocking."
            ),
            "business_recommendation": (
                "Verify this was a scheduled restocking operation. "
                "Unscheduled warehouse access may indicate a security concern."
            ),
            "triggered_at": _iso(first_ev),
            "camera":       "CAM_4",
            "zone":         "warehouse",
        })
        _log.info(
            "Anomaly 3 (warehouse_activity): motion=%d restocking=%d",
            n_motion, n_restock,
        )

    # ── Anomaly 4: Zone abandonment ───────────────────────────────────────────
    # CAM_3 non-staff entry with no zone_dwell at CAM_1 or CAM_2 within
    # zone_abandonment_window_seconds. Only entries in the first 70% of the
    # observation window are checked to avoid false positives.
    cam3_entries = [
        e for e in events
        if e.get("event_type") == "crossing_entry"
        and e.get("camera") == "CAM_3"
        and e.get("track_id") not in staff_cam3
    ]

    if cam3_entries:
        all_ts = [
            float(e.get("timestamp_seconds", 0))
            for e in events
            if "timestamp_seconds" in e
        ]
        max_ts    = max(all_ts) if all_ts else 0.0
        cutoff_ts = max_ts * 0.70

        zone_visits = [
            e for e in events
            if e.get("event_type") == "zone_dwell"
            and e.get("camera") in ("CAM_1", "CAM_2")
        ]

        for entry in cam3_entries:
            entry_ts = float(entry.get("timestamp_seconds", 0))
            if entry_ts > cutoff_ts:
                continue  # too late in window for reliable abandonment detection
            window_end = entry_ts + abandon_window
            has_visit = any(
                entry_ts
                <= float(
                    e.get("timestamp_entry_seconds", e.get("timestamp_seconds", float("inf")))
                )
                <= window_end
                for e in zone_visits
            )
            if not has_visit:
                tid = entry.get("track_id", -1)
                triggered.append({
                    "type":     "zone_abandonment",
                    "severity": "info",
                    "message":  (
                        f"Track {tid} entered at CAM_3 (t={entry_ts:.1f}s) but "
                        f"no zone visit detected within {abandon_window:.0f}s."
                    ),
                    "business_recommendation": (
                        "Review entrance experience and store layout signage. "
                        "Customer entered but did not proceed to a product zone."
                    ),
                    "triggered_at": _iso(entry),
                    "camera":       "CAM_3",
                    "zone":         "entrance",
                })
                _log.info(
                    "Anomaly 4 (zone_abandonment): tid=%d entry_ts=%.1f", tid, entry_ts
                )

    # ── Anomaly 5: Repeat zone visits ─────────────────────────────────────────
    # A track with > repeat_visit_threshold qualifying visits (dwell_seconds >=
    # min_dwell_for_visit_seconds) in the same zone. CAM_5 staff-filtered.
    visit_map: Dict[tuple, List[dict]] = defaultdict(list)

    for e in events:
        if e.get("event_type") != "zone_dwell":
            continue
        if float(e.get("dwell_seconds", 0)) < min_dwell:
            continue
        cam = e.get("camera")
        tid = e.get("track_id")
        if cam == "CAM_5" and tid in staff_cam5:
            continue
        zone = e.get("zone", "unknown")
        visit_map[(tid, zone, cam)].append(e)

    for (tid, zone, cam), visits in visit_map.items():
        if len(visits) > repeat_threshold:
            first_visit = min(visits, key=lambda e: float(e.get("timestamp_seconds", 0)))
            triggered.append({
                "type":     "repeat_zone_visits",
                "severity": "info",
                "message":  (
                    f"Track {tid} visited {zone} ({cam}) {len(visits)} times "
                    f"(threshold: >{repeat_threshold}, "
                    f"min dwell: {min_dwell:.0f}s each)."
                ),
                "business_recommendation": (
                    "Customer may be undecided. Review product display, "
                    "pricing, and staff availability in this zone."
                ),
                "triggered_at": _iso(first_visit),
                "camera":       cam,
                "zone":         zone,
            })
            _log.info(
                "Anomaly 5 (repeat_zone_visits): cam=%s zone=%s tid=%d visits=%d",
                cam, zone, tid, len(visits),
            )

    _log.info("Anomalies complete: %d triggered", len(triggered))
    return triggered
