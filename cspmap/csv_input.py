"""Read supported CSV schemas without retaining household phone numbers."""

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .models import Point
from .projections import WGS84

DEFAULT_SPLITTERS = "splitter_points.csv"
DEFAULT_HOUSEHOLDS = "active_base_mobile_lat_long_time_added_20261022.csv"


@dataclass(frozen=True)
class PointSchema:
    """Source column names and identity prefix for one supported dataset."""

    latitude: str
    longitude: str
    prefix: str
    owner: str | None = None

    @property
    def required_columns(self) -> set[str]:
        columns = {self.latitude, self.longitude}
        if self.owner:
            columns.add(self.owner)
        return columns


SCHEMAS = {
    "splitter": PointSchema("latitude", "longitude", "s", "partner_id"),
    "household": PointSchema("lat", "long", "h"),
}


class CsvPointReader:
    """Adapt one explicit source schema into validated Point records."""

    def __init__(self, schema: PointSchema):
        self.schema = schema

    def read(self, path: Path) -> list[Point]:
        frame = self.read_frame(path)
        records = (
            dict(zip(frame.columns, values))
            for values in frame.itertuples(index=False, name=None)
        )
        return [self._point(row, index) for index, row in enumerate(records, 1)]

    def read_frame(self, path: Path) -> gpd.GeoDataFrame:
        """Read contracted columns, retaining invalid locations as null geometry."""
        try:
            columns = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
            self._validate_columns(path, columns)
            table = pd.read_csv(
                path, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                usecols=lambda name: name in self.schema.required_columns,
            )
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            raise ValueError(f"{path}: invalid or empty CSV: {exc}") from exc
        if table.empty:
            raise ValueError(f"{path}: no data records")
        latitude = pd.to_numeric(table[self.schema.latitude], errors="coerce")
        longitude = pd.to_numeric(table[self.schema.longitude], errors="coerce")
        valid = latitude.between(-90, 90) & longitude.between(-180, 180)
        geometry = gpd.GeoSeries(index=table.index, crs=WGS84)
        geometry.loc[valid] = gpd.points_from_xy(
            longitude.loc[valid], latitude.loc[valid], crs=WGS84
        )
        return gpd.GeoDataFrame(table, geometry=geometry, crs=WGS84)

    def _validate_columns(self, path, columns) -> None:
        missing = self.schema.required_columns - set(columns)
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")

    def _point(self, row: dict, index: int) -> Point:
        geometry = row["geometry"]
        latitude = geometry.y if geometry is not None else None
        longitude = geometry.x if geometry is not None else None
        owner = (row.get(self.schema.owner) or "").strip() if self.schema.owner else ""
        point = Point(
            f"{self.schema.prefix}-{index:07d}", latitude, longitude, owner
        )
        if not point.valid:
            point.flags.append("missing_or_invalid_coordinates")
            point.status = "invalid_coordinates"
        elif latitude == 0 or longitude == 0:
            point.flags.append("zero_coordinate_review")
        if self.schema.owner and not owner:
            point.flags.append("missing_partner_id")
        return point


def read_points(path, kind: str) -> list[Point]:
    """Read a supported dataset using its explicit source contract."""
    try:
        schema = SCHEMAS[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown point dataset kind: {kind}") from exc
    return CsvPointReader(schema).read(path)
