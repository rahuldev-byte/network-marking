"""Recorded metric CRS transformations for GeoPandas-based regional analysis."""

import geopandas as gpd
from pyproj import CRS, Geod, Transformer

from .geo import LocalMetres, coordinate

WGS84 = CRS.from_epsg(4326)


class MetricProjection:
    """A local azimuthal-equidistant CRS with a bounded geographic extent."""

    max_radius_m = 25_000

    def __init__(self, lon, lat, crs=None):
        self.lat, self.lon = coordinate(lat, lon)
        if self.lon is None:
            raise ValueError("Invalid projection origin")
        self.crs = CRS.from_user_input(crs) if crs else CRS.from_proj4(
            f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
        )
        if not self.crs.is_projected or any(
            axis.unit_conversion_factor != 1 for axis in self.crs.axis_info
        ):
            raise ValueError("Road analysis requires a projected CRS in metres")
        self._geod = Geod(ellps="WGS84")
        self._forward = Transformer.from_crs(WGS84, self.crs, always_xy=True)
        self._inverse = Transformer.from_crs(self.crs, WGS84, always_xy=True)

    def _validate_radius(self, lon, lat):
        latitude, longitude = coordinate(lat, lon)
        if latitude is None:
            raise ValueError("Invalid geographic coordinate")
        _, _, distance = self._geod.inv(self.lon, self.lat, longitude, latitude)
        if distance > self.max_radius_m:
            raise ValueError(
                "Road analysis is limited to 25 km from the pilot centre; "
                "choose a smaller region/road file"
            )

    def project(self, lon, lat):
        """Transform one validated longitude/latitude pair to metric coordinates."""
        self._validate_radius(lon, lat)
        return self._forward.transform(lon, lat)

    def unproject(self, east, north):
        """Transform an accepted metric road anchor back to WGS84 for export."""
        return list(self._inverse.transform(east, north))

    def project_frame(self, frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Validate the geographic extent, then transform a declared source CRS."""
        if frame.crs is None:
            raise ValueError("Input geometry must declare its source CRS")
        geographic = frame.to_crs(WGS84)
        for row in geographic.geometry.get_coordinates().itertuples(index=False):
            self._validate_radius(row.x, row.y)
        return geographic.to_crs(self.crs)

    @property
    def metadata(self):
        return {
            "method": "WGS84 local azimuthal equidistant via GeoPandas/PROJ",
            "origin_lon_lat": [self.lon, self.lat],
            "crs": self.crs.to_wkt(),
            "max_radius_m": self.max_radius_m,
            "note": (
                "Local surface distances; no altitude/cable slack allowance. "
                "Run separate regional pilots."
            ),
        }


def projection_from_metadata(metadata):
    """Reconstruct the recorded CRS, including earlier ENU result snapshots."""
    lon, lat = metadata["origin_lon_lat"]
    if "crs" in metadata:
        return MetricProjection(lon, lat, metadata["crs"])
    if metadata.get("method") == LocalMetres(lon, lat).metadata["method"]:
        return LocalMetres(lon, lat)
    raise ValueError("Saved run contains an unsupported projection method")
