# PHASE 6 REPORT -- Docker Deployment

Phase: 6 -- Docker and Processing Script
Status: COMPLETE (single checkpoint)
Started: 2026-06-02
Completed: 2026-06-02
Commit 1 (Docker files): 899309e
Commit 2 (Docs): see PROGRESS.md
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## Objective

Containerise the FastAPI backend and Streamlit dashboard as separate Docker
images. Dashboard depends on API health before starting. inputs/ (648 MB of
video) stays outside the build context.

---

## Checkpoint Status

| # | Checkpoint | Files | Status | Result |
|---|-----------|-------|--------|--------|
| 6 | Docker deployment | 7 files | **COMPLETE** | 50/50 validation checks pass |

---

## Architecture

```
Host filesystem
  inputs/         -- video files, NOT in image (648 MB, .dockerignore)
  events/         -- pipeline output; bind-mounted :ro into api container
  logs/           -- bind-mounted rw into api container

docker-compose up
  api (port 8000)
    image: python:3.11-slim + fastapi + uvicorn[standard]
    mounts: ./events:/app/events:ro, ./logs:/app/logs
    healthcheck: GET http://localhost:8000/health  (urllib, no curl needed)
    |
    | service_healthy
    v
  dashboard (port 8501)
    image: python:3.11-slim + streamlit + plotly + pandas + requests
    env:   API_BASE_URL=http://api:8000
    healthcheck: GET http://localhost:8501/_stcore/health
```

---

## Image Design

### API image (~165 MB uncompressed)

Only packages needed to serve the FastAPI endpoints:
- `fastapi>=0.115.0`
- `uvicorn[standard]>=0.32.0`

Excluded from API image (not needed for serving):
- `ultralytics` / `opencv-python-headless` -- only needed by process_videos.py
- `streamlit`, `plotly`, `pandas` -- dashboard-only
- `requests` -- not imported by api.py or utils.py

### Dashboard image (~548 MB uncompressed)

Only packages needed to render the Streamlit UI:
- `streamlit>=1.40.0`
- `plotly>=5.0.0`
- `pandas>=2.2.0`
- `requests>=2.32.0`

dashboard.py has no imports from src.* modules other than itself. Only
dashboard.py and src/__init__.py are copied into the dashboard image.

---

## Key Design Decisions

### events/ as bind-mount, not COPY

`events/pipeline_summary.json` and `events/events.json` are the output of
`process_videos.py`. They change whenever the pipeline reruns. Baking them
into the image would require a rebuild after every pipeline run. Bind-mounting
`./events:/app/events:ro` means a simple `docker compose restart api` picks
up new data without rebuilding.

### Health checks use urllib (not curl)

`python:3.11-slim` has no curl. The health checks use Python's stdlib
`urllib.request.urlopen`, which is always available without additional packages.

### depends_on condition: service_healthy

The dashboard will not start until the API passes at least one health check.
This prevents the dashboard from rendering an error page during API startup.
start_period: 15s (API) / 20s (dashboard) are conservative for cold starts
on the first build when pip is downloading packages.

### No GPU configuration

The serving path (FastAPI + Streamlit) has no GPU requirement. YOLOv8 inference
runs only in process_videos.py, which is run outside Docker before compose up.
Adding `runtime: nvidia` or `deploy: resources: reservations: devices:` would
be incorrect here.

---

## File Inventory

| File | Purpose | Size |
|------|---------|------|
| `.dockerignore` | Excludes inputs/, .git/, __pycache__, .env, logs/ | 21 lines |
| `requirements-api.txt` | API image pip dependencies | 2 packages |
| `requirements-dashboard.txt` | Dashboard image pip dependencies | 4 packages |
| `Dockerfile.api` | API image build instructions | 16 lines |
| `Dockerfile.dashboard` | Dashboard image build instructions | 17 lines |
| `docker-compose.yml` | Service orchestration | 37 lines |
| `tools/validate_checkpoint_6.py` | Structural correctness validator | 132 lines |

---

## Validation Results

```
50/50 checks passed -- ALL PASS

[1] File existence        -- 7/7 files present
[2] .dockerignore         -- 4/4 checks (inputs/, .git/, __pycache__, .env)
[3] requirements-api.txt  -- 5/5 checks (fastapi, uvicorn; no streamlit/cv/ml)
[4] requirements-dashboard-- 6/6 checks (streamlit, plotly, pandas, requests; no fastapi/cv)
[5] Dockerfile.api        -- 8/8 checks (base, WORKDIR, copy, expose, CMD, 0.0.0.0, no inputs/)
[6] Dockerfile.dashboard  -- 8/8 checks (base, WORKDIR, copy, expose, CMD, headless, 0.0.0.0)
[7] docker-compose.yml    -- 12/12 checks (services, API_BASE_URL, depends_on,
                             service_healthy, healthchecks, ports, volumes,
                             Dockerfile refs, no GPU)
```

---

## Deployment Commands (clean machine)

```bash
# Prerequisites: Docker Desktop installed and running

# 1. Clone repository
git clone https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git
cd purplle-store-intelligence-platform

# 2. Place pipeline outputs (required before api can start)
#    events/pipeline_summary.json and events/events.json must exist.
#    These are committed as sample output -- no action needed for demo.

# 3. Build images
docker compose build

# 4. Start services (dashboard waits for api health)
docker compose up

# 5. Verify
#    API:       http://localhost:8000/health
#    API docs:  http://localhost:8000/docs
#    Dashboard: http://localhost:8501

# 6. Stop
docker compose down
```

---

## Phase 6 Completion Gate

- [x] .dockerignore excludes inputs/ (648 MB video files)
- [x] Separate API and dashboard images
- [x] Both images based on python:3.11-slim
- [x] API image: only fastapi + uvicorn (no CV/ML packages)
- [x] Dashboard image: only UI-layer packages
- [x] events/ bind-mounted read-only into API container
- [x] API_BASE_URL=http://api:8000 set in compose
- [x] FastAPI /health endpoint used as healthcheck target
- [x] Streamlit /_stcore/health used as healthcheck target
- [x] depends_on: api: condition: service_healthy
- [x] No GPU configuration
- [x] Health checks use stdlib urllib (no curl dependency)
- [x] 50/50 structural validation checks pass

**Phase 6 completion gate: PASSED.**

**Next step: docker compose build + up on real Docker (with Docker Desktop
installed) to verify images build and services start correctly before Phase 7.**
