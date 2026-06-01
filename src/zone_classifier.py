"""
Zone classifier — polygon membership test and zone assignment.
"""
from typing import Optional, Tuple, Union


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray-casting point-in-polygon test.
    polygon: list of [x, y] pairs as stored in zones.json."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def classify_zone(
    camera_id: str,
    centroid: Union[Tuple[float, float], list],
    zones_cfg: dict,
) -> Optional[str]:
    """Return the zone name if centroid falls inside the camera's polygon, else None.

    centroid: (cx, cy) or [cx, cy] in pixel space at detection_resolution.
    Raises ValueError if camera_id is not present in zones_cfg.
    Returns None if the camera's polygon is empty or the centroid is outside it.
    """
    if camera_id not in zones_cfg:
        raise ValueError(
            f"camera_id {camera_id!r} not found in zones config. "
            f"Valid cameras: {sorted(zones_cfg.keys())}"
        )
    polygon = zones_cfg[camera_id].get("polygon", [])
    if not polygon:
        return None
    cx, cy = float(centroid[0]), float(centroid[1])
    if point_in_polygon(cx, cy, polygon):
        return zones_cfg[camera_id]["zone"]
    return None
