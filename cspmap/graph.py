"""Split original road edges at accepted anchors for partial-segment routing."""

from collections import defaultdict

from .geo import interpolate
from .models import RoadGraph


def augmented_graph(roads, matches) -> RoadGraph:
    """Build bidirectional pieces while retaining original junction identities."""
    on_edge = defaultdict(dict)
    for match in matches.values():
        on_edge[match.segment][match.anchor] = match.t
    adjacency = defaultdict(list)
    coordinates = dict(roads.nodes)
    pieces = {}
    for index, segment in enumerate(roads.segments):
        positions = {segment.u: 0.0, segment.v: 1.0, **on_edge[index]}
        ordered = sorted(positions.items(), key=lambda item: (item[1], item[0]))
        for node, fraction in ordered:
            if hasattr(roads.projection, "unproject"):
                metric = interpolate(segment.xy_a, segment.xy_b, fraction)
                coordinates[node] = roads.projection.unproject(*metric)
            else:
                coordinates[node] = interpolate(segment.a, segment.b, fraction)
        for part, ((start, first), (end, last)) in enumerate(zip(ordered, ordered[1:])):
            key = f"{segment.id}:{part}"
            length = (last - first) * segment.length
            adjacency[start].append((end, length, key))
            adjacency[end].append((start, length, key))
            pieces[key] = {
                "u": start, "v": end, "length_m": length, "road_id": segment.road_id
            }
    return RoadGraph(adjacency, coordinates, pieces)
