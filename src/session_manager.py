"""
Session manager module — dwell time calculation and session merge.

Responsibilities (Phase 3):
- Aggregate per-track detections within each zone into visit sessions:
  {track_id, zone, start_frame, end_frame, start_time, end_time, dwell_seconds}.
- Apply dwell merge rule: if a new track appears in the same zone within
  dwell_merge_window_seconds (default 30s) of a previous track ending, AND
  the zone has no other active tracks at that moment, merge the two sessions.
  This corrects artificially short dwell times caused by track ID reassignment
  after occlusion.
- Filter out visits shorter than min_dwell_for_visit_seconds (default 10s)
  before passing to funnel.py and anomalies.py.
- Expose aggregated zone metrics: visit count, average dwell, peak hour per zone.
"""
