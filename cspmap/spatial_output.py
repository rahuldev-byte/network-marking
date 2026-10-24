"""GeoJSON feature construction and regional layer exports."""

from .geospatial import feature_frame, geojson_document
from .serialization import feature, point_properties, write_json


def splitter_features(points) -> list[dict]:
    return [
        feature(
            {"type": "Point", "coordinates": [point.lon, point.lat]},
            point_properties(point),
        )
        for point in points if point.valid
    ]


def household_features(points) -> list[dict]:
    return [
        feature(
            {"type": "Point", "coordinates": [point.lon, point.lat]},
            {"id": point.id, "flags": point.flags},
        )
        for point in points if point.valid
    ]


def connection_features(connections) -> list[dict]:
    return [
        feature(
            {"type": "LineString", "coordinates": link["coordinates"]},
            {key: value for key, value in link.items()
             if key not in {"coordinates", "piece_ids"}},
        )
        for link in connections
    ]


def road_features(roads) -> list[dict]:
    if roads is None:
        return []
    return [
        feature(
            {"type": "LineString", "coordinates": [segment.a, segment.b]},
            {"edge_id": segment.id, "road_id": segment.road_id,
             "from_node": segment.u, "to_node": segment.v},
        )
        for segment in roads.segments
    ]


def match_features(points, matches, graph) -> list[dict]:
    return [
        feature(
            {"type": "LineString", "coordinates": [
                [point.lon, point.lat], graph.coordinates[matches[point.id].anchor]
            ]},
            {"splitter_id": point.id, "partner_id": point.partner,
             "offset_m": point.offset_m},
        )
        for point in points if point.id in matches
    ]


def export_spatial(
    output, splitters, households, roads=None, matches=None,
    graph=None, connections=(),
):
    """Persist the five spatial layers without recomputing the analysis."""
    layers = {
        "splitters": splitter_features(splitters),
        "households": household_features(households),
        "connections": connection_features(connections),
        "roads": road_features(roads),
        "road_matches": match_features(splitters, matches or {}, graph),
    }
    for name, features in layers.items():
        frame = feature_frame(features)
        write_json(output / f"{name}.geojson", geojson_document(frame))
