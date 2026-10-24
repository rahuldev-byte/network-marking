"""GeoPandas integration, spatial-index completeness, CRS, and export contracts."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString

from cspmap.csv_input import SCHEMAS, CsvPointReader
from cspmap.geo import LocalMetres
from cspmap.geospatial import feature_frame, geojson_document, road_frame
from cspmap.matching import RoadMatcher, SegmentIndex
from cspmap.models import Point
from cspmap.projections import MetricProjection, projection_from_metadata
from cspmap.road_loaders import load_roads
from cspmap.road_network import Roads


class GeoPandasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_csv_has_declared_crs_null_geometry_and_string_ownership(self):
        path = self.root / "points.csv"
        path.write_text(
            "partner_id,latitude,longitude,mobile\n"
            "000123,28,77,PRIVATE_VALUE\nNA,NaN,77,PRIVATE_VALUE\n"
            "owner,91,77,PRIVATE_VALUE\n"
        )
        reader = CsvPointReader(SCHEMAS["splitter"])
        frame = reader.read_frame(path)
        self.assertIsInstance(frame, gpd.GeoDataFrame)
        self.assertEqual(frame.crs.to_epsg(), 4326)
        self.assertEqual(frame.geometry.isna().tolist(), [False, True, True])
        self.assertNotIn("mobile", frame.columns)
        points = reader.read(path)
        self.assertEqual([p.partner for p in points], ["000123", "NA", "owner"])
        self.assertEqual([p.valid for p in points], [True, False, False])
        self.assertEqual(
            [p.id for p in points], ["s-0000001", "s-0000002", "s-0000003"]
        )

    def test_metric_crs_roundtrip_and_saved_projection_reconstruction(self):
        projection = MetricProjection(77, 28)
        frame = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([77.001], [28.001]), crs=4326
        )
        metric = projection.project_frame(frame)
        self.assertTrue(metric.crs.is_projected)
        self.assertEqual(metric.crs.axis_info[0].unit_name, "metre")
        expected = projection.project(77.001, 28.001)
        self.assertAlmostEqual(metric.geometry.x.iloc[0], expected[0], places=8)
        self.assertAlmostEqual(metric.geometry.y.iloc[0], expected[1], places=8)
        restored = projection_from_metadata(projection.metadata)
        self.assertEqual(restored.crs, projection.crs)
        lon, lat = restored.unproject(*expected)
        self.assertAlmostEqual(lon, 77.001, places=10)
        self.assertAlmostEqual(lat, 28.001, places=10)
        with self.assertRaisesRegex(ValueError, "25 km"):
            projection.project(78, 28)

    def test_previous_enu_metadata_is_replayed_without_changing_its_projection(self):
        original = LocalMetres(77, 28)
        restored = projection_from_metadata(original.metadata)
        self.assertIsInstance(restored, LocalMetres)
        self.assertEqual(
            restored.project(77.001, 28.001), original.project(77.001, 28.001)
        )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            projection_from_metadata({"origin_lon_lat": [77, 28], "method": "unknown"})

    def test_index_finds_middle_of_long_segment_and_keeps_ambiguity(self):
        roads = Roads(MetricProjection(77, 28))
        roads.add("a", "b", [77, 28], [77.02, 28], "long-road")
        matcher = RoadMatcher(roads, 10, 2)
        self.assertIsInstance(matcher.index.frame, gpd.GeoDataFrame)
        point = Point("p", 28, 77.01, "owner")
        matches = matcher.match([point])
        self.assertIn("p", matches)
        self.assertAlmostEqual(matches["p"].t, 0.5, places=5)
        roads.add("c", "d", [77, 28.00001], [77.02, 28.00001], "parallel")
        self.assertFalse(RoadMatcher(roads, 10, 2).match([point]))
        self.assertEqual(point.status, "ambiguous_road_match")

    def test_projected_road_frame_lengths_agree_with_graph_edges(self):
        roads = Roads(MetricProjection(77, 28))
        roads.add("a", "b", [77, 28], [77.001, 28.001], "road")
        frame = road_frame(roads, projected=True)
        self.assertAlmostEqual(frame.length.iloc[0], roads.segments[0].length, places=8)
        self.assertEqual(frame.segment_index.tolist(), [0])

    def test_shared_spatial_index_rejects_a_changed_road_network(self):
        roads = Roads(MetricProjection(77, 28))
        roads.add("a", "b", [77, 28], [77.001, 28], "first")
        index = SegmentIndex(roads)
        roads.add("b", "c", [77.001, 28], [77.002, 28], "second")
        with self.assertRaisesRegex(ValueError, "current road network"):
            RoadMatcher(roads, 10, 2, index)

    def test_company_geopackage_crs_is_transformed_and_topology_is_preserved(self):
        path = self.root / "roads.gpkg"
        frame = gpd.GeoDataFrame(
            {"from_node": ["a"], "to_node": ["b"], "road_id": ["r"]},
            geometry=[LineString([(77, 28), (77.001, 28)])], crs=4326,
        ).to_crs(3857)
        frame.to_file(path, driver="GPKG")
        roads = load_roads(path, MetricProjection(77, 28))
        self.assertEqual(len(roads.segments), 1)
        self.assertEqual(
            (roads.segments[0].u, roads.segments[0].v), ("company:a", "company:b")
        )
        self.assertAlmostEqual(roads.segments[0].b[0], 77.001, places=8)

    def test_company_vector_data_requires_a_declared_crs(self):
        frame = gpd.GeoDataFrame(geometry=[LineString([(77, 28), (77.001, 28)])])
        with patch("cspmap.road_loaders.gpd.read_file", return_value=frame):
            with self.assertRaisesRegex(ValueError, "coordinate system"):
                load_roads(self.root / "roads.gpkg", MetricProjection(77, 28))

    def test_geojson_rejects_projected_or_malformed_crs_declarations(self):
        path = self.root / "roads.geojson"
        document = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"from_node": "a", "to_node": "b"},
                "geometry": {
                    "type": "LineString", "coordinates": [[77, 28], [77.001, 28]]
                },
            }],
        }
        for declaration in (
            {"type": "name", "properties": {"name": "EPSG:3857"}},
            {"type": "name", "properties": {}}, "EPSG:3857",
            {"type": "name", "properties": {"name": "not-a-crs"}},
        ):
            with self.subTest(declaration=declaration):
                document["crs"] = declaration
                path.write_text(json.dumps(document))
                with self.assertRaisesRegex(ValueError, "GeoJSON"):
                    load_roads(path, MetricProjection(77, 28))
        for name in ("EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84"):
            document["crs"] = {"type": "name", "properties": {"name": name}}
            path.write_text(json.dumps(document))
            roads = load_roads(path, MetricProjection(77, 28))
            self.assertEqual(len(roads.segments), 1)

    def test_geojson_export_keeps_empty_layers_and_ownership_flags(self):
        self.assertEqual(geojson_document(feature_frame([])), {
            "type": "FeatureCollection", "features": []
        })
        features = [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [77, 28]},
            "properties": {"id": "s", "flags": ["review"], "partner": "000123"},
        }]
        document = geojson_document(feature_frame(features))
        self.assertEqual(document["features"], features)


if __name__ == "__main__":
    unittest.main()
