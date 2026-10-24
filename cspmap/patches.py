"""Deterministic connected groups of matched same-owner splitters."""

from collections import defaultdict

from .models import Connection, Match, Patch, Point


class DisjointSet:
    """Union-find with path compression and deterministic smallest roots."""

    def __init__(self, keys):
        self.parents = {key: key for key in keys}

    def root(self, key):
        while self.parents[key] != key:
            self.parents[key] = self.parents[self.parents[key]]
            key = self.parents[key]
        return key

    def union(self, first, second) -> None:
        first, second = self.root(first), self.root(second)
        self.parents[max(first, second)] = min(first, second)

    def groups(self) -> list[list[str]]:
        members = defaultdict(list)
        for key in sorted(self.parents):
            members[self.root(key)].append(key)
        return list(members.values())


class PatchBuilder:
    """Apply a strict route threshold, excluding unresolved source records."""

    def build(
        self, points: list[Point], matches: dict[str, Match],
        connections: list[Connection], x_m: float,
    ) -> tuple[list[Connection], list[Patch]]:
        for point in points:
            point.patch = ""
        eligible = {point.id: point for point in points if point.id in matches}
        groups = DisjointSet(eligible)
        selected = [link for link in connections if link["distance_m"] < x_m]
        for link in selected:
            groups.union(link["from_splitter"], link["to_splitter"])
        patches = [self._patch(keys, eligible) for keys in groups.groups()]
        return selected, patches

    @staticmethod
    def _patch(keys: list[str], eligible: dict[str, Point]) -> Patch:
        owner = eligible[keys[0]].partner
        identifier = f"{owner}:{keys[0]}"
        for key in keys:
            eligible[key].patch = identifier
        return {
            "patch_id": identifier,
            "partner_id": owner,
            "splitter_count": len(keys),
            "splitter_ids": keys,
            "isolated": len(keys) == 1,
        }


def assign_patches(points, matches, connections, x_m):
    """Compatibility entry point for deterministic patch assignment."""
    return PatchBuilder().build(points, matches, connections, x_m)
