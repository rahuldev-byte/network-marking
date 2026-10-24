"""Conservative point-to-road matching with an indexed candidate search."""

from shapely import distance, line_locate_point
from shapely.geometry import Point as GeometryPoint
from shapely.geometry import box

from .geospatial import road_frame
from .models import Match, Point
from .road_network import Roads


def anchor_key(segment, index: int, fraction: float) -> str:
    """Give equivalent junction positions the same topological identity."""
    if fraction * segment.length <= 1e-6:
        return segment.u
    if (1 - fraction) * segment.length <= 1e-6:
        return segment.v
    return f"match:{index}:{fraction * segment.length:.6f}"


class SegmentIndex:
    """GeoPandas spatial index over metric road geometries and segment IDs."""

    def __init__(self, roads: Roads):
        self.roads = roads
        self.frame = road_frame(roads, projected=True)
        self.index = self.frame.sindex

    def candidates(self, position, radius: float) -> set[int]:
        x, y = position
        extent = box(
            x - radius, y - radius, x + radius, y + radius
        )
        return {int(index) for index in self.index.query(extent)}

    def ranked(self, position, radius: float) -> list[tuple[float, int, float]]:
        """Filter index candidates by exact distance and locate metric anchors."""
        indices = sorted(self.candidates(position, radius))
        if not indices:
            return []
        geometries = self.frame.geometry.array.take(indices)
        point = GeometryPoint(*position)
        offsets = distance(geometries, point)
        positions = line_locate_point(geometries, point)
        return [
            (float(offset), index, float(along / self.roads.segments[index].length)
             if self.roads.segments[index].length else 0.0)
            for index, offset, along in zip(indices, offsets, positions)
            if offset <= radius
        ]


class RoadMatcher:
    """Accept only in-tolerance positions without competing distinct anchors."""

    def __init__(
        self, roads: Roads, snap_m: float, ambiguity_m: float = 2.0,
        index: SegmentIndex | None = None,
    ):
        self.roads = roads
        self.snap_m = snap_m
        self.ambiguity_m = ambiguity_m
        if index is not None and (
            index.roads is not roads or len(index.frame) != len(roads.segments)
        ):
            raise ValueError("Spatial index must describe the current road network")
        self.index = index if index is not None else SegmentIndex(roads)

    def match(self, points: list[Point]) -> dict[str, Match]:
        matches = {}
        for point in points:
            point.reset_match()
            if not self._eligible(point):
                continue
            match = self._match_one(point)
            if match is not None:
                matches[point.id] = match
        return matches

    @staticmethod
    def _eligible(point: Point) -> bool:
        if not point.valid:
            point.status = "invalid_coordinates"
            return False
        if not point.partner or "zero_coordinate_review" in point.flags:
            point.status = "source_review_required"
            return False
        return True

    def _ranked_candidates(self, point: Point) -> list[tuple]:
        position = self.roads.projection.project(point.lon, point.lat)
        ranked = []
        for distance, index, fraction in self.index.ranked(position, self.snap_m):
            segment = self.roads.segments[index]
            anchor = anchor_key(segment, index, fraction)
            ranked.append((distance, index, fraction, anchor))
        return sorted(ranked)

    def _match_one(self, point: Point) -> Match | None:
        ranked = self._ranked_candidates(point)
        if not ranked:
            point.status = "no_road_within_tolerance"
            return None
        distance, index, fraction, anchor = ranked[0]
        point.offset_m = distance
        ambiguous = any(
            offset <= distance + self.ambiguity_m and other_anchor != anchor
            for offset, _, _, other_anchor in ranked[1:]
        )
        if ambiguous:
            point.status = "ambiguous_road_match"
            return None
        point.status = "matched"
        point.road_id = self.roads.segments[index].road_id
        return Match(index, fraction, distance, anchor)


def match_points(points, roads, snap_m, ambiguity_m=2.0):
    """Compatibility entry point for conservative matching."""
    return RoadMatcher(roads, snap_m, ambiguity_m).match(points)
