"""
Checkpoint 2.4 -- Zone visit detection validation.

Validates that zone visits (person centroid inside polygon for >= min_dwell_for_visit_seconds)
are reliably detectable on CAM_1 (skincare), CAM_2 (main_floor), and CAM_5 (billing)
using YOLO detection and the validated centroid tracker at production-equivalent settings.

This script is a validation tool only. It does NOT write to events.json,
does NOT implement any src/ module, and does NOT generate pipeline events.

Usage:
    python tools/test_zone_visits.py

Output:
    tools/zone_visit_output/CAM_1_visit_validation.mp4
    tools/zone_visit_output/CAM_2_visit_validation.mp4
    tools/zone_visit_output/CAM_5_visit_validation.mp4

Q4 success criterion:
    At least one camera records >= 1 qualifying visit
    (dwell >= min_dwell_for_visit_seconds from config.json).
"""

import cv2
import json
import os
import sys

# -- Paths -------------------------------------------------------------------
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
MODEL_PATH  = os.path.join(ROOT, "models", "yolov8n.pt")
ZONES_PATH  = os.path.join(ROOT, "zones.json")
INPUTS_DIR  = os.path.join(ROOT, "inputs")
OUTPUT_DIR  = os.path.join(ROOT, "tools", "zone_visit_output")

# -- Config ------------------------------------------------------------------
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

W, H              = cfg["detection_resolution"]       # [640, 360]
CONF_THRESH       = cfg["confidence_threshold"]        # 0.5
FRAME_SKIP        = cfg["frame_skip"]                  # 5
TRACKER_DIST      = cfg["tracker_distance_threshold"]  # 80
MIN_DWELL_SECS    = cfg["min_dwell_for_visit_seconds"] # 10
PERSON_CLASS      = 0
MAX_DISAPPEARED   = 10
MAX_SRC_FRAMES    = 1000  # ~200 processed frames per camera

# -- Zones -------------------------------------------------------------------
with open(ZONES_PATH) as f:
    zones_cfg = json.load(f)

# Cameras for Q4 (CAM_4 excluded -- background subtraction, not YOLO)
CAMERAS = ["CAM_1", "CAM_2", "CAM_5"]

# -- Preflight ---------------------------------------------------------------
for path, label in [(MODEL_PATH, "yolov8n.pt"), (ZONES_PATH, "zones.json")]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found: {path}")
        sys.exit(1)

for cam_id in CAMERAS:
    vpath = os.path.join(INPUTS_DIR, f"{cam_id}.mp4")
    if not os.path.exists(vpath):
        print(f"[ERROR] {cam_id}.mp4 not found: {vpath}")
        sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -- YOLO (load once for all cameras) ----------------------------------------
try:
    from ultralytics import YOLO
    model = YOLO(MODEL_PATH)
    print(f"[OK]    YOLO model loaded.\n")
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

# -- Helpers -----------------------------------------------------------------
def _centroid(x1, y1, x2, y2):
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

def _in_rect_zone(cx, cy, x1, y1, x2, y2):
    """Point-in-rectangle zone check (all polygons are axis-aligned rectangles)."""
    return x1 <= cx <= x2 and y1 <= cy <= y2

def _poly_bounds(polygon):
    """Return (min_x, min_y, max_x, max_y) for a rectangular polygon."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)

def _fmt(secs):
    """Format seconds to readable string."""
    return f"{secs:.1f}s" if secs < 60 else f"{int(secs//60)}m {secs%60:.0f}s"

# -- Per-camera processing ---------------------------------------------------
all_results = {}

for cam_id in CAMERAS:
    video_path = os.path.join(INPUTS_DIR, f"{cam_id}.mp4")
    zone_name  = zones_cfg[cam_id]["zone"]
    polygon    = zones_cfg[cam_id]["polygon"]
    zx1, zy1, zx2, zy2 = _poly_bounds(polygon)

    cap       = cv2.VideoCapture(video_path)
    src_fps   = cap.get(cv2.CAP_PROP_FPS)
    total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    time_per_proc = FRAME_SKIP / src_fps   # seconds represented by each processed frame

    print(f"[{cam_id}] zone={zone_name}  polygon=({zx1},{zy1})-({zx2},{zy2})"
          f"  {total_src} frames @ {src_fps:.2f}fps"
          f"  time_per_proc={time_per_proc:.3f}s")

    # Video writer
    mp4_out    = os.path.join(OUTPUT_DIR, f"{cam_id}_visit_validation.mp4")
    out_fps    = max(1, src_fps / FRAME_SKIP)
    fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
    writer     = cv2.VideoWriter(mp4_out, fourcc, out_fps, (W, H))
    use_writer = writer.isOpened()
    if not use_writer:
        writer.release()
        print(f"  [WARN] VideoWriter failed -- saving JPEG frames.")
    else:
        print(f"  [OK]   VideoWriter: {mp4_out}")

    # Tracker state
    next_id       = 0
    active_tracks = {}
    # active_tracks[id] = {
    #   centroid, frames_alive, disappeared,
    #   in_zone, zone_enter_proc, zone_last_proc
    # }

    # Completed visit records
    completed_visits = []
    # {track_id, zone_enter_proc, zone_exit_proc,
    #  enter_ts_sec, exit_ts_sec, dwell_sec, counted, note}

    proc_idx = 0
    src_idx  = 0

    while src_idx < min(MAX_SRC_FRAMES, total_src):
        cap.set(cv2.CAP_PROP_POS_FRAMES, src_idx)
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (W, H))

        # -- YOLO detect -------------------------------------------------------
        res  = model(frame, conf=CONF_THRESH, classes=[PERSON_CLASS], verbose=False)
        dets = []
        if res[0].boxes is not None:
            for box in res[0].boxes:
                if int(box.cls[0]) == PERSON_CLASS:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    dets.append((x1, y1, x2, y2, *_centroid(x1, y1, x2, y2)))

        new_cents = [(d[4], d[5]) for d in dets]

        # -- Greedy match -------------------------------------------------------
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

            cx, cy     = new_cents[di]
            td         = active_tracks[tid]
            was_in     = td["in_zone"]
            now_in     = _in_rect_zone(cx, cy, zx1, zy1, zx2, zy2)

            if not was_in and now_in:
                # Zone entry event
                td["zone_enter_proc"] = proc_idx
            elif was_in and not now_in:
                # Zone exit event -- record visit
                ep    = td["zone_enter_proc"]
                dwell = (proc_idx - ep) * time_per_proc
                completed_visits.append({
                    "track_id":       tid,
                    "zone_enter_proc": ep,
                    "zone_exit_proc":  proc_idx,
                    "enter_ts_sec":    ep * time_per_proc,
                    "exit_ts_sec":     proc_idx * time_per_proc,
                    "dwell_sec":       dwell,
                    "counted":         dwell >= MIN_DWELL_SECS,
                    "note":            "",
                })

            td["centroid"]     = new_cents[di]
            td["in_zone"]      = now_in
            td["zone_last_proc"] = proc_idx if now_in else td.get("zone_last_proc")
            td["frames_alive"] += 1
            td["disappeared"]  = 0
            used_tracks.add(tid)
            used_dets.add(di)

        # -- Remove disappeared tracks ----------------------------------------
        for tid in list(active_tracks):
            if tid not in used_tracks:
                active_tracks[tid]["disappeared"] += 1
                if active_tracks[tid]["disappeared"] >= MAX_DISAPPEARED:
                    td = active_tracks[tid]
                    if td["in_zone"] and td.get("zone_enter_proc") is not None:
                        ep    = td["zone_enter_proc"]
                        dwell = (proc_idx - ep) * time_per_proc
                        completed_visits.append({
                            "track_id":       tid,
                            "zone_enter_proc": ep,
                            "zone_exit_proc":  proc_idx,
                            "enter_ts_sec":    ep * time_per_proc,
                            "exit_ts_sec":     proc_idx * time_per_proc,
                            "dwell_sec":       dwell,
                            "counted":         dwell >= MIN_DWELL_SECS,
                            "note":            "track disappeared inside zone",
                        })
                    del active_tracks[tid]

        # -- Create new tracks ------------------------------------------------
        for di, cent in enumerate(new_cents):
            if di not in used_dets:
                cx, cy = cent
                now_in = _in_rect_zone(cx, cy, zx1, zy1, zx2, zy2)
                active_tracks[next_id] = {
                    "centroid":        cent,
                    "frames_alive":    1,
                    "disappeared":     0,
                    "in_zone":         now_in,
                    "zone_enter_proc": proc_idx if now_in else None,
                    "zone_last_proc":  proc_idx if now_in else None,
                }
                next_id += 1

        # -- Annotate frame ---------------------------------------------------
        vis = frame.copy()

        # Zone polygon outline
        pts = [(p[0], p[1]) for p in polygon]
        for i in range(len(pts)):
            cv2.line(vis, pts[i], pts[(i + 1) % len(pts)], (0, 200, 60), 2)
        cv2.putText(vis, zone_name, (zx1 + 4, zy1 + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 60), 1)

        # Running visit count
        v_count = sum(1 for v in completed_visits if v["counted"])
        in_zone_now = sum(1 for td in active_tracks.values() if td["in_zone"])

        # Bounding boxes
        for det in dets:
            x1, y1, x2, y2, cx, cy = det
            in_z       = False
            dwell_curr = 0.0
            lbl_id     = "?"
            for tid, td in active_tracks.items():
                if td["centroid"] == (cx, cy):
                    in_z   = td["in_zone"]
                    lbl_id = str(tid)
                    if in_z and td.get("zone_enter_proc") is not None:
                        dwell_curr = (proc_idx - td["zone_enter_proc"]) * time_per_proc
                    break
            color = (0, 220, 60) if in_z else (110, 110, 110)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(vis, f"ID:{lbl_id}", (x1, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1)
            if in_z and dwell_curr > 0:
                cv2.putText(vis, _fmt(dwell_curr), (x1, y2 + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 60), 1)

        # Counters overlay
        cv2.rectangle(vis, (3, 3), (240, 62), (0, 0, 0), -1)
        cv2.putText(vis, f"Visits (>={MIN_DWELL_SECS}s): {v_count}", (7, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 60), 1)
        cv2.putText(vis, f"In zone now: {in_zone_now}", (7, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 220, 0), 1)
        cv2.putText(vis, f"src:{src_idx} proc:{proc_idx}",
                    (W - 165, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 0), 1)

        if use_writer:
            writer.write(vis)
        else:
            cv2.imwrite(os.path.join(OUTPUT_DIR, f"{cam_id}_frame_{proc_idx:04d}.jpg"), vis)

        proc_idx += 1
        src_idx  += FRAME_SKIP

    # -- Flush remaining in-zone tracks at end of window ---------------------
    for tid, td in active_tracks.items():
        if td["in_zone"] and td.get("zone_enter_proc") is not None:
            ep    = td["zone_enter_proc"]
            dwell = (proc_idx - ep) * time_per_proc
            completed_visits.append({
                "track_id":       tid,
                "zone_enter_proc": ep,
                "zone_exit_proc":  proc_idx,
                "enter_ts_sec":    ep * time_per_proc,
                "exit_ts_sec":     proc_idx * time_per_proc,
                "dwell_sec":       dwell,
                "counted":         dwell >= MIN_DWELL_SECS,
                "note":            "still in zone at end of window",
            })

    cap.release()
    if use_writer:
        writer.release()

    # -- Compute statistics --------------------------------------------------
    counted = [v for v in completed_visits if v["counted"]]
    dwells  = [v["dwell_sec"] for v in counted]

    all_results[cam_id] = {
        "zone":            zone_name,
        "proc_frames":     proc_idx,
        "total_ids":       next_id,
        "raw_visits":      len(completed_visits),
        "counted_visits":  len(counted),
        "dwells":          dwells,
        "avg_dwell":       sum(dwells) / len(dwells) if dwells else 0.0,
        "max_dwell":       max(dwells) if dwells else 0.0,
        "min_dwell":       min(dwells) if dwells else 0.0,
        "visit_log":       completed_visits,
    }
    print(f"  -> {len(counted)} qualifying visits  "
          f"avg={_fmt(sum(dwells)/len(dwells)) if dwells else 'n/a'}  "
          f"max={_fmt(max(dwells)) if dwells else 'n/a'}\n")

# -- Final summary -----------------------------------------------------------
print()
print("=" * 65)
print("CHECKPOINT 2.4 SUMMARY -- Zone Visit Detection Validation")
print("=" * 65)
print(f"frame_skip={FRAME_SKIP}  conf={CONF_THRESH}"
      f"  tracker_dist={TRACKER_DIST}px  min_dwell={MIN_DWELL_SECS}s\n")

for cam_id in CAMERAS:
    r = all_results[cam_id]
    print(f"{cam_id} | {r['zone'].upper()}")
    print(f"  Processed frames     : {r['proc_frames']}")
    print(f"  Total track IDs      : {r['total_ids']}")
    print(f"  Raw visit events     : {r['raw_visits']}  (any time in zone)")
    print(f"  Qualifying visits    : {r['counted_visits']}  (dwell >= {MIN_DWELL_SECS}s)")
    if r["dwells"]:
        print(f"  Average dwell        : {_fmt(r['avg_dwell'])}")
        print(f"  Longest dwell        : {_fmt(r['max_dwell'])}")
        print(f"  Shortest qualifying  : {_fmt(r['min_dwell'])}")
        if r["visit_log"]:
            print(f"  Visit log (counted):")
            for v in r["visit_log"]:
                if v["counted"]:
                    note = f"  [{v['note']}]" if v.get("note") else ""
                    print(f"    ID:{v['track_id']:>3}  "
                          f"enter={_fmt(v['enter_ts_sec'])}  "
                          f"exit={_fmt(v['exit_ts_sec'])}  "
                          f"dwell={_fmt(v['dwell_sec'])}{note}")
    else:
        print(f"  No qualifying visits detected in this window.")
    print()

# -- Q4 Verdict -------------------------------------------------------------
cameras_with_visits = [c for c in CAMERAS if all_results[c]["counted_visits"] > 0]
print("-" * 65)
if cameras_with_visits:
    print(f"Q4 ANSWER : YES -- zone visits detected and dwell times computed.")
    print(f"            Cameras with visits: {', '.join(cameras_with_visits)}")
else:
    print(f"Q4 ANSWER : UNCERTAIN -- no qualifying visits in this window.")
    print(f"            Check if persons were present in these 1000 src frames.")

print()
print(f"Output videos:")
for cam_id in CAMERAS:
    print(f"  {os.path.join(OUTPUT_DIR, cam_id + '_visit_validation.mp4')}")
print("=" * 65)
