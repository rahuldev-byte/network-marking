"""Adapt analysis snapshots to Folium browser reports."""

import json
from pathlib import Path

from branca.element import Element

from .folium_map import FoliumMapRenderer
from .serialization import point_properties


def map_points(points, matches, graph) -> list[dict]:
    """Retain original locations and include accepted anchor locations separately."""
    rows = []
    for point in points:
        if not point.valid:
            continue
        row = {"lat": point.lat, "lon": point.lon, **point_properties(point)}
        if point.id in matches:
            row["matched_lon"], row["matched_lat"] = graph.coordinates[
                matches[point.id].anchor
            ]
        rows.append(row)
    return rows


def script_json(data) -> str:
    """Escape HTML delimiters in JSON embedded inside a script element."""
    encoded = json.dumps(
        data, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )
    for character, escape in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e")):
        encoded = encoded.replace(character, escape)
    return encoded


def write_map(
    path, splitters, households, bbox, title, roads=None, matches=None,
    graph=None, connections=(), x_m=None, snap_m=None, patch_count=0, osm=False,
):
    """Adapt an analysis snapshot into the persisted map payload contract."""
    data = {
        "title": title, "bbox": bbox,
        "road_status": "available" if roads else "unavailable",
        "x_m": x_m, "snap_m": snap_m, "patch_count": patch_count, "osm": osm,
        "splitters": map_points(splitters, matches or {}, graph),
        "households": [[point.lon, point.lat] for point in households if point.valid],
        "roads": (
            [[segment.a, segment.b] for segment in roads.segments] if roads else []
        ),
        "connections": [
            {key: value for key, value in link.items() if key != "piece_ids"}
            for link in connections
        ],
    }
    write_map_snapshot(path, data)


def write_map_snapshot(path, data):
    """Render a saved map payload without rerunning or changing its analysis."""
    map_view = FoliumMapRenderer().build(data)
    map_view.get_root().html.add_child(Element(
        '<script id="map-data" type="application/json">'
        + script_json(data) + '</script>'
    ))
    Path(path).write_text(map_view.get_root().render(), encoding="utf-8")
