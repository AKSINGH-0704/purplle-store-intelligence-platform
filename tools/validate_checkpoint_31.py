"""
Checkpoint 3.1 validation — foundation layer smoke test.

Run from project root:
    python tools/validate_checkpoint_31.py

Exit 0 = all checks passed.
Exit 1 = one or more checks failed.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

results = []


def check(label: str, fn):
    try:
        detail = fn()
        results.append(("PASS", label, detail or ""))
        return True
    except Exception as exc:
        results.append(("FAIL", label, str(exc)))
        return False


# ---------------------------------------------------------------------------
# 1. Config loading
# ---------------------------------------------------------------------------
def _test_config():
    from src.utils import load_config
    cfg = load_config(os.path.join(ROOT, "config.json"))
    assert cfg["warehouse_motion_threshold"] > 0, (
        f"warehouse_motion_threshold must be positive, got {cfg['warehouse_motion_threshold']}"
    )
    assert cfg["frame_skip"] == 5
    assert cfg["confidence_threshold"] == 0.5
    assert len(cfg) >= 15, "Fewer keys than expected in config"
    return (
        f"warehouse_motion_threshold={cfg['warehouse_motion_threshold']}, "
        f"frame_skip={cfg['frame_skip']}, "
        f"confidence_threshold={cfg['confidence_threshold']}"
    )

check("config.json loads; all required keys present; warehouse_motion_threshold>0", _test_config)


# ---------------------------------------------------------------------------
# 2. Zones loading
# ---------------------------------------------------------------------------
def _test_zones():
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    for cam in ("CAM_1", "CAM_2", "CAM_3", "CAM_4", "CAM_5"):
        assert cam in zones, f"{cam} missing from zones.json"
    assert zones["CAM_4"]["zone"] == "warehouse"
    assert zones["CAM_1"]["zone"] == "skincare"
    return f"{len(zones)} cameras loaded: {', '.join(sorted(zones.keys()))}"

check("zones.json loads; all 5 cameras present", _test_zones)


# ---------------------------------------------------------------------------
# 3. CAM_3 door_x_gate
# ---------------------------------------------------------------------------
def _test_door_x_gate():
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    gate = zones["CAM_3"].get("door_x_gate")
    assert gate is not None, "door_x_gate key absent from CAM_3"
    assert gate == [250, 490], f"Expected [250, 490], got {gate}"
    return f"CAM_3 door_x_gate={gate}"

check("CAM_3 door_x_gate=[250, 490] present and correct", _test_door_x_gate)


# ---------------------------------------------------------------------------
# 4. Event schema — serialisation / deserialisation round-trip
# ---------------------------------------------------------------------------
def _test_event_schema():
    from src.utils import (
        make_zone_dwell_event, make_crossing_event,
        make_warehouse_motion_event, make_zone_entry_event,
        make_zone_exit_event, make_queue_alert_event,
    )
    events = [
        make_zone_dwell_event(
            "CAM_1", "skincare", 7, [100, 80, 160, 200], [130, 140],
            0.82, 33.4, 100, 300, 3.34, 36.74, False,
        ),
        make_crossing_event(
            "CAM_3", 12, [320, 165], [320, 175], 210, 35.0, "entry",
        ),
        make_crossing_event(
            "CAM_3", 12, [320, 175], [320, 165], 890, 89.0, "exit",
        ),
        make_warehouse_motion_event("CAM_4", 718, 23.96, 2340.5, False),
        make_zone_entry_event("CAM_2", "main_floor", 3, [200, 200], 50, 1.67),
        make_zone_exit_event("CAM_2", "main_floor", 3, [200, 200], 350, 11.68),
        make_queue_alert_event("CAM_5", "billing", 600, 20.0, 3, 305.0),
    ]
    for ev in events:
        # Must serialise to JSON
        serialised = json.dumps(ev)
        # Must deserialise back correctly
        recovered = json.loads(serialised)
        assert recovered["event_type"] == ev["event_type"], (
            f"event_type mismatch after round-trip: {recovered['event_type']}"
        )
        assert "event_id" in recovered, "event_id missing from envelope"
        assert "processed_at" in recovered, "processed_at missing from envelope"
        assert "camera" in recovered, "camera missing from envelope"
    # Validate crossing_direction guard
    try:
        make_crossing_event("CAM_3", 0, [0,0], [0,0], 0, 0.0, "sideways")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    types = [e["event_type"] for e in events]
    return f"{len(events)} event types: {', '.join(types)}"

check("Event schema: all 6 types serialise/deserialise; common envelope correct", _test_event_schema)


# ---------------------------------------------------------------------------
# 5. Event writer
# ---------------------------------------------------------------------------
def _test_event_writer():
    from src.utils import append_event, make_zone_dwell_event
    tmp_path = os.path.join(ROOT, "events", "_validate_31_tmp.json")
    ev1 = make_zone_dwell_event(
        "CAM_2", "main_floor", 1, [0,0,1,1], [0,0],
        0.9, 15.0, 0, 90, 0.0, 15.0, False,
    )
    ev2 = make_warehouse_motion_event = __import__(
        "src.utils", fromlist=["make_warehouse_motion_event"]
    ).make_warehouse_motion_event("CAM_4", 0, 0.0, 1800.0)
    try:
        append_event(ev1, path=tmp_path)
        append_event(ev2, path=tmp_path)
        with open(tmp_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2, f"Expected 2 NDJSON lines, got {len(lines)}"
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        assert r1["event_type"] == "zone_dwell"
        assert r2["event_type"] == "warehouse_motion"
        assert r1["camera"] == "CAM_2"
        assert r2["camera"] == "CAM_4"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return "2 events written as NDJSON lines; both read back correctly"

check("Event writer: append_event writes NDJSON; multi-event file correct", _test_event_writer)


# ---------------------------------------------------------------------------
# 6 + 7. Zone classifier — inside and outside polygon
# ---------------------------------------------------------------------------
def _test_zone_inside():
    from src.zone_classifier import classify_zone
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    # CAM_1 polygon: x=20-620, y=80-350
    r = classify_zone("CAM_1", (320, 200), zones)
    assert r == "skincare", f"Expected 'skincare', got {r!r}"
    r2 = classify_zone("CAM_2", (300, 200), zones)
    assert r2 == "main_floor", f"Expected 'main_floor', got {r2!r}"
    r3 = classify_zone("CAM_4", (300, 200), zones)
    assert r3 == "warehouse", f"Expected 'warehouse', got {r3!r}"
    return f"CAM_1(320,200)->'{r}', CAM_2(300,200)->'{r2}', CAM_4(300,200)->'{r3}'"

check("Zone classifier: centroids inside polygons return correct zone names", _test_zone_inside)


def _test_zone_outside():
    from src.zone_classifier import classify_zone
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    # CAM_1 polygon starts at y=80 — point at y=5 is above/outside
    r = classify_zone("CAM_1", (5, 5), zones)
    assert r is None, f"Expected None, got {r!r}"
    # CAM_5 polygon x=10-420 — point at x=500 is outside
    r2 = classify_zone("CAM_5", (500, 200), zones)
    assert r2 is None, f"Expected None (outside CAM_5 x boundary), got {r2!r}"
    return f"CAM_1(5,5)->None, CAM_5(500,200)->None"

check("Zone classifier: centroids outside polygons return None", _test_zone_outside)


def _test_zone_cam5_boundary():
    from src.zone_classifier import classify_zone
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    # CAM_5 polygon: x=10-420, y=60-355; right side deliberately excluded
    inside = classify_zone("CAM_5", (200, 200), zones)
    outside = classify_zone("CAM_5", (500, 200), zones)
    assert inside == "billing", f"Expected 'billing', got {inside!r}"
    assert outside is None, f"Expected None, got {outside!r}"
    return f"CAM_5: (200,200)->'billing', (500,200)->None (x>420 excluded)"

check("Zone classifier: CAM_5 partial polygon boundary enforced correctly", _test_zone_cam5_boundary)


def _test_zone_invalid_camera():
    from src.zone_classifier import classify_zone
    from src.utils import load_zones
    zones = load_zones(os.path.join(ROOT, "zones.json"))
    try:
        classify_zone("CAM_99", (0, 0), zones)
        assert False, "Should have raised ValueError for unknown camera"
    except ValueError as e:
        assert "CAM_99" in str(e)
    return "ValueError raised with informative message for unknown camera"

check("Zone classifier: unknown camera_id raises ValueError", _test_zone_invalid_camera)


# ---------------------------------------------------------------------------
# 9. Structured logging
# ---------------------------------------------------------------------------
def _test_logging():
    from src.utils import get_logger, LOG_BUFFER
    pre_len = len(LOG_BUFFER)
    log = get_logger("validate_31_test")
    log.info("Checkpoint 3.1 logging test - structured JSON")
    log.warning("Sample warning entry")
    assert len(LOG_BUFFER) >= pre_len + 2, (
        f"LOG_BUFFER grew by {len(LOG_BUFFER) - pre_len}, expected >= 2"
    )
    latest = LOG_BUFFER[-1]
    for field in ("timestamp", "level", "module", "message"):
        assert field in latest, f"Field '{field}' missing from log entry"
    assert latest["level"] == "WARNING"
    # Entries must be JSON-serialisable
    json.dumps(list(LOG_BUFFER))
    return (
        f"LOG_BUFFER has {len(LOG_BUFFER)} entries; "
        f"latest={{level={latest['level']!r}, module={latest['module']!r}}}"
    )

check("Structured logging: JSON entries in LOG_BUFFER; all required fields present", _test_logging)


# ---------------------------------------------------------------------------
# 10. SHA256 integrity — compute + determinism
# ---------------------------------------------------------------------------
def _test_sha256():
    from src.utils import compute_sha256
    cfg_path = os.path.join(ROOT, "config.json")
    h1 = compute_sha256(cfg_path)
    h2 = compute_sha256(cfg_path)
    assert len(h1) == 64, f"Expected 64-char hex digest, got {len(h1)}"
    assert h1 == h2, "SHA256 is not deterministic across two calls"
    assert all(c in "0123456789abcdef" for c in h1), "Digest contains non-hex chars"
    return f"config.json -> {h1[:16]}... (deterministic, 64-char hex)"

check("SHA256: compute_sha256 deterministic 64-char lowercase hex digest", _test_sha256)


# ---------------------------------------------------------------------------
# 11. write_hashes + verify_hashes integrity round-trip
# ---------------------------------------------------------------------------
def _test_hash_integrity():
    from src.utils import write_hashes, verify_hashes
    inputs_dir = os.path.join(ROOT, "inputs")
    paths = {
        "config":  os.path.join(ROOT, "config.json"),
        "zones":   os.path.join(ROOT, "zones.json"),
        "CAM_1":   os.path.join(inputs_dir, "CAM_1.mp4"),
        "CAM_2":   os.path.join(inputs_dir, "CAM_2.mp4"),
        "CAM_3":   os.path.join(inputs_dir, "CAM_3.mp4"),
        "CAM_4":   os.path.join(inputs_dir, "CAM_4.mp4"),
        "CAM_5":   os.path.join(inputs_dir, "CAM_5.mp4"),
    }
    tmp_out = os.path.join(ROOT, "events", "_validate_hashes_tmp.json")
    try:
        hashes = write_hashes(paths, output_path=tmp_out)
        # Verify all expected keys are written
        for key in paths:
            assert key in hashes, f"Key {key!r} missing from written hashes"
        # Round-trip: verify_hashes should find zero mismatches for present files
        present_paths = {k: v for k, v in paths.items() if os.path.exists(v)}
        mismatches = verify_hashes(tmp_out, present_paths)
        assert mismatches == [], f"Hash mismatches detected: {mismatches}"
        # Summarise video coverage
        video_keys = ["CAM_1", "CAM_2", "CAM_3", "CAM_4", "CAM_5"]
        found = [k for k in video_keys if isinstance(hashes.get(k), str)]
        missing = [k for k in video_keys if isinstance(hashes.get(k), dict)]
    finally:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
    note = f"{len(found)}/5 videos hashed" if found else "no videos found"
    if missing:
        note += f"; {len(missing)} gracefully skipped (not_found)"
    return f"config + zones verified; {note}"

check("Integrity: write_hashes + verify_hashes round-trip; videos handled correctly", _test_hash_integrity)


# ---------------------------------------------------------------------------
# 12. format_duration helper
# ---------------------------------------------------------------------------
def _test_format_duration():
    from src.utils import format_duration
    cases = [
        (0,     "0s"),
        (59,    "59s"),
        (60,    "1m 0s"),
        (90,    "1m 30s"),
        (3600,  "1h 0m 0s"),
        (8072,  "2h 14m 32s"),
    ]
    for seconds, expected in cases:
        got = format_duration(seconds)
        assert got == expected, f"format_duration({seconds}) -> {got!r}, expected {expected!r}"
    return f"{len(cases)} cases correct"

check("format_duration: correct output for 0s / sub-minute / hours+minutes+seconds", _test_format_duration)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("CHECKPOINT 3.1 VALIDATION - Foundation Layer")
print("=" * 70)

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")

for status, label, detail in results:
    icon = "v" if status == "PASS" else "X"
    print(f"  [{status}] {icon} {label}")
    if detail:
        detail_str = detail[:120] + "..." if len(detail) > 120 else detail
        print(f"         -> {detail_str}")

print()
print(f"  Result: {passed}/{len(results)} checks passed", end="")
if failed:
    print(f"  ({failed} FAILED)")
else:
    print("  -- ALL PASS")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
