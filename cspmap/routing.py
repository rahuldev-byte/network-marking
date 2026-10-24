"""Bounded Dijkstra searches for successive same-owner splitter connections."""

import heapq
import math
from collections import defaultdict

from .models import Connection, Point, RoadGraph


def reconstruct_route(start, end, parents, coordinates) -> tuple[list, list]:
    """Recover a discovered route and its exact augmented road pieces."""
    route = []
    cursor = end
    while cursor != start:
        previous, piece = parents[cursor]
        route.append((previous, cursor, piece))
        cursor = previous
    route.reverse()
    coords = [coordinates[start]] + [coordinates[node] for _, node, _ in route]
    if len(coords) == 1:
        coords.append(coords[0])
    return coords, [piece for _, _, piece in route]


class BoundedRouteSearch:
    """Search one source, stopping branches at the next same-owner splitter."""

    def __init__(self, graph: RoadGraph, occupants: dict, max_distance: float):
        self.graph = graph
        self.occupants = occupants
        self.max_distance = max_distance

    def connections_from(self, point: Point, start: str):
        queue = [(0.0, start)]
        distances = {start: 0.0}
        parents = {}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node] or distance >= self.max_distance:
                continue
            targets = [
                target
                for target in self.occupants[node].get(point.partner, ())
                if target != point.id
            ]
            if targets:
                yield from self._connections(
                    point, start, node, distance, targets, parents
                )
                if node != start:
                    continue
            self._expand(node, distance, queue, distances, parents)

    def _connections(self, point, start, node, distance, targets, parents):
        coords, pieces = reconstruct_route(
            start, node, parents, self.graph.coordinates
        )
        for target in targets:
            yield {
                "from_splitter": point.id,
                "to_splitter": target,
                "partner_id": point.partner,
                "distance_m": distance,
                "coordinates": coords,
                "piece_ids": pieces,
            }

    def _expand(self, node, distance, queue, distances, parents) -> None:
        for neighbour, length, piece in self.graph.adjacency.get(node, ()):
            candidate = distance + length
            if candidate < self.max_distance and candidate < distances.get(
                neighbour, math.inf
            ):
                distances[neighbour] = candidate
                parents[neighbour] = (node, piece)
                heapq.heappush(queue, (candidate, neighbour))


class ConnectionFinder:
    """Index owners at anchors and deduplicate undirected discovered pairs."""

    def __init__(self, graph: RoadGraph, max_distance: float):
        self.graph = RoadGraph(*graph)
        self.max_distance = max_distance

    def find(self, points, matches) -> list[Connection]:
        occupants = defaultdict(lambda: defaultdict(list))
        for point in points:
            if point.id in matches:
                occupants[matches[point.id].anchor][point.partner].append(point.id)
        search = BoundedRouteSearch(self.graph, occupants, self.max_distance)
        connections = []
        seen = set()
        for point in points:
            if point.id not in matches:
                continue
            for connection in search.connections_from(point, matches[point.id].anchor):
                pair = tuple(
                    sorted((connection["from_splitter"], connection["to_splitter"]))
                )
                if pair not in seen:
                    seen.add(pair)
                    connections.append(connection)
        return connections


def qualifying_connections(points, matches, graph, max_x_m):
    """Find successive links; other owners never block physical traversal."""
    return ConnectionFinder(graph, max_x_m).find(points, matches)
