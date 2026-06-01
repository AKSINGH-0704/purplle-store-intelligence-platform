"""
Checkpoint 2.3 — Entry line crossing validation.

Validates that the calibrated CAM_3 entry line (y=170, x=80→560) and
direction vector ([0,1]) can reliably detect entry and exit crossings
using YOLO detection and centroid tracking at production-equivalent settings.

This script is a validation tool only. It does NOT write to events.json,
does NOT implement any src/ module, and does NOT generate pipeline events.

Usage:
    python tools/test_entry_counter.py

Output:
    tools/entry_counter_output/entry_validation.mp4   (preferred)
    tools/entry_counter_output/frame_XXXX.jpg × N     (fallback)

Q3 success criterion:
    Entry and exit crossings are detected and directionally correct
    based on visual inspection of the annotated output.
    Direction vector [0,1]: top-to-bottom (y increasing) = ENTRY.
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
MAX_SRC_FRAMES   = 1000  # → ~200 processed frames
FLASH_DURATION   = 8     # processed frames to show crossing label
AMBIGUOUS_MIN_DY = 8     # crossings with |dy| < this are flagged ambiguous

# ── Load zones — CAM_3 entry config ──────────────────────────────────────────
with open(ZONES_PATH) as f:
    zones = json.load(f)

cam3_cfg   = zones["CAM_3"]
entry_line = cam3_cfg["entry_line"]            # [[80,170],[560,170]]
entry_vec  = cam3_cfg["entry_direction_vector"]  # [0,1]

ENTRY_Y = entry_line[0][1]   # 170  — y-coordinate of the horizontal line
LINE_X1 = entry_line[0][0]   # 80   — left bound
LINE_X2 = entry_line[1][0]   # 560  — right bound
DIR_DY  = entry_vec[1]       # 1    — positive dy = entry

print(f"[CONFIG] resolution={W}x{H}  conf={CONF_THRESH}"
      f"  frame_skip={FRAME_SKIP}  tracker_dist={TRACKER_DIST}px")
print(f"[LINE]   y={ENTRY_Y}, x={LINE_X1}→{LINE_X2}, direction_vec={entry_vec}")
print(f"[RULE]   top→bottom (dy>0) = ENTRY | bottom→top (dy<0) = EXIT")
print(f"[PLAN]   scanning {MAX_SRC_FRAMES} src frames → "
      f"~{MAX_SRC_FRAMES // FRAME_SKIP} processed frames\n")

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
print(f"[VIDEO] {total_src} frames @ {src_fps:.2f} fps")

mp4_path   = os.path.join(OUTPUT_DIR, "entry_validation.mp4")
out_fps    = max(1, src_fps / FRAME_SKIP)
fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
writer     = cv2.VideoWriter(mp4_path, fourcc, out_fps, (W, H))
use_writer = writer.isOpened()
if not use_writer:
    writer.release()
    print("[WARN]  VideoWriter failed — saving individual JPEG frames.")
else:
    print(f"[OK]    VideoWriter opened: {mp4_path}\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _centroid(x1, y1, x2, y2):
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

def _detect_crossing(prev_cy, curr_cy, curr_cx):
    """
    Returns ('entry', dy), ('exit', dy), ('ambiguous', dy), or (None, 0).
    Only checks crossings within the entry line x-range.
    Ambiguous: |dy| < AMBIGUOUS_MIN_DY — person barely cleared the line.
    """
    if prev_cy is None:
        return None, 0
    if not (LINE_X1 <= curr_cx <= LINE_X2):
        return None, 0   # outside line x-span — ignore

    crossed = (prev_cy < ENTRY_Y <= curr_cy) or (prev_cy > ENTRY_Y >= curr_cy)
    if not crossed:
        return None, 0

    dy = curr_cy - prev_cy

    if abs(dy) < AMBIGUOUS_MIN_DY:
        return "ambiguous", dy

    # Direction check: direction_vec = [0,1], so dy sign determines type
    if dy * DIR_DY > 0:   # positive dy AND positive direction = entry
        return "entry", dy
    else:
        return "exit", dy

# ── Tracker state ─────────────────────────────────────────────────────────────
next_id       = 0
active_tracks = {}  # id → {centroid, prev_cy, frames_alive, disappeared}

# ── Crossing state ────────────────────────────────────────────────────────────
total_entries    = 0
total_exits      = 0
total_ambiguous  = 0
crossing_log     = []  # [{proc, src, tid, type, prev_cy, curr_cy, dy}]
flash_labels     = {}  # tid → {label, color, ttl}

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

        prev_cy = active_tracks[tid]["centroid"][1]
        curr_cx, curr_cy = new_cents[di]

        # Check crossing
        ctype, dy = _detect_crossing(prev_cy, curr_cy, curr_cx)
        if ctype == "entry":
            total_entries += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "ENTRY", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy})
            flash_labels[tid] = {"label": "ENTRY", "color": (0, 220, 60), "ttl": FLASH_DURATION}
        elif ctype == "exit":
            total_exits += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "EXIT", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy})
            flash_labels[tid] = {"label": "EXIT", "color": (0, 120, 255), "ttl": FLASH_DURATION}
        elif ctype == "ambiguous":
            total_ambiguous += 1
            crossing_log.append({"proc": proc_idx, "src": src_idx, "tid": tid,
                                  "type": "AMBIGUOUS", "prev_cy": prev_cy,
                                  "curr_cy": curr_cy, "dy": dy})
            flash_labels[tid] = {"label": "?CROSS", "color": (0, 200, 200), "ttl": FLASH_DURATION}

        active_tracks[tid]["centroid"]    = new_cents[di]
        active_tracks[tid]["prev_cy"]     = prev_cy
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
                "prev_cy":     None,
                "frames_alive": 1,
                "disappeared": 0,
            }
            next_id += 1

    # ── Annotate frame ────────────────────────────────────────────────────────
    vis = frame.copy()

    # Entry line
    cv2.line(vis, (LINE_X1, ENTRY_Y), (LINE_X2, ENTRY_Y), (0, 165, 255), 2)
    cv2.putText(vis, f"entry_line y={ENTRY_Y}", (LINE_X1 + 4, ENTRY_Y - 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 165, 255), 1)

    # Bounding boxes + IDs + flash labels
    for det in dets:
        x1, y1, x2, y2, cx, cy = det
        tid_match = None
        for tid, td in active_tracks.items():
            if td["centroid"] == (cx, cy):
                tid_match = tid
                break
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        if tid_match is not None:
            cv2.putText(vis, f"ID:{tid_match}", (x1, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            if tid_match in flash_labels:
                fl = flash_labels[tid_match]
                cv2.putText(vis, fl["label"], (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, fl["color"], 2)
                fl["ttl"] -= 1
                if fl["ttl"] <= 0:
                    del flash_labels[tid_match]

    # Counters overlay (top-left dark box)
    cv2.rectangle(vis, (3, 3), (195, 55), (0, 0, 0), -1)
    cv2.putText(vis, f"Entries: {total_entries}", (7, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 60), 1)
    cv2.putText(vis, f"Exits:   {total_exits}", (7, 43),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 120, 255), 1)
    # Frame info (top-right)
    cv2.putText(vis, f"src:{src_idx}  proc:{proc_idx}", (W - 170, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 0), 1)

    if use_writer:
        writer.write(vis)
    else:
        cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{proc_idx:04d}.jpg"), vis)

    proc_idx += 1
    src_idx  += FRAME_SKIP

# ── Finalize ───────────────────────────────────────────────────────────────────
cap.release()
if use_writer:
    writer.release()

# ── Summary ────────────────────────────────────────────────────────────────────
total_crossings = total_entries + total_exits + total_ambiguous

print()
print("=" * 65)
print("CHECKPOINT 2.3 SUMMARY — Entry Line Crossing Validation")
print("=" * 65)
print(f"Camera               : CAM_3")
print(f"Entry line           : y={ENTRY_Y}, x={LINE_X1}→{LINE_X2}")
print(f"Direction vector     : {entry_vec}  (dy>0 = ENTRY, dy<0 = EXIT)")
print(f"Source frames scanned: {src_idx}  (frame_skip={FRAME_SKIP})"
      f"  →  {proc_idx} processed frames")
print()
print(f"Total ENTRY events   : {total_entries}")
print(f"Total EXIT events    : {total_exits}")
print(f"Total AMBIGUOUS      : {total_ambiguous}"
      f"  (|dy| < {AMBIGUOUS_MIN_DY}px — barely cleared line)")
print(f"Total crossings      : {total_crossings}")
print()

if crossing_log:
    print("Crossing event log:")
    print(f"  {'proc':>4}  {'src':>5}  {'ID':>3}  {'type':<10}"
          f"  {'prev_cy':>7}  {'curr_cy':>7}  {'dy':>4}")
    print(f"  {'-'*4}  {'-'*5}  {'-'*3}  {'-'*10}"
          f"  {'-'*7}  {'-'*7}  {'-'*4}")
    for ev in crossing_log:
        print(f"  {ev['proc']:>4}  {ev['src']:>5}  {ev['tid']:>3}  "
              f"{ev['type']:<10}  {ev['prev_cy']:>7}  {ev['curr_cy']:>7}  "
              f"{ev['dy']:>+4}")
else:
    print("  No crossing events detected in this window.")

print()
print("─" * 65)
if total_entries + total_exits > 0:
    print(f"Q3 ANSWER : CROSSINGS DETECTED ({total_entries} entries, {total_exits} exits).")
    print(f"            Review entry_validation.mp4 to confirm direction accuracy.")
    print(f"            Verify: top→bottom crossings labelled ENTRY (green text).")
    print(f"            Verify: bottom→top crossings labelled EXIT (orange text).")
else:
    print(f"Q3 ANSWER : No entry/exit crossings detected in {proc_idx} processed frames.")
    print(f"            Consider: Is y={ENTRY_Y} in a high-traffic crossing area?")
    print(f"            Try inspecting a different frame range or adjusting entry line.")

if total_ambiguous > 0:
    print(f"\nNote: {total_ambiguous} ambiguous crossing(s) detected (|dy| < {AMBIGUOUS_MIN_DY}px).")
    print(f"      These may indicate persons walking parallel to the entry line.")
    print(f"      Review in video — they do NOT count toward entry/exit totals.")

print()
if use_writer:
    print(f"Output: {mp4_path}")
else:
    n = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpg")])
    print(f"Output: {OUTPUT_DIR}/ ({n} JPEG frames)")
print("=" * 65)
