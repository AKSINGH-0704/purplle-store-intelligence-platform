"""
Checkpoint 3.4 validation — staff_filter and csv_analytics.

Run from project root: python tools/validate_checkpoint_34.py
Exit 0 = all checks passed.

Staff filter tests use synthetic event lists only (no video required).
CSV analytics tests run against the actual data/Brigade_Bangalore_10_April_26.csv.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.utils import load_config

cfg      = load_config(os.path.join(ROOT, "config.json"))
CSV_PATH = os.path.join(ROOT, "data", "Brigade_Bangalore_10_April_26.csv")

results = []


def check(label: str, fn):
    try:
        detail = fn()
        results.append(("PASS", label, detail or ""))
        return True
    except Exception as exc:
        results.append(("FAIL", label, str(exc)))
        return False


# ── Synthetic event builders ──────────────────────────────────────────────────

def _crossing(track_id, direction, ts, camera="CAM_3"):
    return {
        "event_type":        f"crossing_{direction}",
        "camera":            camera,
        "zone":              "entrance",
        "track_id":          track_id,
        "timestamp_seconds": float(ts),
        "crossing_direction": direction,
    }


def _dwell(track_id, entry_ts, camera="CAM_5"):
    return {
        "event_type":               "zone_dwell",
        "camera":                   camera,
        "track_id":                 track_id,
        "timestamp_entry_seconds":  float(entry_ts),
        "dwell_seconds":            30.0,
    }


# Cache csv result — run once, reuse across checks
_csv_result: dict = {}


def _get_csv():
    if not _csv_result:
        from src.csv_analytics import run_csv_analytics
        _csv_result.update(run_csv_analytics(CSV_PATH))
    return _csv_result


# ---------------------------------------------------------------------------
# 1. Both modules import without error
# ---------------------------------------------------------------------------
def _test_import():
    from src.staff_filter  import run_staff_filter   # noqa: F401
    from src.csv_analytics import run_csv_analytics  # noqa: F401
    return "run_staff_filter and run_csv_analytics imported"

check("staff_filter + csv_analytics: imports without error", _test_import)


# ---------------------------------------------------------------------------
# 2. staff_filter_enabled=False -> empty frozensets, count=0
# ---------------------------------------------------------------------------
def _test_disabled():
    from src.staff_filter import run_staff_filter
    result = run_staff_filter([], {**cfg, "staff_filter_enabled": False})
    assert result["staff_filter_enabled"]  is False
    assert result["staff_filtered_count"]  == 0
    assert result["staff_track_ids"]["CAM_3"] == frozenset()
    assert result["staff_track_ids"]["CAM_5"] == frozenset()
    return "staff_filter_enabled=False -> all empty, count=0"

check("staff_filter: disabled flag returns empty classification", _test_disabled)


# ---------------------------------------------------------------------------
# 3. Rule 1: 4 crossings (2 entry, 2 exit) within window -> classified as staff
#    staff_roundtrip_threshold=3; 4 > 3, both directions present -> staff
# ---------------------------------------------------------------------------
def _test_rule1_fires():
    from src.staff_filter import run_staff_filter
    events = [
        _crossing(99, "entry",  100),
        _crossing(99, "exit",   200),
        _crossing(99, "entry",  300),
        _crossing(99, "exit",   400),
    ]
    result = run_staff_filter(events, cfg)
    assert 99 in result["staff_track_ids"]["CAM_3"], (
        f"track_id=99 should be staff; got {result['staff_track_ids']['CAM_3']}"
    )
    assert result["staff_filtered_count"] == 4
    return "track_id=99: 4 crossings, both directions -> CAM_3 staff; filtered_count=4"

check("staff_filter Rule 1: track with 4 roundtrip crossings classified as staff",
      _test_rule1_fires)


# ---------------------------------------------------------------------------
# 4. Rule 1: entry-only track (no exit) -> NOT classified
#    Missing exit direction means single-direction ≠ roundtrip
# ---------------------------------------------------------------------------
def _test_rule1_no_exit():
    from src.staff_filter import run_staff_filter
    events = [
        _crossing(88, "entry", 100),
        _crossing(88, "entry", 200),
        _crossing(88, "entry", 300),
        _crossing(88, "entry", 400),
    ]
    result = run_staff_filter(events, cfg)
    assert 88 not in result["staff_track_ids"]["CAM_3"], (
        "track_id=88 (entry-only) should NOT be classified as staff"
    )
    return "track_id=88: 4 entries, no exit -> not classified (both directions required)"

check("staff_filter Rule 1: entry-only track (no exit) not classified as staff",
      _test_rule1_no_exit)


# ---------------------------------------------------------------------------
# 5. Rule 2: CAM_5 zone_dwell at entry_ts=1.0s < 3.0s threshold -> staff_cam5
# ---------------------------------------------------------------------------
def _test_rule2_fires():
    from src.staff_filter import run_staff_filter
    events = [_dwell(track_id=7, entry_ts=1.0, camera="CAM_5")]
    result = run_staff_filter(events, cfg)
    assert 7 in result["staff_track_ids"]["CAM_5"], (
        f"track_id=7 (entry_ts=1.0s) should be CAM_5 staff"
    )
    return "CAM_5 track_id=7 entry_ts=1.0s < 3.0s -> classified as billing staff"

check("staff_filter Rule 2: billing track at t=1.0s classified as staff",
      _test_rule2_fires)


# ---------------------------------------------------------------------------
# 6. Rule 2: CAM_5 zone_dwell at entry_ts=10.0s > 3.0s threshold -> NOT staff
# ---------------------------------------------------------------------------
def _test_rule2_no_fire():
    from src.staff_filter import run_staff_filter
    events = [_dwell(track_id=8, entry_ts=10.0, camera="CAM_5")]
    result = run_staff_filter(events, cfg)
    assert 8 not in result["staff_track_ids"]["CAM_5"], (
        "track_id=8 (entry_ts=10.0s) should NOT be classified as staff"
    )
    return "CAM_5 track_id=8 entry_ts=10.0s > 3.0s -> not classified"

check("staff_filter Rule 2: billing track at t=10.0s not classified as staff",
      _test_rule2_no_fire)


# ---------------------------------------------------------------------------
# 7. Rule 3: CAM_3 crossing at t=1.5s < 3.0s threshold -> staff_cam3
# ---------------------------------------------------------------------------
def _test_rule3_fires():
    from src.staff_filter import run_staff_filter
    events = [_crossing(track_id=5, direction="entry", ts=1.5)]
    result = run_staff_filter(events, cfg)
    assert 5 in result["staff_track_ids"]["CAM_3"], (
        f"track_id=5 (ts=1.5s) should be CAM_3 staff"
    )
    return "CAM_3 track_id=5 ts=1.5s < 3.0s -> classified as entrance staff"

check("staff_filter Rule 3: CAM_3 crossing at t=1.5s classified as staff",
      _test_rule3_fires)


# ---------------------------------------------------------------------------
# 8. Output schema: all required keys present, correct types
# ---------------------------------------------------------------------------
def _test_schema():
    from src.staff_filter import run_staff_filter
    result = run_staff_filter([], cfg)
    required = {"staff_track_ids", "staff_filtered_count", "staff_filter_enabled"}
    missing = required - result.keys()
    assert not missing, f"Missing keys: {missing}"
    assert isinstance(result["staff_track_ids"]["CAM_3"], frozenset)
    assert isinstance(result["staff_track_ids"]["CAM_5"], frozenset)
    assert isinstance(result["staff_filtered_count"], int)
    assert isinstance(result["staff_filter_enabled"], bool)
    return "all required keys present; frozenset, int, bool types confirmed"

check("staff_filter: output schema has all required keys and correct types",
      _test_schema)


# ---------------------------------------------------------------------------
# 9. csv_analytics: returns dict with all required keys
# ---------------------------------------------------------------------------
REQUIRED_CSV_KEYS = {
    "source", "transactions", "gmv", "nmv",
    "top_categories", "category_distribution", "avg_basket_depth",
    "salesperson_performance", "brand_split",
    "promotion_effectiveness", "hourly_revenue",
}

def _test_csv_keys():
    result = _get_csv()
    missing = REQUIRED_CSV_KEYS - result.keys()
    assert not missing, f"Missing keys: {missing}"
    return f"all {len(REQUIRED_CSV_KEYS)} required keys present"

check("csv_analytics: returns dict with all required keys", _test_csv_keys)


# ---------------------------------------------------------------------------
# 10. csv_analytics: transactions==24 (verified from CSV profile),
#     gmv/nmv/avg_basket_depth positive
# ---------------------------------------------------------------------------
def _test_csv_core_metrics():
    result = _get_csv()
    assert result["transactions"] == 24, (
        f"Expected 24 unique orders, got {result['transactions']}"
    )
    assert result["gmv"]             > 0, "GMV should be positive"
    assert result["nmv"]             > 0, "NMV should be positive"
    assert result["avg_basket_depth"] > 0, "avg_basket_depth should be positive"
    return (f"transactions=24  gmv={result['gmv']:.2f}  "
            f"nmv={result['nmv']:.2f}  avg_basket_depth={result['avg_basket_depth']:.2f}")

check("csv_analytics: transactions==24, gmv/nmv/avg_basket_depth positive",
      _test_csv_core_metrics)


# ---------------------------------------------------------------------------
# 11. csv_analytics: brand_split sums to ~100%
# ---------------------------------------------------------------------------
def _test_csv_brand_split():
    result = _get_csv()
    bs    = result["brand_split"]
    assert "private_brand_gmv_pct"  in bs, "Missing private_brand_gmv_pct"
    assert "external_brand_gmv_pct" in bs, "Missing external_brand_gmv_pct"
    total = bs["private_brand_gmv_pct"] + bs["external_brand_gmv_pct"]
    assert abs(total - 100.0) < 0.11, f"brand_split sum={total:.2f}, expected ~100.0"
    return (f"private={bs['private_brand_gmv_pct']:.1f}%  "
            f"external={bs['external_brand_gmv_pct']:.1f}%  sum={total:.2f}%")

check("csv_analytics: brand_split sums to ~100%", _test_csv_brand_split)


# ---------------------------------------------------------------------------
# 12. csv_analytics: hourly_revenue keys are valid 2-digit hour strings,
#     all values non-negative
# ---------------------------------------------------------------------------
def _test_csv_hourly():
    result = _get_csv()
    hr = result["hourly_revenue"]
    assert isinstance(hr, dict) and len(hr) > 0, "hourly_revenue should be non-empty dict"
    for k, v in hr.items():
        assert isinstance(k, str) and len(k) == 2 and k.isdigit(), (
            f"Hour key should be 2-digit string, got {k!r}"
        )
        assert 0 <= int(k) <= 23, f"Hour out of range: {k}"
        assert v >= 0,            f"Revenue should be non-negative, got {v}"
    return f"{len(hr)} hours with revenue: keys={sorted(hr.keys())}"

check("csv_analytics: hourly_revenue keys are valid 2-digit hour strings",
      _test_csv_hourly)


# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("CHECKPOINT 3.4 VALIDATION — Staff Filter + CSV Analytics")
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
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
