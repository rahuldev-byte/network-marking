"""Topology and geometry diagnostics for an already-computed road result."""

import math
from collections import defaultdict
from statistics import mean

from .statistics import distribution, percent


def component_sizes(adjacency) -> list[int]:
    """Count graph components without changing the supplied adjacency."""
    unseen = set(adjacency)
    components = []
    while unseen:
        stack = [unseen.pop()]
        count = 0
        while stack:
            node = stack.pop()
            count += 1
            for neighbour in adjacency[node] & unseen:
                unseen.remove(neighbour)
                stack.append(neighbour)
        components.append(count)
    return components


def road_statistics(roads, used_length) -> dict:
    """Describe the buffered source graph, including disconnected roads."""
    adjacency = defaultdict(set)
    for segment in roads.segments:
        adjacency[segment.u].add(segment.v)
        adjacency[segment.v].add(segment.u)
    components = component_sizes(adjacency)
    total_length = sum(segment.length for segment in roads.segments)
    return {
        'nodes': len(adjacency),
        'segments': len(roads.segments),
        'connected_components': len(components),
        'largest_component_nodes': max(components, default=0),
        'dead_end_nodes_degree_1': sum(
            (len(nodes) == 1 for nodes in adjacency.values()),
        ),
        'junction_nodes_degree_at_least_3': sum(
            (len(nodes) >= 3 for nodes in adjacency.values()),
        ),
        'total_road_length_m': total_length,
        'used_road_length_pct': percent(used_length, total_length),
    }


def geometry_consistency(result, projection) -> dict:
    """Compare two calculations on the same geometry, without implying truth."""
    errors = []
    for link in result.connections:
        coords = link["coordinates"]
        length = sum(
            math.dist(projection.project(*a), projection.project(*b))
            for a, b in zip(coords, coords[1:])
        )
        errors.append(length - link["distance_m"])
    return {
        'route_length_absolute_difference_m': distribution((abs(e) for e in errors)),
        'route_length_rmse_m': (
            math.sqrt(mean(error ** 2 for error in errors)) if errors else None
        ),
        'meaning': (
            'Agreement between two calculations using the same road geometry, '
            'not surveyed distance accuracy.'
        ),
    }
