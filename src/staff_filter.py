"""
Staff filter module — heuristic-based staff detection and exclusion.

Responsibilities (Phase 3):
- Apply three CAM_3-local heuristic rules to classify tracks as staff:
  Rule 1: A track crossing the entry line in both directions > 3 times
          within 30 minutes is classified as staff (multiple in/out trips).
  Rule 2: A person detected at the billing desk area (CAM_5) without entering
          from the main floor direction is classified as staff stationed at
          checkout. (Requires CAM_5 data; no cross-camera identity assumed.)
  Rule 3: A person detected already inside the store in the first frame of
          the recording is classified as staff on duty at opening.
- staff_filter_enabled flag from config.json controls whether filtering is
  applied; when False, all crossings count toward customer metrics unchanged.
- Return two lists: customer_crossings and staff_crossings.
- Log every staff classification decision for transparency (visible in System
  Health tab as "Staff Movements Detected" count).
"""
