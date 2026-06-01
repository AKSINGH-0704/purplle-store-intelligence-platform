"""
Checkpoint 2.2 — Centroid tracker validation.

Validates that a simple centroid tracker can maintain stable track IDs across
at least 20 consecutive processed frames on CAM_1.mp4 using production-equivalent
settings (frame_skip and tracker_distance_threshold from config.json).

This script is a validation tool only. It does NOT write to events.json,
does NOT implement any src/ module, and does NOT generate pipeline events.

Usage:
    python tools/test_tracker.py

Output (one of):
    tools/tracker_test_output/tracker_validation.mp4   (preferred)
    tools/tracker_test_output/frame_XXXX.jpg × N       (fallback if VideoWriter fails)

Q2 success criterion:
    At least one track survives ≥20 consecutive processed frames.
"""

import cv2
import json
import os
import sys

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
MODEL_PATH  = os.path.join(ROOT, "models", "yolov8n.pt")
VIDEO_PATH  = os.path.join(ROOT, "inputs", "CAM_1.mp4")
OUTPUT_DIR  = os.path.join(ROOT, "tools", "tracker_test_output")

# ── Config ───────────────────────────────────────────────────────────────────
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

W, H            = cfg["detection_resolution"]       # [640, 360]
CONF_THRESH     = cfg["confidence_threshold"]        # 0.5
FRAME_SKIP      = cfg["frame_skip"]                  # 5
TRACKER_DIST    = cfg["tracker_distance_threshold"]  # 80 px
PERSON_CLASS    = 0
Q2_MIN_FRAMES   = 20    # Frames a track must survive to answer Q2 = YES
MAX_DISAPPEARED = 10    # Processed frames before a lost track is removed
MAX_SRC_FRAMES  = 1000  # Source frames to scan → ~200 processed frames at skip 5

print(f"[CONFIG] resolution={W}x{H}  conf={CONF_THRESH}"
      f"  frame_skip={FRAME_SKIP}  tracker_dist={TRACKER_DIST}px")
print(f"[PLAN]   scanning {MAX_SRC_FRAMES} source frames "
      f"→ ~{MAX_SRC_FRAMES // FRAME_SKIP} processed frames")

# ── Preflight ─────────────────────────────────────────────────────────────────
for path, label in [(MODEL_PATH, "yolov8n.pt"), (VIDEO_PATH, "CAM_1.mp4")]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found: {path}")
        sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── YOLO ──────────────────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    model = YOLO(MODEL_PATH)
    print(f"[OK]    YOLO model loaded.\n")
except Exception as e:
    print(f"[ERROR] Failed to load YOLO: {e}")
    sys.exit(1)

# ── Video input ───────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"[ERROR] Cannot open: {VIDEO_PATH}")
    sys.exit(1)

total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps   = cap.get(cv2.CAP_PROP_FPS)
print(f"[VIDEO] {total_src} frames @ {src_fps:.2f} fps")

# ── Video writer (try mp4, fall back to frames) ───────────────────────────────
mp4_path   = os.path.join(OUTPUT_DIR, "tracker_validation.mp4")
out_fps    = max(1, src_fps / FRAME_SKIP)         # playback speed ≈ real time
fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
writer     = cv2.VideoWriter(mp4_path, fourcc, out_fps, (W, H))
use_writer = writer.isOpened()
if not use_writer:
    writer.release()
    print("[WARN]  VideoWriter unavailable — saving individual JPEG frames.")
else:
    print(f"[OK]    VideoWriter opened: {mp4_path}")

# ── Centroid tracker state ────────────────────────────────────────────────────
next_id        = 0
active_tracks  = {}   # id → {centroid, frames_alive, disappeared}
finished_tracks = []  # [{id, frames_alive}]

def _centroid(x1, y1, x2, y2):
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

# ── Main loop ─────────────────────────────────────────────────────────────────
proc_idx = 0
src_idx  = 0

while src_idx < min(MAX_SRC_FRAMES, total_src):
    cap.set(cv2.CAP_PROP_POS_FRAMES, src_idx)
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (W, H))

    # ── YOLO detections ───────────────────────────────────────────────────────
    res  = model(frame, conf=CONF_THRESH, classes=[PERSON_CLASS], verbose=False)
    dets = []  # [(x1,y1,x2,y2, cx,cy)]
    if res[0].boxes is not None:
        for box in res[0].boxes:
            if int(box.cls[0]) == PERSON_CLASS:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                dets.append((x1, y1, x2, y2, *_centroid(x1, y1, x2, y2)))

    new_cents = [(d[4], d[5]) for d in dets]

    # ── Greedy distance-based matching ───────────────────────────────────────
    # Build distance matrix: track × detection
    used_dets   = set()
    used_tracks = set()

    pairs = []  # (dist, track_id, det_idx)
    for tid, tdata in active_tracks.items():
        for di, cent in enumerate(new_cents):
            d = _dist(tdata["centroid"], cent)
            if d <= TRACKER_DIST:
                pairs.append((d, tid, di))

    pairs.sort(key=lambda x: x[0])   # closest match first

    for dist_val, tid, di in pairs:
        if tid in used_tracks or di in used_dets:
            continue
        active_tracks[tid]["centroid"]    = new_cents[di]
        active_tracks[tid]["frames_alive"] += 1
        active_tracks[tid]["disappeared"] = 0
        used_tracks.add(tid)
        used_dets.add(di)

    # ── Increment disappeared for unmatched tracks ────────────────────────────
    for tid in list(active_tracks):
        if tid not in used_tracks:
            active_tracks[tid]["disappeared"] += 1
            if active_tracks[tid]["disappeared"] >= MAX_DISAPPEARED:
                finished_tracks.append({
                    "id": tid,
                    "frames_alive": active_tracks[tid]["frames_alive"]
                })
                del active_tracks[tid]

    # ── Create tracks for unmatched detections ────────────────────────────────
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
    for det in dets:
        x1, y1, x2, y2, cx, cy = det
        # Find which active track owns this centroid
        matched_id    = None
        matched_alive = None
        for tid, tdata in active_tracks.items():
            if tdata["centroid"] == (cx, cy):
                matched_id    = tid
                matched_alive = tdata["frames_alive"]
                break
        color = (0, 255, 0) if matched_id is not None else (0, 165, 255)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        if matched_id is not None:
            lbl = f"ID:{matched_id} [{matched_alive}f]"
            cv2.putText(vis, lbl, (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    hdr = (f"src:{src_idx}  proc:{proc_idx}  "
           f"active:{len(active_tracks)}  total_IDs:{next_id}")
    cv2.putText(vis, hdr, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

    if use_writer:
        writer.write(vis)
    else:
        cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{proc_idx:04d}.jpg"), vis)

    proc_idx += 1
    src_idx  += FRAME_SKIP

# ── Flush remaining active tracks ─────────────────────────────────────────────
for tid, tdata in active_tracks.items():
    finished_tracks.append({"id": tid, "frames_alive": tdata["frames_alive"]})

cap.release()
if use_writer:
    writer.release()

# ── Statistics ────────────────────────────────────────────────────────────────
lengths      = [t["frames_alive"] for t in finished_tracks] or [0]
long_tracks  = [t for t in finished_tracks if t["frames_alive"] >= Q2_MIN_FRAMES]
avg_len      = sum(lengths) / len(lengths)
max_len      = max(lengths)

print()
print("=" * 65)
print("CHECKPOINT 2.2 SUMMARY — Centroid Tracker Validation")
print("=" * 65)
print(f"Source frames scanned      : {src_idx} (every {FRAME_SKIP}th → "
      f"{proc_idx} processed frames)")
print(f"tracker_distance_threshold : {TRACKER_DIST} px")
print(f"max_disappeared            : {MAX_DISAPPEARED} frames")
print()
print(f"Total unique IDs created   : {next_id}")
print(f"Longest track              : {max_len} processed frames")
print(f"Average track length       : {avg_len:.1f} processed frames")
print(f"Tracks surviving ≥{Q2_MIN_FRAMES} frames : {len(long_tracks)}")
print()

if long_tracks:
    print(f"Q2 ANSWER : YES — {len(long_tracks)} track(s) survived "
          f"≥{Q2_MIN_FRAMES} consecutive processed frames.")
    print("  Track breakdown (longest first):")
    for t in sorted(long_tracks, key=lambda x: -x["frames_alive"])[:10]:
        print(f"    ID {t['id']:>3} : {t['frames_alive']} frames")
else:
    print(f"Q2 ANSWER : UNCERTAIN — no single track survived ≥{Q2_MIN_FRAMES} frames.")
    print(f"  Longest track was {max_len} frames.")
    print(f"  Consider reducing tracker_distance_threshold below {TRACKER_DIST}px,")
    print(f"  or increasing max_disappeared above {MAX_DISAPPEARED}.")

print()
if use_writer:
    print(f"Output video : {mp4_path}")
else:
    n_frames = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpg")])
    print(f"Output frames: {OUTPUT_DIR}/ ({n_frames} JPEG files)")
print("=" * 65)
