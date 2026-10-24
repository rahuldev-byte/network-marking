"""Application workflows coordinating inputs, analysis, and output adapters."""

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain

from .analysis import RoadAnalysis
from .configuration import DIRECTION_POLICY, RunSettings
from .csv_input import read_points
from .map_output import write_map
from .models import Point
from .projections import MetricProjection
from .quality import profile
from .regions import auto_pilot, bounds, inside
from .road_download import download_osm
from .road_loaders import load_roads
from .run_output import RegionalOutputWriter, prepare_output
from .serialization import write_json
from .summary import regional_summary
from .tabular_output import review_csv


@dataclass
class InputData:
    """Loaded source points and their full-source quality report."""

    splitters: list[Point]
    households: list[Point]
    quality: dict

    @classmethod
    def read(cls, splitters_path, households_path):
        splitters = read_points(splitters_path, "splitter")
        households = read_points(households_path, "household")
        quality = profile(splitters, households)
        quality["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        quality["inputs"] = {
            "splitters": str(splitters_path), "households": str(households_path)
        }
        return cls(splitters, households, quality)


class ProfileWorkflow:
    """Export source-quality evidence even when no pilot can be selected."""

    def execute(self, data: InputData, output, include_map: bool) -> dict:
        write_json(output / "pilot_suggestion.json", self._suggestion(data.splitters))
        review_csv(
            output / "splitter_review.csv",
            [point for point in data.splitters if point.flags],
        )
        write_json(
            output / "household_review.json",
            [
                {"record_id": point.id, "latitude": point.lat,
                 "longitude": point.lon, "flags": point.flags}
                for point in data.households if point.flags
            ],
        )
        if include_map:
            bbox = (
                bounds(chain(data.splitters, data.households))
                or [-180, -85, 180, 85]
            )
            write_map(
                output / "map.html", data.splitters, data.households, bbox,
                "All supplied points · household ownership unassigned",
            )
        return {
            "output": str(output), "splitter_records": len(data.splitters),
            "household_records": len(data.households),
            "distinct_csps": data.quality["splitters"]["distinct_csps"],
            "road_status": "unavailable",
        }

    @staticmethod
    def _suggestion(points) -> dict:
        suggestion = {"selection": "densest eligible 0.02-degree splitter cell"}
        try:
            suggestion["bbox_west_south_east_north"] = auto_pilot(points)
        except ValueError as exc:
            suggestion.update(bbox_west_south_east_north=None, reason=str(exc))
        return suggestion


class RegionalWorkflow:
    """Run one selected region and persist its chosen threshold result."""

    def execute(self, data: InputData, settings: RunSettings) -> dict:
        bbox = settings.select_bbox(data.splitters)
        points = [point for point in data.splitters if inside(point, bbox)]
        households = [point for point in data.households if inside(point, bbox)]
        self._validate_size(points, settings.points_only)
        config = settings.configuration(bbox, len(points), len(households))
        write_json(settings.output / "config.json", config)
        roads, result, sensitivity = None, None, []
        if not settings.points_only:
            roads = self._roads(settings, bbox, config)
            data.quality["roads_available_in_inputs"] = True
            write_json(settings.output / "data_quality.json", data.quality)
            analysis = RoadAnalysis(roads, settings.snap_m, settings.ambiguity_m)
            results = analysis.evaluate(points, settings.thresholds)
            result = next(row for row in results if row.x_m == settings.x_m)
            points = result.points
            sensitivity = [
                row.sensitivity_row() for row in sorted(results, key=lambda r: r.x_m)
            ]
        summary = regional_summary(points, households, result)
        RegionalOutputWriter(settings.output).write(
            points, households, config, summary, sensitivity, roads, result
        )
        return {
            "output": str(settings.output),
            **{key: value for key, value in summary.items()
               if key not in {"by_partner", "limitations"}},
        }

    @staticmethod
    def _validate_size(points, points_only: bool) -> None:
        if not points:
            raise ValueError("No valid splitters in the selected region")
        if len(points) > 10_000 and not points_only:
            raise ValueError(
                "Road analysis pilots are limited to 10,000 splitters; "
                "choose a smaller bbox"
            )

    @staticmethod
    def _roads(settings, bbox, config):
        projection = MetricProjection((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        for lon in (bbox[0], bbox[2]):
            for lat in (bbox[1], bbox[3]):
                projection.project(lon, lat)
        path = settings.roads
        if settings.download:
            path = settings.output / "osm_roads.json"
            padding = max(settings.thresholds) + settings.snap_m + 100
            download_osm(bbox, padding, path)
        roads = load_roads(path, projection)
        config.update(
            projection=projection.metadata, road_file=str(path),
            direction_policy=DIRECTION_POLICY,
        )
        write_json(settings.output / "config.json", config)
        return roads


class MappingApplication:
    """Dispatch commands after loading and profiling the supplied sources."""

    def execute(self, args) -> dict:
        data = InputData.read(args.splitters, args.households)
        prepare_output(args.output)
        write_json(args.output / "data_quality.json", data.quality)
        if args.command == "profile":
            return ProfileWorkflow().execute(data, args.output, args.map)
        return RegionalWorkflow().execute(data, RunSettings.from_arguments(args))
