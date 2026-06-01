# Purplle Store Intelligence Platform

A retail intelligence platform for the Purplle Brigade Road store built on
computer vision, POS transaction data, and store layout-aware zone analytics.

---

## Quick Start

```bash
# Start the full platform (backend API + dashboard)
docker compose up

# Open dashboard
http://localhost:8501

# Optional: verify live computation (completes in < 5 minutes)
python process_videos.py --quick

# Full video processing (15–60+ minutes depending on hardware)
python process_videos.py
```

> **Note:** `docker compose up` loads precomputed events and starts instantly.
> `process_videos.py` is the optional live recomputation path.

---

## What This Platform Does

Three separate intelligence layers, kept honest and distinct:

| Layer | Source | Date |
|-------|--------|------|
| Customer Intelligence | 5 MP4 video files | 16-04-2026 |
| Revenue Intelligence | POS CSV data | 10-04-2026 |
| Operational Intelligence | CAM 4 + CAM 5 video | 16-04-2026 |

No individual-level matching is claimed between video and CSV. The dates differ.
These layers are reported separately and clearly labelled throughout.

---

## Architecture Overview

```
zones.json + config.json
        |
        v
5 MP4 Videos + POS CSV
        |
        v
Detection Layer
  CAM 1,2,3,5: YOLOv8-nano + centroid tracker
  CAM 4: OpenCV MOG2 background subtraction
        |
        v
Zone Event Layer (entry crossings, dwell time, motion events)
        |
        v
Business Logic (funnel, staff filter, 5 anomaly detectors, CSV analytics)
        |
        v
FastAPI (port 8000) + Streamlit Dashboard (port 8501)
```

Full architecture documentation: see `DESIGN.md` (assembled in Phase 7).

---

## Data Sources

| File | Description |
|------|-------------|
| `inputs/CAM_1.mp4` | Skincare / Bath zone (~1.76 GB, 16-04-2026) |
| `inputs/CAM_2.mp4` | Main Floor / Circulation zone (16-04-2026) |
| `inputs/CAM_3.mp4` | Entrance / Exit (primary funnel camera, ~1.86 GB, 16-04-2026) |
| `inputs/CAM_4.mp4` | Warehouse / Storage zone (16-04-2026) |
| `inputs/CAM_5.mp4` | Billing Counter (16-04-2026) |
| `data/Brigade_Bangalore_10_April_26.csv` | POS transaction data (10-04-2026) |
| `zones.json` | Store layout zone definitions derived from `Brigade_Road_Store_layout.xlsx` |

> MP4 files are excluded from git (`.gitignore`). Place them in `inputs/` before running.

---

## How Integrity Is Verified

When `process_videos.py` runs, it computes a SHA256 hash of every video file
and writes `events/video_hashes.json`. The System Health tab (Tab 5) displays
these hashes. This proves that `events/events.json` was generated from the
specific video files provided, not fabricated.

To verify:
1. Run `python process_videos.py` with the original video files.
2. Check that the hashes in `events/video_hashes.json` match those shown in
   the System Health tab.
3. Replace a video file and rerun — the hash changes, events regenerate,
   and API metrics update accordingly.

---

## What To Look For

1. **Tab 3 (Zone Intelligence)** — see how the official store layout
   (`Brigade_Road_Store_layout.xlsx`) drives the analytics via `zones.json`.
   Every zone polygon is derived from the actual floor plan.

2. **`curl http://localhost:8000/anomalies`** — business-actionable alerts with
   recommendations and `triggered_at` timestamps from actual pipeline computation.
   On committed footage: 1 alert fires (`unusual_warehouse_activity` at t=92.3s).
   All 5 detectors are implemented; others fire when their thresholds are exceeded.

3. **Tab 4 (Revenue Intelligence)** — salesperson performance ranking and
   promotion effectiveness analysis from POS data.

4. **Tab 5 (System Health)** — video hash fingerprint proving events were
   computed from specific files, not fabricated.

5. **`python process_videos.py --quick`** — live computation in under 5 minutes.
   Observe metrics updating after the run. Last full run: 142.6s total on
   Intel Core i7-1355U (CAM_1: 30.3s, CAM_2: 27.2s, CAM_3: 25.7s,
   CAM_4: 28.1s, CAM_5: 30.8s) — 2026-06-01.

6. **`CHOICES.md`** — architectural rationale for using background subtraction
   for CAM 4 instead of person detection. A deliberate design decision, not a
   limitation.

7. **`curl http://localhost:8000/events/sample`** — 10 raw detection events
   directly from the pipeline output showing the underlying data that drives
   all metrics.

---

## Limitations

- **No cross-camera person tracking.** Zone-level aggregate counts only.
  A person appearing in CAM 1 and CAM 5 is not linked as the same individual.
- **Date mismatch.** Video data is from 16-04-2026; POS CSV is from 10-04-2026.
  Traffic-sales "alignment" is illustrative, not causal.
- **Staff filtering is heuristic.** Three pattern-based rules are applied by
  default to exclude likely staff crossings. Perfect staff detection is not
  feasible without badges or face recognition. The filtered count is shown
  transparently in System Health.
- **Frame sampling.** Default config processes 1000 frames per camera with
  frame skip 5, covering approximately 2–3 minutes of footage per camera.
  Metrics represent a sampled window, not the full recording duration.
- **CPU-only processing.** YOLOv8-nano at 640x360 with frame skip 5 runs
  on CPU. Processing time varies from 15 to 60+ minutes depending on hardware.
- **Zone polygons.** Coordinates in `zones.json` are derived from the store
  layout file and visual frame inspection. Polygon accuracy directly affects
  zone visit counts.

---

## Running the Processing Script

```bash
# Full run (all 5 cameras, 1000 frames each)
python process_videos.py

# Quick verification run (300 frames, frame_skip=10, < 5 minutes)
python process_videos.py --quick
```

Last full test run: 142.6s (all 5 cameras, 1000 frames each at frame_skip=5, CAM_4 full video)  
Hardware: Intel Core i7-1355U (13th Gen), 16 GB RAM, Windows 11 Home

---

## Engineering Decisions

See `CHOICES.md` for rationale behind all major architectural decisions.
See `decisions_log.txt` for the raw running log built from day one.
See `DESIGN.md` for the full system architecture document.
