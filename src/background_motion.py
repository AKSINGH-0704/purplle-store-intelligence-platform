"""
Background motion module — CAM_4 warehouse activity detection.
"""
import os
from typing import List, Tuple

import cv2

_NOISE_FLOOR     = 100   # sq px; contours below this are compression/sensor noise
_MOG2_HISTORY    = 200
_MOG2_VAR_THRESH = 16
# Warm-up suppression: MOG2 needs _MOG2_HISTORY frames to build a stable
# background model. Events are not emitted during this period; frames are
# still fed to MOG2 so the model learns the scene. Frame 0 cold-start
# produces area ≈ full zone (entire scene is "foreground" with no model)
# and is confirmed invalid. Value matches _MOG2_HISTORY.
_WARMUP_FRAMES   = 200


def run_background_motion(
    video_path: str,
    config: dict,
    zones_cfg: dict,
) -> Tuple[List[dict], List[dict]]:
    """Process CAM_4 video; return (motion_frames, restocking_events).

    Frames are read SEQUENTIALLY — MOG2's temporal background model requires
    consecutive frames to distinguish lighting flicker from genuine motion.
    frame_skip is NOT applied here.

    motion_frames: one dict per qualifying frame (contour_area > warehouse_motion_threshold)
        {
            "frame_idx":    int,
            "timestamp_sec": float,
            "contour_area": float   # max contour area in zone this frame
        }

    restocking_events: one dict per consecutive run of qualifying motion frames
        {
            "start_frame":      int,
            "end_frame":        int,
            "duration_sec":     float,
            "max_contour_area": float
        }
    """
    W, H      = config["detection_resolution"]
    threshold = config["warehouse_motion_threshold"]
    max_src   = config["max_frames_per_camera"]

    # Zone bounding box from CAM_4 polygon
    polygon = zones_cfg.get("CAM_4", {}).get("polygon", [])
    if polygon:
        zone_x1 = min(p[0] for p in polygon)
        zone_y1 = min(p[1] for p in polygon)
        zone_x2 = max(p[0] for p in polygon)
        zone_y2 = max(p[1] for p in polygon)
    else:
        zone_x1, zone_y1, zone_x2, zone_y2 = 0, 0, W, H

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    src_fps   = cap.get(cv2.CAP_PROP_FPS)
    total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    mog2 = cv2.createBackgroundSubtractorMOG2(
        history=_MOG2_HISTORY,
        varThreshold=_MOG2_VAR_THRESH,
        detectShadows=False,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    motion_frames:     List[dict] = []
    restocking_events: List[dict] = []

    in_event          = False
    event_start_frame = 0
    event_max_area    = 0.0

    src_idx = 0
    try:
        while src_idx < min(max_src, total_src):
            ret, frame = cap.read()   # sequential — do not seek
            if not ret:
                break

            frame   = cv2.resize(frame, (W, H))
            fg_mask = mog2.apply(frame)   # always feed MOG2 to build background model

            # Suppress event emission during warm-up — background model not yet stable
            if src_idx < _WARMUP_FRAMES:
                src_idx += 1
                continue

            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

            # Mask to zone polygon bounding box
            zone_mask = fg_mask.copy()
            zone_mask[:zone_y1, :]  = 0
            zone_mask[zone_y2:, :]  = 0
            zone_mask[:, :zone_x1]  = 0
            zone_mask[:, zone_x2:]  = 0

            contours, _ = cv2.findContours(
                zone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            valid_areas = [
                cv2.contourArea(c) for c in contours
                if cv2.contourArea(c) > _NOISE_FLOOR
            ]
            max_area = max(valid_areas) if valid_areas else 0.0
            is_motion = max_area > threshold

            ts = round(src_idx / src_fps, 3) if src_fps > 0 else 0.0

            if is_motion:
                motion_frames.append({
                    "frame_idx":     src_idx,
                    "timestamp_sec": ts,
                    "contour_area":  round(max_area, 1),
                })
                if not in_event:
                    in_event          = True
                    event_start_frame = src_idx
                    event_max_area    = max_area
                else:
                    event_max_area = max(event_max_area, max_area)
            else:
                if in_event:
                    duration = (src_idx - event_start_frame) / src_fps if src_fps > 0 else 0.0
                    restocking_events.append({
                        "start_frame":      event_start_frame,
                        "end_frame":        src_idx,
                        "duration_sec":     round(duration, 2),
                        "max_contour_area": round(event_max_area, 1),
                    })
                    in_event       = False
                    event_max_area = 0.0

            src_idx += 1

    finally:
        cap.release()

    # Flush an event still open at end of window
    if in_event and src_fps > 0:
        duration = (src_idx - event_start_frame) / src_fps
        restocking_events.append({
            "start_frame":      event_start_frame,
            "end_frame":        src_idx,
            "duration_sec":     round(duration, 2),
            "max_contour_area": round(event_max_area, 1),
        })

    return motion_frames, restocking_events
