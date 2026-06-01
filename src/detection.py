"""
Detection module — YOLOv8-nano person detection and centroid tracker.
"""
import os
from typing import Iterator

import cv2

from src.zone_classifier import classify_zone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_ROOT, "models", "yolov8n.pt")
_PERSON_CLASS = 0
# Processed frames a track can be undetected before removal.
# At frame_skip=5 this equals ~1.7s — calibrated in Phase 2 (Decision 14).
_MAX_DISAPPEARED = 10


def _dist(a: list, b: list) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def run_detection(
    video_path: str,
    camera_id: str,
    config: dict,
    zones_cfg: dict,
) -> Iterator[dict]:
    """Generator: yields one dict per processed frame for YOLO cameras (CAM_1/2/3/5).

    CAM_4 is excluded — use run_background_motion() instead.

    Each yielded dict:
        {
            "frame_idx":     int,    # source frame index
            "proc_idx":      int,    # processed frame counter (0, 1, 2, ...)
            "timestamp_sec": float,  # frame_idx / src_fps
            "tracks": [
                {
                    "track_id":   int,
                    "bbox":       [x1, y1, x2, y2],
                    "centroid":   [cx, cy],
                    "confidence": float,     # YOLO score, current frame
                    "zone":       str|None   # classify_zone() result
                }
            ]
        }

    tracks contains only persons with a YOLO detection this processed frame.
    Disappeared tracks (not matched but not yet removed) are not yielded.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics is not installed. Run: pip install ultralytics"
        )

    W, H = config["detection_resolution"]
    frame_skip    = config["frame_skip"]
    conf_thresh   = config["confidence_threshold"]
    tracker_dist  = config["tracker_distance_threshold"]
    max_src       = config["max_frames_per_camera"]

    model = YOLO(_MODEL_PATH)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    src_fps   = cap.get(cv2.CAP_PROP_FPS)
    total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    tracks  = {}   # track_id -> state dict
    next_id = 0
    proc_idx = 0
    src_idx  = 0

    try:
        while src_idx < min(max_src, total_src):
            cap.set(cv2.CAP_PROP_POS_FRAMES, src_idx)
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.resize(frame, (W, H))

            # YOLO inference — persons only
            res  = model(frame, conf=conf_thresh, classes=[_PERSON_CLASS], verbose=False)
            dets = []
            if res[0].boxes is not None:
                for box in res[0].boxes:
                    if int(box.cls[0]) == _PERSON_CLASS:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        dets.append({
                            "bbox":       [x1, y1, x2, y2],
                            "centroid":   [(x1 + x2) // 2, (y1 + y2) // 2],
                            "confidence": float(box.conf[0]),
                        })

            # Greedy distance-based matching (closest pair first)
            used_dets   = set()
            used_tracks = set()
            pairs = []
            for tid, td in tracks.items():
                for di, det in enumerate(dets):
                    d = _dist(td["centroid"], det["centroid"])
                    if d <= tracker_dist:
                        pairs.append((d, tid, di))
            pairs.sort(key=lambda x: x[0])

            for _, tid, di in pairs:
                if tid in used_tracks or di in used_dets:
                    continue
                det = dets[di]
                tracks[tid].update({
                    "centroid":    det["centroid"],
                    "bbox":        det["bbox"],
                    "confidence":  det["confidence"],
                    "frames_alive": tracks[tid]["frames_alive"] + 1,
                    "disappeared": 0,
                    "zone":        classify_zone(camera_id, det["centroid"], zones_cfg),
                })
                used_tracks.add(tid)
                used_dets.add(di)

            # Age unmatched tracks; remove stale ones
            for tid in list(tracks):
                if tid not in used_tracks:
                    tracks[tid]["disappeared"] += 1
                    if tracks[tid]["disappeared"] >= _MAX_DISAPPEARED:
                        del tracks[tid]

            # Create new tracks for unmatched detections
            for di, det in enumerate(dets):
                if di not in used_dets:
                    tracks[next_id] = {
                        "centroid":    det["centroid"],
                        "bbox":        det["bbox"],
                        "confidence":  det["confidence"],
                        "frames_alive": 1,
                        "disappeared": 0,
                        "zone":        classify_zone(camera_id, det["centroid"], zones_cfg),
                    }
                    next_id += 1

            # Yield only tracks with an active detection this frame
            ts = round(src_idx / src_fps, 3) if src_fps > 0 else 0.0
            yield {
                "frame_idx":     src_idx,
                "proc_idx":      proc_idx,
                "timestamp_sec": ts,
                "tracks": [
                    {
                        "track_id":   tid,
                        "bbox":       td["bbox"],
                        "centroid":   td["centroid"],
                        "confidence": round(td["confidence"], 4),
                        "zone":       td["zone"],
                    }
                    for tid, td in tracks.items()
                    if td["disappeared"] == 0
                ],
            }

            proc_idx += 1
            src_idx  += frame_skip

    finally:
        cap.release()
