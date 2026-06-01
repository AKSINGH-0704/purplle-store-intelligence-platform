# PURPLLE STORE INTELLIGENCE PLATFORM — PROGRESS TRACKER

Last Updated: 2026-06-02
Current Phase: Phase 6 — COMPLETE
Current Status: Docker deployment configuration complete. Separate API and dashboard images on python:3.11-slim. events/ bind-mounted read-only; dashboard depends_on api condition:service_healthy; API_BASE_URL=http://api:8000. 50/50 validation checks pass.
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
| 2 | CV Validation | **COMPLETE** | All 5 checkpoints done. config.json calibrated. Phase 3 ready. |
| 3 | Backend and Event Pipeline | **COMPLETE** | All 6 checkpoints — commits 70f3959, 5b7e5bf, 7b5b9c8, 8423d8a, d042f03, d5a5ee8, a88819f |
| 4 | API Development | **COMPLETE** | Single checkpoint — commit 9e91023 |
| 5 | Dashboard | **COMPLETE** | Single checkpoint -- commit fea0865 |
| 6 | Docker and Processing Script | **COMPLETE** | Single checkpoint -- commits 899309e, (docs commit) |
| 7 | Documentation | NOT STARTED | — |

---

## PHASE 2 — IN PROGRESS

- [x] Checkpoint 2.1: tools/test_yolo.py — COMPLETE. Q1 = YES. 6 detections, conf 0.76–0.88 (Decision 13)
- [x] Created PHASE2_ENVIRONMENT_CHECK.md — ultralytics install resolved
- [x] Checkpoint 2.2: tools/test_tracker.py — COMPLETE. Q2 = YES. Longest track 200f, 3 tracks ≥20f. ByteTrack REJECTED. (Decision 14)
- [~] Checkpoint 2.3: tools/test_entry_counter_v2.py — PARTIAL PASS (CLOSED). Gate proven across 720 proc frames (81% of video). 0 genuine crossings in available footage. Sensitivity validated in Phase 3. (Decision 15)
- [x] Checkpoint 2.4: tools/test_zone_visits.py -- PASS. CAM_1: 2v/33.4s, CAM_2: 5v/26.6s, CAM_5: 2v/27.3s. Pipeline validated. (Decision 16)
- [x] Checkpoint 2.5: tools/test_warehouse_motion.py — COMPLETE. Q5 = PASS. warehouse_motion_threshold = 1631 sq px (p99 flicker × 1.30). False positive rate reduced from 99% → ~0-1%. (Decision 17)

**Next action:** Phase 2 COMPLETE. All checkpoints done. Phase 3 Checkpoint 3.1 complete.

---

## PHASE 3 — IN PROGRESS

- [x] Checkpoint 3.1: Foundation layer — commit 70f3959
  - src/utils.py: load_config, load_zones, compute_sha256, write_hashes, verify_hashes, get_logger, LOG_BUFFER, format_duration, all event schema factories, append_event
  - src/zone_classifier.py: point_in_polygon (ray-casting), classify_zone
  - zones.json: CAM_3 door_x_gate=[250,490] added (Decision 15 carry-forward)
  - tools/validate_checkpoint_31.py: 13/13 checks pass; all 5 video hashes computed
- [x] Checkpoint 3.2: Detection layer — commit 5b7e5bf
  - src/detection.py: run_detection() generator; YOLO + centroid tracker; CAM_1/2/3/5
  - src/background_motion.py: run_background_motion(); MOG2 + warm-up suppression; CAM_4
  - CAM_4 full recalibration (Decision 18): polygon y=355->246; threshold 1631->28085
  - 451 false-positive events eliminated; 2 confirmed genuine events remain (t=92.3s)
  - tools/validate_checkpoint_32.py: 12/12 checks pass
- [x] Checkpoint 3.3A: Session manager — src/session_manager.py — commit 7b5b9c8
  - run_zone_visits(): zone entry/exit/dwell for CAM_1, CAM_2, CAM_5
  - Dwell merge rule (4-condition identity gate), disappeared-track policy (Option A)
  - tools/validate_checkpoint_33a.py: 12/12 checks pass; Phase 2 ground truth matched
- [x] Checkpoint 3.3B: Entry counter — src/entry_counter.py — commit 8423d8a
  - run_entry_crossings(): CAM_3 line crossing with door x-gate [250,490] and direction classification
  - _check_crossing(): extracted private helper; directly testable by validator
  - camera_id guard (ValueError for non-CAM_3)
  - tools/validate_checkpoint_33b.py: 12/12 checks pass (synthetic logic + smoke run)
  - Q3 status: mechanics validated; sensitivity unverified (0 crossings in Phase 2 footage)
- [x] Checkpoint 3.4: Staff filter + CSV analytics — src/staff_filter.py, src/csv_analytics.py — commit d042f03
  - run_staff_filter(): 3 rules; runtime output is authoritative (not events.json flag)
  - Rule 1 (roundtrip) dead code on current footage (0 CAM_3 crossings); Rules 2+3 operational
  - run_csv_analytics(): 24 transactions, GMV 44,920, 6 categories, 5 salespeople — all 11 metrics
  - tools/validate_checkpoint_34.py: 12/12 checks pass; Decision 19 recorded
- [x] Checkpoint 3.5: Funnel + anomaly detectors — src/funnel.py, src/anomalies.py — commit d5a5ee8
  - run_funnel(): 5-stage aggregate funnel; monotonicity validation (warning on current footage — CAM_3 Q3)
  - run_anomalies(): 5 detectors; [] on current footage (expected — thresholds not exceeded in 1000-frame window)
  - tools/validate_checkpoint_35.py: 18/18 checks pass (synthetic fixtures; all boundary conditions tested)
  - Decision 20 recorded: Anomaly 3 reframed (wall-clock time unavailable from frame timestamps)
- [x] Checkpoint 3.6: Orchestrator — process_videos.py — commit a88819f
  - Full pipeline: 51 events, 142.6s, exit 0, no validation warnings
  - CAM_4 full-video override: genuine warehouse events at t=92.3s captured
  - Anomaly 3 fires (unusual_warehouse_activity — 2 motion frames, both restocking)
  - pipeline_summary.json: all 8 required keys; fully JSON-serializable
  - events/events.json, events/video_hashes.json committed as sample pipeline output
  - tools/validate_checkpoint_36.py: 12/12 checks pass (8 structural + 4 end-to-end)
  - Decision 21 recorded: CAM_4 max_frames override in orchestrator

**Phase 3 COMPLETE.**

## PHASE 4 -- COMPLETE

- [x] Checkpoint 4: FastAPI endpoints -- src/api.py -- commit 9e91023
  - All 7 endpoints: /health, /metrics, /funnel, /anomalies, /zone_metrics/{zone}, /events/sample, /dashboard
  - Option C: pipeline_summary.json + events.json loaded once at startup; all responses from _state dict
  - total_dwell_seconds derived directly from zone_dwell events (Option b -- exact sum)
  - CORS middleware, HTTP request logging middleware, lifespan startup, 404 with valid_zones
  - Rerunning process_videos.py requires API restart (documented in PHASE4_REPORT.md)
  - tools/validate_checkpoint_4.py: 18/18 checks pass (TestClient, all endpoints, response times)

**Phase 4 COMPLETE.**

## PHASE 5 -- COMPLETE

- [x] Checkpoint 5: Streamlit dashboard -- src/dashboard.py -- commit fea0865
  - 5 tabs: Executive Overview, Customer Journey, Zone Intelligence, Revenue Intelligence, System Health
  - Single @st.cache_data(ttl=60) fetch_dashboard() call feeds all tabs
  - Plotly go.Funnel for stages 2-4; entry (0) and transactions (24) as separate st.metric cards
  - st.warning() for funnel_validation=="warning"; full disclaimer always visible (Tab 2)
  - total_dwell_seconds from API zone_totals key (Option b -- server-side exact sum, not avg*count)
  - API failure: requests.RequestException + st.error() + st.stop() prevents partial render
  - api.py: zone_totals added to /dashboard response to support exact consumption
  - requirements.txt: plotly>=5.0.0 added
  - tools/validate_checkpoint_5.py: 17/17 structural checks pass

**Phase 5 COMPLETE.**

---

## PHASE 6 -- COMPLETE

- [x] Checkpoint 6: Docker deployment configuration -- commits 899309e, (docs)
  - .dockerignore: excludes inputs/ (648 MB), .git/, __pycache__, .env
  - requirements-api.txt: fastapi + uvicorn[standard] only (~165 MB image)
  - requirements-dashboard.txt: streamlit, plotly, pandas, requests (~548 MB image)
  - Dockerfile.api: python:3.11-slim; src/ copied; events/ + logs/ as volumes; uvicorn CMD
  - Dockerfile.dashboard: python:3.11-slim; dashboard.py only; headless Streamlit on 8501
  - docker-compose.yml: api (port 8000) + dashboard (port 8501); depends_on service_healthy;
    API_BASE_URL=http://api:8000; events/:ro bind-mount; urllib healthchecks; no GPU
  - tools/validate_checkpoint_6.py: 50/50 structural checks pass

**Pending: docker compose build + up verification (real Docker run) before Phase 7.**

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
