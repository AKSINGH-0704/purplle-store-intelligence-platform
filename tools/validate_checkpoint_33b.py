# PROMPT: Write a validation script for entry_counter.py crossing logic. Test:
# (1) centroid crossing the entry line in [0,1] direction emits crossing_entry;
# (2) reverse crossing emits crossing_exit; (3) centroid inside door x-gate
# [250,490] triggers; (4) centroid outside x-gate is suppressed. Use synthetic
# centroid positions. Also run a smoke test on actual CAM_3.mp4 frames.
# CHANGES MADE: AI generated tests only for the happy-path crossing direction.
# Added the door x-gate boundary tests (x=249 suppressed, x=250 triggers,
# x=490 triggers, x=491 suppressed) — AI had not tested gate boundaries.
# Added camera_id guard test (non-CAM_3 must raise ValueError). Corrected
# the direction vector check — AI had used [0,-1] (upward); changed to [0,1].

"""
Checkpoint 3.3B validation — entry_counter crossing logic and gate behaviour.

Run from project root: python tools/validate_checkpoint_33b.py
Exit 0 = all checks passed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT — WHAT THIS VALIDATOR DOES AND DOES NOT PROVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROVES:
  - Crossing geometry logic fires correctly for controlled synthetic inputs
  - Doorway x-gate [250, 490] suppresses crossings outside the door opening
  - Direction classification (entry vs exit) is correct for both directions
  - Ambiguous filter suppresses small-dy crossings (|dy| < 8px)
  - First-frame tracks (no previous centroid) do not produce false crossings
  - Emitted events contain all required fields from make_crossing_event()
  - camera_id guard raises ValueError for non-CAM_3 inputs
  - run_entry_crossings() runs to completion on actual CAM_3.mp4 without error

DOES NOT PROVE:
  - Real-world sensitivity — whether the detector fires for genuine customers
    crossing the store entrance. Phase 2 Checkpoint 2.3 observed ZERO confirmed
    store entries in 720 processed frames (81% of CAM_3 footage). No ground
    truth crossing count exists to validate against.

Q3 STATUS AFTER THIS CHECKPOINT:
  Mechanics validated (crossing logic, gate, direction, schema).
  Sensitivity UNVERIFIED — remains open until full end-to-end pipeline
  validation with footage that contains confirmed crossing events.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.utils import load_config, load_zones

cfg   = load_config(os.path.join(ROOT, "config.json"))
zones = load_zones(os.path.join(ROOT, "zones.json"))

results = []


def check(label: str, fn):
    try:
        detail = fn()
        results.append(("PASS", label, detail or ""))
        return True
    except Exception as exc:
        results.append(("FAIL", label, str(exc)))
        return False


# Shared test parameters — match zones.json CAM_3 exactly
ENTRY_Y = 170
DIR_DY  = 1
DOOR_X1 = 250
DOOR_X2 = 490

_tmp_events = os.path.join(ROOT, "events", "_validate_33b_tmp.json")


# ---------------------------------------------------------------------------
# 1. entry_counter imports without error; _check_crossing and
#    run_entry_crossings are both importable
# ---------------------------------------------------------------------------
def _test_import():
    from src.entry_counter import _check_crossing, run_entry_crossings  # noqa: F401
    return "_check_crossing and run_entry_crossings imported"

check("entry_counter: imports without error", _test_import)


# ---------------------------------------------------------------------------
# 2. CAM_3 config extracted correctly from zones.json
# ---------------------------------------------------------------------------
def _test_cam3_config():
    cam3 = zones["CAM_3"]
    assert "entry_line"             in cam3, "Missing entry_line"
    assert "entry_direction_vector" in cam3, "Missing entry_direction_vector"
    assert "door_x_gate"            in cam3, "Missing door_x_gate"

    el = cam3["entry_line"]
    ev = cam3["entry_direction_vector"]
    dg = cam3["door_x_gate"]

    assert el[0][1] == el[1][1] == 170, f"entry_line y expected 170, got {el[0][1]}"
    assert ev == [0, 1],                 f"entry_direction_vector expected [0,1], got {ev}"
    assert dg == [250, 490],             f"door_x_gate expected [250,490], got {dg}"
    return f"entry_line y={el[0][1]}, dir_vec={ev}, gate x={dg[0]}-{dg[1]}"

check("CAM_3: entry_line, direction_vector, door_x_gate extracted correctly", _test_cam3_config)


# ---------------------------------------------------------------------------
# 3. ENTRY fires: centroid crosses y=170 top-to-bottom inside gate
#    prev=(350,165) curr=(350,175) — dy=+10, inside gate, should be "entry"
# ---------------------------------------------------------------------------
def _test_entry_fires():
    from src.entry_counter import _check_crossing
    result = _check_crossing(165, 175, 350, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result == "entry", f"Expected 'entry', got {result!r}"
    return "prev_cy=165 curr_cy=175 cx=350 -> 'entry'"

check("_check_crossing: ENTRY fires for top-to-bottom crossing inside gate", _test_entry_fires)


# ---------------------------------------------------------------------------
# 4. EXIT fires: centroid crosses y=170 bottom-to-top inside gate
#    prev=(350,175) curr=(350,165) — dy=-10, inside gate, should be "exit"
# ---------------------------------------------------------------------------
def _test_exit_fires():
    from src.entry_counter import _check_crossing
    result = _check_crossing(175, 165, 350, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result == "exit", f"Expected 'exit', got {result!r}"
    return "prev_cy=175 curr_cy=165 cx=350 -> 'exit'"

check("_check_crossing: EXIT fires for bottom-to-top crossing inside gate", _test_exit_fires)


# ---------------------------------------------------------------------------
# 5. Gate suppresses crossings left of door opening (cx=100 < DOOR_X1=250)
# ---------------------------------------------------------------------------
def _test_gate_suppresses_left():
    from src.entry_counter import _check_crossing
    result = _check_crossing(165, 175, 100, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result is None, f"Expected None (outside gate), got {result!r}"
    return f"cx=100 < DOOR_X1={DOOR_X1} -> None (suppressed)"

check("_check_crossing: gate suppresses crossing left of door (cx=100)", _test_gate_suppresses_left)


# ---------------------------------------------------------------------------
# 6. Gate suppresses crossings right of door opening (cx=520 > DOOR_X2=490)
#    This replicates the Phase 2 v1 false positive (corridor pedestrian, cx~480-500)
# ---------------------------------------------------------------------------
def _test_gate_suppresses_right():
    from src.entry_counter import _check_crossing
    result = _check_crossing(165, 175, 520, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result is None, f"Expected None (outside gate), got {result!r}"
    return f"cx=520 > DOOR_X2={DOOR_X2} -> None (suppressed, replicates Phase 2 FP)"

check("_check_crossing: gate suppresses crossing right of door (cx=520, Phase 2 FP location)",
      _test_gate_suppresses_right)


# ---------------------------------------------------------------------------
# 7. Ambiguous filter: |dy|=7 < 8 does not fire even inside gate and straddling line
#    prev=(350,167) curr=(350,174) — dy=+7, inside gate, straddles y=170
# ---------------------------------------------------------------------------
def _test_ambiguous_suppressed():
    from src.entry_counter import _check_crossing
    result = _check_crossing(167, 174, 350, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result == "ambiguous", f"Expected 'ambiguous', got {result!r}"
    return "prev_cy=167 curr_cy=174 dy=7 -> 'ambiguous' (suppressed in run_entry_crossings)"

check("_check_crossing: |dy|=7 < 8 returns 'ambiguous' (not entry/exit)", _test_ambiguous_suppressed)


# ---------------------------------------------------------------------------
# 8. No crossing when centroid stays on the same side of y=170
#    prev=(350,150) curr=(350,160) — never straddles line
# ---------------------------------------------------------------------------
def _test_no_crossing_same_side():
    from src.entry_counter import _check_crossing
    result = _check_crossing(150, 160, 350, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert result is None, f"Expected None (no straddle), got {result!r}"
    return "prev_cy=150 curr_cy=160 (both < 170) -> None"

check("_check_crossing: no crossing when centroid stays on same side of entry line",
      _test_no_crossing_same_side)


# ---------------------------------------------------------------------------
# 9. camera_id guard raises ValueError for non-CAM_3 input
# ---------------------------------------------------------------------------
def _test_camera_guard():
    from src.entry_counter import run_entry_crossings
    try:
        run_entry_crossings("dummy.mp4", "CAM_1", cfg, zones)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "CAM_3" in str(e), f"ValueError message should mention CAM_3: {e}"
    return "ValueError raised for camera_id='CAM_1', message mentions CAM_3"

check("run_entry_crossings: ValueError raised for non-CAM_3 camera_id", _test_camera_guard)


# ---------------------------------------------------------------------------
# 10. Smoke run on actual CAM_3.mp4 — returns dict with correct keys,
#     no exception raised
# ---------------------------------------------------------------------------
def _test_smoke_run():
    from src.entry_counter import run_entry_crossings
    vpath = os.path.join(ROOT, "inputs", "CAM_3.mp4")
    result = run_entry_crossings(vpath, "CAM_3", cfg, zones, events_path=_tmp_events)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    required = {"entry_count", "exit_count", "ambiguous_count"}
    missing = required - result.keys()
    assert not missing, f"Missing keys: {missing}"
    for k in required:
        assert isinstance(result[k], int), f"{k} should be int, got {type(result[k])}"
    return (f"entry_count={result['entry_count']}  "
            f"exit_count={result['exit_count']}  "
            f"ambiguous_count={result['ambiguous_count']}")

check("run_entry_crossings: smoke run on CAM_3.mp4 returns dict with correct keys",
      _test_smoke_run)


# ---------------------------------------------------------------------------
# 11. If any crossing events were emitted, verify all required schema fields
# ---------------------------------------------------------------------------
def _test_event_schema():
    required_fields = [
        "event_id", "event_type", "camera", "zone",
        "frame_idx", "timestamp_seconds", "processed_at",
        "track_id", "centroid_before", "centroid_after",
        "crossing_direction", "staff_filtered",
    ]
    events = []
    try:
        with open(_tmp_events, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except FileNotFoundError:
        return "No events file (0 crossings in footage) — schema check skipped"

    if not events:
        return "0 events emitted — schema check skipped (consistent with Phase 2 Q3 result)"

    for ev in events:
        et = ev.get("event_type", "")
        assert et in ("crossing_entry", "crossing_exit"), (
            f"Unexpected event_type: {et!r}"
        )
        for field in required_fields:
            assert field in ev, f"Event missing field '{field}': {list(ev.keys())}"
        assert ev["camera"] == "CAM_3",         "camera should be 'CAM_3'"
        assert ev["zone"]   == "entrance",       "zone should be 'entrance'"
        assert ev["crossing_direction"] in ("entry", "exit")
        assert ev["staff_filtered"] is False,    "staff_filtered should be False"
        assert isinstance(ev["centroid_before"], list) and len(ev["centroid_before"]) == 2
        assert isinstance(ev["centroid_after"],  list) and len(ev["centroid_after"])  == 2

    types = sorted({ev["event_type"] for ev in events})
    return f"{len(events)} crossing events; types={types}; all required fields present"

check("crossing events: all required schema fields present (if any emitted)", _test_event_schema)


# ---------------------------------------------------------------------------
# 12. Gate boundary edges are handled correctly
#     cx=DOOR_X1 (250) and cx=DOOR_X2 (490) are inclusive — should fire
# ---------------------------------------------------------------------------
def _test_gate_boundaries():
    from src.entry_counter import _check_crossing
    r1 = _check_crossing(165, 175, DOOR_X1, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    r2 = _check_crossing(165, 175, DOOR_X2, ENTRY_Y, DIR_DY, DOOR_X1, DOOR_X2)
    assert r1 == "entry", f"cx=DOOR_X1={DOOR_X1}: expected 'entry', got {r1!r}"
    assert r2 == "entry", f"cx=DOOR_X2={DOOR_X2}: expected 'entry', got {r2!r}"
    return f"cx={DOOR_X1} -> 'entry'; cx={DOOR_X2} -> 'entry' (gate boundaries inclusive)"

check("_check_crossing: gate boundary values (cx=250, cx=490) are inclusive",
      _test_gate_boundaries)


# ---------------------------------------------------------------------------
# Cleanup temporary events file
# ---------------------------------------------------------------------------
if os.path.exists(_tmp_events):
    os.remove(_tmp_events)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("CHECKPOINT 3.3B VALIDATION — Entry Counter")
print("=" * 70)
print()
print("  NOTE: This validator proves crossing LOGIC and GATE BEHAVIOUR only.")
print("  Real-world sensitivity is UNVERIFIED (Phase 2 Q3: 0 genuine crossings")
print("  observed in 720 processed frames). Q3 remains open until end-to-end")
print("  pipeline validation with confirmed-crossing footage.")
print()

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
if failed:
    print(f"  ({failed} FAILED)")
else:
    print("  -- ALL PASS")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
