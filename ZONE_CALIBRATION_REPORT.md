# ZONE CALIBRATION REPORT
## Purplle Store Intelligence Platform

Calibration Completed: 2026-05-31
Status: APPROVED — all 5 cameras finalized
Tool Used: visualise_zones.py (frame 100 extraction + polygon overlay)
Resolution: 640×360 (all coordinates are in this pixel space)
Source of truth: zones.json (do not modify coordinates without re-running visualise_zones.py to verify)

---

## Calibration Methodology

1. `visualise_zones.py` was run to extract frame 100 from each video in `inputs/`.
2. Output images were saved to `zones_preview/` with TODO markers overlaid for empty coordinates.
3. Zone boundaries were identified visually from each frame based on store layout knowledge:
   - Entry door on left wall, billing counter on right, skincare top wall, makeup bottom wall, F.O.H island center.
4. Polygon coordinates were entered into `zones.json` in pixel space at 640×360.
5. `visualise_zones.py` was re-run to overlay the new coordinates and verify visual alignment.
6. Each polygon was reviewed against the preview image and approved.
7. CAM_3 entry line was manually adjusted and finalized to y=170, placing it just inside the glass door threshold.

---

## Final Approved Zone Definitions

### CAM_1 — Skincare Zone

```json
"polygon": [[20,80], [620,80], [620,350], [20,350]]
```

| Property | Value |
|----------|-------|
| Zone | skincare |
| Intelligence layer | customer |
| Detection method | yolov8n |
| Polygon type | Rectangle |
| Frame coverage | ~70% (600×270 px of 640×360) |
| Top margin | 80px (excludes overhead shelving labels, ceiling) |
| Bottom margin | 10px |
| Left / Right margin | 20px each side |

**Calibration note:** Wide coverage appropriate for a browsing zone — captures customers standing at shelving on both sides of the aisle. Top margin at y=80 excludes fixed overhead signage that would never contain a person centroid. Polygon approved as-is.

---

### CAM_2 — Main Floor Zone

```json
"polygon": [[10,60], [630,60], [630,355], [10,355]]
```

| Property | Value |
|----------|-------|
| Zone | main_floor |
| Intelligence layer | customer |
| Detection method | yolov8n |
| Polygon type | Rectangle |
| Frame coverage | ~79% (620×295 px of 640×360) |
| Top margin | 60px (excludes ceiling / overhead) |
| Bottom margin | 5px |
| Left / Right margin | 10px each side |

**Calibration note:** Near-full frame coverage is correct for the main floor — this camera provides a wide-angle overview of the central circulation area. The 60px top margin excludes fixed ceiling structures. Polygon approved as-is.

---

### CAM_3 — Entrance / Exit Zone

```json
"polygon": [[80,60], [560,60], [560,355], [80,355]],
"entry_line": [[80,170], [560,170]],
"entry_direction_vector": [0,1]
```

| Property | Value |
|----------|-------|
| Zone | entrance |
| Intelligence layer | customer |
| Detection method | yolov8n |
| Polygon type | Rectangle |
| Frame coverage | ~62% (480×295 px of 640×360) |
| Top margin | 60px |
| Left / Right margin | 80px each side (excludes wall edges) |
| Entry line | Horizontal at y=170, spanning x=80 to x=560 |
| Entry direction vector | [0, 1] |

**Entry line geometry:**
- The line runs horizontally across the full width of the polygon at y=170.
- y=170 places the line inside the glass door threshold as observed in the CAM_3 frame, above the mid-height, where the door crossing is most reliably detected.
- The line spans x=80 to x=560 — matching the polygon left and right edges exactly so no crossing can occur outside the detection zone.

**Direction vector interpretation:**
- `[0, 1]` means the positive direction is straight downward (increasing y in pixel space).
- A centroid moving from y < 170 to y > 170 (top to bottom, i.e., from exterior into the store) = **entry**.
- A centroid moving from y > 170 to y < 170 (bottom to top, i.e., from store toward exit) = **exit**.
- This is consistent with the camera angle where the street/exterior is at the top of the frame and the store interior is at the bottom.

**Calibration note:** Left/right margins of 80px on each side correctly exclude the wall structures visible at the frame edges. Entry line manually adjusted and finalized at y=170 by the human reviewer. Direction vector [0,1] confirmed consistent with camera orientation.

---

### CAM_4 — Warehouse Zone

```json
"polygon": [[10,30], [630,30], [630,355], [10,355]]
```

| Property | Value |
|----------|-------|
| Zone | warehouse |
| Intelligence layer | operational |
| Detection method | background_subtraction |
| Polygon type | Rectangle |
| Frame coverage | ~88% (620×325 px of 640×360) |
| Top margin | 30px (minimal — nearly full ceiling-to-floor coverage) |
| Bottom margin | 5px |
| Left / Right margin | 10px each side |

**Calibration note:** Near-maximum coverage is appropriate for a warehouse — all motion anywhere in the storage area should be captured. The 30px top margin excludes fixed overhead fixtures. Background subtraction (OpenCV MOG2) uses the polygon as the region of interest mask.

**Critical:** Lighting flicker was observed in the CAM_4 video during Phase 0 inspection (decisions_log.txt Decision 7). The `warehouse_motion_threshold` (config.json, default 500 sq px) **must be calibrated during Phase 2** by measuring the maximum contour area produced by flicker-only frames. Do not use the default value without testing on this camera. See decisions_log.txt Decision 9. Polygon approved as-is.

---

### CAM_5 — Billing Zone

```json
"polygon": [[10,60], [420,60], [420,355], [10,355]]
```

| Property | Value |
|----------|-------|
| Zone | billing |
| Intelligence layer | customer_and_operational |
| Detection method | yolov8n |
| Polygon type | Rectangle |
| Frame coverage | ~52% (410×295 px of 640×360) — left portion only |
| Top margin | 60px |
| Bottom margin | 5px |
| Left margin | 10px |
| Right boundary | x=420 (not full width) |
| Excluded area | x=420 to x=640 — product display screen, no queue relevance |

**Calibration note:** The polygon deliberately excludes the right portion of the frame (x=420–640) which contains a product display screen area with no customer queue relevance. Including that area would introduce false detections from people browsing the display who are not in the billing queue. The left boundary at x=420 is the key calibration decision for this camera. Polygon approved as-is.

---

## Summary Table

| Camera | Zone | Polygon (x1,y1)→(x2,y2) | Entry Line | Direction Vector | Approved |
|--------|------|--------------------------|------------|-----------------|---------|
| CAM_1 | skincare | (20,80)→(620,350) | — | — | ✓ |
| CAM_2 | main_floor | (10,60)→(630,355) | — | — | ✓ |
| CAM_3 | entrance | (80,60)→(560,355) | y=170, x=80→560 | [0,1] | ✓ |
| CAM_4 | warehouse | (10,30)→(630,355) | — | — | ✓ |
| CAM_5 | billing | (10,60)→(420,355) | — | — | ✓ |

---

## Assumptions

| # | Assumption | Impact if Wrong | Mitigation |
|---|------------|-----------------|-----------|
| 1 | All polygons are rectangular — no irregular zone shapes needed | Non-rectangular zones would require additional polygon points | visualise_zones.py supports arbitrary polygons; add points if needed in Phase 2 |
| 2 | Frame 100 is representative of the typical camera view during operation | Zone boundaries could shift if camera was physically moved after frame 100 | Verify using a second frame (e.g., frame 500) if any detection anomalies emerge in Phase 3 |
| 3 | CAM_3 entry line at y=170 consistently separates exterior from interior across the full recording | Camera angle or lighting variation may shift apparent threshold | Validate against ≥10 actual crossings in Phase 2 before committing to this y-value |
| 4 | [0,1] direction vector is correct for the CAM_3 camera orientation | All entries would be classified as exits and vice versa | Phase 2 validation: confirm that ≥8/10 test crossings are classified correctly |
| 5 | CAM_5 right boundary at x=420 correctly excludes the display screen | Queue detections may be missed if customers queue past x=420 | Monitor in Phase 3; adjust if queue consistently extends past x=420 |
| 6 | CAM_4 polygon covers all relevant warehouse activity | Restocking events occurring outside the polygon would be missed | Near-full coverage (88%) makes this unlikely; calibrate threshold before Phase 2 |

---

## Limitations

- **Rectangular polygons only.** All five zones use rectangular bounding boxes. Real zone boundaries in an irregular store layout are rarely perfect rectangles. Persons detected near the edges of adjacent zones may register in the wrong zone. This is acceptable for aggregate zone-level analytics — precise individual placement is not required.
- **Static polygons.** The coordinates are fixed. If a camera is physically moved or tilted, all polygons must be re-derived using visualise_zones.py and the calibration process must be repeated.
- **y=170 entry line depends on camera stability.** If CAM_3 is physically moved, the entry line placement must be re-verified.
- **Frame 100 only.** Calibration was performed on a single frame per camera. Lighting changes, crowds, and temporary obstructions may affect how representative this frame is.
- **No sub-zone support.** Each camera maps to exactly one zone. If a future analysis requires distinguishing between sub-zones within a single camera view (e.g., specific shelves within CAM_1), the zones.json structure would need to be extended.

---

## Re-calibration Procedure (if needed)

1. Edit polygon coordinates in `zones.json`.
2. Run `python visualise_zones.py` to generate new overlay images in `zones_preview/`.
3. Review images against the actual zone boundaries.
4. Iterate until satisfied.
5. Record any coordinate changes in `decisions_log.txt` with the reason for the change.
6. Do not change CAM_3 entry line y-coordinate without re-running Phase 2 crossing validation.
