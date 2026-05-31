# PHASE 1 COMPLETE

Phase: 1 — Business Logic Design and Documentation
Status: COMPLETE
Completed: 2026-05-31
Commit: 4160a0e298f87286601756819c78250edd33953a
Branch: master
Repository: https://github.com/AKSINGH-0704/purplle-store-intelligence-platform.git

---

## COMPLETED DELIVERABLES

| Deliverable | File | Notes |
|-------------|------|-------|
| Full system architecture document | `DESIGN.md` | 16 sections, 3 Mermaid diagrams, event schema frozen |
| Engineering decisions skeleton | `CHOICES.md` | 12 sections, sourced from decisions_log.txt |
| Zone polygon visualisation tool | `visualise_zones.py` | Extracts frame 100, overlays zones.json, saves to zones_preview/ |
| Phase 1 report | `PHASE1_REPORT.md` | Completion checklist, blockers, resumability notes |
| Config update | `config.json` | Added staff_roundtrip_threshold (3) and staff_roundtrip_window_minutes (30) |
| Decisions log update | `decisions_log.txt` | Decisions 8 (Excel image-only), 9 (CAM 4 flicker), 10 (CSV rename) |
| CSV file | `data/Brigade_Bangalore_10_April_26.csv` | Renamed from download artifact; 44.9 KB |
| YOLO weights | `models/yolov8n.pt` | 6.2 MB; bundled for Docker offline operation |

### What DESIGN.md contains

- Executive summary
- Store layout ground truth (image-only Excel finding)
- Three Mermaid diagrams: full pipeline, Docker deployment, startup sequence
- Complete config.json parameter table with rationale for every value
- zones.json structure and polygon derivation workflow
- Detection strategy: YOLOv8-nano rationale + CAM 4 background subtraction with calibration note
- Tracking strategy: centroid tracker algorithm, ByteTrack comparison, dwell merge rule
- Zone event layer: entry line crossing, dwell detection, motion events
- Event schema (frozen) — 4 event types with full JSON structure
- Three intelligence layers with per-layer metric tables
- Business logic: funnel, monotonicity validation, staff filtering (3 rules), 5 anomalies
- API design: 7 endpoints with field names
- Docker architecture: two-service, HEALTHCHECK, API_BASE_URL
- Dashboard structure: all 5 tabs with specific content
- Integrity defence: SHA256 hashing workflow
- Honest limitations table
- Future architecture roadmap (5 items)

### What CHOICES.md contains

Skeleton with 12 sections, each cross-referencing the decisions_log.txt entry:
1. Repository Structure (#1)
2. Dependency Choices (#2, #6)
3. Zone Configuration (#3, #8)
4. Detection Strategy (#4, #9)
5. Tracking Strategy (#5)
6. Camera Zone Mapping (#7)
7. Aggregate Funnel Design
8. Staff Filtering
9. Startup vs Processing Separation
10. Docker Architecture
11. Integrity Defence
12. Future Architecture Roadmap

Sections 4, 5, 6, 8, 11 have TODO markers for Phase 2/3 calibration values and test results.
CHOICES.md is assembled from decisions_log.txt in Phase 7 — the skeleton is the scaffold.

---

## DECISIONS RECORDED (decisions_log.txt now has 10 entries)

| # | Decision | Phase |
|---|----------|-------|
| 1 | Project structure follows master plan Section 24 | 0 |
| 2 | opencv-python-headless over opencv-python | 0 |
| 3 | zones.json template with TODO markers, no fabricated coordinates | 0 |
| 4 | CAM 4 uses background subtraction, not YOLO | 0 |
| 5 | Centroid tracker as primary; ByteTrack conditional fallback | 0 |
| 6 | requirements.txt version bounds, exact pinning deferred | 0 |
| 7 | Camera-to-zone mapping confirmed from direct video inspection | 0 (manual) |
| 8 | Excel layout = image only; frame extraction required for polygons | 1 |
| 9 | CAM 4 flicker observed; warehouse_motion_threshold calibration mandatory in Phase 2 | 1 |
| 10 | CSV filename normalised from download artifact to canonical name | 1 |

---

## KNOWN BLOCKERS FOR PHASE 2

| Blocker | Impact | Resolution |
|---------|--------|-----------|
| zones.json polygon coordinates still empty | Zone classification returns no results; all zone metrics = 0 | Run `python visualise_zones.py` after placing videos in inputs/, then fill coordinates iteratively |
| CAM_3 entry_line and entry_direction_vector still empty | Entry count = 0; entire customer funnel broken | Inspect CAM_3 frame from visualise_zones.py output, define line + vector |
| requirements.txt not yet pinned to exact versions | Reproducibility not guaranteed across machines | `pip install -r requirements.txt` then `pip freeze > requirements_pinned.txt` |
| CAM 4 warehouse_motion_threshold not calibrated | False positive motion events from lighting flicker | Phase 2 calibration: measure flicker contour area from quiet CAM_4 frames, set threshold above max |

---

## NEXT RECOMMENDED PHASE

**Phase 2 — CV Validation (2–3 hours)**

Phase 2 must answer four questions:
1. Does YOLOv8-nano detect people in these videos at 640×360 on this machine?
2. Does the centroid tracker maintain one consistent ID for ≥ 20 consecutive processed frames?
3. Can entry crossings be detected from CAM_3 — at least N correct out of 10 test crossings?
4. Can zone visits be detected from CAM_1, CAM_2, CAM_5?

Additional Phase 2 tasks:
- Run `python visualise_zones.py` and fill polygon coordinates in zones.json
- Calibrate warehouse_motion_threshold for CAM_4 (measure flicker contour area)
- Finalise entry_line and entry_direction_vector for CAM_3
- Pin requirements.txt to exact versions

Phase 2 completion gate: all four validation questions answered positively and results recorded in decisions_log.txt. Do not begin Phase 3 until all are answered.

Trigger phrase to start Phase 2:
> "Phase 1 complete. Proceed with Phase 2 CV Validation."

---

## RECOVERY INSTRUCTIONS FOR FUTURE AI SESSIONS

If this project is resumed by a new AI agent or after context loss:

### Step 1 — Read these files in order:
1. `PURPLLE_MASTER_PLAN.md` — single source of truth
2. `PROGRESS.md` — current phase status and next action
3. `PHASE1_COMPLETE.md` — this file
4. `decisions_log.txt` — 10 decisions recorded with full rationale

### Step 2 — Check state:
```
tree /f
```
Expected files now present: DESIGN.md, CHOICES.md, visualise_zones.py,
data/Brigade_Bangalore_10_April_26.csv, models/yolov8n.pt.

### Step 3 — Verify zones.json status:
- Open `zones.json`. Are polygon arrays still `[]`? If yes, Phase 2 polygon extraction needed.
- If polygons are filled: Phase 2 can run CV validation tests.

### Step 4 — Resume from correct phase:
- zones.json empty → use visualise_zones.py to extract and fill coordinates
- zones.json filled → Phase 2 CV validation tests can run
- Phase 2 complete → proceed to Phase 3 (Backend and Event Pipeline)

### Key locks (do not change without strong reason and decisions_log.txt entry):
- CAM_4: background subtraction only, not YOLO
- Centroid tracker primary, ByteTrack conditional on Phase 2 test
- No cross-camera person tracking — aggregate zone counts only
- zones.json coordinates must come from video frames, never invented
- events.json loaded at startup; process_videos.py is separate optional command
- opencv-python-headless in requirements.txt, not opencv-python
- All config values in config.json — no magic numbers in code

### What NOT to do:
- Do not fabricate zone polygon coordinates
- Do not write detection, tracking, API, or dashboard code before Phase 3/4/5
- Do not create Dockerfiles before Phase 6
- Do not skip Phase 2 validation — the completion gate is mandatory
