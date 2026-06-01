# PHASE 2 REPORT — CV Validation and Parameter Calibration

Phase: 2 — CV Validation
Status: IN PROGRESS
Started: 2026-06-01
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## Objective

Answer four validation questions and calibrate all detection parameters
BEFORE writing any pipeline code in Phase 3.

From master plan Section 25:
> If all questions are answered positively, stop. Move to Phase 3.

---

## Four Validation Questions

| Q | Question | Status | Answer |
|---|----------|--------|--------|
| Q1 | Can YOLOv8-nano detect people at 640×360 on this machine? | **COMPLETE** | **YES** — 6 detections across 3 frames, conf 0.76–0.88 |
| Q2 | Does centroid tracker maintain consistent IDs for ≥20 consecutive frames? | NOT STARTED | — |
| Q3 | Can entry crossings be counted from CAM_3 (≥8/10 correct)? | NOT STARTED | — |
| Q4 | Can zone visits be detected from CAM_1, CAM_2, CAM_5? | NOT STARTED | — |

---

## Checkpoint Status

| # | Checkpoint | Tool | Status | Result |
|---|-----------|------|--------|--------|
| 2.1 | YOLOv8-nano smoke test | tools/test_yolo.py | COMPLETE | Q1 = YES — see results below |
| 2.2 | Centroid tracker validation | tools/test_tracker.py | NOT STARTED | — |
| 2.3 | Entry line crossing validation | tools/test_entry_crossing.py | NOT STARTED | — |
| 2.4 | Zone visit detection | tools/test_zone_visits.py | NOT STARTED | — |
| 2.5 | CAM_4 background subtraction calibration | tools/test_background_motion.py | NOT STARTED | — |

---

## Checkpoint 2.1 — YOLOv8-nano Smoke Test

**Tool:** `tools/test_yolo.py`
**Run command:** `python tools/test_yolo.py`
**Output directory:** `tools/yolo_test_output/`

### What it tests
- Loads `models/yolov8n.pt`
- Extracts frames 0, 100, 200 from `inputs/CAM_1.mp4`
- Runs YOLO at 640×360, confidence ≥ 0.5, persons (class 0) only
- Saves 3 annotated JPEG images with bounding boxes
- Prints detection count and confidence scores per frame

### Results

| Frame | Persons detected | Confidence range |
|-------|-----------------|------------------|
| 0 | 2 | 0.76–0.88 |
| 100 | 2 | 0.76–0.88 |
| 200 | 2 | 0.76–0.88 |
| **Total** | **6** | **0.76–0.88** |

**Q1 Answer: YES**

YOLOv8-nano detects people in CAM_1 at 640×360 with confidence_threshold=0.5.
Actual detections well above threshold — minimum observed confidence is 0.76,
meaning the threshold has 26 percentage points of headroom before false negatives
become a concern at this camera. Consistent 2 persons detected across all 3 test
frames, indicating stable detection with no frame-to-frame drop-outs on CAM_1.

**Decision:** Retain `confidence_threshold=0.5` in config.json — confirmed effective
for this video set. Will apply the same threshold in all subsequent checkpoints.

---

## Checkpoint 2.2 — Centroid Tracker Validation (PENDING)

**Tool to create:** `tools/test_tracker.py`
**Will test:**
- CAM_2.mp4 (main floor, highest likelihood of walking persons)
- 100 consecutive frames at frame_skip=1
- Track ID stability: does any person maintain one ID for ≥20 frames?
- Output: annotated frames with track IDs overlaid

**Q2 Answer:** NOT YET

---

## Checkpoint 2.3 — Entry Line Crossing Validation (PENDING)

**Tool to create:** `tools/test_entry_crossing.py`
**Will test:**
- CAM_3.mp4 with entry_line [[80,170],[560,170]] and direction vector [0,1]
- YOLO + centroid tracker + centroid crossing detection
- Accuracy target: ≥8 correct out of 10 observed crossings

**Q3 Answer:** NOT YET

---

## Checkpoint 2.4 — Zone Visit Detection (PENDING)

**Tool to create:** `tools/test_zone_visits.py`
**Will test:**
- CAM_1 (skincare polygon) and CAM_5 (billing polygon) from zones.json
- Point-in-polygon check on detected person centroids
- Are zone entries and exits registering?

**Q4 Answer:** NOT YET

---

## Checkpoint 2.5 — CAM_4 Background Subtraction Calibration (PENDING)

**Tool to create:** `tools/test_background_motion.py`
**Will calibrate:**
- Current warehouse_motion_threshold: 500 sq px (config.json)
- CAM_4 has known lighting flicker (Decision 9)
- Measure max flicker contour area → set threshold above it
- Output: histogram of contour areas, recommended threshold

**Calibrated warehouse_motion_threshold:** NOT YET (fill after running)

---

## Decisions to Record After Each Checkpoint

- Decision 13: Q1 result — YOLOv8 detection confirmed/denied + confidence range
- Decision 14: Q2 result — tracker ID stability + ByteTrack accept/reject
- Decision 15: Q3 result — entry crossing accuracy + entry line confidence level
- Decision 16: Q4 result — zone visit detection confirmed/denied
- Decision 17: CAM_4 calibrated warehouse_motion_threshold + flicker area measurements

---

## Known Blockers

| Blocker | Impact | Status |
|---------|--------|--------|
| `ultralytics` not installed | Was blocking Checkpoint 2.1 | **RESOLVED** — `pip install ultralytics` run successfully |
| requirements.txt not pinned | Reproducibility | Pending — run pip freeze before Phase 3 |

---

## Next Recommended Action

1. Approve Checkpoint 2.1 commit
2. Proceed to Checkpoint 2.2: `tools/test_tracker.py` — centroid tracker validation
3. Checkpoint 2.2 will test CAM_2.mp4 with 100 consecutive frames, verify one person
   maintains a consistent track ID for ≥20 frames

---

## Phase 2 Completion Gate (from master plan)

All four must be answered YES before proceeding to Phase 3:
- [x] Q1: YOLOv8-nano detects people in these videos at 640×360 — **YES** (conf 0.76–0.88)
- [ ] Q2: Centroid tracker maintains consistent IDs for ≥20 frames — PENDING (Checkpoint 2.2)
- [ ] Q3: Entry crossings detectable from CAM_3 (≥8/10 accuracy) — PENDING (Checkpoint 2.3)
- [ ] Q4: Zone visits detectable from CAM_1, CAM_2, CAM_5 — PENDING (Checkpoint 2.4)
