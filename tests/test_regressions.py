"""Regression cases found during the code review."""
import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from cspmap.__main__ import main
from cspmap.data import Point, auto_pilot, profile
from cspmap.geo import LocalMetres
from cspmap.output import review_csv
from cspmap.report import write_review
from cspmap.roads import (
    Roads,
    assign_patches,
    augmented_graph,
    load_roads,
    match_points,
    qualifying_connections,
)


class ReviewRegressions(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def road_file(self, data):
        path = self.root / 'roads.json'
        path.write_text(json.dumps(data))
        return path

    def test_auto_pilot_ignores_zero_coordinate_records(self):
        bad = [Point(f'bad-{i}', 0, 0, 'owner') for i in range(3)]
        good = Point('good', 28.67, 77.27, 'owner')
        self.assertEqual(auto_pilot(bad + [good]), (77.26, 28.66, 77.28, 28.68))

    def test_auto_pilot_accepts_eastern_longitude_boundary(self):
        west, south, east, north = auto_pilot([Point('s', 28.67, 180, 'owner')])
        self.assertLess(west, east)
        self.assertLessEqual(east, 180)

    def test_profiling_is_idempotent_and_unknown_owner_is_not_a_second_csp(self):
        points = [Point('a', 28, 77, 'one'), Point('b', 28, 77, 'two')]
        households = [Point('h', 30, 80)]
        first = profile(points, households)
        self.assertEqual(profile(points, households), first)
        blank = Point('unknown', 28, 77)
        self.assertEqual(
            profile([points[0], blank], [])['splitters']['coordinates_shared_by_csps'],
            0,
        )
        self.assertNotIn('coordinate_shared_by_csps', points[0].flags)

    def test_rematching_clears_old_match_and_patch(self):
        roads = Roads(LocalMetres(77, 28))
        roads.add('a', 'b', [77, 28], [77.001, 28], 'road')
        point = Point('s', 28.00001, 77.0005, 'owner')
        matches = match_points([point], roads, 30)
        assign_patches([point], matches, [], 100)
        self.assertTrue(point.patch)
        self.assertFalse(match_points([point], roads, 0.1))
        self.assertEqual(point.status, 'no_road_within_tolerance')
        self.assertIsNone(point.offset_m)
        self.assertEqual((point.road_id, point.patch), ('', ''))

    def test_company_shape_vertices_cannot_collide_with_supplied_node_ids(self):
        roads = load_roads(
            self.road_file(
                {
                    'type': 'FeatureCollection',
                    'features': [
                        {
                            'properties': {'from_node': 'a', 'to_node': 'b'},
                            'geometry': {
                                'type': 'LineString',
                                'coordinates': [[77, 28], [77.001, 28], [77.002, 28]],
                            },
                        },
                        {
                            'properties': {'from_node': 'shape:0:1', 'to_node': 'c'},
                            'geometry': {
                                'type': 'LineString',
                                'coordinates': [[77.001, 28], [77.001, 28.001]],
                            },
                        },
                    ],
                },
            ),
            LocalMetres(77, 28),
        )
        points = [Point('s1', 28, 77, 'owner'), Point('s2', 28.001, 77.001, 'owner')]
        matches = match_points(points, roads, 1)
        graph = augmented_graph(roads, matches)
        links = qualifying_connections(points, matches, graph, 300)
        self.assertFalse(
            links, 'A private shape vertex must not establish a company junction'
        )

    def test_osm_areas_are_not_loaded_as_linear_roads(self):
        data = {
            'elements': [
                {'type': 'node', 'id': i, 'lon': lon, 'lat': lat}
                 for i, lon, lat in [(1, 77, 28), (2, 77.001, 28), (3, 77.001, 28.001)]
            ] + [
                {
                    'type': 'way',
                    'id': 10,
                    'nodes': [1, 2],
                    'tags': {'highway': 'residential'},
                },
                {
                    'type': 'way',
                    'id': 11,
                    'nodes': [2, 3, 2],
                    'tags': {'highway': 'pedestrian', 'area': 'yes'},
                },
            ],
        }
        roads = load_roads(self.road_file(data), LocalMetres(77, 28))
        self.assertEqual({segment.road_id for segment in roads.segments}, {'10'})

    def test_incomplete_highway_way_is_not_silently_ignored(self):
        data = {
            'elements': [
                {'type': 'node', 'id': 1, 'lon': 77, 'lat': 28},
                {'type': 'node', 'id': 2, 'lon': 77.001, 'lat': 28},
                {
                    'type': 'way',
                    'id': 10,
                    'nodes': [1, 2],
                    'tags': {'highway': 'residential'},
                },
                {'type': 'way', 'id': 11, 'tags': {'highway': 'residential'}},
            ],
        }
        with self.assertRaisesRegex(ValueError, '11.*nodes'):
            load_roads(self.road_file(data), LocalMetres(77, 28))

    def test_malformed_road_structures_raise_actionable_validation_errors(self):
        for data in (
            [],
            {'elements': [None]},
            {'type': 'FeatureCollection', 'features': [None]},
            {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'geometry': {
                            'type': 'LineString', 'coordinates': [[77], [77, 28]]
                        },
                        'properties': {'from_node': 'a', 'to_node': 'b'},
                    },
                ],
            },
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                load_roads(self.road_file(data), LocalMetres(77, 28))

    def test_review_csv_neutralizes_formulas_in_all_text_columns(self):
        point = Point('s', 28, 77, '=owner', road_id='\t=road', patch='=owner:s')
        path = self.root / 'review.csv'
        review_csv(path, [point])
        with path.open() as handle:
            row = next(csv.DictReader(handle))
        for column in ('partner_id', 'road_id', 'patch_id'):
            self.assertTrue(row[column].startswith("'"), (column, row[column]))
        self.assertEqual(row['latitude'], '28')

    def test_profile_completes_when_no_pilot_can_be_selected(self):
        splitters, households = (self.root / 's.csv', self.root / 'h.csv')
        splitters.write_text('partner_id,latitude,longitude\nowner,,\n')
        households.write_text('lat,long\n28,77\n')
        output = self.root / 'profile'
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = main(
                [
                    'profile',
                    '--splitters',
                    str(splitters),
                    '--households',
                    str(households),
                    '--map',
                    '--output',
                    str(output),
                ],
            )
        self.assertEqual(result, 0)
        suggestion = json.loads((output / 'pilot_suggestion.json').read_text())
        self.assertIsNone(suggestion['bbox_west_south_east_north'])
        self.assertTrue(suggestion['reason'])
        html = (output / 'map.html').read_text()
        payload = json.loads(
            re.search(
                '<script id="map-data" type="application/json">(.*?)</script>',
                html,
                re.S,
            ).group(
                1,
            ),
        )
        self.assertEqual(payload['bbox'], [77, 28, 77, 28])
        self.assertEqual(payload['splitters'], [])

    def test_review_report_escapes_html_in_owner_ids(self):
        owner = '<img src="example" onerror="alert(1)">'
        path = self.root / 'REVIEW.md'
        write_review(
            path,
            {'bbox_west_south_east_north': [77, 28, 77.01, 28.01]},
            {
                'region_splitters': 1,
                'region_households': 0,
                'distinct_csps': 1,
                'road_status': 'unavailable',
                'matching_status_counts': {'roads_unavailable': 1},
                'by_partner': {owner: {'splitters': 1, 'matched': 0, 'patches': 0}},
            },
            [],
            [],
            [],
            [Point('s', 28, 77, owner)],
        )
        self.assertNotIn('<img', path.read_text())
        self.assertIn('&lt;img', path.read_text())

    def test_regional_summary_does_not_count_missing_owner_as_csp(self):
        splitters, households = (self.root / 's.csv', self.root / 'h.csv')
        splitters.write_text('partner_id,latitude,longitude\n,28,77\n')
        households.write_text('lat,long\n28,77\n')
        output = self.root / 'run'
        with contextlib.redirect_stdout(io.StringIO()):
            result = main(
                [
                    'run',
                    '--splitters',
                    str(splitters),
                    '--households',
                    str(households),
                    '--bbox',
                    '76.99',
                    '27.99',
                    '77.01',
                    '28.01',
                    '--points-only',
                    '--output',
                    str(output),
                ],
            )
        self.assertEqual(result, 0)
        summary = json.loads((output / 'summary.json').read_text())
        self.assertEqual(summary['distinct_csps'], 0)
        self.assertEqual(summary['region_splitters'], 1)
if __name__ == '__main__':
    unittest.main()
