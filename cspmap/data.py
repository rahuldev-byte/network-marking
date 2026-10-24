"""Public input API; implementations live in focused input/quality modules."""

from .csv_input import DEFAULT_HOUSEHOLDS, DEFAULT_SPLITTERS, read_points
from .geo import coordinate
from .models import Point
from .quality import profile
from .regions import auto_pilot, bounds, inside, validate_bbox

__all__ = [
    "DEFAULT_HOUSEHOLDS", "DEFAULT_SPLITTERS", "Point", "coordinate",
    "read_points", "profile", "auto_pilot", "bounds", "inside", "validate_bbox",
]
