import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from cspmap.__main__ import main
from cspmap.data import Point, coordinate, profile, read_points
from cspmap.geo import LocalMetres
from cspmap.output import write_map
from cspmap.projections import MetricProjection
from cspmap.roads import (
    Roads,
    assign_patches,
    augmented_graph,
    load_roads,
    match_points,
    qualifying_connections,
)


def ll(x, y=0):
    return [77 + x / (111320 * math.cos(math.radians(28))), 28 + y / 110800]


def point(key, x, y=0, partner='csp-1'):
    lon, lat = ll(x, y)
    return Point(key, lat, lon, partner)


class RoadTests(unittest.TestCase):

    def setUp(self):
        self.roads = Roads(LocalMetres(77, 28))

    def add(self, u, v, x1, y1, x2, y2):
        self.roads.add(u, v, ll(x1, y1), ll(x2, y2), f'{u}-{v}')

    def analyse(self, points, x=100, snap=5, ambiguity=0.1):
        matches = match_points(points, self.roads, snap, ambiguity)
        graph = augmented_graph(self.roads, matches)
        links = qualifying_connections(points, matches, graph, x)
        selected, patches = assign_patches(points, matches, links, x)
        return (matches, selected, patches)

    def test_partial_segment_routes_do_not_round_to_junction(self):
        self.add('a', 'b', 0, 0, 1000, 0)
        pts = [point('s1', 400), point('s2', 450)]
        matches, links, patches = self.analyse(pts, 100)
        self.assertEqual(len(matches), 2)
        self.assertEqual(len(patches), 1)
        self.assertAlmostEqual(links[0]['distance_m'], 50, delta=0.1)

    def test_strict_threshold_equal_above_and_below(self):
        self.add('a', 'b', 0, 0, 100, 0)
        pts = [point('s1', 0), point('s2', 100)]
        length = self.roads.segments[0].length
        self.assertEqual(len(self.analyse(pts, length)[1]), 0)
        self.assertEqual(len(self.analyse(pts, length - 1e-06)[1]), 0)
        self.assertEqual(len(self.analyse(pts, length + 1e-06)[1]), 1)

    def test_long_chain_is_allowed(self):
        self.add('a', 'b', 0, 0, 300, 0)
        pts = [point('s1', 0), point('s2', 80), point('s3', 160), point('s4', 240)]
        _, links, patches = self.analyse(pts, 100)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]['splitter_count'], 4)
        self.assertTrue(all((c['distance_m'] < 100 for c in links)))

    def test_connected_junction_continues_onto_other_road(self):
        self.add('a', 'junction', -100, 0, 0, 0)
        self.add('junction', 'b', 0, 0, 0, 100)
        _, links, patches = self.analyse([point('s1', -40), point('s2', 0, 40)], 90)
        self.assertEqual(len(patches), 1)
        self.assertAlmostEqual(links[0]['distance_m'], 80, delta=0.3)
        self.assertEqual(len(links[0]['coordinates']), 3)

    def test_identical_coordinate_at_real_junction_is_not_ambiguous(self):
        self.add('a', 'junction', -100, 0, 0, 0)
        self.add('junction', 'b', 0, 0, 0, 100)
        matches, _, _ = self.analyse([point('s1', 0)], 100)
        self.assertEqual(matches['s1'].anchor, 'junction')

    def test_disconnected_dead_ends_do_not_jump(self):
        self.add('a', 'end1', -100, 0, 0, 0)
        self.add('end2', 'b', 5, 0, 105, 0)
        pts = [point('s1', -10), point('s2', 15)]
        _, links, patches = self.analyse(pts, 100, snap=2)
        self.assertFalse(links)
        self.assertEqual(len(patches), 2)
        self.assertTrue(all((p.partner == 'csp-1' for p in pts)))

    def test_geometric_crossing_does_not_create_junction(self):
        self.add('west', 'east', -100, 0, 100, 0)
        self.add('south', 'north', 0, -100, 0, 100)
        _, links, patches = self.analyse([point('s1', -30), point('s2', 0, 30)], 100)
        self.assertFalse(links)
        self.assertEqual(len(patches), 2)

    def test_competing_parallel_roads_are_ambiguous(self):
        self.add('a', 'b', -100, -1, 100, -1)
        self.add('c', 'd', -100, 1, 100, 1)
        p = point('s1', 0)
        matches, _, _ = self.analyse([p], ambiguity=2)
        self.assertFalse(matches)
        self.assertEqual(p.status, 'ambiguous_road_match')

    def test_different_csps_at_shared_position_remain_separate(self):
        self.add('a', 'b', -100, 0, 100, 0)
        pts = [point('s1', 20, partner='one'), point('s2', 20, partner='two')]
        _, links, patches = self.analyse(pts)
        self.assertFalse(links)
        self.assertEqual(len(patches), 2)
        self.assertEqual({p['partner_id'] for p in patches}, {'one', 'two'})

    def test_same_csp_at_shared_match_connects_with_zero_length(self):
        self.add('a', 'b', -100, 0, 100, 0)
        _, links, patches = self.analyse([point('s1', 20), point('s2', 20)])
        self.assertEqual(len(patches), 1)
        self.assertEqual(links[0]['distance_m'], 0)

    def test_other_csp_does_not_block_physical_road(self):
        self.add('a', 'b', 0, 0, 200, 0)
        pts = [point('s1', 10), point('s2', 30, partner='other'), point('s3', 60)]
        _, links, patches = self.analyse(pts)
        self.assertEqual(len(links), 1)
        self.assertEqual(len(patches), 2)

    def test_no_nearby_road_and_invalid_coordinate_stay_unresolved(self):
        self.add('a', 'b', 0, 0, 100, 0)
        far = point('s1', 50, 50)
        invalid = Point('s2', None, None, 'csp-1', status='invalid_coordinates')
        matches, _, patches = self.analyse([far, invalid], snap=5)
        self.assertFalse(matches)
        self.assertFalse(patches)
        self.assertEqual(far.status, 'no_road_within_tolerance')
        self.assertEqual(invalid.status, 'invalid_coordinates')

    def test_short_route_around_cycle_and_sensitivity(self):
        for u, v, a, b in [
            ('a', 'b', (0, 0), (80, 0)),
            ('b', 'c', (80, 0), (80, 80)),
            ('c', 'd', (80, 80), (0, 80)),
            ('d', 'a', (0, 80), (0, 0)),
        ]:
            self.add(u, v, *a, *b)
        pts = [point('s1', 0, 0), point('s2', 80, 0), point('s3', 80, 80)]
        matches = match_points(pts, self.roads, 5, 0.1)
        graph = augmented_graph(self.roads, matches)
        candidates = qualifying_connections(pts, matches, graph, 200)
        counts = [
            len(assign_patches(pts, matches, candidates, x)[1])
            for x in [50, 100, 200]
        ]
        self.assertEqual(counts, [3, 1, 1])


class GeoPandasRoadTests(RoadTests):
    """Apply every road invariant to the production GeoPandas/PROJ CRS."""

    def setUp(self):
        self.roads = Roads(MetricProjection(77, 28))


class DataAndExportTests(unittest.TestCase):

    def test_invalid_coordinates_and_missing_schema(self):
        for a, b in [('', '77'), ('nan', '77'), ('28', 'inf'), ('91', '77')]:
            self.assertEqual(coordinate(a, b), (None, None))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.csv'
            path.write_text('lat,long\n28,77\n')
            with self.assertRaisesRegex(ValueError, 'missing columns'):
                read_points(path, 'splitter')

    def test_shared_coordinates_preserve_both_csps(self):
        pts = [point('s1', 0, partner='one'), point('s2', 0, partner='two')]
        report = profile(pts, [])
        self.assertEqual(report['splitters']['coordinates_shared_by_csps'], 1)
        self.assertEqual(len(pts), 2)
        self.assertTrue(all(('coordinate_shared_by_csps' in p.flags for p in pts)))

    def test_road_file_requires_explicit_topology(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'roads.geojson'
            path.write_text(
                json.dumps(
                    {
                        'type': 'FeatureCollection',
                        'features': [
                            {
                                'type': 'Feature',
                                'properties': {},
                                'geometry': {
                                    'type': 'LineString',
                                    'coordinates': [ll(0), ll(100)],
                                },
                            },
                        ],
                    },
                ),
            )
            with self.assertRaisesRegex(ValueError, 'topology|node_ids'):
                load_roads(path, LocalMetres(77, 28))

    def test_osm_preserves_disconnected_nodes_at_identical_locations(self):
        with tempfile.TemporaryDirectory() as temp:
            data = {
                'elements': [
                    {'type': 'node', 'id': i, 'lon': ll(x)[0], 'lat': ll(x)[1]}
                     for i, x in [(1, -100), (2, 0), (3, 0), (4, 100)]
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
                        'nodes': [3, 4],
                        'tags': {'highway': 'residential'},
                    },
                ],
            }
            path = Path(temp) / 'roads.json'
            path.write_text(json.dumps(data))
            roads = load_roads(path, LocalMetres(77, 28))
            pts = [point('s1', -20), point('s2', 20)]
            matches = match_points(pts, roads, 3, 0.1)
            graph = augmented_graph(roads, matches)
            self.assertFalse(qualifying_connections(pts, matches, graph, 100))

    def test_projection_metric_units_and_region_limit(self):
        projection = LocalMetres(0, 0)
        x, y = projection.project(0.001, 0)
        self.assertAlmostEqual(x, 111.31949, places=4)
        self.assertAlmostEqual(y, 0)
        with self.assertRaisesRegex(ValueError, '25 km'):
            projection.project(1, 0)

    def test_map_escapes_script_delimiters(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'map.html'
            write_map(
                path,
                [point('s1', 0, partner='</script><script>alert(1)</script>')],
                [],
                [77, 28, 77.01, 28.01],
                'test',
            )
            text = path.read_text()
            self.assertNotIn('<script>alert(1)', text)
            self.assertIn('\\u003c/script\\u003e', text)

    def test_end_to_end_outputs_and_no_household_phone_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sp = root / 'splitters.csv'
            hp = root / 'households.csv'
            rp = root / 'roads.geojson'
            out = root / 'output'
            with sp.open('w') as handle:
                writer = csv.writer(handle)
                writer.writerow(['partner_id', 'latitude', 'longitude'])
                for x in [20, 60]:
                    lon, lat = ll(x)
                    writer.writerow(['owner', lat, lon])
            hp.write_text('mobile,lat,long\nPRIVATE_PHONE_TOKEN,28.0001,77.0001\n')
            rp.write_text(
                json.dumps(
                    {
                        'type': 'FeatureCollection',
                        'features': [
                            {
                                'type': 'Feature',
                                'properties': {'from_node': 'a', 'to_node': 'b'},
                                'geometry': {
                                    'type': 'LineString',
                                    'coordinates': [ll(0), ll(100)],
                                },
                            },
                        ],
                    },
                ),
            )
            result = main(
                [
                    'run',
                    '--splitters',
                    str(sp),
                    '--households',
                    str(hp),
                    '--roads',
                    str(rp),
                    '--bbox',
                    '76.999',
                    '27.999',
                    '77.002',
                    '28.002',
                    '--x-m',
                    '100',
                    '--compare-x',
                    '20',
                    '--output',
                    str(out),
                ],
            )
            self.assertEqual(result, 0)
            summary = json.loads((out / 'summary.json').read_text())
            self.assertEqual(summary['connected_patches'], 1)
            self.assertEqual(summary['qualifying_connections'], 1)
            review = (out / 'REVIEW.md').read_text()
            self.assertIn('Distance sensitivity', review)
            self.assertIn('| 20 | 2 | 2 | 0 |', review)
            self.assertIn('| owner | 2 | 2 | 0 | 1 |', review)
            self.assertIn('s-0000001 → s-0000002', review)
            for p in out.iterdir():
                self.assertNotIn('PRIVATE_PHONE_TOKEN', p.read_text(), p.name)
            self.assertTrue((out / 'map.html').exists())
if __name__ == '__main__':
    unittest.main()
