"""Adapters from supported road documents into explicit road topology."""

import json
from pathlib import Path

import geopandas as gpd

from .geospatial import geojson_document
from .road_network import Roads
from .road_validation import node_id, road_coordinate, validate_geojson_crs


def object_list(value, label: str) -> list[dict]:
    """Require a collection of objects before interpreting external JSON."""
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be a list of objects")
    return value


class OverpassRoadReader:
    """Interpret OSM ways using their supplied node identities."""

    def __init__(self, roads: Roads):
        self.roads = roads

    def read(self, data: dict) -> None:
        if data.get("remark"):
            raise ValueError(
                f"Overpass returned an incomplete/error response: {data['remark']}"
            )
        elements = object_list(data["elements"], "Overpass elements")
        nodes = self._nodes(elements)
        for element in elements:
            if element.get("type") == "way":
                self._add_way(element, nodes)

    @staticmethod
    def _nodes(elements: list[dict]) -> dict:
        nodes = {}
        for element in elements:
            if element.get("type") != "node":
                continue
            key = node_id(element.get("id"), "OSM node")
            coord = road_coordinate(
                [element.get("lon"), element.get("lat")], f"OSM node {key}"
            )
            if key in nodes and nodes[key] != coord:
                raise ValueError(f"OSM node {key} has inconsistent coordinates")
            nodes[key] = coord
        return nodes

    def _add_way(self, way: dict, nodes: dict) -> None:
        tags = way.get("tags", {})
        if not isinstance(tags, dict):
            raise ValueError("OSM way tags must be an object")
        if "highway" not in tags or tags.get("area") == "yes":
            return
        key = node_id(way.get("id"), "OSM way")
        refs = way.get("nodes")
        if not isinstance(refs, list) or len(refs) < 2:
            raise ValueError(
                f"OSM way {key} requires at least two referenced nodes; "
                "export ways AND their nodes"
            )
        refs = [node_id(ref, f"OSM way {key}") for ref in refs]
        for start, end in zip(refs, refs[1:]):
            if start not in nodes or end not in nodes:
                raise ValueError(
                    f"OSM way {key} is missing referenced nodes; "
                    "export ways AND their nodes"
                )
            self.roads.add(
                f"osm:{start}", f"osm:{end}", nodes[start], nodes[end], key
            )


class CompanyRoadReader:
    """Interpret LineStrings without inventing junctions at crossings."""

    def __init__(self, roads: Roads):
        self.roads = roads

    def read(self, data: dict) -> None:
        validate_geojson_crs(data)
        features = object_list(data.get("features"), "GeoJSON features")
        for index, feature in enumerate(features):
            self._add_feature(feature, index)

    def _add_feature(self, feature: dict, index: int) -> None:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if not isinstance(props, dict) or not isinstance(geometry, dict):
            raise ValueError(
                f"Road feature {index}: properties and geometry must be objects"
            )
        if geometry.get("type") != "LineString":
            raise ValueError(
                "Company roads must be LineString features with explicit topology"
            )
        coords = geometry.get("coordinates", [])
        if not isinstance(coords, list) or len(coords) < 2:
            raise ValueError(f"Road feature {index}: requires at least two coordinates")
        road_id = str(props.get("road_id", feature.get("id", index)))
        refs = self._references(props, coords, road_id, index)
        for a, b, start, end in zip(coords, coords[1:], refs, refs[1:]):
            self.roads.add(start, end, a, b, road_id)

    @staticmethod
    def _references(props, coords, road_id, index) -> list[str]:
        refs = props.get("node_ids")
        if refs is None:
            if props.get("from_node") is None or props.get("to_node") is None:
                raise ValueError(
                    "Each road needs node_ids for every vertex, or "
                    "from_node/to_node. Geometry crossings alone do not "
                    "establish junctions."
                )
            start = "company:" + node_id(props["from_node"], f"Road {road_id}")
            end = "company:" + node_id(props["to_node"], f"Road {road_id}")
            # Bend IDs cannot collide with supplied company junction IDs.
            refs = (
                [start]
                + [f"shape:{index}:{j}" for j in range(1, len(coords) - 1)]
                + [end]
            )
        else:
            if not isinstance(refs, list):
                raise ValueError(f"Road {road_id}: node_ids must be a list")
            refs = ["company:" + node_id(ref, f"Road {road_id}") for ref in refs]
        if len(refs) != len(coords):
            raise ValueError(
                f"Road {road_id}: node_ids must match all geometry vertices"
            )
        return refs


def load_roads(path, projection) -> Roads:
    """Select the supported input adapter and validate the resulting network."""
    path = Path(path)
    if path.suffix.lower() in {".json", ".geojson"}:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = read_vector_roads(path)
    if not isinstance(data, dict):
        raise ValueError(
            "Road input must be a JSON object: Overpass response or "
            "GeoJSON FeatureCollection"
        )
    roads = Roads(projection)
    if "elements" in data:
        reader = OverpassRoadReader(roads)
    elif data.get("type") == "FeatureCollection":
        reader = CompanyRoadReader(roads)
    else:
        raise ValueError(
            "Roads must be an Overpass JSON response or a GeoJSON FeatureCollection"
        )
    reader.read(data)
    if not roads.segments:
        raise ValueError("Road input contains no usable road segments")
    return roads


def read_vector_roads(path) -> dict:
    """Read company vector formats and transform their declared CRS to WGS84."""
    try:
        frame = gpd.read_file(path)
        if frame.crs is None:
            raise ValueError("Company road data must declare its coordinate system")
        return geojson_document(frame)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValueError(f"Cannot read company roads from {path}: {exc}") from exc
