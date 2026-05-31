# PHASE 1 REPORT — Purplle Store Intelligence Platform

Generated: 2026-05-31
Agent: Claude Sonnet 4.6 (claude-sonnet-4-6)
Phase: 1 — Business Logic Design and Documentation
Status: COMPLETE

---

## FILES CREATED

| File | Description | Status |
|------|-------------|--------|
| `DESIGN.md` | Full system architecture document — 16 sections, Mermaid diagrams | COMPLETE |
| `CHOICES.md` | Engineering decisions skeleton — 12 sections, sourced from decisions_log.txt | COMPLETE |
| `visualise_zones.py` | Zone polygon overlay tool — reads zones.json, saves frames to zones_preview/ | COMPLETE |
| `PHASE1_REPORT.md` | This file | COMPLETE |

---

## FILES MODIFIED

| File | Change | Status |
|------|--------|--------|
| `config.json` | Added `staff_roundtrip_threshold: 3` and `staff_roundtrip_window_minutes: 30` | COMPLETE |
| `decisions_log.txt` | Added Decision 8 (layout image-only), Decision 9 (CAM 4 flicker), Decision 10 (CSV rename) | COMPLETE |
| `PROGRESS.md` | Updated phase tracker, completed tasks, pending tasks, blockers | COMPLETE |
| `data/Brigade_Bangalore_10_April_26.csv` | Renamed from `Brigade_Bangalore_10_April_26 (1)bc6219c.csv` — download artifact in filename corrected. All existing references already used the canonical name; no further edits required. (See decisions_log.txt Decision 10.) | COMPLETE |

---

## PHASE 1 DELIVERABLES AUDIT

### DESIGN.md — Sections Created

| Section | Content | Status |
|---------|---------|--------|
| 1. Executive Summary | Three business questions, design philosophy | COMPLETE |
| 2. Store Layout | Excel inspection result, store geometry from floorplan | COMPLETE |
| 3. System Architecture | Mermaid pipeline diagram, deployment diagram, sequence diagram | COMPLETE |
| 4. Configuration System | config.json parameter table with rationale, zones.json structure | COMPLETE |
| 5. Detection Layer | YOLOv8-nano rationale, CAM 4 background subtraction, calibration warning | COMPLETE |
| 6. Tracking Layer | Centroid tracker algorithm, ByteTrack comparison, dwell merge rule | COMPLETE |
| 7. Zone Event Layer | Entry line crossing, dwell detection, motion events | COMPLETE |
| 8. Event Schema | Frozen — 4 event types with full JSON structure | COMPLETE |
| 9. Three Intelligence Layers | Per-layer metric tables with source columns | COMPLETE |
| 10. Business Logic Layer | Funnel, monotonicity validation, staff filtering, 5 anomalies | COMPLETE |
| 11. API Design | All 7 endpoints, logging design | COMPLETE |
| 12. Docker Architecture | Two-service config, HEALTHCHECK, API_BASE_URL, bundled weights | COMPLETE |
| 13. Dashboard Structure | All 5 tabs with specific content per tab | COMPLETE |
| 14. Integrity Defence | SHA256 hashing, video_hashes.json, verification procedure | COMPLETE |
| 15. Honest Limitations | 7 limitations with plain language explanations | COMPLETE |
| 16. Future Roadmap | 5 roadmap items (ReID, Kafka, multi-store, LLM, staffing) | COMPLETE |

### CHOICES.md — Sections Created

| Section | Source Decision | Status |
|---------|----------------|--------|
| 1. Repository Structure | #1 | COMPLETE (skeleton) |
| 2. Dependency Choices | #2, #6 | COMPLETE (skeleton) |
| 3. Zone Configuration | #3, #8 | COMPLETE (skeleton) |
| 4. Detection Strategy | #4, #9 | COMPLETE (skeleton + TODO for Phase 2 calibration values) |
| 5. Tracking Strategy | #5 | COMPLETE (skeleton + TODO for Phase 2 validation result) |
| 6. Camera Zone Mapping | #7 | COMPLETE (skeleton + TODO for entry line values) |
| 7. Aggregate Funnel Design | design principle | COMPLETE (skeleton) |
| 8. Staff Filtering | config.json values | COMPLETE (skeleton + TODO for Phase 3 counts) |
| 9. Startup vs Processing | design principle | COMPLETE (skeleton) |
| 10. Docker Architecture | design principle | COMPLETE (skeleton) |
| 11. Integrity Defence | design principle + TODO | COMPLETE (skeleton + TODO for Phase 3 hashes) |
| 12. Future Roadmap | master plan Section 22 | COMPLETE |

### visualise_zones.py — Features

| Feature | Status |
|---------|--------|
| Reads zones.json | COMPLETE |
| Extracts frame 100 from each video in inputs/ | COMPLETE |
| Overlays polygon (green) where coordinates exist | COMPLETE |
| Overlays entry_line (orange) where defined | COMPLETE |
| Prints TODO warning for empty coordinates | COMPLETE |
| Saves output to zones_preview/ (file only, no cv2.imshow) | COMPLETE |
| Shows direction vector status alongside entry line | COMPLETE |
| Handles missing video files gracefully (skip with message) | COMPLETE |
| Handles unreadable frames gracefully (skip with message) | COMPLETE |

---

## DECISIONS RECORDED IN PHASE 1

| Decision | Summary |
|----------|---------|
| Decision 8 | Brigade_Road_Store_layout.xlsx contains image only; frame extraction required |
| Decision 9 | CAM 4 warehouse_motion_threshold: keep at 500 default, Phase 2 calibration mandatory due to observed flicker |

config.json additions:
- `staff_roundtrip_threshold: 3` — matches staff filtering Rule 1 (3 roundtrip crossings)
- `staff_roundtrip_window_minutes: 30` — 30-minute window for counting roundtrips

---

## EVENT SCHEMA FROZEN

Four event types are now formally frozen in DESIGN.md Section 8:
1. Zone dwell event (CAM 1, 2, 5)
2. Entry/exit crossing event (CAM 3)
3. Warehouse motion event (CAM 4)
4. Common envelope fields applicable to all events

This schema is the contract between the Phase 3 pipeline and the Phase 4 API. Any change to this schema requires updating DESIGN.md, the Phase 3 event generation code, and the Phase 4 API loading code simultaneously.

---

## API CONTRACTS FROZEN

All 7 API endpoints are documented in DESIGN.md Section 11 with exact field names. Cross-referenced against master plan Section 16. These are the contracts Phase 4 must implement exactly:

- GET /health
- GET /metrics
- GET /funnel
- GET /anomalies
- GET /zone_metrics/{zone}
- GET /events/sample
- GET /dashboard

---

## REMAINING PHASE 1 TASKS

None — all AI-executable Phase 1 tasks are complete.

### Items pending from Phase 0 (still unresolved, now blocking Phase 2)

1. **zones.json polygon coordinates** — still empty. visualise_zones.py is now ready to use.
   Run: `python visualise_zones.py` after placing video files in inputs/
2. **CAM_3 entry_line and entry_direction_vector** — still empty. Required for entry counting.
3. **requirements.txt exact version pinning** — still uses >= bounds.

---

## PHASE 1 COMPLETION CRITERIA (from master plan Section 25 Phase 1)

| Criterion | Status |
|-----------|--------|
| Three intelligence layers designed with specific metrics | COMPLETE — DESIGN.md Section 9 |
| Aggregate funnel logic documented precisely | COMPLETE — DESIGN.md Section 10.1 |
| CAM 4 background subtraction approach documented | COMPLETE — DESIGN.md Section 5.2 |
| Five anomaly rules written with implementation approach | COMPLETE — DESIGN.md Section 10.4 |
| Entry line crossing logic documented | COMPLETE — DESIGN.md Section 7.1 |
| 5-tab dashboard structure designed | COMPLETE — DESIGN.md Section 13 |
| Startup vs processing separation designed | COMPLETE — DESIGN.md Section 3.3 + Section 12 |
| Two-service Docker architecture designed | COMPLETE — DESIGN.md Section 12 |
| DESIGN.md template generated | COMPLETE |
| decisions_log.txt continued with Phase 1 decisions | COMPLETE — Decisions 8, 9 added |

---

## KNOWN BLOCKERS FOR PHASE 2

| Blocker | Impact | Resolution |
|---------|--------|-----------|
| zones.json polygons empty | Cannot run zone classification | Use visualise_zones.py to extract coordinates |
| CAM_3 entry_line empty | Entry counting = 0; entire funnel broken | Inspect CAM_3 video frame, define line and vector |
| requirements.txt not pinned | May break during Phase 2 pip install | Run pip install and pip freeze |
| CAM_4 warehouse_motion_threshold not calibrated | False positive motion events from flicker | Phase 2 calibration step (see Decision 9) |

---

## NEXT RECOMMENDED PHASE

**Phase 2 — CV Validation (2–3 hours)**

Prerequisites for Phase 2:
- Video files in inputs/ (required for all validation tests)
- requirements.txt installed on target machine
- zones.json with at least approximate polygon coordinates (for polygon overlay validation)

Phase 2 must answer four questions:
1. Does YOLOv8-nano detect people in these videos at 640×360?
2. Does the centroid tracker maintain consistent IDs for 20+ frames on a single person?
3. Can entry crossings be counted from CAM_3 with > N/10 accuracy on 10 test crossings?
4. Can zone visits be detected from CAM_1, CAM_2, CAM_5?

Phase 2 also includes CAM_4 calibration (find minimum contour area above flicker noise).

Trigger phrase to start Phase 2:
> "Phase 1 reviewed and approved. Proceed with Phase 2 CV Validation."

---

## RESUMABILITY CONFIRMATION

This repository is in a resumable state. A future AI agent can resume using:
1. PURPLLE_MASTER_PLAN.md — single source of truth
2. PROGRESS.md — current status and next actions
3. PHASE1_REPORT.md — this file
4. decisions_log.txt — 9 decisions recorded (Decisions 1–9)

DESIGN.md and CHOICES.md provide the full system design for context.
