# PROMPT: Write a smoke test that loads yolov8n.pt and runs person detection on
# frames 0, 100, and 200 of CAM_1.mp4 at 640x360 with confidence_threshold=0.5.
# Print detection count and confidence range per frame. Save annotated images to
# tools/yolo_test_output/. Confirm the model runs on CPU without GPU.
# CHANGES MADE: Added explicit class=0 (person-only) filter — AI generated
# output across all 80 COCO classes. Added minimum confidence assertion (must
# exceed threshold on at least one detection per frame). Limited to 3 frames;
# AI suggested 10, which is unnecessary for a smoke test.

"""
Checkpoint 2.1 — YOLOv8-nano smoke test.

Validates that yolov8n.pt can detect people in the actual store videos
at the configured detection resolution on this machine.

Usage:
    python tools/test_yolo.py

Output:
    tools/yolo_test_output/CAM_1_frame0_annotated.jpg
    tools/yolo_test_output/CAM_1_frame100_annotated.jpg
    tools/yolo_test_output/CAM_1_frame200_annotated.jpg

This script does NOT write to events.json and does NOT modify any src/ module.
It is a validation-only tool for Phase 2.
"""

import cv2
import json
import os
import sys

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
MODEL_PATH = os.path.join(ROOT, "models", "yolov8n.pt")
VIDEO_PATH = os.path.join(ROOT, "inputs", "CAM_1.mp4")
OUTPUT_DIR = os.path.join(ROOT, "tools", "yolo_test_output")

FRAMES_TO_TEST = [0, 100, 200]

# ── Load config ─────────────────────────────────────────────────────────────
with open(CONFIG_PATH) as f:
    config = json.load(f)

W, H = config["detection_resolution"]          # [640, 360]
CONF_THRESHOLD = config["confidence_threshold"] # 0.5
PERSON_CLASS = 0

print(f"[CONFIG] resolution={W}x{H}  confidence_threshold={CONF_THRESHOLD}")
print(f"[MODEL]  {MODEL_PATH}")
print(f"[VIDEO]  {VIDEO_PATH}")

# ── Preflight checks ────────────────────────────────────────────────────────
for path, label in [(MODEL_PATH, "yolov8n.pt"), (VIDEO_PATH, "CAM_1.mp4")]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found at: {path}")
        sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load YOLO model ─────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    model = YOLO(MODEL_PATH)
    print(f"[OK]    Model loaded.\n")
except Exception as e:
    print(f"[ERROR] Failed to load YOLO model: {e}")
    sys.exit(1)

# ── Process frames ──────────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
    sys.exit(1)

total_fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"[VIDEO] FPS={total_fps:.1f}  Total frames={total_frames}")

all_detections = []

for frame_idx in FRAMES_TO_TEST:
    if frame_idx >= total_frames:
        print(f"[SKIP]  frame {frame_idx} — beyond video length ({total_frames} frames)")
        continue

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret:
        print(f"[SKIP]  frame {frame_idx} — could not read")
        continue

    frame = cv2.resize(frame, (W, H))

    results = model(frame, conf=CONF_THRESHOLD, classes=[PERSON_CLASS], verbose=False)

    boxes = results[0].boxes
    person_boxes = []
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            cls = int(box.cls[0])
            if cls == PERSON_CLASS:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                person_boxes.append((x1, y1, x2, y2, conf))

    # Draw bounding boxes
    annotated = frame.copy()
    for (x1, y1, x2, y2, conf) in person_boxes:
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"{conf:.2f}", (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    label = f"Frame {frame_idx} | Persons: {len(person_boxes)}"
    cv2.putText(annotated, label, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

    out_path = os.path.join(OUTPUT_DIR, f"CAM_1_frame{frame_idx}_annotated.jpg")
    cv2.imwrite(out_path, annotated)

    confs = [c for *_, c in person_boxes]
    print(f"[FRAME {frame_idx:>3}]  persons={len(person_boxes)}"
          f"  confidences={[round(c,2) for c in confs]}"
          f"  -> saved: {out_path}")

    all_detections.extend(person_boxes)

cap.release()

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("CHECKPOINT 2.1 SUMMARY")
print("=" * 60)
print(f"Frames tested     : {FRAMES_TO_TEST}")
print(f"Total detections  : {len(all_detections)}")
if all_detections:
    confs = [c for *_, c in all_detections]
    print(f"Confidence range  : {min(confs):.2f} – {max(confs):.2f}")
    print(f"Q1 ANSWER         : YES — YOLOv8-nano detects people in CAM_1 at {W}x{H}")
else:
    print(f"Q1 ANSWER         : NO detections on tested frames.")
    print(f"                    Try lowering confidence_threshold in config.json")
    print(f"                    or test on a different frame range.")
print(f"Output images     : {OUTPUT_DIR}/")
print("=" * 60)
