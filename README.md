# Purplle Store Intelligence Platform

A store analytics pipeline built from raw CCTV footage and POS transaction data.
Computer vision extracts customer behaviour across five camera zones; a REST API
serves real-time metrics; a Streamlit dashboard surfaces the results for store
managers and operations teams.

## Key Capabilities

- **Zone-aware detection**: store layout polygons (`zones.json`) derived from the
  floor plan drive all zone classification; no hardcoded coordinates
- **Three intelligence layers**: Customer traffic (video), Revenue analytics (POS),
  and Operational alerts (warehouse + billing) kept separate and clearly labelled
- **Staff movement filtering**: heuristic rules exclude likely staff crossings from
  customer metrics; filtered count displayed transparently in System Health
- **Anomaly detection**: five operational detectors including warehouse activity
  alerts, queue buildup, and zone abandonment; each with a `triggered_at` timestamp
  from actual pipeline computation
- **Integrity defence**: SHA-256 fingerprints of all five input videos committed
  alongside `events/events.json`; rerunning with different footage produces different hashes
- **Two-service Docker deployment**: FastAPI backend (port 8000) and Streamlit
  dashboard (port 8501) with health-checked startup ordering
- **Live recomputation**: `process_videos.py --quick` reruns the full pipeline in
  under five minutes and updates all API metrics on restart

## Live Deployment

| Service | URL |
|---------|-----|
| Dashboard (live) | https://purplle-store-intelligence-dashboard.up.railway.app/ |
| API (live) | https://purplle-store-intelligence-platform-production.up.railway.app/ |
| API Docs (live) | https://purplle-store-intelligence-platform-production.up.railway.app/docs |
| Health Check (live) | https://purplle-store-intelligence-platform-production.up.railway.app/health |

## Setup

```bash
docker compose up
```

Dashboard: http://localhost:8501 (local)  
API docs: http://localhost:8000/docs (local)

The stack loads precomputed events at startup. No video files are required to run
the platform. To rerun the detection pipeline, place MP4 files in `inputs/` first.

## Results: Brigade Road Store

Metrics from the committed pipeline run (5 cameras, 1000 frames each, 2026-06-01):

| Metric | Value |
|--------|-------|
| Zone visits | 9 total (Main Floor: 5, Skincare: 2, Billing: 2) |
| Average dwell time | 26-33 seconds per zone |
| Transactions (POS) | 24 transactions, GMV Rs 44,920, NMV Rs 34,832 |
| Top category | Makeup, 64% of GMV (Rs 28,803) |
| Anomaly detected | Warehouse restocking confirmed at t=92.3s |
| Pipeline runtime | 142.6s on Intel Core i7-1355U (13th Gen), 16 GB RAM, Windows 11 |

## Architecture

```
zones.json + config.json
        |
CAM 1,2,3,5: YOLOv8-nano + centroid tracker      POS CSV
CAM 4:       OpenCV MOG2 background subtraction       |
        |                                             |
Zone events (dwell, crossings, motion)        CSV analytics
        |                                             |
        +------------- Business Logic ----------------+
               Funnel . Staff filter . Anomalies
                             |
             FastAPI :8000       Streamlit :8501
```

CAM_4 uses background subtraction rather than YOLO. The warehouse question is
"is there activity?" not "is there a person?", a deliberate architectural choice
documented in `CHOICES.md`.

## Data Sources

| File | Content | Date |
|------|---------|------|
| `inputs/CAM_1.mp4` | Skincare / Bath zone (~1.76 GB) | 16-04-2026 |
| `inputs/CAM_2.mp4` | Main Floor / Circulation | 16-04-2026 |
| `inputs/CAM_3.mp4` | Entrance / Exit (~1.86 GB) | 16-04-2026 |
| `inputs/CAM_4.mp4` | Warehouse / Storage | 16-04-2026 |
| `inputs/CAM_5.mp4` | Billing Counter | 16-04-2026 |
| `data/Brigade_Bangalore_10_April_26.csv` | POS transaction records | 10-04-2026 |
| `zones.json` | Store layout zone definitions | n/a |

Video and POS data are from different dates. No individual-level matching between
datasets is claimed or performed. All API responses label their data source.

MP4 files are excluded from git (`.gitignore`). Place them in `inputs/` before
running `process_videos.py`.

## Live Recomputation

```bash
# Quick verification (300 frames, frame_skip=10, under 5 minutes)
python process_videos.py --quick

# Full run (1000 frames per camera, ~143s on i7-1355U)
python process_videos.py
```

After rerunning, restart the API to load the updated events:

```bash
docker compose restart api
```

## Integrity Verification

When `process_videos.py` runs, it computes SHA-256 of every input video file and
writes `events/video_hashes.json`. The System Health tab (Tab 5) displays these
hashes. Replacing a video file and rerunning updates the hashes and changes all
downstream metrics, proving the pipeline is live and not hardcoded.

```bash
curl http://localhost:8000/health   # local
curl https://purplle-store-intelligence-platform-production.up.railway.app/health   # live
```

## What to Look For

1. **Tab 3 (Zone Intelligence)**: how `zones.json` polygons derived from the
   store layout drive all zone analytics
2. **`GET /stores/STORE_BLR_002/anomalies`**: operational alerts with
   `triggered_at` timestamps from actual pipeline computation
3. **Tab 4 (Revenue Intelligence)**: salesperson performance ranking and
   promotion effectiveness from POS data
4. **Tab 5 (System Health)**: video fingerprints, pipeline elapsed time,
   log buffer showing structured JSON request logs
5. **`python process_videos.py --quick`**: live recomputation in under 5 minutes;
   restart API and observe metrics update
6. **`CHOICES.md`**: rationale for CAM_4 background subtraction, centroid tracker
   selection, event schema design, and AI-assisted decisions
7. **`GET /events/sample`**: 10 raw detection events directly from the pipeline
   showing the data that drives all metrics

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /events/ingest` | Batch event ingest, idempotent by `event_id` |
| `GET /stores/{id}/metrics` | Traffic, revenue, and operational metrics |
| `GET /stores/{id}/funnel` | Zone visit funnel with monotonicity validation |
| `GET /stores/{id}/heatmap` | Dwell and visit frequency, normalised 0-100 |
| `GET /stores/{id}/anomalies` | Active operational anomalies |
| `GET /health` | Service status, uptime, video hashes, log buffer |

Full interactive schema: http://localhost:8000/docs (local) | https://purplle-store-intelligence-platform-production.up.railway.app/docs (live)

## Limitations

- No cross-camera person tracking. All metrics are zone-level aggregate counts.
  A visitor in CAM_1 and CAM_5 is not linked as the same individual.
- Video data (16-04-2026) and POS data (10-04-2026) are from different dates.
  Traffic-sales alignment in the dashboard is illustrative, not causal.
- Entry count is 0 on committed footage. CAM_3 captures a pre-traffic window;
  crossing detection is validated synthetically. See `CHOICES.md` for the full
  analysis.
- Frame sampling covers approximately 2-3 minutes per camera at default settings
  (1000 frames, frame_skip=5).
- Staff filtering uses heuristic positional rules, not badge or face recognition.
  The filtered count is shown transparently in System Health.

## Documentation

`DESIGN.md`: system architecture, detection rationale, event schema, Docker design,
honest limitations, and AI-assisted decisions  
`CHOICES.md`: every major engineering decision with options considered, AI
suggestions, and final rationale  
`decisions_log.txt`: raw running log maintained from day one, cross-referenced
in both documents
