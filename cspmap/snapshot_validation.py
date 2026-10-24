"""Check replayed results against saved identities, memberships and route geometry."""

from collections import Counter
from math import isclose


def close_measurement(first, second, absolute_tolerance=1e-6):
    """Allow floating-point noise, retaining the distinction between null and zero."""
    if first is None or second is None:
        return first is second
    return isclose(first, second, rel_tol=1e-9, abs_tol=absolute_tolerance)


def route_key(link):
    """Normalize undirected connection identity without discarding ownership."""
    return (*sorted((link["from_splitter"], link["to_splitter"])), link["partner_id"])


class SnapshotValidator:
    """Fail replay before computing metrics when the persisted baseline has drifted."""

    def __init__(self, saved):
        self.saved = saved

    @staticmethod
    def _require(condition, label):
        if not condition:
            raise ValueError(f"Reconstructed baseline differs from saved {label}")

    def validate(self, result):
        summary = self.saved.summary
        self._require(
            dict(Counter(point.status for point in result.points))
            == summary["matching_status_counts"]
            and len(result.points) == summary["region_splitters"]
            and len(result.patches) == summary["connected_patches"]
            and len(result.connections) == summary["qualifying_connections"],
            "summary",
        )
        self._points(result.points)
        self._require(
            sorted(result.patches, key=lambda row: row["patch_id"])
            == sorted(self.saved.patches, key=lambda row: row["patch_id"]),
            "patch memberships",
        )
        self._connections(result.connections)

    def _points(self, points):
        expected = {
            feature["properties"]["id"]: feature["properties"]
            for feature in self.saved.splitter_features
        }
        self._require(len(expected) == len(points), "splitter identities")
        for point in points:
            row = expected[point.id]
            self._require(
                (point.partner, point.status, point.road_id, point.patch)
                == (row["partner"], row["status"], row["road_id"], row["patch"])
                # Point exports round offsets to four decimal places.
                and close_measurement(point.offset_m, row["offset_m"], 0.00005001),
                f"splitter state ({point.id})",
            )

    def _connections(self, connections):
        features = self.saved.connection_features
        expected = {route_key(row["properties"]): row for row in features}
        actual = {route_key(link): link for link in connections}
        self._require(
            len(expected) == len(features) == len(connections) == len(actual)
            and expected.keys() == actual.keys(),
            "connection identities",
        )
        for key, link in actual.items():
            feature = expected[key]
            props = feature["properties"]
            coordinates = feature["geometry"]["coordinates"]
            if props["from_splitter"] != link["from_splitter"]:
                coordinates = coordinates[::-1]
            self._require(
                close_measurement(link["distance_m"], props["distance_m"])
                and len(coordinates) == len(link["coordinates"])
                and all(
                    len(first) == len(second) == 2
                    and all(isclose(a, b, rel_tol=0, abs_tol=1e-10)
                            for a, b in zip(first, second))
                    for first, second in zip(coordinates, link["coordinates"])
                ),
                f"connection geometry/distance ({key[0]}, {key[1]})",
            )
