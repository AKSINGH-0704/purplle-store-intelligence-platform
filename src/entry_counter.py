"""
Entry counter module — CAM 3 entry/exit line crossing detection.

Responsibilities (Phase 3):
- Load entry_line and entry_direction_vector from zones.json CAM_3 config.
- For each consecutive pair of processed frames, determine if a track's
  centroid crossed the entry_line between frames using line-segment intersection.
- Use entry_direction_vector to classify each crossing as entry or exit:
  dot product of crossing direction with entry_direction_vector determines sign.
- Return crossing events: {track_id, frame_idx, timestamp_seconds,
  crossing_type="entry"|"exit", centroid_before, centroid_after}.
- Pass crossing events to staff_filter.py before counting toward the funnel.
- Validate against at least 10 actual crossings in Phase 2 and record accuracy
  in decisions_log.txt.
"""
