"""
CAM_4 investigation script — flicker distribution, spatial analysis,
genuine motion search. Run from project root.
Warm-up suppression: first 200 frames skipped (frame 0 cold-start confirmed invalid).
"""
import cv2
import json
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import load_config, load_zones

cfg   = load_config("config.json")
zones = load_zones("zones.json")

W, H      = cfg["detection_resolution"]
threshold = cfg["warehouse_motion_threshold"]
polygon   = zones["CAM_4"]["polygon"]
zone_x1   = min(p[0] for p in polygon)   # 10
zone_y1   = min(p[1] for p in polygon)   # 30
zone_x2   = max(p[0] for p in polygon)   # 630
zone_y2   = max(p[1] for p in polygon)   # 355

zone_h          = zone_y2 - zone_y1          # 325
band_upper_y2   = zone_y1 + zone_h // 3      # 138  — top third: shelves/boxes
band_center_y2  = zone_y1 + 2*(zone_h // 3)  # 247  — mid third: workbench

NOISE_FLOOR   = 100
WARMUP_FRAMES = 200   # confirmed invalid — MOG2 cold-start
PROCESS_MAX   = 9999  # full video (3647 frames)

OUT_DIR = os.path.join("tools", "warehouse_motion_output", "investigation")
os.makedirs(OUT_DIR, exist_ok=True)

print(f"Zone: x={zone_x1}-{zone_x2}, y={zone_y1}-{zone_y2}")
print(f"Band upper : y={zone_y1}-{band_upper_y2}  (shelves/boxes)")
print(f"Band center: y={band_upper_y2}-{band_center_y2}  (workbench area)")
print(f"Band lower : y={band_center_y2}-{zone_y2}  (floor tiles)")
print(f"Warm-up skip: first {WARMUP_FRAMES} frames\n")

mog2 = cv2.createBackgroundSubtractorMOG2(
    history=200, varThreshold=16, detectShadows=False
)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

# Collected data
all_areas:    list = []   # max_area per qualifying frame (post-warmup)
frame_stats:  list = []   # [{frame_idx, ts, max_area, px_upper, px_center, px_lower}]
events:       list = []   # consecutive qualifying runs

in_event       = False
event_start    = 0
event_max_area = 0.0

cap     = cv2.VideoCapture("inputs/CAM_4.mp4")
src_fps = cap.get(cv2.CAP_PROP_FPS)
total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_idx = 0
limit   = min(PROCESS_MAX, total)

print(f"Processing {limit} of {total} frames @ {src_fps:.2f} fps ...")

while src_idx < limit:
    ret, frame = cap.read()
    if not ret:
        break

    frame   = cv2.resize(frame, (W, H))
    fg_mask = mog2.apply(frame)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

    zone_mask = fg_mask.copy()
    zone_mask[:zone_y1, :]  = 0
    zone_mask[zone_y2:, :]  = 0
    zone_mask[:, :zone_x1]  = 0
    zone_mask[:, zone_x2:]  = 0

    contours, _ = cv2.findContours(
        zone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    valid_areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > NOISE_FLOOR]
    max_area    = max(valid_areas) if valid_areas else 0.0
    is_motion   = max_area > threshold

    if src_idx >= WARMUP_FRAMES:
        px_upper  = int(np.sum(zone_mask[zone_y1:band_upper_y2,
                                         zone_x1:zone_x2] > 0))
        px_center = int(np.sum(zone_mask[band_upper_y2:band_center_y2,
                                         zone_x1:zone_x2] > 0))
        px_lower  = int(np.sum(zone_mask[band_center_y2:zone_y2,
                                         zone_x1:zone_x2] > 0))

        if is_motion:
            all_areas.append(max_area)
            frame_stats.append({
                "frame_idx": src_idx,
                "ts":        round(src_idx / src_fps, 2),
                "max_area":  max_area,
                "px_upper":  px_upper,
                "px_center": px_center,
                "px_lower":  px_lower,
            })

        if is_motion and not in_event:
            in_event       = True
            event_start    = src_idx
            event_max_area = max_area
        elif is_motion and in_event:
            event_max_area = max(event_max_area, max_area)
        elif not is_motion and in_event:
            dur = (src_idx - event_start) / src_fps
            events.append({
                "start":    event_start,
                "end":      src_idx,
                "dur":      round(dur, 2),
                "max_area": round(event_max_area, 1),
                "ts_start": round(event_start / src_fps, 2),
            })
            in_event = False

    src_idx += 1

if in_event:
    dur = (src_idx - event_start) / src_fps
    events.append({
        "start":    event_start,
        "end":      src_idx,
        "dur":      round(dur, 2),
        "max_area": round(event_max_area, 1),
        "ts_start": round(event_start / src_fps, 2),
    })

cap.release()
print(f"Processing complete. {src_idx} frames read.\n")

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS 1: Flicker / Area distribution
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 62)
print(f"ANALYSIS 1: Area Distribution  (threshold={threshold}, post-warmup)")
print("=" * 62)
print(f"Qualifying frames : {len(all_areas)}")
if all_areas:
    s = sorted(all_areas)
    n = len(s)
    def pct(p):
        return s[min(int(n * p / 100), n - 1)]

    print(f"  p50 : {pct(50):>10,.0f} sq px")
    print(f"  p90 : {pct(90):>10,.0f} sq px")
    print(f"  p95 : {pct(95):>10,.0f} sq px")
    print(f"  p99 : {pct(99):>10,.0f} sq px")
    print(f"  max : {max(s):>10,.0f} sq px")
    print()
    bands = [
        (1631,   5_000),
        (5_000,  10_000),
        (10_000, 20_000),
        (20_000, 30_000),
        (30_000, 40_000),
        (40_000, 50_000),
        (50_000, 999_999),
    ]
    print("  Histogram (qualifying frames by area band):")
    for lo, hi in bands:
        cnt = sum(1 for a in s if lo <= a < hi)
        bar = "#" * min(int(cnt * 50 // max(n, 1)), 50)
        label = f"{lo//1000}k-{hi//1000}k" if hi < 999_999 else f"{lo//1000}k+"
        print(f"  {label:>10}: {bar} ({cnt})")

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS 2: Spatial distribution
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("ANALYSIS 2: Spatial Distribution of Foreground Pixels")
print("=" * 62)
total_px_upper  = sum(f["px_upper"]  for f in frame_stats)
total_px_center = sum(f["px_center"] for f in frame_stats)
total_px_lower  = sum(f["px_lower"]  for f in frame_stats)
total_px_all    = total_px_upper + total_px_center + total_px_lower

if total_px_all > 0:
    pct_u = 100 * total_px_upper  // total_px_all
    pct_c = 100 * total_px_center // total_px_all
    pct_l = 100 * total_px_lower  // total_px_all
    print(f"  Upper  (y={zone_y1}-{band_upper_y2}, shelves) : "
          f"{total_px_upper:>9,} px  ({pct_u}%)")
    print(f"  Center (y={band_upper_y2}-{band_center_y2}, workbench): "
          f"{total_px_center:>9,} px  ({pct_c}%)")
    print(f"  Lower  (y={band_center_y2}-{zone_y2}, floor)   : "
          f"{total_px_lower:>9,} px  ({pct_l}%)")
    print()
    n = len(frame_stats)
    upper_dom  = sum(1 for f in frame_stats
                     if f["px_upper"]  > f["px_center"] and f["px_upper"]  > f["px_lower"])
    center_dom = sum(1 for f in frame_stats
                     if f["px_center"] > f["px_upper"]  and f["px_center"] > f["px_lower"])
    lower_dom  = sum(1 for f in frame_stats
                     if f["px_lower"]  > f["px_upper"]  and f["px_lower"]  > f["px_center"])
    print(f"  Band dominating each qualifying frame (of {n}):")
    print(f"    Upper  dominant : {upper_dom:>4}  ({100*upper_dom//max(n,1)}%)")
    print(f"    Center dominant : {center_dom:>4}  ({100*center_dom//max(n,1)}%)")
    print(f"    Lower  dominant : {lower_dom:>4}  ({100*lower_dom//max(n,1)}%)")

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS 3: Event summary and genuine motion candidates
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("ANALYSIS 3: Event Summary (post-warmup, full video)")
print("=" * 62)
print(f"Total events: {len(events)}")
buckets = {"<=0.1s": 0, "0.1-0.5s": 0, "0.5-1.0s": 0, "1.0-2.0s": 0, ">2.0s": 0}
long_events = []
for ev in events:
    d = ev["dur"]
    if   d <= 0.1:  buckets["<=0.1s"]   += 1
    elif d <= 0.5:  buckets["0.1-0.5s"] += 1
    elif d <= 1.0:  buckets["0.5-1.0s"] += 1
    elif d <= 2.0:  buckets["1.0-2.0s"] += 1
    else:           buckets[">2.0s"]     += 1
    if d >= 0.5:
        long_events.append(ev)

for k, v in buckets.items():
    print(f"  {k:12}: {v}")
print()
print("Events >= 0.5s (genuine motion candidates):")
for ev in long_events:
    print(f"  ts={ev['ts_start']:6.1f}s  frames={ev['start']:4d}-{ev['end']:<4d}"
          f"  dur={ev['dur']:.2f}s  max_area={ev['max_area']:>8,.0f}")
if not long_events:
    print("  (none found in full video)")

# ─────────────────────────────────────────────────────────────────────────────
# Save inspection frames: sample events across full video + long events
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("Saving inspection frames ...")
print("=" * 62)

# Choose frames to inspect
inspect_targets = set()

# 4 evenly-spaced events across the post-warmup video
if events:
    step = max(1, len(events) // 4)
    for i in range(0, len(events), step):
        inspect_targets.add(events[i]["start"])

# All long events (>= 0.5s)
for ev in long_events:
    inspect_targets.add(ev["start"])
    mid = (ev["start"] + ev["end"]) // 2
    inspect_targets.add(mid)

# Sample near start/mid/end of full video (post-warmup)
for frac in [0.15, 0.40, 0.65, 0.90]:
    inspect_targets.add(int(WARMUP_FRAMES + frac * (limit - WARMUP_FRAMES)))

print(f"Target frames: {sorted(inspect_targets)}")

# Re-run MOG2 to extract frames (must replay sequentially)
mog2b  = cv2.createBackgroundSubtractorMOG2(
    history=200, varThreshold=16, detectShadows=False
)
cap2   = cv2.VideoCapture("inputs/CAM_4.mp4")
saved  = set()
src_idx = 0

while src_idx < limit and len(saved) < len(inspect_targets):
    ret, frame = cap2.read()
    if not ret:
        break

    frame_resized = cv2.resize(frame, (W, H))
    fg             = mog2b.apply(frame_resized)
    fg             = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)

    zone_m = fg.copy()
    zone_m[:zone_y1, :] = 0; zone_m[zone_y2:, :] = 0
    zone_m[:, :zone_x1] = 0; zone_m[:, zone_x2:] = 0

    contours2, _ = cv2.findContours(zone_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if src_idx in inspect_targets and src_idx not in saved:
        valid2  = [(cv2.contourArea(c), c) for c in contours2
                   if cv2.contourArea(c) > NOISE_FLOOR]
        max_a2  = max((a for a, _ in valid2), default=0)
        above   = max_a2 > threshold

        vis = frame_resized.copy()
        # Zone box
        cv2.rectangle(vis, (zone_x1, zone_y1), (zone_x2, zone_y2), (0, 200, 60), 1)
        # Band lines
        cv2.line(vis, (zone_x1, band_upper_y2),  (zone_x2, band_upper_y2),  (255,255,0), 1)
        cv2.line(vis, (zone_x1, band_center_y2), (zone_x2, band_center_y2), (255,255,0), 1)
        # Contours
        for area, cnt in valid2:
            color     = (0, 0, 220) if area > threshold else (0, 200, 220)
            thickness = 2 if area > threshold else 1
            cv2.drawContours(vis, [cnt], -1, color, thickness)
            if area > 2000:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.putText(vis, f"{int(area)}", (cx - 20, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        # Banner
        ts_str = f"{src_idx / src_fps:.2f}s"
        label  = f"f={src_idx} t={ts_str} area={int(max_a2)} {'MOTION' if above else 'static'}"
        cv2.rectangle(vis, (0, 0), (W, 22), (0, 0, 100) if above else (30, 60, 30), -1)
        cv2.putText(vis, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 0), 1)

        mask_bgr = cv2.cvtColor(zone_m, cv2.COLOR_GRAY2BGR)
        combined = np.hstack([vis, mask_bgr])
        path = os.path.join(OUT_DIR, f"inspect_{src_idx:04d}.jpg")
        cv2.imwrite(path, combined)
        saved.add(src_idx)
        print(f"  Saved frame {src_idx:4d}  t={ts_str:7s}  area={int(max_a2):>8,}  {'MOTION' if above else 'static'}")

    src_idx += 1

cap2.release()
print()
print("Investigation complete.")
