#!/usr/bin/env python3
"""
process_videos.py -- Purplle Store Intelligence Platform pipeline orchestrator.

Reads all 5 camera feeds from inputs/ and the POS CSV, runs the full detection
and analytics pipeline, writes events.json + video_hashes.json +
pipeline_summary.json, and prints a human-readable summary.

Usage:
    python process_videos.py           # Full run (config max_frames, frame_skip)
    python process_videos.py --quick   # Fast verification (max 300 frames, skip=10)

CAM_4 always processes the full video regardless of max_frames_per_camera:
genuine warehouse events at t=92.3s are beyond the config 1000-frame window.
See decisions_log.txt Decision 21.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List

# All src imports at module level so the validator can detect import errors early.
from src.utils import (
    append_event,
    get_logger,
    load_config,
    load_zones,
    make_warehouse_motion_event,
    write_hashes,
)
from src.session_manager   import run_zone_visits
from src.entry_counter     import run_entry_crossings
from src.background_motion import run_background_motion
from src.staff_filter      import run_staff_filter
from src.csv_analytics     import run_csv_analytics
from src.funnel            import run_funnel
from src.anomalies         import run_anomalies

_log = get_logger(__name__)

# ── Path constants ─────────────────────────────────────────────────────────────
_ROOT         = os.path.dirname(os.path.abspath(__file__))
_INPUTS_DIR   = os.path.join(_ROOT, "inputs")
_EVENTS_PATH  = os.path.join(_ROOT, "events", "events.json")
_HASHES_PATH  = os.path.join(_ROOT, "events", "video_hashes.json")
_SUMMARY_PATH = os.path.join(_ROOT, "events", "pipeline_summary.json")
_CSV_PATH     = os.path.join(_ROOT, "data", "Brigade_Bangalore_10_April_26.csv")
_CONFIG_PATH  = os.path.join(_ROOT, "config.json")
_ZONES_PATH   = os.path.join(_ROOT, "zones.json")

# CAM_4 override: process the full recording regardless of max_frames_per_camera.
# Genuine warehouse events at t=92.3s (frame 2306) are beyond the 1000-frame window.
# MOG2 processes 3,647 frames in ~15s -- acceptable even in --quick mode.
# The config value is preserved for all YOLO cameras. Decision 21.
_CAM4_MAX_FRAMES = 999_999

_YOLO_CAMERAS = ["CAM_1", "CAM_2", "CAM_5"]

# Required top-level keys in the summary dict. Used by validator.
SUMMARY_REQUIRED_KEYS = frozenset({
    "processing_metadata",
    "event_counts",
    "funnel",
    "anomalies",
    "csv_analytics",
    "staff_filter_summary",
    "video_hashes",
    "validation_warnings",
})


# ── Importable helper functions (testable without video files) ─────────────────

def _video_path(camera_id: str) -> str:
    return os.path.join(_INPUTS_DIR, f"{camera_id}.mp4")


def _load_events(path: str) -> list:
    """Load an NDJSON events file into a flat list of dicts."""
    if not os.path.exists(path):
        return []
    events: list = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _build_event_counts(events: list) -> dict:
    """Count events by event_type. Returns a JSON-serializable dict."""
    by_type: Dict[str, int] = {}
    for e in events:
        et = e.get("event_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1
    return {"total": len(events), "by_type": by_type}


def _build_summary(
    events: list,
    funnel: dict,
    anomalies: list,
    csv_result: dict,
    staff_result: dict,
    hashes: dict,
    camera_elapsed: dict,
    validation_warnings: list,
    quick_mode: bool,
    elapsed: float,
    max_frames: int,
    frame_skip: int,
) -> dict:
    """
    Assemble the full pipeline_summary dict from upstream module outputs.
    All values are JSON-serializable: frozensets are extracted to integer counts.

    Returns a dict with keys matching SUMMARY_REQUIRED_KEYS.
    """
    staff_ids = staff_result.get("staff_track_ids", {})
    return {
        "processing_metadata": {
            "run_at":            datetime.now(tz=timezone.utc).isoformat(),
            "quick_mode":        quick_mode,
            "total_elapsed_sec": round(elapsed, 1),
            "config_snapshot": {
                "max_frames_per_camera": max_frames,
                "frame_skip":            frame_skip,
                "cam4_override":         "full_video",
            },
            "camera_elapsed_sec": camera_elapsed,
        },
        "event_counts":  _build_event_counts(events),
        "funnel":        funnel,
        "anomalies":     anomalies,
        "csv_analytics": {k: v for k, v in csv_result.items() if k != "source"},
        "staff_filter_summary": {
            "staff_filtered_count":   staff_result.get("staff_filtered_count", 0),
            "staff_filter_enabled":   staff_result.get("staff_filter_enabled", True),
            "cam3_staff_track_count": len(staff_ids.get("CAM_3", frozenset())),
            "cam5_staff_track_count": len(staff_ids.get("CAM_5", frozenset())),
        },
        "video_hashes":        hashes,
        "validation_warnings": validation_warnings,
    }


def _print_summary(summary: dict) -> None:
    """Print a human-readable judge-facing summary to stdout. ASCII only."""
    meta   = summary.get("processing_metadata", {})
    counts = summary.get("event_counts", {})
    funnel = summary.get("funnel", {})
    zv     = funnel.get("zone_visits", {})
    adwell = funnel.get("avg_dwell_seconds", {})
    csv    = summary.get("csv_analytics", {})
    staff  = summary.get("staff_filter_summary", {})
    hashes = summary.get("video_hashes", {})
    warns  = summary.get("validation_warnings", [])
    anom   = summary.get("anomalies", [])
    snap   = meta.get("config_snapshot", {})

    mode_label = "QUICK" if meta.get("quick_mode") else "FULL"
    mode_str   = (
        f"{mode_label}  (max_frames={snap.get('max_frames_per_camera')}, "
        f"frame_skip={snap.get('frame_skip')}, cam4=full)"
    )
    fv_state = funnel.get("funnel_validation", "unknown").upper()

    top_cats = csv.get("top_categories") or [{}]
    top_sps  = csv.get("salesperson_performance") or [{}]
    top_cat  = top_cats[0].get("name", "N/A") if top_cats else "N/A"
    top_sp   = top_sps[0].get("name", "N/A") if top_sps else "N/A"

    print()
    print("=" * 62)
    print("PURPLLE STORE INTELLIGENCE PLATFORM -- PIPELINE SUMMARY")
    print("=" * 62)
    print(f"  Mode:       {mode_str}")
    print(f"  Completed:  {meta.get('run_at', 'N/A')}")
    print(f"  Elapsed:    {meta.get('total_elapsed_sec', 0)}s")
    print()

    print(f"  EVENTS GENERATED: {counts.get('total', 0)}")
    for et, n in sorted(counts.get("by_type", {}).items()):
        print(f"    {et:<28}: {n}")
    print()

    print(f"  CUSTOMER FUNNEL  [{fv_state}]")
    print(f"    Entries (CAM_3)    :  {funnel.get('entry_count', 0)}")
    mf = zv.get("main_floor", 0)
    sk = zv.get("skincare", 0)
    bi = zv.get("billing", 0)
    print(f"    Main floor  (CAM_2):  {mf}  avg {adwell.get('main_floor', 0)}s")
    print(f"    Skincare    (CAM_1):  {sk}  avg {adwell.get('skincare', 0)}s")
    print(f"    Billing     (CAM_5):  {bi}  avg {adwell.get('billing', 0)}s")
    print(f"    Transactions       :  {funnel.get('transaction_count', 0)}  "
          f"(POS CSV 10-04-2026)")
    for note in funnel.get("validation_notes", []):
        wrapped = note[:110] + ("..." if len(note) > 110 else "")
        print(f"    NOTE: {wrapped}")
    print()

    print(f"  ANOMALIES: {len(anom)} triggered")
    for a in anom:
        sev = a.get("severity", "?").upper()
        msg = a.get("message", "")[:55]
        print(f"    [{sev}] {a.get('type','?')}: {msg}")
    print()

    print(f"  STAFF FILTERED: {staff.get('staff_filtered_count', 0)} events  "
          f"(CAM_3: {staff.get('cam3_staff_track_count', 0)} tracks, "
          f"CAM_5: {staff.get('cam5_staff_track_count', 0)} tracks)")
    print()

    gmv = csv.get("gmv", 0)
    nmv = csv.get("nmv", 0)
    print("  REVENUE (POS CSV 10-04-2026)")
    try:
        print(f"    GMV: {gmv:,.0f} INR   NMV: {nmv:,.0f} INR")
    except (TypeError, ValueError):
        print(f"    GMV: {gmv}   NMV: {nmv}")
    print(f"    Top category     : {top_cat}")
    print(f"    Top salesperson  : {top_sp}")
    print()

    print("  VIDEO HASHES")
    for cam in ["CAM_1", "CAM_2", "CAM_3", "CAM_4", "CAM_5"]:
        h = hashes.get(cam, {"error": "not_found"})
        if isinstance(h, dict):
            print(f"    {cam}: [not found]")
        else:
            print(f"    {cam}: {h[:16]}...")
    print()

    print("  OUTPUT FILES")
    print(f"    events/events.json           {counts.get('total', 0)} events")
    print(f"    events/video_hashes.json     5 cameras")
    print(f"    events/pipeline_summary.json")
    print()

    if warns:
        print(f"  VALIDATION WARNINGS: {len(warns)}")
        for w in warns:
            print(f"    [WARN] {w}")
    else:
        print("  VALIDATION WARNINGS: 0")
    print("=" * 62)
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purplle Store Intelligence Platform -- pipeline orchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Output files (in events/):\n"
            "  events.json           NDJSON event stream from all cameras\n"
            "  video_hashes.json     SHA256 fingerprint per video file\n"
            "  pipeline_summary.json Structured summary of all metrics\n\n"
            "Events file is cleared at the start of each run (idempotent).\n"
            "CAM_4 always processes the full recording (see Decision 21)."
        ),
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Fast verification run: max 300 frames per YOLO camera, frame_skip=10. "
            "Completes in under 5 minutes. CAM_4 still processes the full video."
        ),
    )
    args = parser.parse_args()

    pipeline_start  = time.time()
    validation_warns: List[str] = []
    camera_elapsed:   Dict[str, float] = {}

    # ── Step 0: Fail-fast for configuration and data errors ───────────────────
    try:
        config = load_config(_CONFIG_PATH)
    except FileNotFoundError:
        sys.exit(f"FATAL: config.json not found at {_CONFIG_PATH}")
    except KeyError as exc:
        sys.exit(f"FATAL: config.json is invalid -- {exc}")

    try:
        zones_cfg = load_zones(_ZONES_PATH)
    except FileNotFoundError:
        sys.exit(f"FATAL: zones.json not found at {_ZONES_PATH}")

    if not os.path.exists(_CSV_PATH):
        sys.exit(f"FATAL: CSV not found at {_CSV_PATH}")

    # ── Apply --quick overrides ───────────────────────────────────────────────
    if args.quick:
        config = {**config, "max_frames_per_camera": 300, "frame_skip": 10}
        _log.info("Quick mode active: max_frames=300 frame_skip=10")

    runtime_max_frames = config["max_frames_per_camera"]
    runtime_frame_skip = config["frame_skip"]

    # ── Step 1: Reset event stream ────────────────────────────────────────────
    # Clear events.json so each run is idempotent. Prevents double-counting
    # if the orchestrator is run multiple times against the same inputs.
    os.makedirs(os.path.dirname(_EVENTS_PATH), exist_ok=True)
    if os.path.exists(_EVENTS_PATH):
        os.remove(_EVENTS_PATH)
        _log.info("Cleared existing events.json for fresh run")

    # ── Step 2: YOLO cameras (CAM_1, CAM_2, CAM_5) ───────────────────────────
    for cam_id in _YOLO_CAMERAS:
        vpath = _video_path(cam_id)
        if not os.path.exists(vpath):
            msg = f"{cam_id}: video not found at {vpath} -- skipped"
            _log.warning(msg)
            validation_warns.append(msg)
            continue
        try:
            t0 = time.time()
            run_zone_visits(vpath, cam_id, config, zones_cfg, _EVENTS_PATH)
            camera_elapsed[cam_id] = round(time.time() - t0, 1)
            _log.info("%s: complete in %.1fs", cam_id, camera_elapsed[cam_id])
        except Exception as exc:
            msg = f"{cam_id}: processing failed -- {exc}"
            _log.error(msg)
            validation_warns.append(msg)

    # ── Step 3: CAM_3 entry counter ───────────────────────────────────────────
    cam3_path = _video_path("CAM_3")
    if not os.path.exists(cam3_path):
        msg = "CAM_3: video not found -- entry count will be 0"
        _log.warning(msg)
        validation_warns.append(msg)
    else:
        try:
            t0 = time.time()
            run_entry_crossings(cam3_path, "CAM_3", config, zones_cfg, _EVENTS_PATH)
            camera_elapsed["CAM_3"] = round(time.time() - t0, 1)
            _log.info("CAM_3: complete in %.1fs", camera_elapsed["CAM_3"])
        except Exception as exc:
            msg = f"CAM_3: processing failed -- {exc}"
            _log.error(msg)
            validation_warns.append(msg)

    # ── Step 4: CAM_4 background motion (full video override) ─────────────────
    # Override max_frames_per_camera so genuine events at t=92.3s are captured.
    # run_background_motion() has no events_path param -- caller writes events.
    cam4_path = _video_path("CAM_4")
    if not os.path.exists(cam4_path):
        msg = "CAM_4: video not found -- warehouse motion events absent"
        _log.warning(msg)
        validation_warns.append(msg)
    else:
        try:
            cam4_config = {**config, "max_frames_per_camera": _CAM4_MAX_FRAMES}
            t0 = time.time()
            motion_frames, restocking_events = run_background_motion(
                cam4_path, cam4_config, zones_cfg
            )
            camera_elapsed["CAM_4"] = round(time.time() - t0, 1)
            for mf in motion_frames:
                is_restock = any(
                    re["start_frame"] <= mf["frame_idx"] <= re["end_frame"]
                    for re in restocking_events
                )
                append_event(
                    make_warehouse_motion_event(
                        camera="CAM_4",
                        frame_idx=mf["frame_idx"],
                        timestamp_seconds=mf["timestamp_sec"],
                        contour_area=mf["contour_area"],
                        is_restocking_event=is_restock,
                    ),
                    _EVENTS_PATH,
                )
            _log.info(
                "CAM_4: complete in %.1fs -- motion=%d restocking=%d events_written=%d",
                camera_elapsed["CAM_4"],
                len(motion_frames),
                len(restocking_events),
                len(motion_frames),
            )
        except Exception as exc:
            msg = f"CAM_4: processing failed -- {exc}"
            _log.error(msg)
            validation_warns.append(msg)

    # ── Step 5: Load event stream into memory ─────────────────────────────────
    events = _load_events(_EVENTS_PATH)
    _log.info("Loaded %d events from events.json", len(events))

    # ── Step 6: Analytics (all pure computation, no file I/O) ─────────────────
    staff_result = run_staff_filter(events, config)
    csv_result   = run_csv_analytics(_CSV_PATH)
    funnel       = run_funnel(events, csv_result, staff_result, config)
    anomalies    = run_anomalies(events, staff_result, config)

    # Funnel monotonicity notes (data quality) stay inside funnel["validation_notes"].
    # Operational issues (missing videos, failures) go into validation_warns only.

    # ── Step 7: Video hashes ──────────────────────────────────────────────────
    video_paths = {cam: _video_path(cam) for cam in ["CAM_1","CAM_2","CAM_3","CAM_4","CAM_5"]}
    hashes = write_hashes(video_paths, _HASHES_PATH)

    # ── Step 8: Assemble and write pipeline summary ───────────────────────────
    total_elapsed = time.time() - pipeline_start
    summary = _build_summary(
        events=events,
        funnel=funnel,
        anomalies=anomalies,
        csv_result=csv_result,
        staff_result=staff_result,
        hashes=hashes,
        camera_elapsed=camera_elapsed,
        validation_warnings=validation_warns,
        quick_mode=args.quick,
        elapsed=total_elapsed,
        max_frames=runtime_max_frames,
        frame_skip=runtime_frame_skip,
    )
    with open(_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    _log.info("Pipeline summary written to %s", _SUMMARY_PATH)

    # ── Step 9: Print console summary ─────────────────────────────────────────
    _print_summary(summary)

    return 0 if not validation_warns else 1


if __name__ == "__main__":
    sys.exit(main())
