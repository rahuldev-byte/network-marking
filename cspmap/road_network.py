"""Explicit physical road topology with metric edge lengths."""

from shapely.geometry import LineString

from .models import Segment
from .road_validation import node_id, road_coordinate


class Roads:
    """Own validated nodes and deduplicated undirected original segments."""

    def __init__(self, projection):
        self.projection = projection
        self.nodes = {}
        self.segments = []
        self._pairs = set()

    def _register_node(self, key, coordinate):
        self.projection.project(*coordinate)
        previous = self.nodes.get(key)
        if previous is not None and any(
            abs(old - new) > 1e-8 for old, new in zip(previous, coordinate[:2])
        ):
            raise ValueError(
                f"Road node {key} has inconsistent coordinates; check topology IDs"
            )
        self.nodes.setdefault(key, coordinate)
        return self.nodes[key]

    def add(self, u, v, a, b, road_id):
        """Add one edge without inferring junctions from coordinate proximity."""
        u, v = node_id(u, f"Road {road_id}"), node_id(v, f"Road {road_id}")
        a = self._register_node(u, road_coordinate(a, f"Road {road_id}"))
        b = self._register_node(v, road_coordinate(b, f"Road {road_id}"))
        pair = tuple(sorted((u, v)))
        if u == v or pair in self._pairs:
            return
        projected_a = self.projection.project(*a[:2])
        projected_b = self.projection.project(*b[:2])
        self._pairs.add(pair)
        self.segments.append(Segment(
            f"edge-{len(self.segments)}", u, v, list(a[:2]), list(b[:2]),
            projected_a, projected_b,
            LineString([projected_a, projected_b]).length, str(road_id),
        ))
