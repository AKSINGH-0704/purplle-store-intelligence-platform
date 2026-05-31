# PHASE 0 REPORT — Purplle Store Intelligence Platform

Generated: 2026-05-31
Agent: Claude Sonnet 4.6 (claude-sonnet-4-6)
Phase: 0 — Prerequisites, Zone Extraction, and Project Scaffolding
Status: Scaffolding COMPLETE — manual validation pending

---

## FILES CREATED

| File | Description | Status |
|------|-------------|--------|
| `config.json` | All 13 system parameters from master plan Section 6 | COMPLETE |
| `zones.json` | 5-camera template with TODO markers, no fabricated coordinates | COMPLETE (template) |
| `requirements.txt` | 7 dependencies, opencv-python-headless, version bounds | COMPLETE (pinning pending) |
| `decisions_log.txt` | 6 decisions recorded | COMPLETE |
| `README.md` | Project overview, architecture placeholder, data sources, disclaimers, What To Look For | COMPLETE |
| `PROGRESS.md` | Phase tracker, completed/pending tasks, blockers, next actions | COMPLETE |
| `PHASE0_REPORT.md` | This file | COMPLETE |
| `.gitignore` | Excludes *.mp4, __pycache__/, *.pyc, .env, logs/, *.egg-info/, .DS_Store | COMPLETE |
| `src/__init__.py` | Empty init for Python package | COMPLETE |
| `src/detection.py` | Docstring placeholder — YOLOv8 detection + centroid tracker | COMPLETE (placeholder) |
| `src/background_motion.py` | Docstring placeholder — CAM 4 MOG2 background subtraction | COMPLETE (placeholder) |
| `src/zone_classifier.py` | Docstring placeholder — polygon membership checks | COMPLETE (placeholder) |
| `src/entry_counter.py` | Docstring placeholder — CAM 3 entry line crossing | COMPLETE (placeholder) |
| `src/session_manager.py` | Docstring placeholder — dwell time + session merge | COMPLETE (placeholder) |
| `src/staff_filter.py` | Docstring placeholder — 3-rule staff heuristic | COMPLETE (placeholder) |
| `src/funnel.py` | Docstring placeholder — aggregate funnel + monotonicity validation | COMPLETE (placeholder) |
| `src/anomalies.py` | Docstring placeholder — 5 anomaly detectors | COMPLETE (placeholder) |
| `src/csv_analytics.py` | Docstring placeholder — revenue intelligence from POS CSV | COMPLETE (placeholder) |
| `src/api.py` | Docstring placeholder — FastAPI endpoints | COMPLETE (placeholder) |
| `src/dashboard.py` | Docstring placeholder — Streamlit 5-tab dashboard | COMPLETE (placeholder) |
| `src/utils.py` | Docstring placeholder — logging, hashing, config loading | COMPLETE (placeholder) |

---

## FOLDERS CREATED

| Folder | Purpose |
|--------|---------|
| `src/` | All Python source modules |
| `models/` | YOLO weights (yolov8n.pt to be placed here — NOT yet present) |
| `events/` | Precomputed events.json and video_hashes.json (to be generated in Phase 3) |
| `data/` | POS CSV file (Brigade_Bangalore_10_April_26.csv to be placed here) |

**Not yet created** (created on first use):
- `inputs/` — video files placed here when running; excluded from git via .gitignore
- `logs/` — runtime log files; excluded from git via .gitignore

---

## DECISIONS MADE DURING SCAFFOLDING

### Decision 1 — Project Structure
Follows master plan Section 24 exactly. No deviation without updating the plan.

### Decision 2 — opencv-python-headless over opencv-python
opencv-python-headless has no Qt/GUI dependency, installs faster, produces a smaller
Docker image, and avoids X11 errors in headless containers. Trade-off: cv2.imshow()
is unavailable; all visualisation must use file output.

### Decision 3 — zones.json as template with TODO markers
Polygon coordinates were NOT fabricated. Empty arrays with clear TODO markers are used.
Rationale: fabricated coordinates would produce silently wrong zone classifications.
An empty template that fails loudly is safer than fake data that silently corrupts metrics.

### Decision 4 — CAM 4 uses background subtraction (architectural decision)
MOG2 background subtraction, not YOLOv8, for the warehouse zone. Appropriate for
activity detection (not customer identification). Minimum contour area threshold
filters lighting noise. Configurable via warehouse_motion_threshold in config.json.

### Decision 5 — Centroid tracker as primary, ByteTrack as fallback
Centroid tracker chosen for zero external dependency chain. ByteTrack is a conditional
fallback subject to Phase 2 validation on actual hardware.

### Decision 6 — requirements.txt version bounds (not pinned yet)
Pinning deferred until pip install is run on actual development machine. Pinning to
exact versions without testing may create impossible dependency combinations.

---

## ASSUMPTIONS MADE

| # | Assumption | Impact if Wrong | Validation Action |
|---|------------|-----------------|-------------------|
| 1 | zones.json polygons will be extractable from Brigade_Road_Store_layout.xlsx and/or video frames | Pipeline cannot run; zone metrics will be wrong | Open Excel file in Phase 0; inspect video frames; use visualise_zones.py |
| 2 | CAM 3 camera angle allows entry_line placement and direction vector determination | Entry counting will be wrong; entire funnel top is incorrect | Inspect CAM_3 video; validate against 10 actual crossings in Phase 2 |
| 3 | YOLOv8-nano can detect people in these videos at 640x360 on CPU | Detection may be unreliable; all customer metrics affected | Phase 2 validation test on actual machine |
| 4 | CSV columns match master plan Section 2.2 (order_id, GMV, NMV, etc.) | csv_analytics.py will error on missing columns | Open CSV and verify column names before Phase 3 |
| 5 | Video files are named CAM_1.mp4 through CAM_5.mp4 in inputs/ | process_videos.py will fail to find files | Confirm actual file names when placing videos |
| 6 | requirements.txt dependencies are compatible on the development machine | pip install will fail; pipeline cannot run | Run pip install and verify; pin versions after success |
| 7 | Processing 1000 frames per camera is feasible in the available time budget | Phase 3 runs over; submission risk | Test on actual machine in Phase 2; adjust max_frames_per_camera if needed |

---

## REMAINING PHASE 0 TASKS

(Manual tasks — cannot be completed by AI scaffolding)

1. Open Brigade_Road_Store_layout.xlsx. Time budget: 30 minutes.
   Record: does it contain machine-readable coordinates? If not, extraction must
   come from video frames.

2. Open each of the 5 video files briefly (10 seconds per camera).
   Record: does camera-to-zone mapping match master plan Section 2.1?
   Note any unexpected camera angles.

3. Download yolov8n.pt and place in models/ directory.
   Verify file size is approximately 6MB.

4. Fill in zones.json polygon coordinates after video/Excel inspection.

5. Define entry_line and entry_direction_vector for CAM_3.

6. Create tools/visualise_zones.py (20-line OpenCV script per master plan Section 25).

7. Run pip install -r requirements.txt and pin exact versions.

8. Place Brigade_Bangalore_10_April_26.csv in data/.

9. Verify data/ CSV column names match master plan Section 2.2.

10. Add camera mapping decision to decisions_log.txt.

11. Add zone extraction method decision to decisions_log.txt.

12. Freeze event schema — document exact event dict structure.

---

## MANUAL VALIDATION ITEMS

Before proceeding to Phase 1:

- [ ] Confirm: yolov8n.pt is in models/ (~6MB)
- [ ] Confirm: Brigade_Bangalore_10_April_26.csv is in data/
- [ ] Confirm: video files are accessible (confirm file naming convention)
- [ ] Confirm: zones.json polygon arrays are filled (not empty [])
- [ ] Confirm: zones.json CAM_3 entry_line and entry_direction_vector are filled
- [ ] Confirm: pip install succeeded with no conflicts
- [ ] Confirm: requirements.txt has exact pinned versions
- [ ] Confirm: decisions_log.txt has >= 5 entries recording Phase 0 findings
- [ ] Confirm: Brigade_Road_Store_layout.xlsx inspection outcome recorded
- [ ] Confirm: camera-to-zone mapping verified from actual video, recorded in decisions_log.txt

---

## SELF-AUDIT: PHASE 0 COMPLETION CRITERIA (from master plan Section 25)

| Criterion | Status | Notes |
|-----------|--------|-------|
| Camera mapping confirmed from actual video inspection | BLOCKED | Requires video file access |
| zones.json with polygon visualisation script verifying coordinates | PARTIALLY COMPLETE | Template created; coordinates and visualise_zones.py pending |
| config.json with all fields defined | COMPLETE | All 13 parameters present |
| requirements.txt with pinned versions using opencv-python-headless | PARTIALLY COMPLETE | opencv-python-headless specified; version pinning pending |
| Event schema frozen | PENDING | Master plan Section 16 contracts exist; formal schema freeze pending Phase 2 |
| API contracts frozen with exact field names | DOCUMENTED | Master plan Section 16; to be confirmed against pipeline output |
| All five anomaly rules with implementation notes | COMPLETE | Documented in src/anomalies.py docstring |
| decisions_log.txt started with >= 5 entries | COMPLETE | 6 entries recorded |
| yolov8n.pt downloaded and in models/ | BLOCKED | Requires manual download |

---

## PROJECT TREE (post-scaffolding)

```
D:\Purplle_hackathon\
├── PURPLLE_MASTER_PLAN.md       (source of truth)
├── README.md
├── PROGRESS.md
├── PHASE0_REPORT.md             (this file)
├── config.json
├── zones.json                   (template — coordinates TODO)
├── requirements.txt
├── decisions_log.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── detection.py             (placeholder)
│   ├── background_motion.py     (placeholder)
│   ├── zone_classifier.py       (placeholder)
│   ├── entry_counter.py         (placeholder)
│   ├── session_manager.py       (placeholder)
│   ├── staff_filter.py          (placeholder)
│   ├── funnel.py                (placeholder)
│   ├── anomalies.py             (placeholder)
│   ├── csv_analytics.py         (placeholder)
│   ├── api.py                   (placeholder)
│   ├── dashboard.py             (placeholder)
│   └── utils.py                 (placeholder)
├── models/
│   └── (yolov8n.pt — NOT YET DOWNLOADED)
├── events/
│   └── (events.json and video_hashes.json — generated in Phase 3)
└── data/
    └── (Brigade_Bangalore_10_April_26.csv — NOT YET PLACED)
```

Files NOT yet present (per master plan Section 24, deferred to later phases):
- process_videos.py (Phase 3)
- Dockerfile.api (Phase 6)
- Dockerfile.dashboard (Phase 6)
- docker-compose.yml (Phase 6)
- DESIGN.md (Phase 7)
- CHOICES.md (Phase 7)
- tools/visualise_zones.py (Phase 0 manual task, deferred)

---

## RESUMABILITY CONFIRMATION

This repository is in a resumable state. A future AI agent can continue using:
1. PURPLLE_MASTER_PLAN.md — single source of truth
2. PROGRESS.md — current status, completed tasks, blockers, next actions
3. PHASE0_REPORT.md — this file
4. decisions_log.txt — all decisions with rationale

No implementation code has been written. All src/ files contain only module
docstrings describing future responsibilities. No business logic, no detection
code, no API code, no dashboard code, no Docker configuration.
