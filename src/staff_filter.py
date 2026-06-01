"""
Staff filter — heuristic-based classification of staff tracks.

Three rules, all within individual camera views (no cross-camera identity):

  Rule 1 — Roundtrip (CAM_3):
    A track_id with crossings in BOTH directions AND total crossings within
    any staff_roundtrip_window_minutes window exceeding staff_roundtrip_threshold
    is classified as staff. Staff make multiple trips in and out; customers do not.

  Rule 2 — Billing start (CAM_5):
    A zone_dwell track_id whose timestamp_entry_seconds is less than
    _FIRST_FRAME_THRESHOLD_SECONDS is classified as staff. Staff are stationed
    at the billing desk before customers arrive.

  Rule 3 — In first frame (CAM_3):
    A crossing event track_id whose timestamp_seconds is less than
    _FIRST_FRAME_THRESHOLD_SECONDS is classified as staff. Staff are at the
    entry threshold when recording starts.

This module does NOT perform file I/O. The caller owns loading events.json
and passing the events list. The return value is the authoritative source
of truth for staff classification. The staff_filtered field in events.json
is a schema placeholder and is not read by this module or any downstream
module. See decisions_log.txt Decision 19.
"""
from collections import defaultdict
from typing import Dict

from src.utils import get_logger

_log = get_logger(__name__)

# Tracks whose first appearance is within this many seconds of recording start
# are classified as staff (Rules 2 and 3). Not in config.json — this is a
# calibration detail derived from frame_skip / fps, not a business parameter.
# At frame_skip=5 and 30fps, 3.0s covers ~18 processed frames.
# Consistent with _AMBIGUOUS_MIN_DY in entry_counter.py (module constant pattern).
_FIRST_FRAME_THRESHOLD_SECONDS = 3.0


def run_staff_filter(events: list, config: dict) -> dict:
    """Classify tracks as staff or customer from a flat list of events.

    Args:
        events: All events loaded from events.json into memory (list of dicts).
                Caller owns the load — this function performs no file I/O.
        config: Loaded config.json dict.

    Returns:
        {
            "staff_track_ids": {
                "CAM_3": frozenset[int],   # entrance track_ids classified as staff
                "CAM_5": frozenset[int],   # billing track_ids classified as staff
            },
            "staff_filtered_count": int,   # crossing_entry + crossing_exit events
                                           # whose track_id is in CAM_3 staff set
            "staff_filter_enabled":  bool, # mirrors config["staff_filter_enabled"]
        }

    Track IDs are camera-local: CAM_3 ID 5 is not the same person as CAM_5 ID 5.
    When staff_filter_enabled is False, both frozensets are empty and
    staff_filtered_count is 0 — downstream modules apply no filtering.
    """
    enabled = bool(config.get("staff_filter_enabled", True))
    _empty = frozenset()

    if not enabled:
        _log.info("Staff filter disabled (staff_filter_enabled=False)")
        return {
            "staff_track_ids":    {"CAM_3": _empty, "CAM_5": _empty},
            "staff_filtered_count": 0,
            "staff_filter_enabled": False,
        }

    roundtrip_threshold = int(config.get("staff_roundtrip_threshold", 3))
    window_seconds      = float(config.get("staff_roundtrip_window_minutes", 30)) * 60.0

    # Partition relevant events
    cam3_crossings = [
        e for e in events
        if e.get("camera") == "CAM_3"
        and e.get("event_type") in ("crossing_entry", "crossing_exit")
    ]
    cam5_dwells = [
        e for e in events
        if e.get("camera") == "CAM_5"
        and e.get("event_type") == "zone_dwell"
    ]

    staff_cam3: set = set()
    staff_cam5: set = set()

    # ── Rule 1 — roundtrip heuristic (CAM_3) ─────────────────────────────────
    by_track: Dict[int, list] = defaultdict(list)
    for e in cam3_crossings:
        by_track[e["track_id"]].append(e)

    for tid, crossings in by_track.items():
        crossings_sorted = sorted(crossings, key=lambda x: x["timestamp_seconds"])
        for anchor in crossings_sorted:
            t0 = anchor["timestamp_seconds"]
            window = [
                x for x in crossings_sorted
                if t0 <= x["timestamp_seconds"] <= t0 + window_seconds
            ]
            if len(window) > roundtrip_threshold:
                has_entry = any(x.get("crossing_direction") == "entry" for x in window)
                has_exit  = any(x.get("crossing_direction") == "exit"  for x in window)
                if has_entry and has_exit:
                    staff_cam3.add(tid)
                    _log.info(
                        "Staff filter: CAM_3 track_id=%d classified as staff "
                        "(rule_1_roundtrip: %d crossings in %.0fs window)",
                        tid, len(window), window_seconds,
                    )
                    break

    # ── Rule 2 — billing staff at opening (CAM_5) ─────────────────────────────
    for e in cam5_dwells:
        entry_ts = e.get("timestamp_entry_seconds", float("inf"))
        tid = e["track_id"]
        if entry_ts < _FIRST_FRAME_THRESHOLD_SECONDS and tid not in staff_cam5:
            staff_cam5.add(tid)
            _log.info(
                "Staff filter: CAM_5 track_id=%d classified as staff "
                "(rule_2_billing_start: entry_ts=%.2fs)",
                tid, entry_ts,
            )

    # ── Rule 3 — at entrance threshold in first frame (CAM_3) ────────────────
    for e in cam3_crossings:
        ts  = e.get("timestamp_seconds", float("inf"))
        tid = e["track_id"]
        if ts < _FIRST_FRAME_THRESHOLD_SECONDS and tid not in staff_cam3:
            staff_cam3.add(tid)
            _log.info(
                "Staff filter: CAM_3 track_id=%d classified as staff "
                "(rule_3_in_first_frame: ts=%.2fs)",
                tid, ts,
            )

    # Count crossing events whose track_id is classified as staff
    staff_filtered_count = sum(
        1 for e in cam3_crossings if e["track_id"] in staff_cam3
    )

    _log.info(
        "Staff filter complete: cam3_staff=%d cam5_staff=%d filtered_crossings=%d",
        len(staff_cam3), len(staff_cam5), staff_filtered_count,
    )

    return {
        "staff_track_ids": {
            "CAM_3": frozenset(staff_cam3),
            "CAM_5": frozenset(staff_cam5),
        },
        "staff_filtered_count": staff_filtered_count,
        "staff_filter_enabled": True,
    }
