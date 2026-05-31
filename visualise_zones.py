"""
Zone polygon visualisation tool.

Extracts frame 100 from each video in inputs/, overlays zones.json polygon
coordinates and entry line onto the frame, and saves output images to
zones_preview/. Prints a clear TODO warning for any camera whose coordinates
are not yet filled in zones.json.

No display window is opened (cv2.imshow is not used — safe for headless environments).

Usage:
    python visualise_zones.py

Output:
    zones_preview/CAM_1_frame100.jpg
    zones_preview/CAM_2_frame100.jpg
    zones_preview/CAM_3_frame100.jpg
    zones_preview/CAM_4_frame100.jpg
    zones_preview/CAM_5_frame100.jpg

Iterate:
    1. Run this script.
    2. Open the output images.
    3. Adjust polygon/entry_line coordinates in zones.json.
    4. Re-run to verify alignment.
    5. Repeat until all polygons visually match actual zone boundaries.
"""

import cv2
import json
import os
import numpy as np

INPUTS_DIR = "inputs"
OUTPUT_DIR = "zones_preview"
ZONES_FILE = "zones.json"
FRAME_TO_EXTRACT = 100
TARGET_SIZE = (640, 360)

COLOUR_POLYGON = (0, 255, 0)       # green
COLOUR_ENTRY_LINE = (0, 165, 255)  # orange
COLOUR_MISSING = (0, 0, 255)       # red
COLOUR_LABEL = (255, 255, 0)       # yellow

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(ZONES_FILE, "r") as f:
    zones = json.load(f)

todos = []

for cam_id, cam_cfg in zones.items():
    video_path = os.path.join(INPUTS_DIR, f"{cam_id}.mp4")

    if not os.path.exists(video_path):
        print(f"[SKIP]  {cam_id}: video not found at {video_path}")
        continue

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, FRAME_TO_EXTRACT)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print(f"[SKIP]  {cam_id}: could not read frame {FRAME_TO_EXTRACT}")
        continue

    frame = cv2.resize(frame, TARGET_SIZE)

    # Header label
    header = f"{cam_id} | {cam_cfg['zone']} | {cam_cfg['intelligence_layer']}"
    cv2.putText(frame, header, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOUR_LABEL, 2)

    y_offset = 45
    polygon = cam_cfg.get("polygon", [])
    entry_line = cam_cfg.get("entry_line", [])
    entry_vec = cam_cfg.get("entry_direction_vector", [])

    # Draw polygon
    if polygon and len(polygon) >= 3:
        pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], isClosed=True, color=COLOUR_POLYGON, thickness=2)
        cv2.putText(frame, "polygon: OK", (8, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOUR_POLYGON, 1)
    elif "polygon" in cam_cfg:
        cv2.putText(frame, "TODO: polygon coordinates", (8, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOUR_MISSING, 2)
        todos.append(f"  {cam_id}: polygon coordinates not filled in zones.json")
    y_offset += 20

    # Draw entry line (CAM_3 only in current config)
    if entry_line and len(entry_line) == 2:
        pt1 = tuple(int(v) for v in entry_line[0])
        pt2 = tuple(int(v) for v in entry_line[1])
        cv2.line(frame, pt1, pt2, COLOUR_ENTRY_LINE, 2)
        vec_text = f"dir_vec: {entry_vec}" if entry_vec else "dir_vec: TODO"
        cv2.putText(frame, f"entry_line: OK | {vec_text}", (8, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_ENTRY_LINE, 1)
    elif "entry_line" in cam_cfg:
        cv2.putText(frame, "TODO: entry_line + direction_vector", (8, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOUR_MISSING, 2)
        todos.append(f"  {cam_id}: entry_line and entry_direction_vector not filled in zones.json")

    out_path = os.path.join(OUTPUT_DIR, f"{cam_id}_frame{FRAME_TO_EXTRACT}.jpg")
    cv2.imwrite(out_path, frame)
    print(f"[OK]    {cam_id}: saved -> {out_path}")

print()
if todos:
    print("Coordinates still required in zones.json:")
    for t in todos:
        print(t)
    print(f"\n{len(todos)} TODO(s) remaining. Fill coordinates and re-run to verify.")
else:
    print("All zone coordinates are defined. Visual verification complete.")

print(f"\nOutput images saved to: {OUTPUT_DIR}/")
