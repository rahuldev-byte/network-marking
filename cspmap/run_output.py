"""Persist a regional result through dedicated output adapters."""

from contextlib import contextmanager
from pathlib import Path
from stat import S_IMODE
from tempfile import TemporaryDirectory

from .map_output import write_map
from .report import write_review
from .serialization import write_json
from .spatial_output import export_spatial
from .tabular_output import review_csv


def prepare_output(path: Path) -> None:
    """Require an empty destination so existing runs are preserved."""
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ValueError(
            f"Output directory {path} is not empty; choose a new directory "
            "to preserve earlier runs"
        )


@contextmanager
def staged_output(path: Path):
    """Publish a complete directory; failed work leaves the destination empty."""
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError("Output directory must not be a symbolic link")
    prepare_output(path)
    with TemporaryDirectory(prefix=f".{path.name}-", dir=path.parent) as temporary:
        staging = Path(temporary)
        yield staging
        # Recheck in case another writer populated the destination during work.
        if path.is_symlink():
            raise ValueError("Output directory must not be a symbolic link")
        prepare_output(path)
        staging.chmod(S_IMODE(path.stat().st_mode))
        staging.rename(path)


class RegionalOutputWriter:
    """Write one complete result snapshot; never recalculate its analysis."""

    def __init__(self, directory: Path):
        self.directory = directory

    def write(self, points, households, config, summary, sensitivity, roads, result):
        connections = result.connections if result else []
        patches = result.patches if result else []
        matches = result.matches if result else {}
        graph = result.graph if result else None
        for name, value in (
            ("summary.json", summary),
            ("patches.json", patches),
            ("sensitivity.json", sensitivity),
        ):
            write_json(self.directory / name, value)
        review_csv(self.directory / "splitter_review.csv", points)
        export_spatial(
            self.directory, points, households, roads, matches, graph, connections
        )
        self._map(points, households, config, roads, result)
        write_review(
            self.directory / "REVIEW.md", config, summary,
            sensitivity, patches, connections, points,
        )

    def _map(self, points, households, config, roads, result):
        osm = config["source"] == "openstreetmap" or bool(
            roads and str(next(iter(roads.nodes))).startswith("osm:")
        )
        write_map(
            self.directory / "map.html", points, households,
            config["bbox_west_south_east_north"],
            "Regional pilot · current infrastructure footprint",
            roads, result.matches if result else {},
            result.graph if result else None,
            result.connections if result else [],
            config["x_m"], config["snap_m"],
            len(result.patches) if result else 0, osm=osm,
        )
