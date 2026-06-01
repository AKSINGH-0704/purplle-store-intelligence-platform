"""
Entry counter — CAM_3 entry/exit line crossing detection.

Consumes run_detection() output for CAM_3 only; emits crossing_entry and
crossing_exit events.

Crossing algorithm:
  For each consecutive pair of processed frames sharing the same track_id,
  check whether the centroid straddled entry_line_y between frames.
  Apply the door x-gate to exclude crossings outside the physical doorway.
  Classify direction using entry_direction_vector dot product (dy sign).

Doorway gate:
  Only crossings where curr_cx is within [door_x1, door_x2] are counted.
  Gate was derived from visual inspection of CAM_3 frame 100 and proven in
  Phase 2 Checkpoint 2.3 v2 to suppress one confirmed corridor false positive.
  See decisions_log.txt Decision 15.

Ambiguous filter:
  Crossings where |dy| < _AMBIGUOUS_MIN_DY (8px) are counted as ambiguous
  and not emitted as events. These represent centroid jitter at the line.

Sensitivity note:
  Crossing mechanics and gate behaviour have been validated synthetically
  and against Phase 2 footage. However, Phase 2 Checkpoint 2.3 observed
  zero genuine store entries in 720 processed frames (81% of CAM_3 footage).
  Real-world sensitivity — whether the detector fires for actual customers
  crossing the entrance — is UNVERIFIED until full end-to-end pipeline
  validation with footage that contains confirmed crossing events.
  Q3 status: mechanics validated; sensitivity unverified.
"""
from typing import Dict, Optional

from src.detection import run_detection
from src.utils import append_event, get_logger, make_crossing_event

_log = get_logger(__name__)

# Minimum |dy| (pixels) for a crossing to be classified as entry or exit.
# Crossings with |dy| below this are counted as ambiguous and suppressed.
# Carried from Phase 2 Checkpoint 2.3 validation (hardcoded there as 8).
_AMBIGUOUS_MIN_DY = 8


def _check_crossing(
    prev_cy: int,
    curr_cy: int,
    curr_cx: int,
    entry_y: int,
    dir_dy: int,
    door_x1: int,
    door_x2: int,
    ambiguous_min_dy: int = _AMBIGUOUS_MIN_DY,
) -> Optional[str]:
    """Classify one centroid transition as "entry", "exit", "ambiguous", or None.

    Returns None if:
      - curr_cx is outside the doorway gate [door_x1, door_x2]
      - the centroid did not straddle entry_y between frames
    Returns "ambiguous" if |dy| < ambiguous_min_dy.
    Returns "entry" if dy * dir_dy > 0, "exit" otherwise.
    """
    # Doorway gate — suppress crossings outside the physical door opening
    if not (door_x1 <= curr_cx <= door_x2):
        return None

    # Geometry check — centroid must have straddled the entry line
    crossed = (prev_cy < entry_y <= curr_cy) or (prev_cy > entry_y >= curr_cy)
    if not crossed:
        return None

    dy = curr_cy - prev_cy
    if abs(dy) < ambiguous_min_dy:
        return "ambiguous"

    return "entry" if dy * dir_dy > 0 else "exit"


def run_entry_crossings(
    video_path: str,
    camera_id: str,
    config: dict,
    zones_cfg: dict,
    events_path: str = "events/events.json",
) -> dict:
    """Process CAM_3; emit crossing_entry and crossing_exit events.

    Args:
        video_path:  Absolute path to CAM_3.mp4.
        camera_id:   Must be "CAM_3". Raises ValueError otherwise.
        config:      Loaded config.json dict.
        zones_cfg:   Loaded zones.json dict.
        events_path: NDJSON output path for crossing events.

    Returns:
        {
            "entry_count":    int,  # qualifying entry crossings
            "exit_count":     int,  # qualifying exit crossings
            "ambiguous_count": int, # crossings suppressed by ambiguous filter
        }
    """
    if camera_id != "CAM_3":
        raise ValueError(
            f"run_entry_crossings is for CAM_3 only; got '{camera_id}'. "
            "Use run_zone_visits() for CAM_1, CAM_2, and CAM_5."
        )

    cam_cfg = zones_cfg.get("CAM_3", {})
    entry_line = cam_cfg.get("entry_line")
    entry_vec  = cam_cfg.get("entry_direction_vector")
    door_gate  = cam_cfg.get("door_x_gate")

    if not entry_line or not entry_vec or not door_gate:
        raise KeyError(
            "zones.json CAM_3 is missing one or more required keys: "
            "entry_line, entry_direction_vector, door_x_gate"
        )

    entry_y = entry_line[0][1]   # y=170 — horizontal line, same y on both ends
    dir_dy  = entry_vec[1]       # 1: top-to-bottom = ENTRY
    door_x1 = door_gate[0]      # 250
    door_x2 = door_gate[1]      # 490

    # prev_centroids[track_id] = [cx, cy] from the last frame this track appeared.
    # Not pruned on disappearance — run_detection does not signal track removal,
    # and retaining the last known centroid is correct for crossing detection
    # across brief disappearance gaps (consistent with Phase 2 behaviour).
    prev_centroids: Dict[int, list] = {}

    entry_count    = 0
    exit_count     = 0
    ambiguous_count = 0

    for frame in run_detection(video_path, camera_id, config, zones_cfg):
        frame_idx = frame["frame_idx"]
        ts        = frame["timestamp_sec"]

        for track in frame["tracks"]:
            tid      = track["track_id"]
            centroid = track["centroid"]
            curr_cx, curr_cy = centroid

            if tid not in prev_centroids:
                # First appearance — record centroid, no crossing possible yet
                prev_centroids[tid] = centroid
                continue

            prev_cx, prev_cy = prev_centroids[tid]
            result = _check_crossing(
                prev_cy, curr_cy, curr_cx,
                entry_y, dir_dy, door_x1, door_x2,
            )

            if result == "entry":
                entry_count += 1
                append_event(
                    make_crossing_event(
                        camera_id, tid,
                        [prev_cx, prev_cy], centroid,
                        frame_idx, ts,
                        crossing_direction="entry",
                        staff_filtered=False,
                    ),
                    path=events_path,
                )
            elif result == "exit":
                exit_count += 1
                append_event(
                    make_crossing_event(
                        camera_id, tid,
                        [prev_cx, prev_cy], centroid,
                        frame_idx, ts,
                        crossing_direction="exit",
                        staff_filtered=False,
                    ),
                    path=events_path,
                )
            elif result == "ambiguous":
                ambiguous_count += 1
                _log.debug(
                    "CAM_3 track_id=%d ambiguous crossing suppressed "
                    "(prev_cy=%d curr_cy=%d dy=%d cx=%d)",
                    tid, prev_cy, curr_cy, curr_cy - prev_cy, curr_cx,
                )

            prev_centroids[tid] = centroid

    _log.info(
        "CAM_3 entry_crossings complete: entries=%d exits=%d ambiguous=%d",
        entry_count, exit_count, ambiguous_count,
    )
    return {
        "entry_count":     entry_count,
        "exit_count":      exit_count,
        "ambiguous_count": ambiguous_count,
    }
