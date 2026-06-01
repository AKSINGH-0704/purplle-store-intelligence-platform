"""
CAM_4 enhanced investigation — post-warmup-suppression.
Characterises flicker vs genuine motion using:
  - contour count per frame
  - contour compactness (4pi*area/perimeter^2)
  - spatial band distribution
  - temporal persistence (event duration)

Run from project root: python tools/investigate_cam4_v2.py
"""
import cv2
import math
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import load_config, load_zones

cfg   = load_config("config.json")
zones = load_zones("zones.json")

W, H      = cfg["detection_resolution"]
THRESHOLD = cfg["warehouse_motion_threshold"]
polygon   = zones["CAM_4"]["polygon"]
ZONE_X1   = min(p[0] for p in polygon)
ZONE_Y1   = min(p[1] for p in polygon)
ZONE_X2   = max(p[0] for p in polygon)
ZONE_Y2   = max(p[1] for p in polygon)

zone_h         = ZONE_Y2 - ZONE_Y1
BAND_UPPER_Y2  = ZONE_Y1 + zone_h // 3        # 138
BAND_CENTER_Y2 = ZONE_Y1 + 2 * (zone_h // 3)  # 246

NOISE_FLOOR   = 100
WARMUP_FRAMES = 200
OUT_DIR = os.path.join("tools", "warehouse_motion_output", "investigation_v2")
os.makedirs(OUT_DIR, exist_ok=True)

# ── MOG2 ────────────────────────────────────────────────────────────────────
mog2   = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16, detectShadows=False)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

cap     = cv2.VideoCapture("inputs/CAM_4.mp4")
src_fps = cap.get(cv2.CAP_PROP_FPS)
total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"Processing {total} frames @ {src_fps:.2f} fps  (warmup={WARMUP_FRAMES} frames)")

# ── Per-frame data ──────────────────────────────────────────────────────────
frame_data = []   # one entry per post-warmup frame that qualifies (area > THRESHOLD)
all_events = []   # consecutive qualifying runs

in_event       = False
ev_start       = 0
ev_max_area    = 0.0
ev_frames      = []   # frame_data entries within current event

src_idx = 0
while src_idx < total:
    ret, raw = cap.read()
    if not ret:
        break

    frame   = cv2.resize(raw, (W, H))
    fg_mask = mog2.apply(frame)           # always feed MOG2

    if src_idx < WARMUP_FRAMES:
        src_idx += 1
        continue

    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

    zone_mask = fg_mask.copy()
    zone_mask[:ZONE_Y1, :]  = 0
    zone_mask[ZONE_Y2:, :]  = 0
    zone_mask[:, :ZONE_X1]  = 0
    zone_mask[:, ZONE_X2:]  = 0

    contours_raw, _ = cv2.findContours(
        zone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    valid_cnts = [(cv2.contourArea(c), c) for c in contours_raw
                  if cv2.contourArea(c) > NOISE_FLOOR]

    max_area   = max((a for a, _ in valid_cnts), default=0.0)
    is_motion  = max_area > THRESHOLD
    ts         = round(src_idx / src_fps, 3)

    if is_motion:
        # Spatial bands (white pixel counts)
        px_upper  = int(np.sum(zone_mask[ZONE_Y1:BAND_UPPER_Y2,  ZONE_X1:ZONE_X2] > 0))
        px_center = int(np.sum(zone_mask[BAND_UPPER_Y2:BAND_CENTER_Y2, ZONE_X1:ZONE_X2] > 0))
        px_lower  = int(np.sum(zone_mask[BAND_CENTER_Y2:ZONE_Y2, ZONE_X1:ZONE_X2] > 0))
        total_px  = px_upper + px_center + px_lower

        # Contour count (number of distinct blobs above noise floor)
        cnt_count = len(valid_cnts)

        # Compactness of the LARGEST contour: 4pi*area / perimeter^2
        # Perfect circle = 1.0; elongated/irregular shapes < 1.0
        max_cnt = max(valid_cnts, key=lambda x: x[0])[1]
        perim    = cv2.arcLength(max_cnt, True)
        max_area_val = max_area
        compactness = (4 * math.pi * max_area_val / (perim ** 2)) if perim > 0 else 0.0

        # X-spread: width of bounding rect of largest contour relative to zone width
        rx, ry, rw, rh = cv2.boundingRect(max_cnt)
        x_spread = round(rw / (ZONE_X2 - ZONE_X1), 3)   # 0-1; flicker spans wide
        y_center = round((ry + rh / 2 - ZONE_Y1) / zone_h, 3)  # 0=top, 1=bottom of zone

        fd = {
            "frame_idx":   src_idx,
            "ts":          ts,
            "max_area":    round(max_area, 1),
            "cnt_count":   cnt_count,
            "compactness": round(compactness, 4),
            "x_spread":    x_spread,
            "y_center":    y_center,   # 0=top of zone, 1=bottom
            "px_upper":    px_upper,
            "px_center":   px_center,
            "px_lower":    px_lower,
            "pct_lower":   round(100 * px_lower / total_px, 1) if total_px else 0,
        }
        frame_data.append(fd)

        if not in_event:
            in_event    = True
            ev_start    = src_idx
            ev_max_area = max_area
            ev_frames   = [fd]
        else:
            ev_max_area = max(ev_max_area, max_area)
            ev_frames.append(fd)
    else:
        if in_event:
            dur = (src_idx - ev_start) / src_fps
            all_events.append({
                "start":     ev_start,
                "end":       src_idx,
                "dur":       round(dur, 3),
                "max_area":  round(ev_max_area, 1),
                "ts_start":  round(ev_start / src_fps, 2),
                "n_frames":  len(ev_frames),
                "frames":    ev_frames,
            })
            in_event = False
            ev_frames = []

    src_idx += 1

cap.release()

if in_event:
    dur = (src_idx - ev_start) / src_fps
    all_events.append({
        "start": ev_start, "end": src_idx,
        "dur": round(dur, 3), "max_area": round(ev_max_area, 1),
        "ts_start": round(ev_start / src_fps, 2),
        "n_frames": len(ev_frames), "frames": ev_frames,
    })

print(f"Done. {len(frame_data)} qualifying frames, {len(all_events)} events.\n")

# ── ANALYSIS A: Overview ──────────────────────────────────────────────────
print("=" * 65)
print(f"A. OVERVIEW  (post-warmup, threshold={THRESHOLD})")
print("=" * 65)
print(f"  Qualifying frames : {len(frame_data)}")
print(f"  Total events      : {len(all_events)}")
if frame_data:
    areas = [f["max_area"] for f in frame_data]
    s = sorted(areas); n = len(s)
    def pct(p): return s[min(int(n*p/100), n-1)]
    print(f"  Area p50/p90/p99/max: {pct(50):,.0f} / {pct(90):,.0f} / {pct(99):,.0f} / {max(s):,.0f}")

# ── ANALYSIS B: Contour count ─────────────────────────────────────────────
print()
print("=" * 65)
print("B. CONTOUR COUNT  (blobs per qualifying frame)")
print("   Flicker = many scattered blobs; motion = 1-2 concentrated blobs")
print("=" * 65)
if frame_data:
    cnt_vals = [f["cnt_count"] for f in frame_data]
    for v in sorted(set(cnt_vals)):
        c = cnt_vals.count(v)
        bar = "#" * min(int(c * 50 // len(cnt_vals)), 50)
        print(f"  {v:2d} blob(s): {bar} ({c})")
    print(f"  mean={sum(cnt_vals)/len(cnt_vals):.1f}  "
          f"median={sorted(cnt_vals)[len(cnt_vals)//2]}")

# ── ANALYSIS C: Compactness ───────────────────────────────────────────────
print()
print("=" * 65)
print("C. COMPACTNESS  (4pi*area/perim^2;  circle=1.0, floor blob<0.3)")
print("   Low compactness = sprawling irregular shape = floor reflection")
print("=" * 65)
if frame_data:
    comp_vals = [f["compactness"] for f in frame_data]
    bins = [(0.0,0.1),(0.1,0.2),(0.2,0.3),(0.3,0.5),(0.5,0.7),(0.7,1.01)]
    for lo, hi in bins:
        c = sum(1 for v in comp_vals if lo <= v < hi)
        bar = "#" * min(int(c * 50 // len(comp_vals)), 50)
        print(f"  {lo:.1f}-{hi:.1f}: {bar} ({c})")
    mean_c = sum(comp_vals)/len(comp_vals)
    print(f"  mean compactness={mean_c:.3f}")

# ── ANALYSIS D: Spatial distribution ─────────────────────────────────────
print()
print("=" * 65)
print("D. SPATIAL DISTRIBUTION  (% foreground pixels in lower floor band)")
print("   Flicker = dominated by lower band; motion = spread or upper/center")
print("=" * 65)
if frame_data:
    pct_lower_vals = [f["pct_lower"] for f in frame_data]
    y_center_vals  = [f["y_center"]  for f in frame_data]
    x_spread_vals  = [f["x_spread"]  for f in frame_data]

    lower_bins = [(0,20),(20,40),(40,60),(60,80),(80,101)]
    print("  % foreground in lower floor band:")
    for lo, hi in lower_bins:
        c = sum(1 for v in pct_lower_vals if lo <= v < hi)
        bar = "#" * min(int(c * 50 // len(pct_lower_vals)), 50)
        print(f"  {lo:3d}-{hi:3d}%: {bar} ({c})")

    mean_lower = sum(pct_lower_vals)/len(pct_lower_vals)
    mean_xsprd = sum(x_spread_vals)/len(x_spread_vals)
    mean_yctr  = sum(y_center_vals)/len(y_center_vals)
    print(f"  mean lower%={mean_lower:.1f}%  "
          f"mean x_spread={mean_xsprd:.2f}  "
          f"mean y_center={mean_yctr:.2f}  (1.0=floor)")

# ── ANALYSIS E: Temporal persistence ─────────────────────────────────────
print()
print("=" * 65)
print("E. TEMPORAL PERSISTENCE  (event duration distribution)")
print("   Flicker = very short (<= 0.1s = 1-2 frames); motion = sustained")
print("=" * 65)
if all_events:
    bins = [("<=0.04s", 0, 0.04),
            ("0.04-0.08s", 0.04, 0.08),
            ("0.08-0.12s", 0.08, 0.12),
            ("0.12-0.5s",  0.12, 0.5),
            ("0.5-1.0s",   0.5, 1.0),
            (">1.0s",      1.0, 999)]
    for label, lo, hi in bins:
        c = sum(1 for e in all_events if lo <= e["dur"] < hi)
        bar = "#" * min(int(c * 50 // len(all_events)), 50)
        print(f"  {label:12s}: {bar} ({c})")

    long_evs = [e for e in all_events if e["dur"] >= 0.5]
    print(f"\n  Events >= 0.5s ({len(long_evs)}):")
    for ev in long_evs:
        print(f"    ts={ev['ts_start']:6.1f}s  frames={ev['start']}-{ev['end']}"
              f"  dur={ev['dur']}s  max_area={ev['max_area']:>8,.0f}")

# ── ANALYSIS F: Feature comparison — short vs long events ────────────────
print()
print("=" * 65)
print("F. FEATURE COMPARISON: short events (<= 0.1s) vs long (>= 0.5s)")
print("=" * 65)

def mean(vals): return sum(vals)/len(vals) if vals else 0.0

short_frames = [f for ev in all_events if ev["dur"] <= 0.1 for f in ev["frames"]]
long_frames  = [f for ev in all_events if ev["dur"] >= 0.5 for f in ev["frames"]]

if short_frames and long_frames:
    metrics = [
        ("cnt_count",   "Contour count"),
        ("compactness", "Compactness"),
        ("pct_lower",   "% lower floor px"),
        ("x_spread",    "X-spread (0-1)"),
        ("y_center",    "Y-centre (1=floor)"),
        ("max_area",    "Max area (sq px)"),
    ]
    fmt_label = f"  {'Metric':<22} {'Short<=0.1s (n='+str(len(short_frames))+')':>28}   {'Long>=0.5s (n='+str(len(long_frames))+')':>26}"
    print(fmt_label)
    print("  " + "-" * 62)
    for key, label in metrics:
        sv = mean([f[key] for f in short_frames])
        lv = mean([f[key] for f in long_frames])
        print(f"  {label:<22}  short={sv:>10.2f}    long={lv:>10.2f}")
else:
    if not long_frames:
        print("  No long events found — cannot compare.")

# ── ANALYSIS G: Algorithmic separability assessment ──────────────────────
print()
print("=" * 65)
print("G. ALGORITHMIC SEPARABILITY")
print("=" * 65)

thresholds_to_test = {
    "Duration > 0.4s":      lambda ev: ev["dur"] > 0.4,
    "Max area > 50000":     lambda ev: ev["max_area"] > 50000,
    "Cnt_count <= 2":       lambda ev: all(f["cnt_count"] <= 2 for f in ev["frames"]),
    "Compactness > 0.3":    lambda ev: any(f["compactness"] > 0.3 for f in ev["frames"]),
    "Lower% < 70":          lambda ev: any(f["pct_lower"] < 70 for f in ev["frames"]),
    "Y_center < 0.7":       lambda ev: any(f["y_center"] < 0.7 for f in ev["frames"]),
    "Duration>0.4 OR Upper active": lambda ev: (
        ev["dur"] > 0.4 or any(f["px_upper"] > 500 for f in ev["frames"])
    ),
}

long_ev_set = set(id(e) for e in all_events if e["dur"] >= 0.5)

print(f"  Total events: {len(all_events)}  (genuine candidates: {len(long_ev_set)})")
print(f"  {'Rule':<38}  {'Triggered':>9}  {'TP':>4}  {'FP':>6}  {'Precision':>9}")
print("  " + "-" * 72)
for rule_name, rule_fn in thresholds_to_test.items():
    triggered = [e for e in all_events if rule_fn(e)]
    tp = sum(1 for e in triggered if id(e) in long_ev_set)
    fp = len(triggered) - tp
    prec = tp / len(triggered) if triggered else 0
    print(f"  {rule_name:<38}  {len(triggered):>9}  {tp:>4}  {fp:>6}  {prec:>9.2f}")

# ── ANALYSIS H: Save inspection frames for long events ───────────────────
print()
print("=" * 65)
print("H. Saving inspection frames for long events ...")
print("=" * 65)

long_events = [e for e in all_events if e["dur"] >= 0.5]
inspect_frames = set()
for ev in long_events:
    inspect_frames.add(ev["start"])
    inspect_frames.add((ev["start"] + ev["end"]) // 2)
    inspect_frames.add(max(ev["end"] - 1, ev["start"]))
# Add a sample static frame for comparison
inspect_frames.add(1500)

mog2b  = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16, detectShadows=False)
cap2   = cv2.VideoCapture("inputs/CAM_4.mp4")
saved  = set()
src_idx = 0

while src_idx < total and len(saved) < len(inspect_frames):
    ret, raw = cap2.read()
    if not ret:
        break

    frame  = cv2.resize(raw, (W, H))
    fg     = mog2b.apply(frame)

    if src_idx < WARMUP_FRAMES:
        src_idx += 1
        continue

    fg     = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)
    zm     = fg.copy()
    zm[:ZONE_Y1, :] = 0; zm[ZONE_Y2:, :] = 0
    zm[:, :ZONE_X1] = 0; zm[:, ZONE_X2:] = 0

    if src_idx in inspect_frames and src_idx not in saved:
        cnts2, _ = cv2.findContours(zm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid2   = [(cv2.contourArea(c), c) for c in cnts2 if cv2.contourArea(c) > NOISE_FLOOR]
        max_a2   = max((a for a, _ in valid2), default=0)
        above    = max_a2 > THRESHOLD

        vis = frame.copy()
        cv2.rectangle(vis, (ZONE_X1, ZONE_Y1), (ZONE_X2, ZONE_Y2), (0, 200, 60), 1)
        cv2.line(vis, (ZONE_X1, BAND_UPPER_Y2),  (ZONE_X2, BAND_UPPER_Y2),  (255,255,0), 1)
        cv2.line(vis, (ZONE_X1, BAND_CENTER_Y2), (ZONE_X2, BAND_CENTER_Y2), (255,255,0), 1)
        for area, cnt in valid2:
            col = (0, 0, 220) if area > THRESHOLD else (0, 200, 220)
            cv2.drawContours(vis, [cnt], -1, col, 2)
            if area > 1500:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = int(M["m10"]/M["m00"]); cy = int(M["m01"]/M["m00"])
                    cv2.putText(vis, f"{int(area)}", (cx-20, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255,255,255), 1)
        banner = f"f={src_idx} t={src_idx/src_fps:.2f}s  area={int(max_a2)}  n_cnts={len(valid2)}  {'MOTION' if above else 'static'}"
        cv2.rectangle(vis, (0,0), (W, 22), (0,0,100) if above else (20,60,20), -1)
        cv2.putText(vis, banner, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220,220,0), 1)

        mask_bgr = cv2.cvtColor(zm, cv2.COLOR_GRAY2BGR)
        cv2.imwrite(os.path.join(OUT_DIR, f"v2_frame_{src_idx:04d}.jpg"),
                    np.hstack([vis, mask_bgr]))
        saved.add(src_idx)
        print(f"  frame {src_idx:4d}  t={src_idx/src_fps:.2f}s  area={int(max_a2):>8,}  "
              f"n_cnts={len(valid2):2d}  {'MOTION' if above else 'static'}")

    src_idx += 1

cap2.release()
print("\nDone.")
