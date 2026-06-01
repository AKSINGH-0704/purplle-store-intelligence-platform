"""
Checkpoint 2.5 -- CAM_4 background subtraction calibration.

Validates whether OpenCV MOG2 background subtraction can reliably detect
warehouse activity on CAM_4 despite observed lighting flicker, and determines
the correct warehouse_motion_threshold for config.json.

Design note: Unlike YOLO tools (which use frame_skip), MOG2 is a temporal model
that requires consecutive frames to build an accurate background model. Skipping
frames prevents MOG2 from adapting to gradual lighting changes, making it unable
to distinguish flicker from genuine motion. This tool processes frames
sequentially (no frame_skip) for accurate background modeling.

This script is a validation tool only. It does NOT write to events.json,
does NOT implement any src/ module, and does NOT generate pipeline events.

Usage:
    python tools/test_warehouse_motion.py

Output:
    tools/warehouse_motion_output/warehouse_validation.mp4

Q5 success criterion:
    MOG2 produces detectable motion events for genuine warehouse activity
    AND the lighting flicker produces a measurable contour area that can be
    used to set warehouse_motion_threshold above the noise floor.
"""

import cv2
import json
import os
import sys

# -- Paths -------------------------------------------------------------------
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
ZONES_PATH  = os.path.join(ROOT, "zones.json")
VIDEO_PATH  = os.path.join(ROOT, "inputs", "CAM_4.mp4")
OUTPUT_DIR  = os.path.join(ROOT, "tools", "warehouse_motion_output")

# -- Config ------------------------------------------------------------------
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

W, H                      = cfg["detection_resolution"]       # [640, 360]
CURRENT_THRESHOLD         = cfg["warehouse_motion_threshold"]  # 500 sq px
FRAME_SKIP_NOTE           = cfg["frame_skip"]                  # 5 (not used -- see docstring)
MAX_SRC_FRAMES            = 1000   # consecutive frames for background modeling

# Area classification thresholds for annotation (not for counting)
NOISE_FLOOR_MAX   = 100    # below this: sensor/compression noise, ignore
FLICKER_BAND_MAX  = CURRENT_THRESHOLD   # 100-500: flicker candidates
# above CURRENT_THRESHOLD: motion event candidates

# -- Zones -- CAM_4 ----------------------------------------------------------
with open(ZONES_PATH) as f:
    zones_cfg = json.load(f)

cam4_cfg = zones_cfg["CAM_4"]
polygon  = cam4_cfg["polygon"]
zone_name = cam4_cfg["zone"]
ZONE_X1  = min(p[0] for p in polygon)
ZONE_Y1  = min(p[1] for p in polygon)
ZONE_X2  = max(p[0] for p in polygon)
ZONE_Y2  = max(p[1] for p in polygon)

# -- Preflight ---------------------------------------------------------------
for path, label in [(VIDEO_PATH, "CAM_4.mp4"), (CONFIG_PATH, "config.json")]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found: {path}")
        sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -- Video input -------------------------------------------------------------
cap       = cv2.VideoCapture(VIDEO_PATH)
src_fps   = cap.get(cv2.CAP_PROP_FPS)
total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"[CONFIG]  resolution={W}x{H}  warehouse_motion_threshold={CURRENT_THRESHOLD}sq px")
print(f"[VIDEO]   {total_src} frames @ {src_fps:.2f} fps")
print(f"[PLAN]    processing {min(MAX_SRC_FRAMES, total_src)} consecutive frames")
print(f"[NOTE]    frame_skip NOT applied -- MOG2 requires consecutive frames\n")

# -- Video writer ------------------------------------------------------------
mp4_out    = os.path.join(OUTPUT_DIR, "warehouse_validation.mp4")
fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
writer     = cv2.VideoWriter(mp4_out, fourcc, src_fps, (W, H))
use_writer = writer.isOpened()
if not use_writer:
    writer.release()
    print("[WARN]  VideoWriter failed -- saving JPEG frames.")
else:
    print(f"[OK]    VideoWriter: {mp4_out}\n")

# -- MOG2 background subtractor ---------------------------------------------
mog2 = cv2.createBackgroundSubtractorMOG2(
    history=200,          # number of frames for background model
    varThreshold=16,      # pixel variance threshold for foreground detection
    detectShadows=False   # shadows not needed; reduces noise
)

# -- Data collection ---------------------------------------------------------
frame_areas   = []   # max contour area per frame (0 if no contours)
motion_frames = []   # frame indices (raw) where max_area > CURRENT_THRESHOLD
all_contour_areas = []  # every individual contour area > NOISE_FLOOR_MAX

motion_event_count = 0
in_motion_event    = False
current_event_start = None
motion_events      = []   # [{start_frame, end_frame, duration_sec, max_area}]

# -- Main loop ---------------------------------------------------------------
src_idx = 0
while src_idx < min(MAX_SRC_FRAMES, total_src):
    ret, frame = cap.read()  # sequential read -- critical for MOG2
    if not ret:
        break

    frame = cv2.resize(frame, (W, H))

    # -- Apply MOG2 foreground mask -------------------------------------------
    fg_mask = mog2.apply(frame)

    # Clean mask: remove small holes and noise blobs
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

    # -- Find contours in zone polygon only -----------------------------------
    zone_mask = fg_mask.copy()
    zone_mask[:ZONE_Y1, :]  = 0
    zone_mask[ZONE_Y2:, :]  = 0
    zone_mask[:, :ZONE_X1]  = 0
    zone_mask[:, ZONE_X2:]  = 0

    contours, _ = cv2.findContours(zone_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    # Compute contour areas (ignore tiny noise)
    valid_areas = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > NOISE_FLOOR_MAX:
            valid_areas.append((area, cnt))
            all_contour_areas.append(area)

    max_area = max((a for a, _ in valid_areas), default=0)
    frame_areas.append(max_area)

    # -- Motion event tracking -----------------------------------------------
    is_motion = max_area > CURRENT_THRESHOLD

    if is_motion and not in_motion_event:
        in_motion_event    = True
        current_event_start = src_idx
        motion_event_count += 1

    if in_motion_event and not is_motion:
        duration = (src_idx - current_event_start) / src_fps
        motion_events.append({
            "start_frame": current_event_start,
            "end_frame":   src_idx,
            "duration_sec": duration,
            "max_area":    max(
                frame_areas[current_event_start:src_idx + 1]
                if current_event_start < len(frame_areas) else [0]
            ),
        })
        in_motion_event = False

    if is_motion:
        motion_frames.append(src_idx)

    # -- Annotate frame -------------------------------------------------------
    vis = frame.copy()

    # Semi-transparent foreground overlay (light blue tint for motion areas)
    fg_color = cv2.cvtColor(zone_mask, cv2.COLOR_GRAY2BGR)
    fg_color[:, :, 0] = 0      # R channel
    fg_color[:, :, 1] = fg_color[:, :, 1] // 3   # G channel
    vis = cv2.addWeighted(vis, 0.75, fg_color, 0.25, 0)

    # Zone polygon outline
    pts = [(p[0], p[1]) for p in polygon]
    for i in range(len(pts)):
        cv2.line(vis, pts[i], pts[(i + 1) % len(pts)], (0, 200, 60), 1)
    cv2.putText(vis, zone_name, (ZONE_X1 + 4, ZONE_Y1 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 60), 1)

    # Draw contours by classification
    for area, cnt in valid_areas:
        if area > CURRENT_THRESHOLD:
            color     = (0, 0, 220)   # red  -- above threshold
            thickness = 2
        else:
            color     = (0, 200, 220) # yellow -- flicker candidate
            thickness = 1
        cv2.drawContours(vis, [cnt], -1, color, thickness)
        # Label area on largest contours
        if area > 200:
            m = cv2.moments(cnt)
            if m["m00"] > 0:
                cx = int(m["m10"] / m["m00"])
                cy = int(m["m01"] / m["m00"])
                cv2.putText(vis, f"{int(area)}", (cx - 15, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

    # Event state banner
    if is_motion:
        state_text  = f"MOTION EVENT  area={int(max_area)}"
        state_color = (0, 0, 220)
        cv2.rectangle(vis, (0, 0), (W, 28), (0, 0, 150), -1)
    elif max_area > NOISE_FLOOR_MAX:
        state_text  = f"flicker?  area={int(max_area)}  (threshold={CURRENT_THRESHOLD})"
        state_color = (0, 200, 220)
        cv2.rectangle(vis, (0, 0), (W, 28), (60, 60, 0), -1)
    else:
        state_text  = "static"
        state_color = (140, 140, 140)

    cv2.putText(vis, state_text, (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, state_color, 1)

    # Counters overlay (bottom strip)
    cv2.rectangle(vis, (0, H - 30), (W, H), (0, 0, 0), -1)
    cv2.putText(vis, f"frame:{src_idx}  events:{motion_event_count}"
                     f"  threshold:{CURRENT_THRESHOLD}",
                (6, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 0), 1)

    if use_writer:
        writer.write(vis)
    else:
        if src_idx % 5 == 0:   # save every 5th frame if no VideoWriter
            cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{src_idx:05d}.jpg"), vis)

    src_idx += 1
    if src_idx % 100 == 0:
        print(f"  processed {src_idx}/{min(MAX_SRC_FRAMES, total_src)} frames ...")

# -- Flush last open event ---------------------------------------------------
if in_motion_event:
    duration = (src_idx - current_event_start) / src_fps
    motion_events.append({
        "start_frame":  current_event_start,
        "end_frame":    src_idx,
        "duration_sec": duration,
        "max_area":     max(frame_areas[current_event_start:] if current_event_start < len(frame_areas) else [0]),
    })

cap.release()
if use_writer:
    writer.release()

# -- Statistics --------------------------------------------------------------
total_frames = len(frame_areas)
frames_with_motion = len(motion_frames)
frames_flicker     = sum(1 for a in frame_areas if NOISE_FLOOR_MAX < a <= CURRENT_THRESHOLD)
frames_static      = sum(1 for a in frame_areas if a <= NOISE_FLOOR_MAX)
frames_above       = sum(1 for a in frame_areas if a > CURRENT_THRESHOLD)

# Percentile calculation
def percentile(data, p):
    if not data:
        return 0
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]

max_area_vals = sorted(frame_areas)
pct_stats = {p: percentile(frame_areas, p) for p in [50, 75, 90, 95, 99, 100]}

# Recommend threshold: just above the 99th percentile of flicker-band frames
flicker_areas = [a for a in frame_areas if NOISE_FLOOR_MAX < a <= CURRENT_THRESHOLD * 3]
p99_flicker   = percentile(flicker_areas, 99) if flicker_areas else 0
recommended   = max(int(p99_flicker * 1.3), CURRENT_THRESHOLD)  # 30% safety margin

# Simple ASCII histogram of max_area per frame
def ascii_hist(values, bins=10, width=40):
    if not values or max(values) == 0:
        return "  (no data)"
    max_v   = max(values)
    bin_w   = max_v / bins
    counts  = [0] * bins
    for v in values:
        b = min(int(v / bin_w), bins - 1)
        counts[b] += 1
    max_c   = max(counts)
    lines   = []
    for i, c in enumerate(counts):
        lo = int(i * bin_w)
        hi = int((i + 1) * bin_w)
        bar = "#" * int(c / max_c * width) if max_c > 0 else ""
        lines.append(f"  {lo:>6}-{hi:<6}: {bar} ({c})")
    return "\n".join(lines)

# -- Print summary -----------------------------------------------------------
print()
print("=" * 70)
print("CHECKPOINT 2.5 SUMMARY -- CAM_4 Background Subtraction Calibration")
print("=" * 70)
print(f"Video processed   : {src_idx} consecutive frames @ {src_fps:.2f} fps")
print(f"Duration covered  : {src_idx / src_fps:.1f}s of footage")
print(f"MOG2 settings     : history=200, varThreshold=16, detectShadows=False")
print(f"Current threshold : {CURRENT_THRESHOLD} sq px")
print()
print("Frame classification:")
print(f"  Static (max_area <= {NOISE_FLOOR_MAX}px)        : {frames_static} frames  ({100*frames_static//total_frames}%)")
print(f"  Flicker-band ({NOISE_FLOOR_MAX}-{CURRENT_THRESHOLD}px) : {frames_flicker} frames  ({100*frames_flicker//total_frames}%)")
print(f"  Motion event  (> {CURRENT_THRESHOLD}px)         : {frames_above} frames  ({100*frames_above//total_frames}%)")
print()
print("Max contour area per frame -- percentiles:")
for p, v in pct_stats.items():
    print(f"  {p:>3}th percentile : {v:.0f} sq px")
print()
print("Max contour area distribution (all frames):")
print(ascii_hist(frame_areas))
print()
print(f"Motion events detected (area > {CURRENT_THRESHOLD}sq px):")
if motion_events:
    for i, ev in enumerate(motion_events, 1):
        print(f"  Event {i:>2}: frames {ev['start_frame']:>5}-{ev['end_frame']:<5}"
              f"  duration={ev['duration_sec']:.1f}s  max_area={ev['max_area']:.0f}")
else:
    print("  None detected above current threshold.")
print()
print("Threshold calibration analysis:")
print(f"  99th percentile of flicker-band areas : {p99_flicker:.0f} sq px")
print(f"  Recommended threshold (99th x 1.3)    : {recommended} sq px")
print(f"  Current threshold                      : {CURRENT_THRESHOLD} sq px")
if recommended > CURRENT_THRESHOLD:
    print(f"  ACTION: Consider raising threshold to {recommended} sq px in config.json")
    print(f"          to clear the observed flicker noise floor.")
elif recommended < CURRENT_THRESHOLD:
    print(f"  Current threshold appears conservative. No change needed.")
else:
    print(f"  Current threshold aligns with calibration. No change needed.")
print()
print("-" * 70)

# Q5 verdict
if frames_above > 0 or motion_events:
    print(f"Q5 ANSWER : MOTION DETECTED -- {len(motion_events)} event(s) above threshold.")
    print(f"            Review warehouse_validation.mp4 for visual confirmation.")
    print(f"            Red contours = above threshold (genuine motion candidate).")
    print(f"            Yellow contours = flicker-band (below threshold).")
elif frames_flicker > 0:
    print(f"Q5 ANSWER : ONLY FLICKER OBSERVED -- all motion below threshold ({CURRENT_THRESHOLD}sq px).")
    print(f"            Threshold may be well-calibrated for this footage window.")
    print(f"            Extend to more frames to find genuine warehouse activity.")
else:
    print(f"Q5 ANSWER : NO MOTION -- all frames static in this window.")
    print(f"            Try a different frame range in the video.")

print()
if use_writer:
    print(f"Output: {mp4_out}")
else:
    n = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpg")])
    print(f"Output: {OUTPUT_DIR}/ ({n} JPEG frames)")
print("=" * 70)
