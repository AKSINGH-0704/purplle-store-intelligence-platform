"""
Utilities — config/zones loading, event writing, logging, and integrity helpers.
"""
import collections
import hashlib
import json
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Required config keys — all must be present in config.json
# ---------------------------------------------------------------------------
_REQUIRED_CONFIG_KEYS = frozenset([
    "max_frames_per_camera", "frame_skip", "detection_resolution",
    "confidence_threshold", "tracker_distance_threshold",
    "warehouse_motion_threshold", "dwell_merge_window_seconds",
    "zone_abandonment_window_seconds", "repeat_visit_threshold",
    "min_dwell_for_visit_seconds", "queue_occupancy_threshold",
    "queue_duration_threshold_seconds", "staff_filter_enabled",
    "staff_roundtrip_threshold", "staff_roundtrip_window_minutes",
])

# Project root — derived from this file's location (src/utils.py → root/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# In-memory log buffer — last 50 entries, readable by api.py /health
# ---------------------------------------------------------------------------
LOG_BUFFER: collections.deque = collections.deque(maxlen=50)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        LOG_BUFFER.append(entry)
        return json.dumps(entry)


def get_logger(name: str) -> logging.Logger:
    """Return a JSON-formatted logger writing to stdout and logs/pipeline.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = _JsonFormatter()

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logs_dir = os.path.join(_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, "pipeline.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_config(path: str = "config.json") -> dict:
    """Load config.json; raise KeyError listing any missing required keys."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    missing = sorted(_REQUIRED_CONFIG_KEYS - cfg.keys())
    if missing:
        raise KeyError(
            f"config.json is missing required keys: {missing}. "
            f"Re-check config.json against the master plan Section 6."
        )
    return cfg


# ---------------------------------------------------------------------------
# Zones loader
# ---------------------------------------------------------------------------
def load_zones(path: str = "zones.json") -> dict:
    """Load zones.json; warn (do not crash) if any camera polygon is empty."""
    with open(path, encoding="utf-8") as f:
        zones = json.load(f)
    logger = logging.getLogger(__name__)
    for cam_id, cam_cfg in zones.items():
        if not cam_cfg.get("polygon"):
            logger.warning(
                "zones.json: %s polygon is empty — zone classification "
                "disabled for this camera until polygon is populated.",
                cam_id,
            )
    return zones


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------
def compute_sha256(filepath: str) -> str:
    """Return the lowercase hex SHA256 digest of the file at filepath."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_hashes(paths: dict, output_path: str = "events/video_hashes.json") -> dict:
    """
    Compute SHA256 for each {label: filepath} entry.
    Write {label: hex_digest} to output_path (NDJSON-adjacent file under events/).
    Missing files are recorded as {"error": "not_found"} rather than crashing.
    Returns the written dict.
    """
    hashes: dict = {}
    for label, filepath in paths.items():
        if os.path.exists(filepath):
            hashes[label] = compute_sha256(filepath)
        else:
            hashes[label] = {"error": "not_found"}
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)
    return hashes


def verify_hashes(hashes_path: str, paths: dict) -> list:
    """
    Re-compute SHA256 for each {label: filepath} and compare against stored hashes.
    Returns a list of mismatch dicts; empty list means all verified.
    Skips labels whose stored value is {"error": "not_found"}.
    """
    with open(hashes_path, encoding="utf-8") as f:
        stored = json.load(f)
    mismatches = []
    for label, filepath in paths.items():
        expected = stored.get(label)
        if isinstance(expected, dict):
            continue  # was "not_found" when written — skip
        if not os.path.exists(filepath):
            mismatches.append(
                {"label": label, "expected": expected, "actual": None, "match": False}
            )
            continue
        actual = compute_sha256(filepath)
        if actual != expected:
            mismatches.append(
                {"label": label, "expected": expected, "actual": actual, "match": False}
            )
    return mismatches


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------
def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable string, e.g. '2h 14m 32s'."""
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Event schema (frozen — matches DESIGN.md Section 8 exactly)
# ---------------------------------------------------------------------------
# All events share a common envelope:
#   event_id, event_type, camera, frame_idx, timestamp_seconds, processed_at
# Type-specific fields are merged in by each factory function below.

def _make_event_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def make_zone_dwell_event(
    camera: str,
    zone: str,
    track_id: int,
    bbox: list,
    centroid: list,
    confidence: float,
    dwell_seconds: float,
    frame_entry: int,
    frame_exit: int,
    timestamp_entry_seconds: float,
    timestamp_exit_seconds: float,
    staff_filtered: bool = False,
) -> dict:
    """Emitted by session_manager when a qualifying zone visit completes."""
    return {
        "event_id": _make_event_id(),
        "event_type": "zone_dwell",
        "camera": camera,
        "zone": zone,
        "frame_idx": frame_entry,
        "timestamp_seconds": timestamp_entry_seconds,
        "processed_at": _utcnow(),
        "track_id": track_id,
        "bbox": bbox,
        "centroid": centroid,
        "confidence": round(confidence, 4),
        "dwell_seconds": round(dwell_seconds, 2),
        "frame_entry": frame_entry,
        "frame_exit": frame_exit,
        "timestamp_entry_seconds": timestamp_entry_seconds,
        "timestamp_exit_seconds": timestamp_exit_seconds,
        "staff_filtered": staff_filtered,
    }


def make_crossing_event(
    camera: str,
    track_id: int,
    centroid_before: list,
    centroid_after: list,
    frame_idx: int,
    timestamp_seconds: float,
    crossing_direction: str,  # "entry" | "exit"
    staff_filtered: bool = False,
) -> dict:
    """Emitted by entry_counter for each line crossing at CAM_3."""
    if crossing_direction not in ("entry", "exit"):
        raise ValueError(
            f"crossing_direction must be 'entry' or 'exit', got {crossing_direction!r}"
        )
    event_type = "crossing_entry" if crossing_direction == "entry" else "crossing_exit"
    return {
        "event_id": _make_event_id(),
        "event_type": event_type,
        "camera": camera,
        "zone": "entrance",
        "frame_idx": frame_idx,
        "timestamp_seconds": timestamp_seconds,
        "processed_at": _utcnow(),
        "track_id": track_id,
        "centroid_before": centroid_before,
        "centroid_after": centroid_after,
        "crossing_direction": crossing_direction,
        "staff_filtered": staff_filtered,
    }


def make_warehouse_motion_event(
    camera: str,
    frame_idx: int,
    timestamp_seconds: float,
    contour_area: float,
    is_restocking_event: bool = False,
) -> dict:
    """Emitted by background_motion for each qualifying MOG2 motion frame."""
    return {
        "event_id": _make_event_id(),
        "event_type": "warehouse_motion",
        "camera": camera,
        "zone": "warehouse",
        "frame_idx": frame_idx,
        "timestamp_seconds": timestamp_seconds,
        "processed_at": _utcnow(),
        "contour_area": round(contour_area, 1),
        "is_restocking_event": is_restocking_event,
    }


def make_zone_entry_event(
    camera: str,
    zone: str,
    track_id: int,
    centroid: list,
    frame_idx: int,
    timestamp_seconds: float,
) -> dict:
    """Emitted by session_manager when a track first enters a zone polygon."""
    return {
        "event_id": _make_event_id(),
        "event_type": "zone_entry",
        "camera": camera,
        "zone": zone,
        "frame_idx": frame_idx,
        "timestamp_seconds": timestamp_seconds,
        "processed_at": _utcnow(),
        "track_id": track_id,
        "centroid": centroid,
    }


def make_zone_exit_event(
    camera: str,
    zone: str,
    track_id: int,
    centroid: list,
    frame_idx: int,
    timestamp_seconds: float,
) -> dict:
    """Emitted by session_manager when a track leaves a zone polygon."""
    return {
        "event_id": _make_event_id(),
        "event_type": "zone_exit",
        "camera": camera,
        "zone": zone,
        "frame_idx": frame_idx,
        "timestamp_seconds": timestamp_seconds,
        "processed_at": _utcnow(),
        "track_id": track_id,
        "centroid": centroid,
    }


def make_queue_alert_event(
    camera: str,
    zone: str,
    frame_idx: int,
    timestamp_seconds: float,
    occupancy_count: int,
    duration_seconds: float,
) -> dict:
    """Emitted by anomalies when CAM_5 queue exceeds occupancy threshold."""
    return {
        "event_id": _make_event_id(),
        "event_type": "queue_alert",
        "camera": camera,
        "zone": zone,
        "frame_idx": frame_idx,
        "timestamp_seconds": timestamp_seconds,
        "processed_at": _utcnow(),
        "occupancy_count": occupancy_count,
        "duration_seconds": round(duration_seconds, 2),
    }


# ---------------------------------------------------------------------------
# Event writer
# ---------------------------------------------------------------------------
def append_event(event: dict, path: str = "events/events.json") -> None:
    """Append a single event dict as one JSON line to path (NDJSON format).
    Creates the events/ directory if it does not exist."""
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
