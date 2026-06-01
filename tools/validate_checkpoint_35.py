"""
Checkpoint 3.5 validation -- funnel and anomaly detectors.

Run from project root: python tools/validate_checkpoint_35.py
Exit 0 = all checks passed.

All tests use synthetic event fixtures only (no video required).

Note: Both run_funnel() and run_anomalies() return empty/warning results on
current footage due to footage constraints (CAM_3 Q3 Partial Pass, 1000-frame
processing window). This validator proves the logic is correct using synthetic
fixtures that exercise each threshold boundary independently.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.utils import load_config

cfg = load_config(os.path.join(ROOT, "config.json"))

results = []


def check(label, fn):
    try:
        detail = fn()
        results.append(("PASS", label, detail or ""))
        return True
    except Exception as exc:
        results.append(("FAIL", label, str(exc)))
        return False


# ── Synthetic event builders ──────────────────────────────────────────────────

def _dwell(track_id, camera, dwell_seconds, entry_ts=10.0, zone=None):
    cam_zone = {"CAM_1": "skincare", "CAM_2": "main_floor", "CAM_5": "billing"}
    return {
        "event_type":              "zone_dwell",
        "camera":                  camera,
        "zone":                    zone or cam_zone.get(camera, "unknown"),
        "track_id":                track_id,
        "dwell_seconds":           float(dwell_seconds),
        "timestamp_seconds":       float(entry_ts),
        "timestamp_entry_seconds": float(entry_ts),
        "timestamp_exit_seconds":  float(entry_ts) + float(dwell_seconds),
        "processed_at":            "2026-04-16T10:00:00+00:00",
    }


def _zone_entry(track_id, camera, ts, zone=None):
    cam_zone = {"CAM_5": "billing", "CAM_2": "main_floor", "CAM_1": "skincare"}
    return {
        "event_type":        "zone_entry",
        "camera":            camera,
        "zone":              zone or cam_zone.get(camera, "unknown"),
        "track_id":          track_id,
        "timestamp_seconds": float(ts),
        "processed_at":      "2026-04-16T10:00:00+00:00",
        "centroid":          [100, 100],
    }


def _zone_exit(track_id, camera, ts, zone=None):
    cam_zone = {"CAM_5": "billing", "CAM_2": "main_floor", "CAM_1": "skincare"}
    return {
        "event_type":        "zone_exit",
        "camera":            camera,
        "zone":              zone or cam_zone.get(camera, "unknown"),
        "track_id":          track_id,
        "timestamp_seconds": float(ts),
        "processed_at":      "2026-04-16T10:00:00+00:00",
        "centroid":          [100, 100],
    }


def _crossing(track_id, direction, ts, camera="CAM_3"):
    return {
        "event_type":         f"crossing_{direction}",
        "camera":             camera,
        "zone":               "entrance",
        "track_id":           track_id,
        "timestamp_seconds":  float(ts),
        "crossing_direction": direction,
        "processed_at":       "2026-04-16T10:00:00+00:00",
        "staff_filtered":     False,
    }


def _warehouse(ts, contour_area=30000.0, is_restocking=True):
    return {
        "event_type":          "warehouse_motion",
        "camera":              "CAM_4",
        "zone":                "warehouse",
        "timestamp_seconds":   float(ts),
        "contour_area":        float(contour_area),
        "is_restocking_event": is_restocking,
        "processed_at":        "2026-04-16T10:00:00+00:00",
    }


def _empty_staff():
    return {
        "staff_track_ids":     {"CAM_3": frozenset(), "CAM_5": frozenset()},
        "staff_filtered_count": 0,
        "staff_filter_enabled": True,
    }


def _empty_csv():
    return {"transactions": 24}


REQUIRED_FUNNEL_KEYS = {
    "entry_count", "zone_visits", "avg_dwell_seconds",
    "transaction_count", "staff_filtered_count",
    "funnel_validation", "validation_notes", "disclaimer",
}
REQUIRED_ZONE_VISIT_KEYS  = {"main_floor", "skincare", "billing"}
REQUIRED_ANOMALY_KEYS     = {
    "type", "severity", "message",
    "business_recommendation", "triggered_at", "camera", "zone",
}


# ---------------------------------------------------------------------------
# 1. Imports
# ---------------------------------------------------------------------------
def _test_imports():
    from src.funnel    import run_funnel     # noqa: F401
    from src.anomalies import run_anomalies  # noqa: F401
    return "run_funnel and run_anomalies imported"

check("funnel + anomalies: imports without error", _test_imports)


# ---------------------------------------------------------------------------
# 2. funnel: all required keys present in output
# ---------------------------------------------------------------------------
def _test_funnel_schema():
    from src.funnel import run_funnel
    result = run_funnel([], _empty_csv(), _empty_staff(), cfg)
    missing = REQUIRED_FUNNEL_KEYS - result.keys()
    assert not missing, f"Missing keys: {missing}"
    missing_zone = REQUIRED_ZONE_VISIT_KEYS - result["zone_visits"].keys()
    assert not missing_zone, f"zone_visits missing: {missing_zone}"
    missing_dwell = REQUIRED_ZONE_VISIT_KEYS - result["avg_dwell_seconds"].keys()
    assert not missing_dwell, f"avg_dwell_seconds missing: {missing_dwell}"
    assert isinstance(result["validation_notes"], list)
    assert isinstance(result["disclaimer"], str)
    return "all required funnel keys present; correct types"

check("funnel: output schema has all required keys and correct types", _test_funnel_schema)


# ---------------------------------------------------------------------------
# 3. funnel: Check A warning fires (billing > entries)
# ---------------------------------------------------------------------------
def _test_funnel_check_a_warning():
    from src.funnel import run_funnel
    events = [_dwell(1, "CAM_5", 30.0)]  # 1 billing visit, 0 entries
    result = run_funnel(events, _empty_csv(), _empty_staff(), cfg)
    assert result["funnel_validation"] == "warning", (
        f"Expected 'warning', got {result['funnel_validation']!r}"
    )
    assert len(result["validation_notes"]) >= 1
    assert any("Check A" in note for note in result["validation_notes"])
    assert result["zone_visits"]["billing"] == 1
    assert result["entry_count"] == 0
    return "billing=1 > entries=0 -> validation='warning', Check A note present"

check("funnel Check A: billing > entries triggers warning", _test_funnel_check_a_warning)


# ---------------------------------------------------------------------------
# 4. funnel: Check A pass (billing <= entries)
# ---------------------------------------------------------------------------
def _test_funnel_check_a_pass():
    from src.funnel import run_funnel
    events = [
        _crossing(10, "entry", 5.0),  # 1 entry
        _dwell(1, "CAM_5", 30.0),     # 1 billing visit
    ]
    result = run_funnel(events, _empty_csv(), _empty_staff(), cfg)
    assert result["entry_count"] == 1
    assert result["zone_visits"]["billing"] == 1
    check_a_notes = [n for n in result["validation_notes"] if "Check A" in n]
    assert not check_a_notes, f"Check A should not fire; notes: {check_a_notes}"
    return "billing=1, entries=1 -> Check A does not fire"

check("funnel Check A: billing <= entries does not trigger warning", _test_funnel_check_a_pass)


# ---------------------------------------------------------------------------
# 5. funnel: Check B warning fires (skincare > main_floor)
# ---------------------------------------------------------------------------
def _test_funnel_check_b_warning():
    from src.funnel import run_funnel
    events = [
        _dwell(1, "CAM_1", 30.0),  # 1 skincare, 0 main_floor
    ]
    result = run_funnel(events, _empty_csv(), _empty_staff(), cfg)
    assert result["zone_visits"]["skincare"] == 1
    assert result["zone_visits"]["main_floor"] == 0
    assert any("Check B" in note for note in result["validation_notes"])
    return "skincare=1 > main_floor=0 -> Check B warning fires"

check("funnel Check B: skincare > main_floor triggers warning", _test_funnel_check_b_warning)


# ---------------------------------------------------------------------------
# 6. funnel: CAM_5 staff tracks excluded from billing count
# ---------------------------------------------------------------------------
def _test_funnel_staff_filter():
    from src.funnel import run_funnel
    staff = {
        "staff_track_ids":     {"CAM_3": frozenset(), "CAM_5": frozenset({99})},
        "staff_filtered_count": 0,
        "staff_filter_enabled": True,
    }
    events = [
        _dwell(99, "CAM_5", 30.0),  # staff -- should be excluded
        _dwell(10, "CAM_5", 30.0),  # customer -- should be included
    ]
    result = run_funnel(events, _empty_csv(), staff, cfg)
    assert result["zone_visits"]["billing"] == 1, (
        f"Expected 1 billing visit (staff excluded); got {result['zone_visits']['billing']}"
    )
    return "CAM_5 track_id=99 (staff) excluded; track_id=10 counted -> billing=1"

check("funnel: CAM_5 staff tracks excluded from billing count", _test_funnel_staff_filter)


# ---------------------------------------------------------------------------
# 7. funnel: disclaimer is a non-empty string
# ---------------------------------------------------------------------------
def _test_funnel_disclaimer():
    from src.funnel import run_funnel
    result = run_funnel([], _empty_csv(), _empty_staff(), cfg)
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 50, "Disclaimer is too short"
    assert "CAM_3" in result["disclaimer"], "Disclaimer should mention CAM_3"
    return f"disclaimer present: {len(result['disclaimer'])} chars"

check("funnel: disclaimer is a non-empty informative string", _test_funnel_disclaimer)


# ---------------------------------------------------------------------------
# 8. Anomaly 1: extended dwell fires (dwell >= 900s)
# ---------------------------------------------------------------------------
def _test_anomaly1_fires():
    from src.anomalies import run_anomalies
    events = [_dwell(1, "CAM_1", dwell_seconds=1000)]
    result = run_anomalies(events, _empty_staff(), cfg)
    extended = [a for a in result if a["type"] == "extended_dwell"]
    assert len(extended) >= 1, "Expected at least 1 extended_dwell anomaly"
    assert extended[0]["severity"] == "warning"
    return f"dwell=1000s >= 900s threshold -> extended_dwell fires (severity=warning)"

check("Anomaly 1: extended dwell fires when dwell_seconds >= 900s", _test_anomaly1_fires)


# ---------------------------------------------------------------------------
# 9. Anomaly 1: does not fire (dwell < 900s)
# ---------------------------------------------------------------------------
def _test_anomaly1_no_fire():
    from src.anomalies import run_anomalies
    events = [_dwell(1, "CAM_1", dwell_seconds=300)]
    result = run_anomalies(events, _empty_staff(), cfg)
    extended = [a for a in result if a["type"] == "extended_dwell"]
    assert not extended, f"Extended dwell should not fire at 300s; got {extended}"
    return "dwell=300s < 900s threshold -> no extended_dwell anomaly"

check("Anomaly 1: does not fire when dwell_seconds < 900s", _test_anomaly1_no_fire)


# ---------------------------------------------------------------------------
# 10. Anomaly 2: queue buildup fires (3+ persons for >= 300s)
#     queue_occupancy_threshold=2 so fires when occupancy > 2 (i.e. 3+)
# ---------------------------------------------------------------------------
def _test_anomaly2_fires():
    from src.anomalies import run_anomalies
    events = [
        _zone_entry(1, "CAM_5", ts=0),
        _zone_entry(2, "CAM_5", ts=1),
        _zone_entry(3, "CAM_5", ts=2),    # occupancy = 3 > 2, buildup starts
        _zone_exit(1,  "CAM_5", ts=400),  # occupancy = 2, duration=398s >= 300s
    ]
    result = run_anomalies(events, _empty_staff(), cfg)
    queue = [a for a in result if a["type"] == "queue_buildup"]
    assert len(queue) >= 1, f"Expected queue_buildup anomaly; got {result}"
    assert queue[0]["severity"] == "warning"
    return "3+ persons for 398s >= 300s threshold -> queue_buildup fires"

check("Anomaly 2: queue buildup fires (3+ persons for >= 300s)", _test_anomaly2_fires)


# ---------------------------------------------------------------------------
# 11. Anomaly 2: does not fire (occupancy never exceeds threshold)
# ---------------------------------------------------------------------------
def _test_anomaly2_no_fire():
    from src.anomalies import run_anomalies
    # queue_occupancy_threshold=2, so 2 persons = not > 2, no trigger
    events = [
        _zone_entry(1, "CAM_5", ts=0),
        _zone_entry(2, "CAM_5", ts=1),  # occupancy = 2 (not > 2, no buildup)
        _zone_exit(1,  "CAM_5", ts=500),
    ]
    result = run_anomalies(events, _empty_staff(), cfg)
    queue = [a for a in result if a["type"] == "queue_buildup"]
    assert not queue, f"queue_buildup should not fire with occupancy=2; got {queue}"
    return "occupancy=2 not > threshold of 2 -> no queue_buildup"

check("Anomaly 2: does not fire when occupancy <= threshold", _test_anomaly2_no_fire)


# ---------------------------------------------------------------------------
# 12. Anomaly 3: warehouse activity fires on any warehouse_motion event
# ---------------------------------------------------------------------------
def _test_anomaly3_fires():
    from src.anomalies import run_anomalies
    events = [_warehouse(ts=92.3, is_restocking=True)]
    result = run_anomalies(events, _empty_staff(), cfg)
    wh = [a for a in result if a["type"] == "unusual_warehouse_activity"]
    assert len(wh) == 1, f"Expected 1 warehouse anomaly; got {result}"
    assert wh[0]["camera"] == "CAM_4"
    assert wh[0]["zone"] == "warehouse"
    return f"warehouse_motion event -> unusual_warehouse_activity fires (severity={wh[0]['severity']})"

check("Anomaly 3: warehouse activity fires on any warehouse_motion event", _test_anomaly3_fires)


# ---------------------------------------------------------------------------
# 13. Anomaly 3: does not fire when no warehouse_motion events
# ---------------------------------------------------------------------------
def _test_anomaly3_no_fire():
    from src.anomalies import run_anomalies
    result = run_anomalies([], _empty_staff(), cfg)
    wh = [a for a in result if a["type"] == "unusual_warehouse_activity"]
    assert not wh, f"warehouse anomaly should not fire on empty events; got {wh}"
    return "no warehouse_motion events -> no unusual_warehouse_activity"

check("Anomaly 3: does not fire when no warehouse_motion events", _test_anomaly3_no_fire)


# ---------------------------------------------------------------------------
# 14. Anomaly 4: zone abandonment fires (entry, no zone visit within 300s)
# ---------------------------------------------------------------------------
def _test_anomaly4_fires():
    from src.anomalies import run_anomalies
    # max_ts will be determined from all events. entry at t=5, max_ts=100 -> cutoff=70
    # 5 <= 70, so this entry qualifies. No zone_dwell from CAM_1/CAM_2.
    events = [
        _crossing(20, "entry", ts=5.0),
        _zone_entry(99, "CAM_5", ts=5.1),  # billing, not a qualifying zone visit
        _dwell(99, "CAM_5", dwell_seconds=10, entry_ts=5.1),  # CAM_5, not CAM_1/CAM_2
        # Include a high-ts event so max_ts is computed correctly
        _zone_entry(99, "CAM_5", ts=100.0),
    ]
    result = run_anomalies(events, _empty_staff(), cfg)
    abandon = [a for a in result if a["type"] == "zone_abandonment"]
    assert len(abandon) >= 1, f"Expected zone_abandonment; got {result}"
    assert abandon[0]["camera"] == "CAM_3"
    return "entry at CAM_3, no CAM_1/CAM_2 visit within 300s -> zone_abandonment fires"

check("Anomaly 4: zone abandonment fires (entry, no zone visit follows)", _test_anomaly4_fires)


# ---------------------------------------------------------------------------
# 15. Anomaly 4: does not fire when zone visit follows entry within window
# ---------------------------------------------------------------------------
def _test_anomaly4_no_fire():
    from src.anomalies import run_anomalies
    events = [
        _crossing(21, "entry", ts=5.0),
        _dwell(5, "CAM_2", dwell_seconds=30, entry_ts=10.0),  # CAM_2 visit at t=10
        _zone_entry(99, "CAM_2", ts=100.0),  # high-ts anchor for max_ts
    ]
    result = run_anomalies(events, _empty_staff(), cfg)
    abandon = [a for a in result if a["type"] == "zone_abandonment"]
    assert not abandon, f"zone_abandonment should not fire; got {abandon}"
    return "entry at CAM_3, CAM_2 zone_dwell within 300s -> no zone_abandonment"

check("Anomaly 4: does not fire when zone visit follows entry", _test_anomaly4_no_fire)


# ---------------------------------------------------------------------------
# 16. Anomaly 5: repeat visits fires (4 qualifying visits, threshold=3)
# ---------------------------------------------------------------------------
def _test_anomaly5_fires():
    from src.anomalies import run_anomalies
    events = [
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=10),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=40),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=70),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=100),
    ]  # 4 visits > threshold 3 -> fires
    result = run_anomalies(events, _empty_staff(), cfg)
    repeat = [a for a in result if a["type"] == "repeat_zone_visits"]
    assert len(repeat) >= 1, f"Expected repeat_zone_visits; got {result}"
    assert "30" in repeat[0]["message"] or str(30) in repeat[0]["message"]
    return "track_id=30: 4 visits > threshold 3 -> repeat_zone_visits fires"

check("Anomaly 5: repeat visits fires (4 qualifying visits, threshold=3)", _test_anomaly5_fires)


# ---------------------------------------------------------------------------
# 17. Anomaly 5: does not fire (3 qualifying visits = threshold, not > threshold)
# ---------------------------------------------------------------------------
def _test_anomaly5_no_fire():
    from src.anomalies import run_anomalies
    events = [
        _dwell(31, "CAM_1", dwell_seconds=15, entry_ts=10),
        _dwell(31, "CAM_1", dwell_seconds=15, entry_ts=40),
        _dwell(31, "CAM_1", dwell_seconds=15, entry_ts=70),
    ]  # 3 visits = threshold (not >) -> no fire
    result = run_anomalies(events, _empty_staff(), cfg)
    repeat = [a for a in result if a["type"] == "repeat_zone_visits"]
    assert not repeat, f"repeat_zone_visits should not fire at exactly threshold; got {repeat}"
    return "track_id=31: 3 visits == threshold 3 (not >) -> no repeat_zone_visits"

check("Anomaly 5: does not fire at exactly the threshold (needs >)", _test_anomaly5_no_fire)


# ---------------------------------------------------------------------------
# 18. Anomaly schema: all required keys present in every emitted anomaly
# ---------------------------------------------------------------------------
def _test_anomaly_schema():
    from src.anomalies import run_anomalies
    events = [
        _dwell(1, "CAM_1", dwell_seconds=1000),                     # Anomaly 1
        _zone_entry(1, "CAM_5", ts=0),
        _zone_entry(2, "CAM_5", ts=1),
        _zone_entry(3, "CAM_5", ts=2),
        _zone_exit(1,  "CAM_5", ts=400),                             # Anomaly 2
        _warehouse(ts=92.3, is_restocking=True),                     # Anomaly 3
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=10),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=40),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=70),
        _dwell(30, "CAM_1", dwell_seconds=15, entry_ts=100),         # Anomaly 5
    ]
    result = run_anomalies(events, _empty_staff(), cfg)
    assert len(result) >= 1, "Expected at least 1 anomaly from test fixtures"
    for i, anomaly in enumerate(result):
        missing = REQUIRED_ANOMALY_KEYS - anomaly.keys()
        assert not missing, f"Anomaly {i} ({anomaly.get('type')}) missing keys: {missing}"
        assert anomaly["severity"] in ("warning", "info"), (
            f"Anomaly {i} severity must be 'warning' or 'info', got {anomaly['severity']!r}"
        )
        assert isinstance(anomaly["triggered_at"], str) and anomaly["triggered_at"], (
            f"Anomaly {i} triggered_at must be a non-empty string"
        )
    return f"{len(result)} anomaly/anomalies checked; all have required keys and valid types"

check("Anomaly schema: all emitted anomalies have required keys and valid types",
      _test_anomaly_schema)


# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("CHECKPOINT 3.5 VALIDATION -- Funnel + Anomaly Detectors")
print("=" * 70)

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")

for status, label, detail in results:
    icon = "v" if status == "PASS" else "X"
    print(f"  [{status}] {icon} {label}")
    if detail:
        d = detail[:120] + "..." if len(detail) > 120 else detail
        print(f"         -> {d}")

print()
print(f"  Result: {passed}/{len(results)} checks passed", end="")
print("  -- ALL PASS" if not failed else f"  ({failed} FAILED)")
print()
if failed == 0:
    print("  Note: run_funnel() and run_anomalies() return warning/[] on current")
    print("  footage due to CAM_3 Q3 Partial Pass and 1000-frame window. This is")
    print("  correct behaviour -- detector logic is verified synthetically above.")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
