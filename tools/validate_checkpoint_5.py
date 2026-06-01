"""
Checkpoint 5 validation -- Streamlit dashboard (src/dashboard.py).

Run from project root: python tools/validate_checkpoint_5.py
Exit 0 = all checks passed.

Streamlit apps cannot be deterministically end-to-end tested without a browser
driver. This validator covers structural correctness via source inspection and
py_compile. The definitive test is manual: streamlit run src/dashboard.py.
"""
import os
import py_compile
import sys

ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_PATH = os.path.join(ROOT, "src", "dashboard.py")

results = []


def check(label, fn):
    try:
        detail = fn()
        results.append(("PASS", label, detail or ""))
        return True
    except AssertionError as exc:
        results.append(("FAIL", label, str(exc)))
        return False
    except Exception as exc:
        results.append(("FAIL", label, f"{type(exc).__name__}: {exc}"))
        return False


def _src() -> str:
    with open(DASHBOARD_PATH, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. File exists at src/dashboard.py
# ---------------------------------------------------------------------------
def _test_file_exists():
    assert os.path.isfile(DASHBOARD_PATH), f"Not found: {DASHBOARD_PATH}"
    return "dashboard.py found at src/dashboard.py"

check("dashboard.py exists at src/dashboard.py", _test_file_exists)


# ---------------------------------------------------------------------------
# 2. Valid Python syntax
# ---------------------------------------------------------------------------
def _test_syntax():
    py_compile.compile(DASHBOARD_PATH, doraise=True)
    return "no syntax errors detected"

check("dashboard.py: valid Python syntax", _test_syntax)


# ---------------------------------------------------------------------------
# 3. API_BASE_URL environment variable used
# ---------------------------------------------------------------------------
def _test_api_url():
    src = _src()
    assert 'os.getenv("API_BASE_URL"' in src or "os.getenv('API_BASE_URL'" in src, (
        "API_BASE_URL env var not found"
    )
    return "os.getenv('API_BASE_URL', ...) present"

check("API_BASE_URL environment variable used", _test_api_url)


# ---------------------------------------------------------------------------
# 4. @st.cache_data(ttl=60) caching
# ---------------------------------------------------------------------------
def _test_cache():
    src = _src()
    assert "cache_data(ttl=60)" in src, "@st.cache_data(ttl=60) not found"
    return "@st.cache_data(ttl=60) decorator present"

check("@st.cache_data(ttl=60) caching decorator used", _test_cache)


# ---------------------------------------------------------------------------
# 5-9. All five tab names present
# ---------------------------------------------------------------------------
TAB_NAMES = [
    "Executive Overview",
    "Customer Journey",
    "Zone Intelligence",
    "Revenue Intelligence",
    "System Health",
]
for _tab in TAB_NAMES:
    def _make_tab_check(name):
        def _t():
            assert name in _src(), f"Tab name '{name}' not found in source"
            return f"'{name}' found in source"
        return _t
    check(f"Tab '{_tab}' present in source", _make_tab_check(_tab))


# ---------------------------------------------------------------------------
# 10. Plotly go.Funnel used for customer journey chart
# ---------------------------------------------------------------------------
def _test_plotly_funnel():
    src = _src()
    assert "go.Funnel" in src,           "go.Funnel not found in source"
    assert "plotly.graph_objects" in src, "plotly.graph_objects import not found"
    return "go.Funnel and plotly.graph_objects import present"

check("Plotly go.Funnel used for Customer Journey chart", _test_plotly_funnel)


# ---------------------------------------------------------------------------
# 11. st.warning conditional on funnel_validation == "warning"
# ---------------------------------------------------------------------------
def _test_funnel_warning():
    src = _src()
    assert "funnel_validation" in src, "funnel_validation not referenced"
    assert 'st.warning(' in src,       "st.warning not found"
    assert 'fv == "warning"' in src or "fv == 'warning'" in src, (
        "Conditional check on fv == 'warning' not found"
    )
    return "st.warning() conditional on funnel_validation found"

check("st.warning() shown when funnel_validation == 'warning'", _test_funnel_warning)


# ---------------------------------------------------------------------------
# 12. KPI cards use st.metric
# ---------------------------------------------------------------------------
def _test_metrics():
    src = _src()
    count = src.count("st.metric(")
    assert count >= 10, f"Expected >= 10 st.metric calls, found {count}"
    return f"{count} st.metric() calls (KPI cards confirmed)"

check("st.metric() used for KPI cards (>= 10 calls)", _test_metrics)


# ---------------------------------------------------------------------------
# 13. fetch_dashboard and fetch_health functions defined
# ---------------------------------------------------------------------------
def _test_fetch_fns():
    src = _src()
    assert "def fetch_dashboard" in src, "fetch_dashboard function not found"
    assert "def fetch_health"    in src, "fetch_health function not found"
    assert "fetch_dashboard()"   in src, "fetch_dashboard() not called"
    assert "fetch_health()"      in src, "fetch_health() not called"
    return "fetch_dashboard and fetch_health defined and called"

check("fetch_dashboard() and fetch_health() defined and called", _test_fetch_fns)


# ---------------------------------------------------------------------------
# 14. requests.RequestException handling (graceful API failure)
# ---------------------------------------------------------------------------
def _test_exception_handling():
    src = _src()
    assert "requests.RequestException" in src, (
        "requests.RequestException handler not found -- API failure not handled gracefully"
    )
    return "requests.RequestException exception handler present in fetch functions"

check("requests.RequestException: graceful API failure handling present", _test_exception_handling)


# ---------------------------------------------------------------------------
# 15. st.error() fallback present for API unavailability
# ---------------------------------------------------------------------------
def _test_error_fallback():
    src = _src()
    assert "st.error(" in src, "st.error() fallback not found"
    return "st.error() fallback present for API unavailability"

check("st.error() fallback present for API unavailability", _test_error_fallback)


# ---------------------------------------------------------------------------
# 16. st.stop() prevents partial render after API failure
# ---------------------------------------------------------------------------
def _test_stop():
    src = _src()
    assert "st.stop()" in src, "st.stop() not found -- partial render on API failure not prevented"
    return "st.stop() prevents partial render after API error"

check("st.stop() prevents partial render after st.error()", _test_stop)


# ---------------------------------------------------------------------------
# 17. /dashboard single data source (not multiple routes for main data)
# ---------------------------------------------------------------------------
def _test_single_source():
    src = _src()
    assert "def fetch_dashboard" in src
    assert "/dashboard" in src, '"/dashboard" route not found'
    assert "/health"    in src, '"/health" route not found'
    # Confirm data is unpacked from a single fetch_dashboard() call at top level
    assert "data   = fetch_dashboard()" in src or "data = fetch_dashboard()" in src, (
        "fetch_dashboard() not assigned to 'data' at top level"
    )
    return "fetch_dashboard() used as single data source; /dashboard and /health routes present"

check("Single fetch_dashboard() call supplies data for all tabs", _test_single_source)


# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("CHECKPOINT 5 VALIDATION -- Streamlit Dashboard")
print("=" * 70)
print()
print("  NOTE: Structural validation only. Definitive test is manual:")
print("        1. uvicorn src.api:app --port 8000")
print("        2. streamlit run src/dashboard.py")
print("        3. Verify all 5 tabs render with correct data.")
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
print("  -- ALL PASS" if not failed else f"  ({failed} FAILED)")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
