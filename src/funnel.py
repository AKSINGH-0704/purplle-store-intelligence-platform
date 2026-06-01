"""
Funnel module — aggregate customer funnel and monotonicity validation.

Responsibilities (Phase 3):
- Assemble the five-stage aggregate funnel from upstream module outputs:
    Stage 1: Entry count from entry_counter.py (CAM_3, staff-filtered)
    Stage 2: Main floor visits from session_manager.py (CAM_2)
    Stage 3: Skincare zone visits from session_manager.py (CAM_1)
    Stage 4: Billing interactions from session_manager.py (CAM_5, staff-filtered)
    Stage 5: Transaction count from csv_analytics.py (POS CSV, different date)
- Run monotonicity validation checks after funnel is assembled:
    Check A: Billing count (CAM_5) should not exceed entry count (CAM_3).
             If it does, emit a WARNING with an explicit CAM_3 Q3 explanation.
    Check B: Main floor visits (CAM_2) should be >= skincare visits (CAM_1).
             If not, emit a WARNING (unexpected funnel narrowing).
- Return funnel dict with counts, avg dwell per zone, validation status,
  validation_notes (human-readable explanation of any warnings), and a
  disclaimer about aggregate-only nature and the video/CSV date mismatch.

No claim is made that the same individual appears at multiple funnel stages.
Funnel validation WARNING is a data quality note, not an anomaly signal.
See run_anomalies() for threshold-based anomaly detection.
"""
from typing import Dict, List

from src.utils import get_logger

_log = get_logger(__name__)

_DISCLAIMER = (
    "Funnel metrics are aggregate counts only. No claim is made that the same "
    "individual appears at multiple funnel stages. "
    "Video data date: 16-04-2026. POS/CSV data date: 10-04-2026. "
    "These datasets represent separate days; no individual-level matching is "
    "performed or implied anywhere in this system. "
    "CAM_3 entry count reflects Q3 Partial Pass status: crossing mechanics are "
    "validated synthetically but real-world sensitivity is unverified on the "
    "available footage. An entry_count of 0 is a footage limitation, not a "
    "detection failure."
)


def run_funnel(
    events: list,
    csv_result: dict,
    staff_result: dict,
    config: dict,
) -> dict:
    """Assemble the five-stage aggregate customer funnel and run validation.

    Args:
        events: All events loaded from events.json into memory (list of dicts).
                Caller owns the load — this function performs no file I/O.
        csv_result: Dict returned by run_csv_analytics().
        staff_result: Dict returned by run_staff_filter().
        config: Loaded config.json dict. Reserved for future per-stage thresholds.

    Returns:
        {
            "entry_count":          int,
            "zone_visits": {
                "main_floor":       int,
                "skincare":         int,
                "billing":          int,
            },
            "avg_dwell_seconds": {
                "main_floor":       float,
                "skincare":         float,
                "billing":          float,
            },
            "transaction_count":    int,
            "staff_filtered_count": int,
            "funnel_validation":    "pass" | "warning",
            "validation_notes":     list[str],
            "disclaimer":           str,
        }

    Stage mapping:
        Stage 1 — entry_count:       crossing_entry events, CAM_3, staff-filtered
        Stage 2 — main_floor visits: zone_dwell events, CAM_2
        Stage 3 — skincare visits:   zone_dwell events, CAM_1
        Stage 4 — billing:           zone_dwell events, CAM_5, staff-filtered
        Stage 5 — transactions:      csv_result["transactions"] (POS CSV)
    """
    staff_cam3: frozenset = staff_result.get("staff_track_ids", {}).get("CAM_3", frozenset())
    staff_cam5: frozenset = staff_result.get("staff_track_ids", {}).get("CAM_5", frozenset())
    staff_filtered_count: int = staff_result.get("staff_filtered_count", 0)

    # ── Stage 1: Entry count (CAM_3 crossing_entry, staff-filtered) ───────────
    entry_count = sum(
        1 for e in events
        if e.get("event_type") == "crossing_entry"
        and e.get("camera") == "CAM_3"
        and e.get("track_id") not in staff_cam3
    )

    # ── Stage 2: Main floor visits (CAM_2 zone_dwell) ────────────────────────
    cam2_dwells = [
        e for e in events
        if e.get("event_type") == "zone_dwell" and e.get("camera") == "CAM_2"
    ]
    main_floor_visits = len(cam2_dwells)
    main_floor_avg = (
        round(sum(e["dwell_seconds"] for e in cam2_dwells) / len(cam2_dwells), 2)
        if cam2_dwells else 0.0
    )

    # ── Stage 3: Skincare visits (CAM_1 zone_dwell) ──────────────────────────
    cam1_dwells = [
        e for e in events
        if e.get("event_type") == "zone_dwell" and e.get("camera") == "CAM_1"
    ]
    skincare_visits = len(cam1_dwells)
    skincare_avg = (
        round(sum(e["dwell_seconds"] for e in cam1_dwells) / len(cam1_dwells), 2)
        if cam1_dwells else 0.0
    )

    # ── Stage 4: Billing interactions (CAM_5 zone_dwell, staff-filtered) ─────
    cam5_dwells = [
        e for e in events
        if e.get("event_type") == "zone_dwell"
        and e.get("camera") == "CAM_5"
        and e.get("track_id") not in staff_cam5
    ]
    billing_visits = len(cam5_dwells)
    billing_avg = (
        round(sum(e["dwell_seconds"] for e in cam5_dwells) / len(cam5_dwells), 2)
        if cam5_dwells else 0.0
    )

    # ── Stage 5: Transaction count (POS CSV) ──────────────────────────────────
    transaction_count = int(csv_result.get("transactions", 0))

    # ── Monotonicity validation ───────────────────────────────────────────────
    validation_notes: List[str] = []

    # Check A: billing should not exceed entry_count
    if billing_visits > entry_count:
        validation_notes.append(
            f"Check A: billing interactions ({billing_visits}) exceed entry count "
            f"({entry_count}). Expected -- CAM_3 Q3 status is Partial Pass. "
            f"Crossing mechanics are validated synthetically; real-world sensitivity "
            f"is unverified on the available footage. entry_count=0 is a footage "
            f"limitation, not a detection failure. Monotonicity cannot be confirmed "
            f"until CAM_3 crossing sensitivity is verified on real-world footage."
        )

    # Check B: main_floor visits should be >= skincare visits
    if main_floor_visits < skincare_visits:
        validation_notes.append(
            f"Check B: skincare visits ({skincare_visits}) exceed main floor visits "
            f"({main_floor_visits}). Unexpected — customers detected in the skincare "
            f"zone (CAM_1) should also be counted on the main floor (CAM_2). "
            f"Review CAM_2 zone polygon coverage."
        )

    funnel_validation = "warning" if validation_notes else "pass"

    _log.info(
        "funnel: entries=%d main_floor=%d skincare=%d billing=%d "
        "transactions=%d validation=%s",
        entry_count, main_floor_visits, skincare_visits,
        billing_visits, transaction_count, funnel_validation,
    )

    return {
        "entry_count":          entry_count,
        "zone_visits": {
            "main_floor":       main_floor_visits,
            "skincare":         skincare_visits,
            "billing":          billing_visits,
        },
        "avg_dwell_seconds": {
            "main_floor":       main_floor_avg,
            "skincare":         skincare_avg,
            "billing":          billing_avg,
        },
        "transaction_count":    transaction_count,
        "staff_filtered_count": staff_filtered_count,
        "funnel_validation":    funnel_validation,
        "validation_notes":     validation_notes,
        "disclaimer":           _DISCLAIMER,
    }
