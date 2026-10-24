"""Geographic bounds and deterministic pilot selection."""

import math
from collections import Counter


def bounds(points):
    """Return the envelope of valid points, or None for an empty extent."""
    valid = [point for point in points if point.valid]
    if not valid:
        return None
    return [
        min(point.lon for point in valid), min(point.lat for point in valid),
        max(point.lon for point in valid), max(point.lat for point in valid),
    ]


def inside(point, bbox) -> bool:
    """Test inclusive region membership without changing a source record."""
    return (
        point.valid
        and bbox[0] <= point.lon <= bbox[2]
        and bbox[1] <= point.lat <= bbox[3]
    )


def validate_bbox(bbox) -> tuple:
    """Require ordered finite bounds within the supported geographic range."""
    west, south, east, north = bbox
    if not all(math.isfinite(value) for value in bbox) or not (
        -180 <= west < east <= 180 and -85 <= south < north <= 85
    ):
        raise ValueError(
            "bbox must be WEST SOUTH EAST NORTH within longitude ±180 and latitude ±85"
        )
    return tuple(bbox)


def auto_pilot(points, cell_degrees=0.02) -> tuple:
    """Choose the densest eligible grid cell with a deterministic tie-break."""
    if not math.isfinite(cell_degrees) or cell_degrees <= 0:
        raise ValueError("Pilot cell size must be finite and positive")
    last_lon_cell = math.ceil(180 / cell_degrees) - 1
    cells = Counter(
        (min(math.floor(point.lon / cell_degrees), last_lon_cell),
         math.floor(point.lat / cell_degrees))
        for point in points
        if point.valid and point.partner and 0 < abs(point.lat) < 85 and point.lon != 0
    )
    if not cells:
        raise ValueError("No valid splitters available for an automatic pilot")
    (column, row), _ = min(cells.items(), key=lambda item: (-item[1], item[0]))
    west, south, east, north = (
        round(value * cell_degrees, 8)
        for value in (column, row, column + 1, row + 1)
    )
    return validate_bbox((
        max(-180, west), max(-85, south), min(180, east), min(85, north)
    ))
