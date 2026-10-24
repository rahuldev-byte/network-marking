"""Shared JSON and GeoJSON serialization contracts."""

import json
from pathlib import Path


def write_json(path, data):
    """Write readable UTF-8 JSON, rejecting non-finite numeric values."""
    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def point_properties(point):
    """Expose derived point fields without leaking source-only household data."""
    return {
        "id": point.id, "partner": point.partner, "flags": point.flags,
        "status": point.status,
        "offset_m": round(point.offset_m, 4) if point.offset_m is not None else None,
        "road_id": point.road_id, "patch": point.patch,
    }


def feature(geometry, properties):
    """Build one GeoJSON feature without interpreting its geometry."""
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def collection(features):
    """Wrap features using the GeoJSON collection contract."""
    return {"type": "FeatureCollection", "features": features}
