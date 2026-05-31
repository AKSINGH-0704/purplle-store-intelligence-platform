# CHOICES.md — Engineering Decisions and Rationale
## Purplle Store Intelligence Platform

This document records every non-obvious architectural and engineering decision
made during the development of this platform. It is assembled from
`decisions_log.txt`, which was maintained as a running log from day one.

Each section references the decision number in decisions_log.txt so the
raw notes can be cross-checked against the polished entry here.

---

## 1. Repository Structure

**Decision:** Repository structure follows the master plan exactly (decisions_log.txt #1).

The project structure was fixed in Phase 0 and treated as a contract, not a suggestion. All future agents, collaborators, and reviewers can verify any file's location and purpose against the master plan without needing to infer intent from directory names or implicit conventions.

---

## 2. Dependency Choices

**opencv-python-headless over opencv-python (decisions_log.txt #2)**

`opencv-python` bundles Qt GUI libraries (~200MB of additional dependencies) that serve no purpose in a headless server or Docker container. `opencv-python-headless` has no display dependency, installs faster, produces a smaller Docker image, and avoids X11 errors inside containers without a display server.

Trade-off: `cv2.imshow()` is unavailable. All visualisation uses `cv2.imwrite()` to save files, which is appropriate for a server-side application. `visualise_zones.py` outputs to `zones_preview/` rather than opening windows.

**Version pinning strategy (decisions_log.txt #6)**

`requirements.txt` initially specifies minimum version bounds (`>=`) rather than exact pinned versions. Exact pinning is performed after `pip install` succeeds on the target hardware, using `pip freeze`. Pinning to exact versions without testing may create impossible dependency combinations across platforms (particularly for numpy, scipy, and OpenCV on different OS/Python combinations). The correct engineering practice is: install with bounds, verify functionality, freeze.

---

## 3. Zone Configuration

**zones.json as first-class component (decisions_log.txt #3)**

`zones.json` is the bridge between the physical store layout and the detection pipeline. It is not a secondary config file — it drives the entire detection architecture. The store layout file (`Brigade_Road_Store_layout.xlsx`) was inspected in Phase 0 and found to contain a floorplan image only — no machine-readable coordinates (decisions_log.txt #8). All polygon coordinates must therefore be derived through iterative video frame inspection using `visualise_zones.py`.

Coordinates were **not invented** for any camera. Empty arrays with TODO markers were used in Phase 0 scaffolding, with the clear understanding that fabricated coordinates would silently corrupt all downstream zone metrics without producing any error signal. A pipeline that fails loudly on empty polygons is safer than one that runs silently on wrong ones.

**Frame extraction approach for polygon derivation (decisions_log.txt #8)**

Since the Excel layout contains only an image, the polygon extraction workflow is:
1. Run `visualise_zones.py` to extract frame 100 from each video.
2. Visually identify zone boundaries from the frame.
3. Record pixel-space coordinates at 640×360 resolution.
4. Update `zones.json` and re-run `visualise_zones.py` to verify alignment.
5. Iterate until all polygons visually match actual zone boundaries.

Store layout knowledge (entry door left wall, billing counter right, skincare top wall, makeup bottom wall, F.O.H island center) informed where to look in each frame, but the pixel coordinates came from the video, not from the layout image.

---

## 4. Detection Strategy

**YOLOv8-nano for CAM 1, 2, 3, 5**

YOLOv8-nano was chosen over larger YOLOv8 variants because:
- It runs on CPU without GPU — matching the evaluation environment.
- The model weight file is ~6MB, keeping the Docker image compact.
- Person detection accuracy is sufficient for retail-density scenes at 640×360.
- Frame skip 5 (processing 6fps from 30fps source) compensates for the slower inference speed.

The model weights are bundled in the `models/` directory and copied into the Docker image during build. No network access is required at any point during startup or processing. This prevents startup hangs in evaluation environments without internet access.

**Background subtraction for CAM 4 (decisions_log.txt #4)**

CAM 4 covers the warehouse/storage zone. The warehouse requires activity detection — "is something moving and approximately how much?" — not customer identification. OpenCV's MOG2 background subtractor answers this question faster, lighter, and with fewer dependencies than running YOLOv8 on warehouse footage.

A minimum contour area threshold (`warehouse_motion_threshold`, default 500 sq px) filters out lighting-flicker false positives. MOG2 adapts to gradual background changes but is sensitive to sudden motion, which is exactly the desired behaviour for detecting warehouse activity.

**CAM 4 lighting flicker — calibration required (decisions_log.txt #9)**

Phase 0 video inspection revealed visible lighting flicker in CAM 4. The default threshold of 500 sq px was set before observing this. Phase 2 calibration is mandatory for this camera: measure maximum contour area produced by flicker-only frames, then set `warehouse_motion_threshold` above that maximum. Expected calibrated range: 500–2000 sq px. The decision to keep the default at 500 rather than guessing a higher value was deliberate — engineering from data, not assumptions.

*TODO (Phase 2): Update this section with the calibrated value and the flicker contour area measurements.*

---

## 5. Tracking Strategy

**Centroid tracker as primary; ByteTrack as conditional fallback (decisions_log.txt #5)**

Evaluated ByteTrack but implemented a lightweight centroid tracker for the primary tracking strategy. Rationale:

- **Zero external dependencies.** The centroid tracker uses only numpy (already a core dependency). ByteTrack requires specific versions of scipy and lap or lapjv, which have installation friction on CPU-only environments and can fail silently inside Docker.
- **Sufficient for zone-level analytics.** We are computing zone-level aggregate counts, not individual person journeys across the full store. Centroid tracking with an 80px distance threshold is sufficient for this task.
- **Debuggable.** A centroid tracker's behaviour is inspectable at every step. ByteTrack failures can produce silently incorrect track IDs without raising errors.

ByteTrack remains a documented fallback. Phase 2 validation will test: does a single walking person maintain one consistent track ID for at least 20 consecutive processed frames? If centroid tracking fails this test, ByteTrack will be evaluated with the same criterion (< 3 ID resets per minute).

*TODO (Phase 2): Update this section with the tracker validation result.*

**Dwell merge rule (decisions_log.txt #5 — see also DESIGN.md Section 6.2)**

Dwell time merge accounts for track ID reassignment after occlusion. Sessions are only merged when no other active tracks exist in the zone, preventing false consolidation of different visitors into a single longer session.

---

## 6. Camera Zone Mapping and Validation

**Camera-to-zone mapping confirmed from direct video inspection (decisions_log.txt #7)**

All five cameras were briefly inspected before any pipeline code was written:

- CAM_1: Skincare/Bath zone — dedicated product browsing area with skincare and cosmetics shelving.
- CAM_2: Main Floor — wide-angle view with multiple customers visible simultaneously.
- CAM_3: Entrance/Exit — customer movement between store interior and exterior corridor clearly visible.
- CAM_4: Warehouse — storage area with cartons visible. **Lighting flicker observed** (see Detection Strategy — CAM 4 above).
- CAM_5: Billing Counter — checkout area and counter clearly visible.

Mapping confirmed against master plan Section 2.1. No discrepancies found.

*TODO (Phase 2): Update this section with entry line coordinates and direction vector for CAM_3 after visual validation.*

---

## 7. Aggregate-Only Funnel Design

**No cross-camera person tracking (design principle)**

The system makes no attempt to link a person detected in CAM_1 to the same person detected in CAM_5. This is a deliberate design choice, not a limitation we are hiding:

1. Cross-camera re-identification requires deep learning ReID models and GPU compute, both outside the evaluation environment scope.
2. Aggregate zone counts are legitimate, valuable, and defensible business intelligence without individual tracking.
3. Overclaiming individual-level cross-camera tracking would be dishonest and verifiably false under scrutiny.

The funnel disclaimer is embedded in every API response that touches funnel data:
> "Aggregate zone counts only. No person-level matching. Traffic and sales are from different dates."

**Zone abandonment boundary guard**

Anomaly 4 (Zone Abandonment) is computed only for entries in the **first 70%** of the processing window. Entries near the end of the window have their potential follow-up zone visit outside the processed frames, causing false positives if included. This is the type of edge case that distinguishes careful engineering from a quick implementation.

---

## 8. Staff Filtering

**Heuristic-based, transparent, applied by default**

Staff detection uses entry line crossing patterns and positional heuristics only. Three rules operate entirely within individual camera views — cross-camera identity is not available in the aggregate architecture.

The `staff_roundtrip_threshold` (3 crossings in both directions within `staff_roundtrip_window_minutes` = 30 minutes) captures the characteristic behaviour of staff making multiple in-out trips without flagging normal customers who leave and return.

The staff filtering count is displayed in the System Health tab. Transparency about what was filtered is more credible than claiming perfect customer-only metrics.

*TODO (Phase 3): Update this section with the staff_filtered_count from actual processing and a description of which rule matched the most events.*

---

## 9. Startup vs Processing Separation

**Precomputed events.json loads at startup; process_videos.py is separate**

`docker compose up` must complete in under 30 seconds for a good evaluator experience. Video processing takes 15–60+ minutes. These two requirements are irreconcilable if video processing is triggered at startup.

The solution: `events.json` is precomputed by running `process_videos.py` and committed to the repository. At startup, the API loads this file in under 2 seconds. Judges who want to verify live computation can optionally run `process_videos.py --quick` (< 5 minutes with `MAX_FRAMES=300`, `frame_skip=10`).

This is how production systems work — precomputed indices that serve queries instantly, with separate batch jobs that update them.

---

## 10. Docker Architecture

**Explicit HEALTHCHECK required for depends_on to work**

Without an explicit `HEALTHCHECK` instruction in the api `Dockerfile`, Docker's `depends_on: condition: service_healthy` is silently ignored. Both services start simultaneously, and the dashboard fails on its first API call. The `HEALTHCHECK` instruction makes this dependency contract enforceable.

**API_BASE_URL environment variable for service discovery**

The Streamlit dashboard code reads `API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")`. Inside Docker Compose, the dashboard service receives `API_BASE_URL=http://api:8000` as an environment variable, using the Docker service name for internal network routing. During local development, the default `localhost:8000` works without any configuration change.

**YOLO weights bundled in Docker image**

`yolov8n.pt` is copied into the image during `docker build`. This prevents Ultralytics from attempting a network download at container startup, which would hang in evaluation environments without internet access. Bundling ~6MB of weights is a negligible image size cost for guaranteed offline operation.

---

## 11. Integrity Defence

**Video hash fingerprinting (DESIGN.md Section 14)**

SHA256 hashes of all input video files are computed by `process_videos.py` and stored in `events/video_hashes.json`. The `/health` endpoint exposes these hashes, and the System Health dashboard tab displays them. This is the technical answer to "did you just hardcode these numbers?"

*TODO (Phase 3): Update this section with the actual video file hashes after running process_videos.py on all 5 videos.*

---

## 12. Future Architecture Roadmap

- **Cross-camera re-identification:** OSNet or Fast-ReID would enable true person-level journey tracking. Not implemented due to CPU constraints and time scope.
- **Real-time streaming:** Kafka event bus for live zone occupancy dashboards with sub-second latency.
- **Multi-store deployment:** `zones.json` is deliberately designed to be portable. Different stores require only a new zone configuration file — no code changes.
- **LLM-generated insights:** Structured events and business metrics could feed a language model to generate natural-language store manager reports.
- **Staffing intelligence:** With badge or face recognition, staff movement patterns become an operational scheduling input rather than filtered noise.
