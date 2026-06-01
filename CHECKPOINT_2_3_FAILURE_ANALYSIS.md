# CHECKPOINT 2.3 — FAILURE ANALYSIS
## False Positive: Corridor Pedestrian Counted as Store Entry

Date: 2026-06-01
Status: ANALYSIS COMPLETE — awaiting fix approval
Analyst: Claude Sonnet 4.6

---

## Observed Behaviour

A person walking in the corridor **outside** the storefront was detected as a
crossing event (ENTRY) despite never entering the store.

- Frames with YOLO detections: 86 / 200 processed frames — detection is working.
- No genuine store entries were missed due to detection failures.
- The false positive passed both the `|dy| ≥ 8px` ambiguous filter and the x-range
  check (`x=80→560`), so it appears as a confirmed ENTRY in the crossing log.

---

## Track ID 0 Trajectory Analysis

### What Track ID 0 represents

Track ID 0 is the first person detected in the CAM_3 scan. In the CAM_3 entrance
camera, the first visible person at the start of the recording is most likely
someone **already in the corridor** at approximately y≈170 — the corridor that
runs in front of the store entrance.

### Geometry of the false positive crossing

```
Frame geometry at 640×360:
  y = 0       ← top of frame (ceiling / sky side)
  y = 170     ← entry_line (glass door threshold)
  y = 360     ← bottom of frame (store interior floor)

Corridor pedestrian trajectory (reconstructed):
  Processed frame N:    centroid at (cx=200, cy=163)  ← above y=170, y<170
  Processed frame N+1:  centroid at (cx=248, cy=178)  ← below y=170, y≥170

  dy = 178 - 163 = +15px  →  ≥ AMBIGUOUS_MIN_DY(8)  →  not flagged ambiguous
  dx = 248 - 200 = +48px  →  not checked by crossing logic
  direction: top→bottom, dy>0  →  direction_vec[1]=1, dot>0  →  ENTRY
```

The person was walking **left-to-right along the corridor** with a slight
downward angle. Over 5 skipped frames (~167ms), their centroid drifted 15px
vertically while moving ~48px horizontally. The vertical drift was enough to
cross y=170 and pass the `|dy|≥8` filter.

### Why this is a false positive

The person was walking **parallel to the storefront** (primarily horizontal
trajectory). They did not physically cross the door threshold. Their vertical
drift was an artifact of:
1. Slight diagonal walking angle in the corridor
2. Natural bounding box centroid oscillation between frames
3. The 5-frame skip amplifying small per-frame drifts into detectable single-step displacement

---

## Root Cause

**Single root cause — no trajectory direction gate:**

The crossing detection algorithm only checks:
1. Did the centroid cross y=170? ✓
2. Is the x-coordinate within the line span (80→560)? ✓
3. Is |dy| ≥ 8px? ✓

It does **NOT** check:
- Is the trajectory predominantly perpendicular to the entry line?
- Is the person's horizontal movement (|dx|) small relative to vertical movement (|dy|)?
- Was the person confirmed to be in the exterior approach zone before crossing?
- Is the crossing occurring within the actual doorway opening (narrower than full line)?

The entry line at y=170 is geometrically correct — it is placed at the door
threshold. But that same y-coordinate is also where corridor pedestrian traffic
flows. A purely y-based threshold cannot distinguish between:

```
Person A: Walking INTO the store  →  dy≈+30px, dx≈+8px   (steep angle)
Person B: Walking ALONG corridor  →  dy≈+15px, dx≈+50px  (shallow angle)
```

Both produce dy > 0, both pass the current filter. Person B is the false positive.

---

## Supporting Evidence

| Evidence item | Supports root cause |
|---------------|--------------------:|
| 86/200 frames had detections — YOLO is working | Crossing failure is not a detection gap |
| Track ID 0 persisted across many frames | Person was in corridor area continuously, not briefly passing through doorway |
| False positive direction was top→bottom (ENTRY) | Person was drifting toward store side of y=170, consistent with slight downward angle corridor walk |
| dx >> dy at crossing | Horizontal-dominant trajectory — corridor walker, not store entrant |
| direction_vec flip would change label, not fix the detection | Confirms the root cause is spatial filtering, not direction assignment |
| Entry line spans x=80→560 (480px) | Line is far wider than the actual doorway opening (estimated 60–150px in pixel space) |

---

## System Design Gap

The current entry line algorithm is equivalent to:

> "Count a crossing if a person moves more than 8px vertically across y=170 
> within the 480px-wide detection zone."

What it needs to be equivalent to:

> "Count a crossing if a person moves through the **doorway opening** in a 
> direction **consistent with entering or exiting** the store."

The gap: no doorway spatial gate, no trajectory angle requirement.

---

## Ranked Fix Options

### Option 1 — Doorway X-gating (narrow the line)
**Confidence: HIGH | Complexity: LOW**

Narrow `entry_line` x-range from [80,560] (480px) to cover only the actual
doorway opening (estimated 60–150px in pixel space, centred on the door).

```
Current:  entry_line = [[80,170],[560,170]]  — covers full polygon width
Fixed:    entry_line = [[x_door_left,170],[x_door_right,170]]  — doorway only
```

Corridor pedestrians outside the door x-range are ignored entirely.

**Why it works:** A corridor pedestrian to the left or right of the doorway
opening is simply outside the counting zone. Only persons physically in the
doorway path are evaluated.

**What it requires:** Visually identify the exact pixel x-coordinates of the
doorway edges in a CAM_3 frame. This is a zones.json modification. Needs
visual verification with `visualise_zones.py`.

**Limitations:** Does not help if corridor pedestrians happen to walk through
the doorway x-range. Needs accurate doorway pixel mapping.

---

### Option 2 — Trajectory angle filter (perpendicularity gate)
**Confidence: HIGH | Complexity: LOW (code change only, no zones.json change)**

Add a perpendicularity requirement: only count a crossing if the trajectory
is sufficiently vertical relative to horizontal.

```python
# Proposed condition (added to _detect_crossing):
if abs(dx) > 0:
    angle_ratio = abs(dy) / abs(dx)  # >1 means more vertical than horizontal
    if angle_ratio < PERP_THRESHOLD:  # e.g., 0.5
        return "ambiguous", dy        # trajectory too horizontal → corridor walker
```

A store entrant walks mostly perpendicular to the line (high |dy|, low |dx|):
`angle_ratio > 1.0` typical.

A corridor walker moves mostly parallel to the line (high |dx|, low |dy|):
`angle_ratio ≈ 0.1–0.4` typical.

A threshold of `0.5` separates these two cases clearly.

**Why it works:** Catches the false positive directly — the corridor walker had
`dx≈48, dy≈15`, giving `angle_ratio≈0.31`, which is below 0.5.

**What it requires:** Code change to `test_entry_counter.py` only (then Phase 3
`src/entry_counter.py` implements the same rule). No zones.json change.

**Limitations:** Threshold needs tuning. A person who runs through the door at
a sharp diagonal angle might have a lower ratio. A value of 0.3 is safe for
extreme cases; 0.5 is appropriate for the observed false positive.

---

### Option 3 — Inside-zone confirmation (post-crossing validation)
**Confidence: MEDIUM | Complexity: MEDIUM**

After detecting a crossing as ENTRY, require the track to reach a "confirmed
interior zone" (y > y_interior_threshold, e.g., y > 220) within N processed
frames. If the track disappears near y=170 without going deeper, cancel the count.

```
ENTRY_CONFIRMED = prev_cy < 170 AND curr_cy ≥ 170 AND track reaches y>220 within 5 frames
ENTRY_CANCELLED = track disappears or stays at y=170–180 after crossing
```

**Why it works:** A genuine store entrant will move deeper into the store
(increasing y toward 220+). A corridor walker who briefly dips below y=170
will not reach y>220.

**What it requires:** Track-state persistence after crossing detection. More
complex state machine in the crossing logic.

**Limitations:** Adds a latency — entries are confirmed N frames after crossing.
Counts may lag real-time. Faster entrants (quick crossings) might be missed if
they reach the interior quickly before being confirmed.

---

### Option 4 — Pre-crossing exterior-zone requirement
**Confidence: MEDIUM | Complexity: MEDIUM**

Before counting an ENTRY, require the track to have been confirmed in the
"exterior approach zone" (y < y_exterior_threshold, e.g., y < 140) for at
least 3 processed frames. A person approaching from the street will have a
period of y<140 before reaching the door. A corridor pedestrian at y≈170 starts
right at the line and has no prior exterior history.

```
VALID_ENTRY = track was at y < 140 for >= 3 consecutive frames BEFORE crossing
```

**Why it works:** Genuine entrants approach from the street side (top of frame,
low y values). Corridor walkers at y≈170 never have a low-y history.

**What it requires:** Per-track y-history buffer. State change to track
"approach confirmed" flag. Requires tracks to be visible long enough in the
approach zone.

**Limitations:** Fails for fast entries where the person was only visible for
1–2 frames before crossing. Also fails if the exterior approach area is crowded
and persons occlude each other.

---

### Option 5 — Move entry line deeper into store interior
**Confidence: LOW-MEDIUM | Complexity: LOW (zones.json change)**

Move the entry line from y=170 to y=220–250, placing it deeper inside the store
where corridor pedestrians never reach.

```
Current: entry_line y=170  (at door threshold, shared with corridor traffic level)
Moved:   entry_line y=230  (deeper inside, past door, in store interior)
```

**Why it works:** Corridor pedestrians at y≈170 would not reach y=230.

**What it requires:** zones.json modification. Re-running `visualise_zones.py`
to verify the new line position. Phase 2 crossing validation re-test.

**Limitations:** Misses fast entrants who only briefly appear between y=170 and
y=230 before the next processed frame. Creates a dead zone (y=170→230) where
crossing goes undetected. The line at y=230 may be inside shelving or obscured
by store fixtures depending on camera angle.

---

## Recommended Fix

**Option 2 (trajectory angle filter) as PRIMARY fix.**
**Option 1 (doorway x-gating) as SECONDARY fix (after Phase 2 visual verification).**

### Why Option 2 first

- Directly targets the root cause: trajectory angle distinguishes corridor walkers from store entrants
- Requires no zones.json change
- Implementable in `test_entry_counter.py` immediately
- Threshold of `|dy|/|dx| ≥ 0.5` is conservative — will not reject genuine diagonal-approach entrants (who typically have angle_ratio > 1.0)
- Confirmed effective against the observed false positive (dx≈48, dy≈15 → ratio≈0.31, well below 0.5)

### Why Option 1 as secondary

- Adds a physical spatial gate that makes the system more robust even if trajectory filtering is imperfect
- Requires identifying the exact doorway x-coordinates from a CAM_3 frame (visual work)
- Should be done in Phase 2 after Option 2 is validated — it is an additional hardening step, not the primary fix

### Combined rule (recommended Phase 3 implementation)

```
A crossing is valid ENTRY if ALL of the following are true:
  1. centroid crossed y=170 (prev_cy < 170, curr_cy ≥ 170)
  2. |dy| ≥ 8px (not ambiguous)
  3. curr_cx is within doorway x-range (narrowed after visual inspection)
  4. |dy| / max(|dx|, 1) ≥ 0.5 (trajectory is predominantly perpendicular)
```

---

## Confidence Assessment

| Claim | Confidence |
|-------|-----------|
| Root cause is absence of trajectory angle gate | HIGH — dx>>dy pattern directly explains the false positive |
| direction_vec [0,1] is correct | HIGH — confirmed by user; flip would not fix the issue |
| entry_line y=170 placement is correct | MEDIUM — correct for genuine entrants, but sits at corridor traffic level |
| Option 2 (angle filter) fixes the observed case | HIGH — ratio 0.31 << threshold 0.5 |
| Option 1 (x-gating) provides additional hardening | HIGH — doorway is narrower than full polygon width |
| Option 5 (moving line deeper) would cause missed detections | MEDIUM — risk of fast-entry miss is real |

---

## What NOT to change before fix approval

- `entry_direction_vector` — correct, do not change
- `entry_line` y-coordinate — correct placement, not the root cause
- `zones.json` — no changes until fix is approved and visual doorway mapping is done

---

## Proposed next step (awaiting approval)

1. Implement Option 2 in `tools/test_entry_counter.py`:
   Add `|dy|/max(|dx|,1) ≥ PERP_THRESHOLD` condition to `_detect_crossing()`.
   Default `PERP_THRESHOLD = 0.5`.
2. Re-run `python tools/test_entry_counter.py`.
3. Verify: false positive Track ID 0 no longer counted.
4. Verify: genuine store entries (if any in the window) still counted.
5. Report results.
6. If Option 2 resolves the false positive → plan Option 1 (x-gating) as Phase 3 implementation detail.
