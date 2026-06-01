# PURPLLE STORE INTELLIGENCE PLATFORM — PROGRESS TRACKER

Last Updated: 2026-05-31
Current Phase: Phase 1.5 Zone Calibration — COMPLETE / Phase 2 — READY TO START
Current Status: All zones finalized and approved. zones.json LOCKED. Phase 2 CV validation can begin.
Phase 0 Git Commit: a612c5bfdea01f0e427c527a35ee2387e9a5e7f7
Phase 1 Git Commit: 4160a0e298f87286601756819c78250edd33953a
Phase 1.5 Commit: 94d0da359bab04fb934f3c21f36ddb01519a5e6f
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## OVERALL PHASE TRACKER

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Prerequisites and Zone Extraction | COMPLETE | Committed a612c5b; yolov8n.pt + CSV confirmed present |
| 1 | Business Logic Design | COMPLETE | Committed 4160a0e; DESIGN.md, CHOICES.md, visualise_zones.py |
| 1.5 | Zone Calibration | COMPLETE | All 5 zones approved; zones.json LOCKED; Decision 11 recorded |
| 2 | CV Validation | IN PROGRESS | Checkpoints 2.1 + 2.2 COMPLETE — awaiting Checkpoint 2.3 instructions |
| 3 | Backend and Event Pipeline | NOT STARTED | — |
| 4 | API Development | NOT STARTED | — |
| 5 | Dashboard | NOT STARTED | — |
| 6 | Docker and Processing Script | NOT STARTED | — |
| 7 | Documentation | NOT STARTED | — |

---

## PHASE 2 — IN PROGRESS

- [x] Checkpoint 2.1: tools/test_yolo.py — COMPLETE. Q1 = YES. 6 detections, conf 0.76–0.88 (Decision 13)
- [x] Created PHASE2_ENVIRONMENT_CHECK.md — ultralytics install resolved
- [x] Checkpoint 2.2: tools/test_tracker.py — COMPLETE. Q2 = YES. Longest track 200f, 3 tracks ≥20f. ByteTrack REJECTED. (Decision 14)
- [ ] Checkpoint 2.3: tools/test_entry_crossing.py — entry line crossing validation
- [ ] Checkpoint 2.4: tools/test_zone_visits.py — zone visit detection
- [ ] Checkpoint 2.5: tools/test_background_motion.py — CAM_4 MOG2 calibration

**Next action:** Approve Checkpoint 2.2 commit → create Checkpoint 2.3 (entry line crossing).

---

## PHASE 1.5 — COMPLETED TASKS (Zone Calibration)

- [x] Read and verified finalized zones.json — all 5 cameras with real coordinates
- [x] Created ZONE_CALIBRATION_REPORT.md — per-camera notes, geometry, assumptions, limitations
- [x] Updated decisions_log.txt — Decision 11 (zone calibration finalized, CAM_3 entry line approved)
- [x] Created PHASE1_5_COMPLETE.md — completion summary and Phase 2 readiness
- [x] Updated PROGRESS.md (this file)

---

## PHASE 1 — COMPLETED TASKS

- [x] Created DESIGN.md — 16-section full architecture document with 3 Mermaid diagrams
- [x] Created CHOICES.md — 12-section engineering decisions skeleton sourced from decisions_log.txt
- [x] Created visualise_zones.py — zone polygon overlay tool (file output only, no cv2.imshow)
- [x] Updated config.json — added staff_roundtrip_threshold (3) and staff_roundtrip_window_minutes (30)
- [x] Updated decisions_log.txt — added Decision 8 (layout image-only finding) and Decision 9 (CAM 4 flicker calibration)
- [x] Created PHASE1_REPORT.md
- [x] Updated PROGRESS.md (this file)
- [x] Event schema frozen in DESIGN.md Section 8
- [x] API contracts frozen in DESIGN.md Section 11

---

## PHASE 0 — COMPLETED TASKS

- [x] Read and parsed PURPLLE_MASTER_PLAN.md completely
- [x] Created project directory structure: src/, models/, events/, data/
- [x] Created config.json with all 13 default parameters from Section 6
- [x] Created zones.json template — all 5 cameras with intelligence_layer fields,
       TODO markers for polygon coordinates, no fabricated geometry
- [x] Created requirements.txt with 7 dependencies (opencv-python-headless chosen
       over opencv-python for Docker compatibility — see decisions_log.txt Decision 2)
- [x] Created decisions_log.txt with 6 decisions recorded
- [x] Created README.md with project overview, architecture placeholder, data sources,
       disclaimers, limitations, and What To Look For section (7 bullets)
- [x] Created .gitignore excluding *.mp4, __pycache__/, *.pyc, .env, logs/, *.egg-info/, .DS_Store
- [x] Created src/__init__.py
- [x] Created placeholder modules (docstrings only, no business logic):
       src/detection.py, src/background_motion.py, src/zone_classifier.py,
       src/entry_counter.py, src/session_manager.py, src/staff_filter.py,
       src/funnel.py, src/anomalies.py, src/csv_analytics.py,
       src/api.py, src/dashboard.py, src/utils.py
- [x] Created PHASE0_REPORT.md
- [x] Created PROGRESS.md (this file)

---

## PHASE 0 — PENDING TASKS

These tasks require manual action with actual files (cannot be completed by AI scaffolding):

- [ ] Open Brigade_Road_Store_layout.xlsx — determine if machine-readable coordinates
       exist or if manual polygon extraction from video frames is needed.
       Time budget: 30 minutes max (per master plan).
- [ ] Open each video file briefly to confirm camera-to-zone mapping matches
       expectations (5 cameras × brief inspection).
- [ ] Download yolov8n.pt (~6MB) and place in models/ directory.
       Command: python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
       (Ultralytics auto-downloads on first use; move the cached file to models/)
- [ ] Fill in zones.json polygon coordinates after video/Excel inspection.
       Use tools/visualise_zones.py (to be created in Phase 0 or early Phase 2)
       to overlay polygons on actual video frames and verify accuracy visually.
- [ ] Define entry_line and entry_direction_vector for CAM_3 in zones.json
       after inspecting camera angle from actual video.
- [ ] Pin exact dependency versions in requirements.txt:
       pip install -r requirements.txt && pip freeze > requirements_pinned.txt
       Then replace requirements.txt content with pinned output.
- [ ] Create tools/visualise_zones.py — a 20-line OpenCV script that draws
       zones.json polygons overlaid on a video frame from each camera.
       (Master plan Section 25 Phase 0: "Write a 20-line OpenCV polygon
       visualisation script...")
- [ ] Record camera mapping rationale in decisions_log.txt after video inspection.
- [ ] Record zone extraction method in decisions_log.txt (Excel vs frame extraction).
- [ ] Verify decisions_log.txt has >= 5 entries (currently has 6 — condition met
       once the camera mapping decision is added from actual inspection).
- [ ] Freeze event schema (document in decisions_log.txt or separate schema file).
- [ ] Freeze API contracts with exact field names (master plan Section 16 contracts
       are documented but should be cross-checked against actual pipeline output).
- [ ] Write all five anomaly rules with implementation notes (done in src/anomalies.py
       docstring — verify against actual data after Phase 2).

---

## PHASE 0 COMPLETION CRITERIA CHECKLIST
(from master plan Section 25)

- [ ] Camera mapping confirmed from actual video inspection
- [ ] zones.json created with polygon visualisation script verifying all coordinates
- [x] config.json created with all fields defined
- [ ] requirements.txt created with pinned versions using opencv-python-headless
       (opencv-python-headless is specified; pinning is pending environment install)
- [ ] Event schema frozen
- [ ] API contracts frozen with exact field names
- [ ] All five anomaly rules written with implementation notes
       (documented in src/anomalies.py — verify completeness)
- [ ] decisions_log.txt started with at least 5 entries (6 entries recorded)
- [ ] yolov8n.pt downloaded and in models/ directory

---

## KNOWN BLOCKERS

1. zones.json polygon coordinates — BLOCKED on video file inspection and
   Brigade_Road_Store_layout.xlsx analysis. Cannot proceed with pipeline
   testing until coordinates are filled in.

2. yolov8n.pt — NOT YET DOWNLOADED. Must be placed in models/ before Phase 3
   detection code can run. Size: ~6MB.

3. requirements.txt exact version pinning — BLOCKED until pip install is
   run on the actual development machine.

4. CSV file — data/Brigade_Bangalore_10_April_26.csv not yet placed in data/.
   Must be copied there before Phase 3 csv_analytics.py can be tested.

5. Video files — NOT in repository (correctly excluded by .gitignore).
   Must be accessible at inputs/ path before process_videos.py can run.
   (Note: inputs/ directory not yet created — create when placing video files.)

---

## CURRENT STATUS

Scaffolding complete. All files and directories from master plan Section 24
have been created. The repository is in a resumable state.

Next recommended action: Begin manual Phase 0 validation tasks listed above.
Start with Brigade_Road_Store_layout.xlsx inspection (30 min max), then
brief video file inspection for camera-to-zone mapping confirmation.

---

## NEXT RECOMMENDED ACTION

1. Open Brigade_Road_Store_layout.xlsx. Spend max 30 minutes.
   Record findings in decisions_log.txt under "Camera mapping rationale".
2. Open each video file briefly (5–10 seconds per camera) to confirm zones.
3. pip install -r requirements.txt and verify no conflicts.
4. Run pip freeze and replace requirements.txt with pinned versions.
5. Download yolov8n.pt into models/.
6. Fill in zones.json polygon coordinates.
7. Create tools/visualise_zones.py to verify polygon accuracy.
8. Complete decisions_log.txt entries for camera mapping and zone extraction.

---

## RESUMABILITY GUARANTEE

A future AI agent can resume this project using ONLY:
- PURPLLE_MASTER_PLAN.md (single source of truth)
- PROGRESS.md (this file — current status and next actions)
- PHASE0_REPORT.md (files created, decisions, assumptions)
- decisions_log.txt (all engineering decisions with rationale)
