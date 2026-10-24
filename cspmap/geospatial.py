"""GeoDataFrame construction and geographic serialization at GIS boundaries."""

import json

import geopandas as gpd
from shapely.geometry import LineString

from .projections import WGS84


def road_frame(roads, projected=False) -> gpd.GeoDataFrame:
    """Keep explicit segment identities alongside CRS-aware road geometries."""
    frame = gpd.GeoDataFrame(
        {"segment_index": list(range(len(roads.segments)))},
        geometry=[LineString([segment.a, segment.b]) for segment in roads.segments],
        crs=WGS84,
    )
    if not projected:
        return frame
    if hasattr(roads.projection, "project_frame"):
        return roads.projection.project_frame(frame)
    # Earlier ENU snapshots have metric engineering coordinates without a CRS.
    return gpd.GeoDataFrame(
        frame.drop(columns="geometry"),
        geometry=[
            LineString([segment.xy_a, segment.xy_b]) for segment in roads.segments
        ],
    )


def feature_frame(features) -> gpd.GeoDataFrame:
    """Normalize exported WGS84 features, including an empty spatial layer."""
    if features:
        return gpd.GeoDataFrame.from_features(features, crs=WGS84)
    return gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=WGS84))


def geojson_document(frame: gpd.GeoDataFrame) -> dict:
    """Serialize via GeoPandas while retaining the existing export schema."""
    return json.loads(frame.to_json(
        na="null", drop_id=True, to_wgs84=True, allow_nan=False, ensure_ascii=False
    ))
