"""
Zone classifier module — polygon membership and zone assignment.

Responsibilities (Phase 3):
- Load zones.json at startup; parse polygon coordinates per camera.
- Provide a point-in-polygon check: given a centroid (x, y) and a camera ID,
  return the zone name if the centroid falls inside the configured polygon,
  or None if outside all defined zones.
- Support multi-zone cameras if needed (currently each camera maps to one zone).
- Raise a clear error if zones.json is missing required coordinate fields,
  guiding the user to complete TODO markers before running the pipeline.
- Used by session_manager.py and entry_counter.py to classify detections.
"""
