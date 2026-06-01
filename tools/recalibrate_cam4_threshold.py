"""
CAM_4 threshold recalibration against revised zone polygon (y=30-246).
Measures residual flicker after floor exclusion and computes p99 x 1.30 threshold.
Run from project root: python tools/recalibrate_cam4_threshold.py
"""
import cv2
import math
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import load_config, load_zones

cfg   = load_config("config.json")
zones = load_zones("zones.json")    # reads the UPDATED polygon (y=30-246)

W, H      = cfg["detection_resolution"]
OLD_THRESH = cfg["warehouse_motion_threshold"]   # 1631 — being recalibrated
polygon   = zones["CAM_4"]["polygon"]
ZONE_X1   = min(p[0] for p in polygon)   # 10
ZONE_Y1   = min(p[1] for p in polygon)   # 30
ZONE_X2   = max(p[0] for p in polygon)   # 630
ZONE_Y2   = max(p[1] for p in polygon)   # 246  (revised)

NOISE_FLOOR   = 100
WARMUP_FRAMES = 200

print(f"Revised zone: x={ZONE_X1}-{ZONE_X2}, y={ZONE_Y1}-{ZONE_Y2}")
print(f"Zone area   : {(ZONE_X2-ZONE_X1) * (ZONE_Y2-ZONE_Y1):,} sq px")
print(f"Old threshold: {OLD_THRESH}")
print(f"Warmup: skipping first {WARMUP_FRAMES} frames\n")

mog2   = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16, detectShadows=False)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

cap     = cv2.VideoCapture("inputs/CAM_4.mp4")
src_fps = cap.get(cv2.CAP_PROP_FPS)
total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Collect ALL max contour areas post-warmup (not just above-threshold ones)
# so we can see the full noise distribution and pick a threshold above the tail
all_max_areas = []   # max_area per post-warmup frame (0 if no contours)
events_at_old = []   # events using old threshold, for comparison
in_event = False; ev_start = 0; ev_max = 0.0

src_idx = 0
while src_idx < total:
    ret, frame = cap.read()
    if not ret:
        break

    frame   = cv2.resize(frame, (W, H))
    fg_mask = mog2.apply(frame)

    if src_idx < WARMUP_FRAMES:
        src_idx += 1
        continue

    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

    zone_mask = fg_mask.copy()
    zone_mask[:ZONE_Y1, :]  = 0
    zone_mask[ZONE_Y2:, :]  = 0
    zone_mask[:, :ZONE_X1]  = 0
    zone_mask[:, ZONE_X2:]  = 0

    contours, _ = cv2.findContours(
        zone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    valid = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > NOISE_FLOOR]
    max_area = max(valid) if valid else 0.0
    all_max_areas.append(max_area)

    is_motion = max_area > OLD_THRESH
    if is_motion and not in_event:
        in_event = True; ev_start = src_idx; ev_max = max_area
    elif is_motion and in_event:
        ev_max = max(ev_max, max_area)
    elif not is_motion and in_event:
        events_at_old.append({"start": ev_start, "end": src_idx,
                              "dur": round((src_idx-ev_start)/src_fps, 2),
                              "max_area": round(ev_max, 1),
                              "ts": round(ev_start/src_fps, 1)})
        in_event = False

    src_idx += 1

cap.release()

if in_event:
    events_at_old.append({"start": ev_start, "end": src_idx,
                          "dur": round((src_idx-ev_start)/src_fps, 2),
                          "max_area": round(ev_max, 1),
                          "ts": round(ev_start/src_fps, 1)})

print(f"Post-warmup frames analysed: {len(all_max_areas)}")

# ── Distribution of ALL frame max areas (the noise floor) ────────────────
nonzero = [a for a in all_max_areas if a > 0]
above_noise = [a for a in all_max_areas if a > NOISE_FLOOR]

print(f"Frames with any contour > {NOISE_FLOOR}: {len(above_noise)}")
print()

# Percentiles of the noise distribution (all frames with any signal)
if above_noise:
    s = sorted(above_noise); n = len(s)
    def pct(p): return s[min(int(n*p/100), n-1)]
    print("Full noise distribution (all frames with signal > noise_floor):")
    for p in [50, 75, 90, 95, 99, 100]:
        print(f"  p{p:3d}: {pct(p):>8,.0f} sq px")
    print()

    # Threshold recommendation: p99 x 1.30
    p99_val     = pct(99)
    recommended = int(p99_val * 1.30)
    print(f"p99 of noise distribution : {p99_val:,.0f} sq px")
    print(f"Recommended threshold (x1.30): {recommended:,} sq px")
    print(f"Old threshold              : {OLD_THRESH:,} sq px")
    print()

    # Area histogram
    print("Area histogram (all frames with signal):")
    max_val = max(above_noise)
    bins_above = [
        (101,   500),
        (500,   1000),
        (1000,  2000),
        (2000,  5000),
        (5000,  10000),
        (10000, 20000),
        (20000, 999999),
    ]
    for lo, hi in bins_above:
        c = sum(1 for a in above_noise if lo <= a < hi)
        bar = "#" * min(int(c * 50 // len(above_noise)), 50)
        lbl = f"{lo//1000}k-{hi//1000}k" if hi < 999999 else f"{lo//1000}k+"
        print(f"  {lbl:>8}: {bar} ({c})")

# ── Events at old threshold ───────────────────────────────────────────────
print()
print(f"Events at old threshold={OLD_THRESH}: {len(events_at_old)}")
if events_at_old:
    dur_dist = {"<=0.1s":0, "0.1-0.5s":0, ">=0.5s":0}
    for ev in events_at_old:
        if ev["dur"] <= 0.1:   dur_dist["<=0.1s"] += 1
        elif ev["dur"] < 0.5:  dur_dist["0.1-0.5s"] += 1
        else:                  dur_dist[">=0.5s"] += 1
    for k, v in dur_dist.items():
        print(f"  {k}: {v}")
    long_evs = [ev for ev in events_at_old if ev["dur"] >= 0.5]
    if long_evs:
        print("  Long events (>=0.5s):")
        for ev in long_evs:
            print(f"    ts={ev['ts']}s  frames={ev['start']}-{ev['end']}"
                  f"  dur={ev['dur']}s  max_area={ev['max_area']:,}")

# ── Events at recommended threshold ──────────────────────────────────────
if above_noise:
    print()
    print(f"Events at recommended threshold={recommended}:")
    evs_new = []
    in_e = False; e_start = 0; e_max = 0.0; frame_areas = all_max_areas
    # Re-scan frame_areas with new threshold
    for fi, area in enumerate(frame_areas):
        is_m = area > recommended
        if is_m and not in_e:
            in_e = True; e_start = fi; e_max = area
        elif is_m and in_e:
            e_max = max(e_max, area)
        elif not is_m and in_e:
            e_ts = round((WARMUP_FRAMES + e_start) / src_fps, 1)
            evs_new.append({"start_fi": e_start, "dur_frames": fi - e_start,
                            "max_area": round(e_max, 1), "ts": e_ts})
            in_e = False
    if in_e:
        evs_new.append({"start_fi": e_start, "dur_frames": len(frame_areas)-e_start,
                        "max_area": round(e_max, 1),
                        "ts": round((WARMUP_FRAMES+e_start)/src_fps, 1)})
    print(f"  Total: {len(evs_new)}")
    for ev in evs_new:
        dur_s = round(ev["dur_frames"] / src_fps, 2)
        print(f"  ts={ev['ts']}s  dur={dur_s}s  max_area={ev['max_area']:,}")
    print()
    print(f"RECOMMENDED: set warehouse_motion_threshold = {recommended}")
