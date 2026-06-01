"""
Checkpoint 6 validation -- Docker configuration correctness.

Checks file existence, content correctness, and structural requirements
without running Docker. Exits 0 on all pass, 1 on any failure.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = []
FAIL = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(f"  FAIL  {label}{': ' + detail if detail else ''}")


def read(relpath: str) -> str:
    path = os.path.join(ROOT, relpath)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── File existence ─────────────────────────────────────────────────────────────
print("\n[1] File existence")
for fname in [
    ".dockerignore",
    "requirements-api.txt",
    "requirements-dashboard.txt",
    "Dockerfile.api",
    "Dockerfile.dashboard",
    "docker-compose.yml",
    "tools/validate_checkpoint_6.py",
]:
    check(f"exists: {fname}", os.path.exists(os.path.join(ROOT, fname)))


# ── .dockerignore ──────────────────────────────────────────────────────────────
print("\n[2] .dockerignore")
di = read(".dockerignore")
check("dockerignore: inputs/ excluded", "inputs/" in di)
check("dockerignore: .git/ excluded", ".git/" in di)
check("dockerignore: __pycache__ excluded", "__pycache__" in di)
check("dockerignore: .env excluded", ".env" in di)


# ── requirements-api.txt ───────────────────────────────────────────────────────
print("\n[3] requirements-api.txt")
api_req = read("requirements-api.txt")
check("api-req: fastapi present", "fastapi" in api_req)
check("api-req: uvicorn present", "uvicorn" in api_req)
check("api-req: no streamlit (lean image)", "streamlit" not in api_req)
check("api-req: no ultralytics (not needed for serving)", "ultralytics" not in api_req)
check("api-req: no opencv (not needed for serving)", "opencv" not in api_req)


# ── requirements-dashboard.txt ─────────────────────────────────────────────────
print("\n[4] requirements-dashboard.txt")
dash_req = read("requirements-dashboard.txt")
check("dash-req: streamlit present", "streamlit" in dash_req)
check("dash-req: plotly present", "plotly" in dash_req)
check("dash-req: pandas present", "pandas" in dash_req)
check("dash-req: requests present", "requests" in dash_req)
check("dash-req: no fastapi (not needed in UI layer)", "fastapi" not in dash_req)
check("dash-req: no ultralytics", "ultralytics" not in dash_req)


# ── Dockerfile.api ─────────────────────────────────────────────────────────────
print("\n[5] Dockerfile.api")
dapi = read("Dockerfile.api")
check("Dockerfile.api: python:3.11-slim base", "python:3.11-slim" in dapi)
check("Dockerfile.api: WORKDIR /app", "WORKDIR /app" in dapi)
check("Dockerfile.api: copies requirements-api.txt", "requirements-api.txt" in dapi)
check("Dockerfile.api: copies src/", "COPY src/" in dapi)
check("Dockerfile.api: exposes 8000", "8000" in dapi)
check("Dockerfile.api: uvicorn CMD", "uvicorn" in dapi and "src.api:app" in dapi)
check("Dockerfile.api: binds to 0.0.0.0", "0.0.0.0" in dapi)
check("Dockerfile.api: no inputs/ copy", "COPY inputs" not in dapi)


# ── Dockerfile.dashboard ───────────────────────────────────────────────────────
print("\n[6] Dockerfile.dashboard")
ddash = read("Dockerfile.dashboard")
check("Dockerfile.dashboard: python:3.11-slim base", "python:3.11-slim" in ddash)
check("Dockerfile.dashboard: WORKDIR /app", "WORKDIR /app" in ddash)
check("Dockerfile.dashboard: copies requirements-dashboard.txt", "requirements-dashboard.txt" in ddash)
check("Dockerfile.dashboard: copies dashboard.py", "dashboard.py" in ddash)
check("Dockerfile.dashboard: exposes 8501", "8501" in ddash)
check("Dockerfile.dashboard: streamlit run CMD", "streamlit" in ddash and "run" in ddash)
check("Dockerfile.dashboard: headless mode", "headless" in ddash)
check("Dockerfile.dashboard: binds to 0.0.0.0", "0.0.0.0" in ddash)


# ── docker-compose.yml ─────────────────────────────────────────────────────────
print("\n[7] docker-compose.yml")
dc = read("docker-compose.yml")
check("compose: api service defined", "api:" in dc)
check("compose: dashboard service defined", "dashboard:" in dc)
check("compose: API_BASE_URL=http://api:8000", "API_BASE_URL=http://api:8000" in dc)
check("compose: depends_on api", "depends_on" in dc)
check("compose: service_healthy condition", "service_healthy" in dc)
check("compose: api healthcheck defined", "healthcheck" in dc)
check("compose: api port 8000 exposed", "8000:8000" in dc)
check("compose: dashboard port 8501 exposed", "8501:8501" in dc)
check("compose: events volume mount", "events" in dc)
check("compose: Dockerfile.api referenced", "Dockerfile.api" in dc)
check("compose: Dockerfile.dashboard referenced", "Dockerfile.dashboard" in dc)
check("compose: no GPU config", "runtime: nvidia" not in dc and "deploy:" not in dc)


# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\n{'='*52}")
print(f"  PASSED: {len(PASS)}/{len(PASS)+len(FAIL)}")
if FAIL:
    print(f"  FAILED: {len(FAIL)}")
    for f in FAIL:
        print(f"    - {f}")
    print()
    sys.exit(1)
else:
    print("  All checks passed.")
    print()
    sys.exit(0)
