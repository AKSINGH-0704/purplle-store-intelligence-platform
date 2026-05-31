"""
Detection module — YOLOv8-nano person detection and centroid tracker.

Responsibilities (Phase 3):
- Load yolov8n.pt from models/ directory (bundled, no network download).
- Accept a video path and config dict, yield processed frames up to
  max_frames_per_camera with frame_skip applied.
- Run YOLOv8-nano at detection_resolution [640, 360] with
  confidence_threshold filtering; return only class 0 (person) bounding boxes.
- Maintain a centroid tracker: match new detections to existing tracks by
  minimum Euclidean distance within tracker_distance_threshold (default 80px).
  Assign stable integer track IDs across consecutive processed frames.
- Return per-frame detection results as structured dicts:
  {frame_idx, timestamp_seconds, track_id, bbox, centroid, confidence}.
- CAM_4 is excluded from this module; it uses background_motion.py instead.
"""
