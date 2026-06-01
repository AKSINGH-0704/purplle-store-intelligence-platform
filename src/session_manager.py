"""
Session manager — zone visit tracking for YOLO cameras (CAM_1, CAM_2, CAM_5).

Consumes run_detection() output; emits zone_entry, zone_exit, zone_dwell events.

Disappeared-track policy (Option A):
  Session remains open while the track_id is alive in the detection layer.
  Temporary YOLO detection gaps (disappeared 1-9, up to ~1.7s) are transparent
  to session state. Sessions close only when the track reappears in a different
  zone, or when the generator exhausts and remaining open sessions are flushed.

Dwell merge rule:
  When a new track enters a zone, the most recently closed session for that zone
  is merged into the new session if ALL four conditions hold:
    1. Same zone
    2. Time gap since close < dwell_merge_window_seconds
    3. No other track currently has an open session in that zone
    4. dist(closed session's last centroid, new track's first centroid)
       <= tracker_distance_threshold
  Condition 4 is the identity gate — it prevents two different sequential
  visitors from being merged by requiring spatial proximity consistent with
  ID fragmentation of a single person (same threshold the tracker uses).
"""
import math
from typing import Dict

from src.detection import run_detection
from src.utils import (
    append_event,
    get_logger,
    make_zone_dwell_event,
    make_zone_entry_event,
    make_zone_exit_event,
)

_log = get_logger(__name__)


def _dist(a: list, b: list) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def run_zone_visits(
    video_path: str,
    camera_id: str,
    config: dict,
    zones_cfg: dict,
    events_path: str = "events/events.json",
) -> dict:
    """Process one YOLO camera; emit zone_entry/exit/dwell events.

    Returns per-zone summary:
        {
            zone_name: {
                "visit_count":     int,
                "avg_dwell_sec":   float,
                "total_dwell_sec": float,
            }
        }
    """
    min_dwell    = config["min_dwell_for_visit_seconds"]
    merge_window = config["dwell_merge_window_seconds"]
    tracker_dist = config["tracker_distance_threshold"]

    cam_cfg   = zones_cfg.get(camera_id, {})
    zone_name = cam_cfg.get("zone")
    if not zone_name:
        _log.warning("%s: no zone defined in zones.json — skipping", camera_id)
        return {}

    # open_sessions[track_id] = {
    #   zone, entry_frame, entry_ts, entry_centroid, entry_bbox,
    #   entry_confidence, last_centroid, last_frame, last_ts
    # }
    open_sessions: Dict[int, dict] = {}

    # recently_closed[zone] = most recent closed session metadata for merge check
    # {closed_ts, last_centroid, entry_frame, entry_ts, entry_centroid,
    #  entry_bbox, entry_confidence}
    recently_closed: Dict[str, dict] = {}

    # completed qualifying visits per zone: list of dwell_seconds values
    completed: Dict[str, list] = {}

    def _close_session(tid: int, exit_frame: int, exit_ts: float) -> None:
        sess = open_sessions.pop(tid, None)
        if sess is None:
            return
        z     = sess["zone"]
        dwell = exit_ts - sess["entry_ts"]

        append_event(
            make_zone_exit_event(
                camera_id, z, tid, sess["last_centroid"], exit_frame, exit_ts,
            ),
            path=events_path,
        )

        if dwell >= min_dwell:
            append_event(
                make_zone_dwell_event(
                    camera_id, z, tid,
                    sess["entry_bbox"], sess["entry_centroid"],
                    sess["entry_confidence"],
                    dwell,
                    sess["entry_frame"], exit_frame,
                    sess["entry_ts"],    exit_ts,
                    staff_filtered=False,
                ),
                path=events_path,
            )
            completed.setdefault(z, []).append(dwell)

        recently_closed[z] = {
            "closed_ts":        exit_ts,
            "last_centroid":    sess["last_centroid"],
            "entry_frame":      sess["entry_frame"],
            "entry_ts":         sess["entry_ts"],
            "entry_centroid":   sess["entry_centroid"],
            "entry_bbox":       sess["entry_bbox"],
            "entry_confidence": sess["entry_confidence"],
        }

    def _open_session(
        tid: int, zone: str, frame_idx: int, ts: float,
        centroid: list, bbox: list, confidence: float,
    ) -> None:
        prev         = recently_closed.get(zone)
        other_active = any(s["zone"] == zone for s in open_sessions.values())

        merged = False
        if (
            prev is not None
            and not other_active
            and (ts - prev["closed_ts"]) < merge_window
            and _dist(prev["last_centroid"], centroid) <= tracker_dist
        ):
            # Merge: re-open using the previous session's entry data
            open_sessions[tid] = {
                "zone":             zone,
                "entry_frame":      prev["entry_frame"],
                "entry_ts":         prev["entry_ts"],
                "entry_centroid":   prev["entry_centroid"],
                "entry_bbox":       prev["entry_bbox"],
                "entry_confidence": prev["entry_confidence"],
                "last_centroid":    centroid,
                "last_frame":       frame_idx,
                "last_ts":          ts,
            }
            recently_closed.pop(zone, None)
            merged = True
            _log.debug(
                "%s track_id=%d merged into prior session "
                "(gap=%.1fs dist=%.0fpx)",
                camera_id, tid,
                ts - prev["closed_ts"],
                _dist(prev["last_centroid"], centroid),
            )

        if not merged:
            open_sessions[tid] = {
                "zone":             zone,
                "entry_frame":      frame_idx,
                "entry_ts":         ts,
                "entry_centroid":   centroid,
                "entry_bbox":       bbox,
                "entry_confidence": confidence,
                "last_centroid":    centroid,
                "last_frame":       frame_idx,
                "last_ts":          ts,
            }
            append_event(
                make_zone_entry_event(
                    camera_id, zone, tid, centroid, frame_idx, ts,
                ),
                path=events_path,
            )

    # ── Main processing loop ─────────────────────────────────────────────
    for frame in run_detection(video_path, camera_id, config, zones_cfg):
        frame_idx = frame["frame_idx"]
        ts        = frame["timestamp_sec"]

        for track in frame["tracks"]:
            tid        = track["track_id"]
            zone       = track["zone"]
            centroid   = track["centroid"]
            bbox       = track["bbox"]
            confidence = track["confidence"]

            if zone is None:
                if tid in open_sessions:
                    _close_session(tid, frame_idx, ts)
            else:
                if tid not in open_sessions:
                    _open_session(tid, zone, frame_idx, ts,
                                  centroid, bbox, confidence)
                else:
                    sess = open_sessions[tid]
                    if sess["zone"] != zone:
                        # Track moved to a different zone within same camera
                        _close_session(tid, frame_idx, ts)
                        _open_session(tid, zone, frame_idx, ts,
                                      centroid, bbox, confidence)
                    else:
                        # Still in same zone — update last position and time
                        sess["last_centroid"] = centroid
                        sess["last_frame"]    = frame_idx
                        sess["last_ts"]       = ts

    # ── Flush all sessions still open at end of video ────────────────────
    # Use each session's own last_frame/last_ts (the final detection for that
    # track), not a global approximation.
    for tid in list(open_sessions):
        sess = open_sessions[tid]
        _close_session(tid, sess["last_frame"], sess["last_ts"])

    # ── Build summary ────────────────────────────────────────────────────
    summary: dict = {}
    for zone, dwells in completed.items():
        summary[zone] = {
            "visit_count":     len(dwells),
            "avg_dwell_sec":   round(sum(dwells) / len(dwells), 2) if dwells else 0.0,
            "total_dwell_sec": round(sum(dwells), 2),
        }

    _log.info(
        "%s zone_visits complete: %s",
        camera_id,
        {z: v["visit_count"] for z, v in summary.items()},
    )
    return summary
