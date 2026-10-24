"""Generated map behavior beyond the provider-selection policy."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import folium

from cspmap.folium_map import FoliumMapRenderer
from cspmap.map_layers import ResultLayers
from cspmap.models import Point
from cspmap.quality import profile
from cspmap.workflows import InputData, ProfileWorkflow


class MapOutputTests(unittest.TestCase):
    def test_profile_extent_includes_households_outside_splitter_extent(self):
        splitters = [Point("s", 28, 77, "owner")]
        households = [Point("h", 29, 78)]
        data = InputData(splitters, households, profile(splitters, households))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            ProfileWorkflow().execute(data, output, True)
            html = (output / "map.html").read_text()
        payload = json.loads(re.search(
            '<script id="map-data" type="application/json">(.*?)</script>',
            html, re.S,
        ).group(1))
        self.assertEqual(payload["bbox"], [77, 28, 78, 29])

    @staticmethod
    def map_data():
        return {
            "bbox": [77, 28, 77.01, 28.01], "title": "Review",
            "road_status": "unavailable", "osm": False,
            "roads": [], "households": [], "connections": [],
            "splitters": [{
                "id": "s", "lat": 28, "lon": 77, "partner": "owner",
                "status": "ambiguous_road_match", "flags": [],
                "offset_m": 1.0, "road_id": "", "patch": "",
            }],
        }

    def test_review_splitter_has_one_marker_and_keeps_its_popup(self):
        html = FoliumMapRenderer().build(self.map_data()).get_root().render()
        self.assertEqual(html.count(".bindPopup("), 1)

    def test_single_network_layer_contains_nodes_and_links_without_duplication(self):
        data = self.map_data()
        original = data["splitters"][0]
        data["splitters"] += [
            {**original, "id": "matched", "status": "matched"},
            {**original, "id": "flagged", "status": "matched", "flags": ["check"]},
            {**original, "id": "unanalysed", "status": "roads_unavailable"},
        ]
        data["connections"] = [{
            "from_splitter": "s", "to_splitter": "matched",
            "partner_id": "owner", "distance_m": 42,
            "coordinates": [[77, 28], [77.001, 28]],
        }]
        data["splitters"][0].update(matched_lon=77.0001, matched_lat=28)
        layers = ResultLayers(data)
        map_view = folium.Map(tiles=None)
        owners, entries = layers.add_to(map_view)
        self.assertEqual(owners, ["owner"])
        self.assertEqual(len(entries), 1)  # One filterable provider network.
        self.assertEqual(entries[0]["point_count"], 4)
        network = layers.groups["network"]
        self.assertEqual(network.layer_name, "Provider network · nodes and links")
        self.assertIn(network.get_name(), map_view._children)
        provider = next(iter(network._children.values()))
        items = [row for child in provider._children.values()
                 for row in child.data["features"]]
        points = [row for row in items if row["geometry"]["type"] == "Point"]
        lines = [row for row in items if row["geometry"]["type"] == "LineString"]
        self.assertEqual({row["properties"]["id"] for row in points},
                         {"s", "matched", "flagged", "unanalysed"})
        self.assertEqual(len(points), 4)
        self.assertEqual(len(lines), 2)  # One route plus one dashed snap offset.
        self.assertEqual(len({entry["layer"] for entry in entries}), 1)

    def test_osm_tiles_and_combined_network_are_visible_by_default(self):
        data = self.map_data()
        data["households"] = [[77, 28]]
        data["splitters"][0].update(matched_lon=77.0001, matched_lat=28)
        data["roads"] = [[[77, 28], [77.001, 28]]]
        map_view = FoliumMapRenderer().build(data)
        layers = {
            child.layer_name: child for child in map_view._children.values()
            if hasattr(child, "layer_name")
        }
        self.assertFalse(layers["Households · owner unknown"].show)
        self.assertTrue(layers["Road graph · OSM geometry"].show)
        self.assertTrue(layers["Provider network · nodes and links"].show)
        tiles = [child for child in map_view._children.values()
                 if isinstance(child, folium.raster_layers.TileLayer)]
        self.assertEqual(len(tiles), 1)
        self.assertTrue(tiles[0].show)
        html = map_view.get_root().render()
        self.assertIn('"collapsed": true', html)
        self.assertIn("About this map", html)
        self.assertIn("Estimated position-to-road snap", html)
        self.assertNotIn("L.Control.MousePosition", html)

    def test_household_only_overview_still_shows_its_data(self):
        data = self.map_data()
        data.update(splitters=[], households=[[77, 28]])
        map_view = FoliumMapRenderer().build(data)
        household_layer = next(
            child for child in map_view._children.values()
            if getattr(child, "layer_name", "") == "Households · owner unknown"
        )
        self.assertTrue(household_layer.show)
