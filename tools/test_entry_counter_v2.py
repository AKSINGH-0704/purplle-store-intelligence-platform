"""
Checkpoint 2.3 v2 — Entry line crossing validation with doorway x-gating.

Iteration 2 of the entry crossing validation. Adds a DOORWAY GATE that
restricts crossing detection to the actual door opening (x=250->490) derived
from visual inspection of zones_preview/CAM_3_frame100.jpg.

The entry_line and entry_direction_vector in zones.json are NOT changed.
The gate is a code-level filter applied during crossing detection only.

Key change vs v1:
    v1: crossing counted if centroid x is within LINE_X1->LINE_X2 (80->560)
    v2: crossing counted if centroid x is within DOOR_X1->DOOR_X2 (250->490)

Doorway gate rationale (from CAM_3_frame100.jpg inspection):
    x < 250  — Promotional display / left store wall.  Not a crossing zone.
    x 250-490 — Glass entrance opening.  The actual door gap.
    x > 490  — Exterior right-side corridor.  Where false-positive was detected.

Annotation:
    Orange dim line  : full entry_line from zones.json (x=80->560)
    Cyan bright line : active doorway gate (x=250->490) — what actually counts
    Green/orange flash: ENTRY / EXIT labels on crossing events

Output:
    tools/entry_counter_output/entry_validation_v2.mp4

This script is a validation tool only. It does NOT modify zones.json,
does NOT write to events.json, and does NOT implement any src/ module.
"""

import cv2
import json
import os
import sys

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
MODEL_PATH  = os.path.join(ROOT, "models", "yolov8n.pt")
ZONES_PATH  = os.path.join(ROOT, "zones.json")
VIDEO_PATH  = os.path.join(ROOT, "inputs", "CAM_3.mp4")
OUTPUT_DIR  = os.path.join(ROOT, "tools", "entry_counter_output")

# ── Load config ───────────────────────────────────────────────────────────────
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

W, H          = cfg["detection_resolution"]       # [640, 360]
CONF_THRESH   = cfg["confidence_threshold"]        # 0.5
FRAME_SKIP    = cfg["frame_skip"]                  # 5
TRACKER_DIST  = cfg["tracker_distance_threshold"]  # 80
PERSON_CLASS  = 0
MAX_DISAPPEARED  = 10
MAX_SRC_FRAMES   = 3600  # extended run: ~2 min of footage at 29.97fps
FLASH_DURATION   = 8
AMBIGUOUS_MIN_DY = 8

# ── Load zones — CAM_3 entry config (NOT modified) ────────────────────────────
with open(ZONES_PATH) as f:
    zones = json.load(f)

cam3_cfg   = zones["CAM_3"]
entry_line = cam3_cfg["entry_line"]              # [[80,170],[560,170]]
entry_vec  = cam3_cfg["entry_direction_vector"]  # [0,1]

ENTRY_Y = entry_line[0][1]    # 170  — from zones.json, unchanged
LINE_X1 = entry_line[0][0]    # 80   — full line left (display only)
LINE_X2 = entry_line[1][0]    # 560  — full line right (display only)
DIR_DY  = entry_vec[1]        # 1    — positive dy = entry

# ── Doorway gate (x-gating fix — code only, zones.json unchanged) ─────────────
#
# Derived from visual inspection of zones_preview/CAM_3_frame100.jpg at 640×360:
#
#   x = 80  -> 250  : Promotional sign + left store wall structure.
#                     No one physically enters from this x-range.
#   x = 250 -> 490  : Glass entrance opening — the actual doorway gap.
#                     People entering and exiting the store cross here.
#   x = 490 -> 560  : Exterior right-side corridor floor visible.
#                     This is where the v1 false-positive Track ID 0 was
#                     detected (corridor pedestrian walking right-to-left
#                     with slight downward drift crossing y=170).
#
DOOR_X1 = 250   # left edge of actual door opening
DOOR_X2 = 490   # right edge of actual door opening

# Output v2 (separate file, preserves v1 for comparison)
MP4_OUT = os.path.join(OUTPUT_DIR, "entry_validation_v2_extended.mp4")

print(f"[CONFIG]  resolution={W}x{H}  conf={CONF_THRESH}"
      f"  frame_skip={FRAME_SKIP}  tracker_dist={TRACKER_DIST}px")
print(f"[LINE]    y={ENTRY_Y}  full span x={LINE_X1}->{LINE_X2}  (from zones.json, display only)")
print(f"[GATE]    DOORWAY x={DOOR_X1}->{DOOR_X2}  (v2 fix — active counting zone)")
print(f"[RULE]    top->bottom (dy>0) = ENTRY | bottom->top (dy<0) = EXIT")
print(f"[EXPECT]  False-positive Track ID 0 had cx~480-500 -> outside gate -> suppressed")
print(f"[PLAN]    scanning {MAX_SRC_FRAMES} src frames"
      f" -> ~{MAX_SRC_FRAMES // FRAME_SKIP} processed frames\n")

# ── Preflight ─────────────────────────────────────────────────────────────────
for path, label in [(MODEL_PATH, "yolov8n.pt"), (VIDEO_PATH, "CAM_3.mp4"),
                    (ZONES_PATH, "zones.json")]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found: {path}")
        sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── YOLO ──────────────────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    model = YOLO(MODEL_PATH)
    print(f"[OK]    YOLO model loaded.")
except Exception as e:
    print(f"[ERROR] Failed to load YOLO: {e}")
    sys.exit(1)

# ── Video I/O ─────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"[ERROR] Cannot open: {VIDEO_PATH}")
    sys.exit(1)

total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps   = cap.get(cv2.CAP_PROP_FPS)
print(f"[VIDEO]  {total_src} frames @ {src_fps:.2f} fps")

out_fps    = max(1, src_fps / FRAME_SKIP)
fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
writer     = cv2.VideoWriter(MP4_OUT, fourcc, out_fps, (W, H))
use_writer = writer.isOpened()
if not use_writer:
    writer.release()
    print("[WARN]   VideoWriter failed — saving individual JPEG frames.")
else:
    print(f"[OK]     VideoWriter opened: {MP4_OUT}\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _centroid(x1, y1, x2, y2):
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

def _detect_crossing(prev_cy, curr_cy, curr_cx):
    """
    Returns ('entry', dy), ('exit', dy), ('ambiguous', dy), or (None, 0).

    v2 change: uses DOOR_X1/DOOR_X2 (doorway gate) instead of LINE_X1/LINE_X2.
    Crossings where curr_cx is outside the doorway gate are ignored entirely.
    The entry_line y-coordinate and direction_vector are unchanged from zones.json.
    """
    if prev_cy is None:
        return None, 0

    # ── DOORWAY GATE (v2 fix) ─────────────────────────────────────────────────
    if not (DOOR_X1 <= curr_cx <= DOOR_X2):
        return None, 0   # centroid is outside doorway — not a store crossing

    crossed = (prev_cy < ENTRY_Y <= curr_cy) or (prev_cy > ENTRY_Y >= curr_cy)
    if not crossed:
        return None, 0

    dy = curr_cy - prev_cy

    if abs(dy) < AMBIGUOUS_MIN_DY:
        return "ambiguous", dy

    if dy * DIR_DY > 0:
        return "entry", dy
    else:
        return "exit", dy

# ── Tracker state ─────────────────────────────────────────────────────────────
next_id       = 0
active_tracks = {}

# ── Crossing state ────────────────────────────────────────────────────────────
total_entries   = 0
total_exits     = 0
total_ambiguous = 0
total_suppressed = 0   # crossings outside doorway gate (would have been counted in v1)
crossing_log    = []
flash_labels    = {}

# ── Main loop ─────────────────────────────────────────────────────────────────
proc_idx = 0
src_idx  = 0

while src_idx < min(MAX_SRC_FRAMES, total_src):
    cap.set(cv2.CAP_PROP_POS_FRAMES, src_idx)
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (W, H))

    # ── Detect ────────────────────────────────────────────────────────────────
    res  = model(frame, conf=CONF_THRESH, classes=[PERSON_CLASS], verbose=False)
    dets = []
    if res[0].boxes is not None:
        for box in res[0].boxes:
            if int(box.cls[0]) == PERSON_CLASS:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                dets.append((x1, y1, x2, y2, *_centroid(x1, y1, x2, y2)))

    new_cents = [(d[4], d[5]) for d in dets]

    # ── Greedy match ──────────────────────────────────────────────────────────
    used_dets   = set()
    used_tracks = set()
    pairs = []
    for tid, td in active_tracks.items():
        for di, cent in enumerate(new_cents):
            d = _dist(td["centroid"], cent)
            if d <= TRACKER_DIST:
                pairs.append((d, tid, di))
    pairs.sort()

    for _, tid, di in pairs:
        if tid in used_tracks or di in used_dets:
            continue

        prev_cy       = active_tracks[tid]["centroid"][1]
        curr_cx, curr_cy = new_cents[di]

        # Check crossing — uses DOOR_X1/DOOR_X2 gate
        ctype, dy = _detect_crossing(prev_cy, curr_cy, curr_cx)

        # Separately check: would this have fired in v1 (full line span)?
        # Used to count suppressed events for reporting.
        if ctype is None:
            crossed_full = ((prev_cy < ENTRY_Y <= curr_cy)
                            or (prev_cy > ENTRY_Y >= curr_cy))
            in_full_span = LINE_X1 <= curr_cx <= LINE_X2
            not_in_gate  = not (DOOR_X1 <= curr_cx <= DOOR_X2)
            if crossed_full and in_full_span and not_in_gate and abs(dy) >= AMBIGUOUS_MIN_DY:
                total_suppressed += 1
                crossing_log.append({
                    "proc": proc_idx, "src": src_idx, "tid": tid,
                    "type": "SUPPRESSED", "prev_cy": prev_cy,
                    "curr_cy": curr_cy, "dy": dy, "cx": curr_cx
                })

        if ctype == "entry":
            total_entries += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "ENTRY", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy, "cx": curr_cx})
            flash_labels[tid] = {"label": "ENTRY", "color": (0, 220, 60), "ttl": FLASH_DURATION}
        elif ctype == "exit":
            total_exits += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "EXIT", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy, "cx": curr_cx})
            flash_labels[tid] = {"label": "EXIT", "color": (0, 120, 255), "ttl": FLASH_DURATION}
        elif ctype == "ambiguous":
            total_ambiguous += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "AMBIGUOUS", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy, "cx": curr_cx})
            flash_labels[tid] = {"label": "?CROSS", "color": (0, 200, 200), "ttl": FLASH_DURATION}

        active_tracks[tid]["centroid"]    = new_cents[di]
        active_tracks[tid]["frames_alive"] += 1
        active_tracks[tid]["disappeared"] = 0
        used_tracks.add(tid)
        used_dets.add(di)

    # ── Remove disappeared tracks ─────────────────────────────────────────────
    for tid in list(active_tracks):
        if tid not in used_tracks:
            active_tracks[tid]["disappeared"] += 1
            if active_tracks[tid]["disappeared"] >= MAX_DISAPPEARED:
                del active_tracks[tid]
                flash_labels.pop(tid, None)

    # ── Create new tracks ─────────────────────────────────────────────────────
    for di, cent in enumerate(new_cents):
        if di not in used_dets:
            active_tracks[next_id] = {
                "centroid":    cent,
                "frames_alive": 1,
                "disappeared": 0,
            }
            next_id += 1

    # ── Annotate frame ────────────────────────────────────────────────────────
    vis = frame.copy()

    # Full entry_line from zones.json — shown dim (display only, not active gate)
    cv2.line(vis, (LINE_X1, ENTRY_Y), (LINE_X2, ENTRY_Y), (0, 100, 160), 1)
    cv2.putText(vis, f"zones.json line (full)", (LINE_X1 + 4, ENTRY_Y - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 100, 160), 1)

    # Doorway gate — shown bright cyan (this is what counts in v2)
    cv2.line(vis, (DOOR_X1, ENTRY_Y), (DOOR_X2, ENTRY_Y), (255, 220, 0), 2)
    cv2.putText(vis, f"GATE x={DOOR_X1}-{DOOR_X2}", (DOOR_X1, ENTRY_Y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 220, 0), 1)

    # Gate boundary markers (vertical tick lines)
    cv2.line(vis, (DOOR_X1, ENTRY_Y - 8), (DOOR_X1, ENTRY_Y + 8), (255, 220, 0), 2)
    cv2.line(vis, (DOOR_X2, ENTRY_Y - 8), (DOOR_X2, ENTRY_Y + 8), (255, 220, 0), 2)

    # Bounding boxes + IDs + flash labels
    for det in dets:
        x1, y1, x2, y2, cx, cy = det
        tid_match = None
        for tid, td in active_tracks.items():
            if td["centroid"] == (cx, cy):
                tid_match = tid
                break
        # Box colour: bright green if in gate, dim grey if outside gate
        in_gate = DOOR_X1 <= cx <= DOOR_X2
        box_color = (0, 255, 0) if in_gate else (120, 120, 120)
        cv2.rectangle(vis, (x1, y1), (x2, y2), box_color, 2)
        if tid_match is not None:
            cv2.putText(vis, f"ID:{tid_match}", (x1, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)
            if tid_match in flash_labels:
                fl = flash_labels[tid_match]
                cv2.putText(vis, fl["label"], (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, fl["color"], 2)
                fl["ttl"] -= 1
                if fl["ttl"] <= 0:
                    del flash_labels[tid_match]

    # Counters overlay
    cv2.rectangle(vis, (3, 3), (230, 70), (0, 0, 0), -1)
    cv2.putText(vis, f"Entries:    {total_entries}", (7, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 220, 60), 1)
    cv2.putText(vis, f"Exits:      {total_exits}", (7, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 120, 255), 1)
    cv2.putText(vis, f"Suppressed: {total_suppressed}", (7, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 100, 100), 1)
    cv2.putText(vis, f"src:{src_idx} proc:{proc_idx}", (W - 165, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 0), 1)

    if use_writer:
        writer.write(vis)
    else:
        cv2.imwrite(os.path.join(OUTPUT_DIR, f"v2_frame_{proc_idx:04d}.jpg"), vis)

    proc_idx += 1
    src_idx  += FRAME_SKIP

# ── Finalize ───────────────────────────────────────────────────────────────────
cap.release()
if use_writer:
    writer.release()

# ── Summary ────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("CHECKPOINT 2.3 v2 SUMMARY — Entry Line Crossing + Doorway X-Gating")
print("=" * 70)
print(f"Camera            : CAM_3")
print(f"Entry line        : y={ENTRY_Y}, full span x={LINE_X1}->{LINE_X2} (zones.json — unchanged)")
print(f"Doorway gate (v2) : x={DOOR_X1}->{DOOR_X2}  (active counting zone)")
print(f"Direction vector  : {entry_vec}  (dy>0=ENTRY, dy<0=EXIT — unchanged)")
print(f"Frames scanned    : {src_idx} src (skip={FRAME_SKIP}) -> {proc_idx} processed")
print()
print(f"Total ENTRY events      : {total_entries}")
print(f"Total EXIT events       : {total_exits}")
print(f"Total AMBIGUOUS events  : {total_ambiguous}  (|dy| < {AMBIGUOUS_MIN_DY}px)")
print(f"Total SUPPRESSED events : {total_suppressed}"
      f"  (would have fired in v1 — outside doorway gate x={DOOR_X1}->{DOOR_X2})")
print()

if crossing_log:
    print("Crossing event log:")
    print(f"  {'proc':>4}  {'src':>5}  {'ID':>3}  {'type':<11}"
          f"  {'cx':>5}  {'prev_cy':>7}  {'curr_cy':>7}  {'dy':>4}")
    print(f"  {'-'*4}  {'-'*5}  {'-'*3}  {'-'*11}"
          f"  {'-'*5}  {'-'*7}  {'-'*7}  {'-'*4}")
    for ev in crossing_log:
        print(f"  {ev['proc']:>4}  {ev['src']:>5}  {ev['tid']:>3}  "
              f"{ev['type']:<11}  {ev['cx']:>5}  {ev['prev_cy']:>7}  "
              f"{ev['curr_cy']:>7}  {ev['dy']:>+4}")
else:
    print("  No events detected.")

print()
print("─" * 70)

# Q3 verdict
if total_suppressed > 0 and (total_entries + total_exits) < total_suppressed:
    print(f"GATE EFFECT : {total_suppressed} v1 false positive(s) suppressed by doorway gate.")
elif total_suppressed > 0:
    print(f"GATE EFFECT : {total_suppressed} crossing(s) suppressed (outside doorway gate).")
else:
    print(f"GATE EFFECT : No suppressed events — false positive was already outside gate.")

print()
if total_entries + total_exits > 0:
    print(f"Q3 ANSWER : CROSSINGS DETECTED ({total_entries} entries, {total_exits} exits).")
    print(f"            Review entry_validation_v2.mp4 to confirm direction accuracy.")
    print(f"            Bright tracks (green box) = inside doorway gate.")
    print(f"            Dim tracks (grey box)    = outside gate, not counted.")
else:
    print(f"Q3 ANSWER : No entry/exit crossings in doorway gate x={DOOR_X1}->{DOOR_X2}.")
    print(f"            Suppressed events confirm gate is working.")
    print(f"            This window ({proc_idx} frames) may not contain genuine store entries.")

print()
if use_writer:
    print(f"Output : {MP4_OUT}")
else:
    n = len([f for f in os.listdir(OUTPUT_DIR) if f.startswith("v2_") and f.endswith(".jpg")])
    print(f"Output : {OUTPUT_DIR}/ ({n} v2 JPEG frames)")
print("=" * 70)
