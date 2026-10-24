"""Shared road-analysis pipeline used by regional runs and metric sweeps."""

import math
from dataclasses import dataclass, replace

from .graph import augmented_graph
from .matching import RoadMatcher, SegmentIndex
from .models import Connection, Match, Patch, Point, RoadGraph
from .patches import PatchBuilder
from .road_network import Roads
from .routing import ConnectionFinder


def used_road_length(graph: RoadGraph, connections: list[Connection]) -> float:
    """Measure distinct pieces once, including pieces shared by providers."""
    used = {piece for link in connections for piece in link["piece_ids"]}
    return sum(graph.pieces[piece]["length_m"] for piece in used)


@dataclass
class AnalysisResult:
    """One threshold result with explicit inputs and traceable topology."""

    points: list[Point]
    matches: dict[str, Match]
    graph: RoadGraph
    connections: list[Connection]
    patches: list[Patch]
    x_m: float
    snap_m: float
    ambiguity_m: float

    @property
    def membership(self) -> dict[str, str]:
        # Derive from this result, independent of later point.patch mutations.
        return {
            key: patch["patch_id"]
            for patch in self.patches
            for key in patch["splitter_ids"]
        }

    @property
    def link_pairs(self) -> set[tuple[str, str]]:
        return {
            tuple(sorted((link["from_splitter"], link["to_splitter"])))
            for link in self.connections
        }

    @property
    def road_length_m(self) -> float:
        return used_road_length(self.graph, self.connections)

    def sensitivity_row(self) -> dict:
        return {
            "x_m": self.x_m,
            "matched_splitters": len(self.matches),
            "patches": len(self.patches),
            "isolated_patches": sum(patch["isolated"] for patch in self.patches),
            "qualifying_links": len(self.connections),
            "unique_road_length_m": round(self.road_length_m, 3),
        }


class RoadAnalysis:
    """Match and search once, then derive results for multiple thresholds."""

    def __init__(
        self, roads: Roads, snap_m: float, ambiguity_m: float,
        index: SegmentIndex | None = None,
    ):
        if not math.isfinite(snap_m) or snap_m <= 0:
            raise ValueError("Matching tolerance must be finite and positive")
        if not math.isfinite(ambiguity_m) or ambiguity_m < 0:
            raise ValueError("Ambiguity margin must be finite and nonnegative")
        self.roads = roads
        self.snap_m = snap_m
        self.ambiguity_m = ambiguity_m
        self.index = index

    def evaluate(self, points: list[Point], thresholds) -> list[AnalysisResult]:
        if len({point.id for point in points}) != len(points):
            raise ValueError("Splitter record IDs must be unique")
        thresholds = list(thresholds)
        if not thresholds:
            raise ValueError("At least one road threshold is required")
        if any(not math.isfinite(value) or value <= 0 for value in thresholds):
            raise ValueError("Road thresholds must be finite and positive")
        points = [replace(point, flags=list(point.flags)) for point in points]
        matches = RoadMatcher(
            self.roads, self.snap_m, self.ambiguity_m, self.index
        ).match(points)
        graph = augmented_graph(self.roads, matches)
        candidates = ConnectionFinder(graph, max(thresholds)).find(points, matches)
        builder = PatchBuilder()
        results = []
        for threshold in thresholds:
            connections, patches = builder.build(points, matches, candidates, threshold)
            results.append(
                AnalysisResult(
                    [replace(point, flags=list(point.flags)) for point in points],
                    matches, graph, connections, patches,
                    threshold, self.snap_m, self.ambiguity_m,
                )
            )
        return results
