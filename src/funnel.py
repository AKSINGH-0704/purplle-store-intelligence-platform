"""
Funnel module — aggregate customer funnel and monotonicity validation.

Responsibilities (Phase 3):
- Assemble the five-stage aggregate funnel from upstream module outputs:
    Stage 1: Entry count from entry_counter.py (CAM_3, staff-filtered)
    Stage 2: Main floor visits from session_manager.py (CAM_2)
    Stage 3: Skincare zone visits from session_manager.py (CAM_1)
    Stage 4: Billing interactions from session_manager.py (CAM_5)
    Stage 5: Transaction count from csv_analytics.py (POS CSV, different date)
- Run monotonicity validation checks after funnel is assembled:
    Check A: Checkout count (CAM_5) should not significantly exceed entry
             count (CAM_3). If it does, log a WARNING in System Health.
    Check B: Main floor visits (CAM_2) should be >= skincare visits (CAM_1).
             If not, log a WARNING.
- Return funnel dict with counts, validation result ("pass" or "warning"),
  and disclaimer text about aggregate-only nature and date mismatch.
- No claim is made that the same person appears at multiple funnel stages.
"""
