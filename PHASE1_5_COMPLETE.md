# PHASE 1.5 COMPLETE — Zone Calibration and Entry Line Finalization

Phase: 1.5 — Zone Calibration Checkpoint
Status: COMPLETE
Completed: 2026-05-31
Commit: pending (awaiting approval)
Branch: master
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## What Was Done

Zone polygon coordinates and the CAM_3 entry line were derived using visualise_zones.py,
reviewed against actual video frames, manually adjusted where needed, and approved
by the human reviewer. zones.json is now LOCKED — do not modify coordinates without
re-running visualise_zones.py and recording the change in decisions_log.txt.

---

## Final Approved Zones

| Camera | Zone | Polygon corners (x1,y1)→(x2,y2) | Entry Line | Direction Vector | Status |
|--------|------|----------------------------------|------------|-----------------|--------|
| CAM_1 | skincare | (20,80)→(620,350) | — | — | APPROVED |
| CAM_2 | main_floor | (10,60)→(630,355) | — | — | APPROVED |
| CAM_3 | entrance | (80,60)→(560,355) | y=170, x=80→560 | [0,1] | APPROVED |
| CAM_4 | warehouse | (10,30)→(630,355) | — | — | APPROVED |
| CAM_5 | billing | (10,60)→(420,355) | — | — | APPROVED |

All coordinates are in pixel space at 640×360 resolution.

---

## Key Calibration Decisions

**CAM_3 entry line:** Horizontal at y=170, spanning x=80 to x=560 (aligned to polygon edges).
Placed just inside the glass door threshold as observed in frame 100.

**CAM_3 direction vector [0,1]:** Top-to-bottom (increasing y) = entering the store.
Bottom-to-top = exiting. Consistent with camera orientation: exterior at top of frame,
store interior at bottom.

**CAM_5 right boundary at x=420:** Deliberately excludes the product display screen area
(x=420–640) which has no queue relevance and would introduce false detections.

**CAM_4 note:** Near-full-frame coverage (88%). Lighting flicker still requires
warehouse_motion_threshold calibration in Phase 2 (see decisions_log.txt Decision 9).
Polygon itself is approved — the threshold is a separate config.json tuning task.

---

## Completed Deliverables

| File | Description |
|------|-------------|
| `ZONE_CALIBRATION_REPORT.md` | Per-camera calibration notes, geometry analysis, assumptions, limitations, re-calibration procedure |
| `decisions_log.txt` | Decision 11 added: zone calibration finalized, all coordinates APPROVED |
| `PROGRESS.md` | Phase 1.5 COMPLETE, Phase 2 READY TO START |
| `PHASE1_5_COMPLETE.md` | This file |

**No new code written. zones.json coordinates not modified by this checkpoint.**

---

## Remaining Blockers Before Phase 2

| Blocker | Impact | Status |
|---------|--------|--------|
| zones.json polygon coordinates | ~~Primary blocker~~ | **RESOLVED — Decision 11** |
| CAM_3 entry_line and direction_vector | ~~Primary blocker~~ | **RESOLVED — Decision 11** |
| CAM_4 warehouse_motion_threshold calibration | False positive motion events from flicker | OPEN — Phase 2 task |
| requirements.txt exact version pinning | Reproducibility | OPEN — do before Phase 2 pip install |

The two primary Phase 2 blockers are now resolved. The remaining two are Phase 2 tasks,
not prerequisites.

---

## Next Recommended Phase

**Phase 2 — CV Validation (2–3 hours)**

All prerequisites are now met:
- zones.json has finalized, approved coordinates ✓
- yolov8n.pt is in models/ ✓
- CSV is in data/ ✓
- Video files expected in inputs/

Phase 2 must answer four questions (from master plan Section 25):
1. Does YOLOv8-nano detect people in these videos at 640×360?
2. Does the centroid tracker maintain one consistent ID for ≥20 consecutive processed frames?
3. Are entry crossings detectable from CAM_3? (Validate against ≥10 actual crossings)
4. Are zone visits detectable from CAM_1, CAM_2, CAM_5?

Phase 2 additional tasks:
- Calibrate CAM_4 warehouse_motion_threshold against actual flicker contour areas
- Verify CAM_3 entry line at y=170 produces correct entry/exit classification
- Pin requirements.txt to exact versions
- Record all validation results in decisions_log.txt

Trigger phrase to start Phase 2:
> "Phase 1.5 complete. Proceed with Phase 2 CV Validation."

---

## Recovery Instructions for Future AI Sessions

### Files to read in order:
1. `PURPLLE_MASTER_PLAN.md` — single source of truth
2. `PROGRESS.md` — current phase and status
3. `PHASE1_COMPLETE.md` — what Phase 1 delivered
4. `PHASE1_5_COMPLETE.md` — this file (zone calibration checkpoint)
5. `ZONE_CALIBRATION_REPORT.md` — final zone coordinates and calibration notes
6. `decisions_log.txt` — 11 decisions recorded

### Current zones.json state:
All polygons are filled with real coordinates. CAM_3 has entry_line and entry_direction_vector.
**Do not modify zones.json coordinates** without re-running visualise_zones.py and
adding a new decision to decisions_log.txt.

### Key locks:
- zones.json coordinates: LOCKED (Decision 11)
- CAM_4: background subtraction only, warehouse_motion_threshold needs Phase 2 calibration
- Centroid tracker primary; ByteTrack conditional on Phase 2 validation
- No cross-camera person tracking
- All config values in config.json — no magic numbers in code

### What Phase 2 does NOT require from this agent:
Phase 2 is primarily a validation and calibration exercise run on the actual machine
with the actual video files. It does not require new documentation files — it produces
decisions_log.txt entries and updates to config.json (warehouse_motion_threshold).
