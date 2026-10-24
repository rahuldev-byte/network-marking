"""Validation at the external road-input boundary."""

from pyproj import CRS
from pyproj.exceptions import CRSError

from .geo import coordinate


def validate_geojson_crs(data):
    """Reject legacy CRS declarations that contradict the WGS84 input contract."""
    declaration = data.get("crs")
    if declaration is None:
        return
    try:
        crs = CRS.from_user_input(declaration["properties"]["name"])
    except (KeyError, TypeError, ValueError, CRSError) as exc:
        raise ValueError("GeoJSON has an invalid CRS declaration") from exc
    if not crs.equals(CRS.from_epsg(4326), ignore_axis_order=True):
        raise ValueError(
            "GeoJSON roads must use WGS84 longitude/latitude; reproject the file "
            "or provide a GeoPackage with its source CRS declared"
        )


def road_coordinate(value, label):
    """Validate longitude/latitude ordering, returning two coordinate components."""
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError(f"{label}: requires a longitude/latitude coordinate pair")
    lat, lon = coordinate(value[1], value[0])
    if lat is None:
        raise ValueError(f"{label}: invalid longitude/latitude coordinate")
    return [lon, lat]


def node_id(value, label):
    """Normalize explicit topology identities while rejecting booleans/empty IDs."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int))
        or not str(value).strip()
    ):
        raise ValueError(f"{label}: node IDs must be nonempty strings or integers")
    return str(value)
