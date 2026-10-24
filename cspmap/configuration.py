"""Typed run settings and the persisted configuration contract."""

from dataclasses import dataclass
from pathlib import Path

from .regions import auto_pilot, validate_bbox

DIRECTION_POLICY = (
    "bidirectional physical road connectivity; traffic one-way restrictions "
    "do not constrain cable routes"
)


@dataclass(frozen=True)
class RunSettings:
    """Road/region options independent of argparse and output formatting."""

    output: Path
    automatic: bool
    bbox: tuple | None
    roads: Path | None
    download: bool
    points_only: bool
    x_m: float | None
    snap_m: float
    ambiguity_m: float
    compare_x: tuple[float, ...]

    @classmethod
    def from_arguments(cls, args):
        return cls(
            args.output, args.auto_pilot,
            tuple(args.bbox) if args.bbox is not None else None, args.roads,
            args.download_osm, args.points_only, args.x_m,
            args.snap_m, args.ambiguity_m, tuple(args.compare_x),
        )

    @property
    def thresholds(self) -> list[float]:
        return sorted({self.x_m, *self.compare_x})

    def select_bbox(self, points) -> tuple:
        return validate_bbox(auto_pilot(points) if self.automatic else self.bbox)

    def configuration(self, bbox, splitter_count, household_count) -> dict:
        source = str(self.roads)
        if self.points_only:
            source = "points_only"
        elif self.download:
            source = "openstreetmap"
        return {
            'bbox_west_south_east_north': bbox,
            'selection': (
                'automatic densest cell' if self.automatic else 'explicit bbox'
            ),
            'x_m': self.x_m,
            'snap_m': self.snap_m,
            'ambiguity_m': self.ambiguity_m,
            'compare_x_m': list(self.compare_x),
            'parameter_validation': 'exploratory; local review required',
            'source': source,
            'ownership': 'recorded partner_id retained',
            'household_ownership': 'unassigned',
            'region_splitters': splitter_count,
            'region_households': household_count,
        }
