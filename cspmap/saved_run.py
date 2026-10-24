"""Read completed result snapshots for reproducible metrics evaluation."""

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Point
from .projections import projection_from_metadata
from .road_network import Roads


@dataclass
class SavedRun:
    """Persisted settings and source features, independent of later sweeps."""

    directory: Path
    config: dict
    summary: dict
    quality: dict
    splitter_features: list[dict]
    roads: Roads
    patches: list[dict]
    connection_features: list[dict]

    @classmethod
    def read(cls, directory: Path):
        directory = Path(directory)

        def read(name):
            return json.loads((directory / name).read_text(encoding="utf-8"))

        config = read("config.json")
        summary = read("summary.json")
        if summary["road_status"] != "available":
            raise ValueError("Metrics require a completed run with roads")
        projection = projection_from_metadata(config["projection"])
        roads = Roads(projection)
        for feature in read("roads.geojson")["features"]:
            props = feature["properties"]
            coords = feature["geometry"]["coordinates"]
            roads.add(
                props["from_node"], props["to_node"],
                coords[0], coords[1], props["road_id"],
            )
        return cls(
            directory, config, summary, read("data_quality.json"),
            read("splitters.geojson")["features"], roads,
            read("patches.json"), read("connections.geojson")["features"],
        )

    def fresh_points(self) -> list[Point]:
        """Give each evaluation fresh mutable state, including its own flags."""
        return [
            Point(
                feature["properties"]["id"],
                feature["geometry"]["coordinates"][1],
                feature["geometry"]["coordinates"][0],
                feature["properties"]["partner"],
                list(feature["properties"]["flags"]),
            )
            for feature in self.splitter_features
        ]
