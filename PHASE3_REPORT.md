# PHASE 3 REPORT — Backend and Event Pipeline

Phase: 3 — Backend and Event Pipeline
Status: IN PROGRESS (2 of 6 checkpoints complete)
Started: 2026-06-01
Checkpoint 3.1 Commit: 70f3959
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## Objective

Implement the production pipeline that processes all 5 video inputs and the POS CSV,
writes events.json and video_hashes.json, and produces all intelligence outputs
consumed by the Phase 4 API and Phase 5 dashboard.

From master plan Section 25:
> Phase 3 ends when process_videos.py runs to completion and produces a valid events.json.

---

## Checkpoint Status

| # | Checkpoint | Files | Status | Result |
|---|-----------|-------|--------|--------|
| 3.1 | Foundation layer | src/utils.py, src/zone_classifier.py, zones.json | **COMPLETE** | 13/13 validation checks pass — commit 70f3959 |
| 3.2 | Detection layer | src/detection.py, src/background_motion.py | **COMPLETE** | 12/12 validation — commit 5b7e5bf |
| 3.3 | Entry counter + session manager | src/entry_counter.py, src/session_manager.py | NOT STARTED | Scope review pending |
| 3.4 | Staff filter | src/staff_filter.py | NOT STARTED | — |
| 3.5 | Funnel + anomalies + CSV | src/funnel.py, src/anomalies.py, src/csv_analytics.py | NOT STARTED | — |
| 3.6 | Orchestrator | process_videos.py | NOT STARTED | — |

---

## Checkpoint 3.1 — Foundation Layer

**Commit:** `70f3959`
**Tool:** `tools/validate_checkpoint_31.py`
**Validation:** `python tools/validate_checkpoint_31.py` — 13/13 PASS

### What was implemented

**`src/utils.py`**

| Function / Symbol | Purpose |
|-------------------|---------|
| `load_config(path)` | Load config.json; raise KeyError listing missing required keys |
| `load_zones(path)` | Load zones.json; warn (do not crash) on empty polygons |
| `compute_sha256(filepath)` | Deterministic lowercase hex SHA256 digest |
| `write_hashes(paths, output_path)` | Hash all input files; write events/video_hashes.json; graceful on missing files |
| `verify_hashes(hashes_path, paths)` | Re-compute and compare; return mismatches list |
| `get_logger(name)` | JSON-formatted logger; stdout + rotating file at logs/pipeline.log; idempotent |
| `LOG_BUFFER` | `collections.deque(maxlen=50)`; populated by `_JsonFormatter`; read by api.py /health |
| `format_duration(seconds)` | `"2h 14m 32s"` style output |
| `make_zone_dwell_event(...)` | Emitted by session_manager on visit close |
| `make_zone_entry_event(...)` | Emitted by session_manager on zone entry |
| `make_zone_exit_event(...)` | Emitted by session_manager on zone exit |
| `make_crossing_event(...)` | Emitted by entry_counter; event_type = crossing_entry or crossing_exit |
| `make_warehouse_motion_event(...)` | Emitted by background_motion per qualifying MOG2 frame |
| `make_queue_alert_event(...)` | Emitted by anomalies on billing queue buildup |
| `append_event(event, path)` | NDJSON append; creates events/ dir if absent |

**`src/zone_classifier.py`**

| Function | Purpose |
|----------|---------|
| `point_in_polygon(x, y, polygon)` | Ray-casting; handles all approved rectangular polygons |
| `classify_zone(camera_id, centroid, zones_cfg)` | Returns zone name string or None; raises ValueError on unknown camera |

**`zones.json`**

- `CAM_3`: added `"door_x_gate": [250, 490]` — Decision 15 carry-forward.
  No entry-counting logic uses this field yet. Captured in schema before `load_zones()` was written.

### Event schema (frozen — DESIGN.md Section 8)

All events share a common envelope: `event_id` (UUID4), `event_type`, `camera`, `frame_idx`,
`timestamp_seconds`, `processed_at` (ISO8601 UTC).

#### Representative serialised events (as written to events.json)

**zone_dwell** (session_manager → funnel, anomaly 1, anomaly 5):
```json
{
  "event_id": "a80b58d6-245b-4d89-a0da-5252656450ca",
  "event_type": "zone_dwell",
  "camera": "CAM_1",
  "zone": "skincare",
  "frame_idx": 100,
  "timestamp_seconds": 16.7,
  "processed_at": "2026-06-01T09:26:14.096554+00:00",
  "track_id": 7,
  "bbox": [100, 80, 160, 200],
  "centroid": [130, 140],
  "confidence": 0.82,
  "dwell_seconds": 33.4,
  "frame_entry": 100,
  "frame_exit": 300,
  "timestamp_entry_seconds": 16.7,
  "timestamp_exit_seconds": 50.1,
  "staff_filtered": false
}
```

**crossing_entry** (entry_counter → funnel stage 1, anomaly 4):
```json
{
  "event_id": "680b1ecf-f9f1-47bb-8007-f908d2266943",
  "event_type": "crossing_entry",
  "camera": "CAM_3",
  "zone": "entrance",
  "frame_idx": 210,
  "timestamp_seconds": 35.0,
  "processed_at": "2026-06-01T09:26:14.096566+00:00",
  "track_id": 12,
  "centroid_before": [340, 165],
  "centroid_after": [340, 175],
  "crossing_direction": "entry",
  "staff_filtered": false
}
```

**warehouse_motion** (background_motion → anomaly 3, operational intelligence):
```json
{
  "event_id": "44c03604-2e1e-405c-b8cd-0a51dd426d91",
  "event_type": "warehouse_motion",
  "camera": "CAM_4",
  "zone": "warehouse",
  "frame_idx": 718,
  "timestamp_seconds": 23.96,
  "processed_at": "2026-06-01T09:26:14.096571+00:00",
  "contour_area": 2340.5,
  "is_restocking_event": false
}
```

### Validation results

```
13/13 checks passed -- ALL PASS

[PASS] config.json loads; warehouse_motion_threshold=1631, frame_skip=5
[PASS] zones.json loads; 5 cameras: CAM_1, CAM_2, CAM_3, CAM_4, CAM_5
[PASS] CAM_3 door_x_gate=[250, 490]
[PASS] Event schema: 7 types serialise/deserialise; common envelope correct
[PASS] Event writer: 2 events written as NDJSON; both read back correctly
[PASS] Zone classifier: inside polygons return correct zone names
[PASS] Zone classifier: outside polygons return None
[PASS] Zone classifier: CAM_5 partial polygon boundary enforced
[PASS] Zone classifier: unknown camera_id raises ValueError
[PASS] Structured logging: JSON entries in LOG_BUFFER; all required fields
[PASS] SHA256: deterministic 64-char lowercase hex digest
[PASS] Integrity: write_hashes + verify_hashes round-trip; 5/5 videos hashed
[PASS] format_duration: 6 cases correct
```

---

## Checkpoint 3.2 — Detection Layer

**Commit:** `5b7e5bf`
**Validation:** `python tools/validate_checkpoint_32.py` — 12/12 PASS

### What was implemented

**`src/detection.py`** — `run_detection(video_path, camera_id, config, zones_cfg)`

Generator function for CAM_1/2/3/5. Yields one dict per processed frame:
- YOLO inference at `detection_resolution` with `confidence_threshold`
- Centroid tracker: greedy distance-based matching, `_MAX_DISAPPEARED=10`
- `classify_zone()` called per matched track per frame
- Only tracks with active YOLO detection yielded (disappeared tracks excluded)

**`src/background_motion.py`** — `run_background_motion(video_path, config, zones_cfg)`

Returns `(motion_frames, restocking_events)` for CAM_4:
- Sequential reads (no seek — MOG2 temporal model requirement)
- `_WARMUP_FRAMES=200`: frames fed to MOG2 for background model building; event emission suppressed during this period. Frame-0 cold-start artifact class eliminated.
- Zone polygon bounding box applied as mask

### CAM_4 Full Recalibration (Decision 18)

Phase 2 threshold `1631` was invalidated by Checkpoint 3.2 investigation.

**Root cause of Phase 2 failure:** `flicker_areas` sample in `test_warehouse_motion.py` was capped at `CURRENT_THRESHOLD × 3 = 1500 sq px`. Actual floor flicker spans 10,000–50,000 sq px — the Phase 2 tool measured the wrong population.

**Algorithmic separation tested and ruled out:** Four characterisation methods applied across 3,447 post-warmup frames:

| Feature | Short events (≤0.1s) | Long events (≥0.5s) | Precision |
|---------|---------------------|---------------------|-----------|
| Contour count | 6.56 mean | 13.44 mean | 0.00 |
| Compactness | 0.130 | 0.120 | 0.06 |
| % lower floor px | 76.2% | 67.0% | 0.02 |
| Duration > 0.4s | — | — | **1.00** (but selects prolonged flicker, not genuine motion) |

All spatial/morphological features were non-separable. Duration was the only precision-1.00 rule but selects prolonged flicker, not genuine activity.

**Zone geometry revision:** CAM_4 polygon bottom raised `y=355 → y=246`, excluding the reflective tile floor band confirmed responsible for 74% of foreground pixels across the full 146s recording.

**Threshold recalibration on revised zone (full video, post-warmup):**

| Statistic | Value |
|-----------|-------|
| p99 noise (revised zone) | 21,604 sq px |
| p99 × 1.30 | **28,085 sq px** (new threshold) |
| Events at T=28,085 | **2** (both at t=92.3s — confirmed genuine scene change) |
| False positives eliminated | 449 of 451 |

Genuine event confirmed: frame 2306 (t=92.31s), contour area 63,617 sq px (47% of revised zone) — boxes/items visually rearranged in the shelf area.

**Open item — processing window gap:** `max_frames_per_camera=1000` covers only the first 40s of the 146s CAM_4 recording. Genuine events at t=92s are beyond this window. Deferred to Checkpoint 3.6 orchestrator implementation.

### Validation results

```
12/12 checks passed -- ALL PASS

[PASS] run_detection: imports without error
[PASS] run_detection: returns a generator (not a list)
[PASS] CAM_1: frame dict correct top-level keys and types
       -> 40 frames; frame_idx=0, proc_idx=0, ts=0.0s, tracks=2
[PASS] CAM_1: track dict fields correct types and value ranges
       -> track_id=0, bbox=[477,84,540,205], centroid=[508,144], conf=0.8384, zone='skincare'
[PASS] CAM_1: track zone field matches classify_zone for every centroid
       -> 79 track observations; 79 inside polygon (zone='skincare'), 0 outside
[PASS] CAM_1: at least one track survives >=10 frames (ID stability)
       -> 2 unique IDs, 2 stable (>=10 frames), longest=40 frames
[PASS] CAM_2 smoke test: non-zero frames, correct structure
[PASS] CAM_5 smoke test: non-zero frames, correct structure
[PASS] CAM_4: run_background_motion returns (list[dict], list[dict])
       -> motion_frames: 2 entries; restocking_events: 2 entries
[PASS] CAM_4: motion_frames non-empty; genuine event at t=92s confirmed
       -> 2 qualifying frames; first=2306, last=2323
[PASS] CAM_4: all contour_areas above warehouse_motion_threshold=28085
       -> area range [39738, 63617]
[PASS] CAM_4: restocking_events structure and field types correct
```

---

## Decisions to Record After Each Checkpoint

- Decision 18: Detection module architecture choices (frame_skip vs sequential, batch size)
- Decision 19: session_manager dwell merge implementation detail
- Decision 20: process_videos.py orchestration strategy (sequential vs parallel per camera)

---

## Known Pre-conditions for Remaining Checkpoints

| Checkpoint | Pre-condition |
|-----------|---------------|
| 3.2 | models/yolov8n.pt present (confirmed Phase 0) |
| 3.3 | 3.2 complete; zones.json door_x_gate readable via load_zones() (confirmed 3.1) |
| 3.4 | 3.3 complete; crossing events emitted by entry_counter |
| 3.5 | 3.3 + 3.4 complete; data/Brigade_Bangalore_10_April_26.csv present |
| 3.6 | All src/ modules implemented; events/ directory structure established (confirmed 3.1) |

---

## Phase 3 Completion Gate

Process_videos.py runs to completion and produces:
- [ ] `events/events.json` — NDJSON file with all events from all 5 cameras
- [ ] `events/video_hashes.json` — SHA256 fingerprint per video
- [ ] Console summary: processing time, event counts per type
- [ ] `logs/pipeline.log` — structured JSON log of full run
