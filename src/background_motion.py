"""
Background motion module — CAM 4 warehouse activity detection.

Responsibilities (Phase 3):
- Accept CAM_4 video path and config dict.
- Apply OpenCV MOG2 background subtractor frame-by-frame with frame_skip.
- Filter detected motion contours by minimum area (warehouse_motion_threshold,
  default 500 sq pixels at 640x360); discard smaller blobs as lighting noise.
- Emit a motion event dict for each frame where qualifying motion is detected:
  {frame_idx, timestamp_seconds, contour_area, event_type="warehouse_motion"}.
- Aggregate consecutive motion frames into restocking events when motion
  persists for >= N frames (N to be calibrated in Phase 2 from actual CAM_4
  footage; add to config.json if threshold needs to be a tunable parameter).
- Return list of motion events and list of restocking events separately.
"""
