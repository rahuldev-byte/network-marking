"""Regression coverage for shared services and isolated result snapshots."""
import contextlib
import csv
import io
import json
import math
import tempfile
import unittest
import urllib.error
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from cspmap.analysis import RoadAnalysis
from cspmap.cli import main
from cspmap.configuration import RunSettings
from cspmap.geo import LocalMetres
from cspmap.geospatial import road_frame
from cspmap.metric_service import MetricsService
from cspmap.metrics_report import write_report
from cspmap.models import Point
from cspmap.road_download import OverpassClient
from cspmap.road_network import Roads
from cspmap.saved_run import SavedRun
from cspmap.tabular_output import write_records
from cspmap.workflows import InputData, RegionalWorkflow


class AnalysisServiceTests(unittest.TestCase):

    def setUp(self):
        self.roads = Roads(LocalMetres(77, 28))
        self.roads.add('a', 'b', [77, 28], [77.002, 28], 'road')
        self.points = [
            Point('first', 28, 77.0001, 'owner', ['original_flag']),
            Point('second', 28, 77.001, 'owner'),
        ]

    def test_threshold_snapshots_keep_their_own_point_and_membership_state(self):
        small, large = RoadAnalysis(self.roads, 5, 0).evaluate(self.points, [50, 200])
        self.assertEqual(len(small.patches), 2)
        self.assertEqual(len(large.patches), 1)
        self.assertEqual(len(set(small.membership.values())), 2)
        self.assertEqual(len(set(large.membership.values())), 1)
        for result in (small, large):
            for point in result.points:
                self.assertEqual(point.patch, result.membership[point.id])
        large.points[0].flags.append('later_review')
        self.assertNotIn('later_review', small.points[0].flags)
        self.assertNotIn('later_review', self.points[0].flags)

    def test_direct_service_rejects_invalid_parameters(self):
        for tolerance, margin in ((0, 2), (math.inf, 2), (5, -1), (5, math.nan)):
            with self.subTest(tolerance=tolerance, margin=margin):
                with self.assertRaises(ValueError):
                    RoadAnalysis(self.roads, tolerance, margin)
        analysis = RoadAnalysis(self.roads, 5, 0)
        for thresholds in ([], [0], [-1], [math.inf], [math.nan]):
            with self.subTest(thresholds=thresholds):
                with self.assertRaises(ValueError):
                    analysis.evaluate(self.points, thresholds)

    def test_duplicate_record_ids_cannot_silently_merge_splitters(self):
        self.points[1].id = self.points[0].id
        with self.assertRaisesRegex(ValueError, "record IDs must be unique"):
            RoadAnalysis(self.roads, 5, 0).evaluate(self.points, [100])

    def test_analysis_does_not_rewrite_caller_source_records(self):
        before = [asdict(point) for point in self.points]
        result = RoadAnalysis(self.roads, 5, 0).evaluate(self.points, [100])[0]
        self.assertTrue(result.matches)
        self.assertEqual([asdict(point) for point in self.points], before)


class SavedRunTests(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'splitters.csv').write_text(
            'partner_id,latitude,longitude\nowner,28,77.0001\nowner,28,77.0005\n',
        )
        (self.root / 'households.csv').write_text('lat,long\n28,77.0003\n')
        (self.root / 'roads.json').write_text(
            json.dumps(
                {
                    'type': 'FeatureCollection',
                    'features': [
                        {
                            'type': 'Feature',
                            'properties': {
                                'from_node': 'a',
                                'to_node': 'b',
                                'road_id': 'road',
                            },
                            'geometry': {
                                'type': 'LineString',
                                'coordinates': [[77, 28], [77.001, 28]],
                            },
                        },
                    ],
                },
            ),
        )
        self.run_dir = self.root / 'run'
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(
                [
                    'run',
                    '--splitters',
                    str(self.root / 'splitters.csv'),
                    '--households',
                    str(self.root / 'households.csv'),
                    '--roads',
                    str(self.root / 'roads.json'),
                    '--bbox',
                    '76.999',
                    '27.999',
                    '77.002',
                    '28.001',
                    '--x-m',
                    '100',
                    '--compare-x',
                    '20',
                    '200',
                    '--output',
                    str(self.run_dir),
                ],
            )
        self.assertEqual(status, 0)

    def test_metrics_replay_and_sweeps_leave_saved_source_state_untouched(self):
        before = (self.run_dir / 'splitters.geojson').read_bytes()
        with patch('cspmap.matching.road_frame', wraps=road_frame) as build_frame:
            metrics = MetricsService().analyse(self.run_dir)
            self.assertEqual(build_frame.call_count, 1)
        self.assertEqual(metrics['connectivity']['qualifying_links'], 1)
        self.assertEqual(metrics['connectivity']['patches'], 1)
        self.assertEqual(len(metrics['parameter_sensitivity']['distance_threshold']), 3)
        self.assertEqual((self.run_dir / 'splitters.geojson').read_bytes(), before)
        saved = SavedRun.read(self.run_dir)
        first, second = (saved.fresh_points(), saved.fresh_points())
        first[0].flags.append('experiment')
        self.assertNotIn('experiment', second[0].flags)

    def test_metrics_refuse_a_different_saved_baseline(self):
        path = self.run_dir / 'summary.json'
        summary = json.loads(path.read_text())
        summary['connected_patches'] += 1
        path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError, 'baseline differs'):
            MetricsService().analyse(self.run_dir)

    def test_metrics_refuse_different_patch_members_with_unchanged_counts(self):
        path = self.run_dir / 'patches.json'
        patches = json.loads(path.read_text())
        patches[0]['splitter_ids'][0] = 'different-record'
        path.write_text(json.dumps(patches))
        with self.assertRaisesRegex(ValueError, 'baseline differs.*memberships'):
            MetricsService().analyse(self.run_dir)

    def test_metrics_refuse_changed_routes_with_unchanged_counts(self):
        path = self.run_dir / 'connections.geojson'
        original = json.loads(path.read_text())
        for change in ('endpoint', 'distance', 'geometry'):
            with self.subTest(change=change):
                document = json.loads(json.dumps(original))
                feature = document['features'][0]
                if change == 'endpoint':
                    feature['properties']['to_splitter'] = 'different-record'
                elif change == 'distance':
                    feature['properties']['distance_m'] += 1
                else:
                    feature['geometry']['coordinates'][0][0] += 0.00001
                path.write_text(json.dumps(document))
                with self.assertRaisesRegex(ValueError, 'baseline differs.*connection'):
                    MetricsService().analyse(self.run_dir)

    def test_metrics_refuse_changed_point_state_with_unchanged_counts(self):
        path = self.run_dir / 'splitters.geojson'
        document = json.loads(path.read_text())
        document['features'][0]['properties']['road_id'] = 'different-road'
        path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, 'baseline differs.*splitter state'):
            MetricsService().analyse(self.run_dir)

    def test_metrics_accept_reversed_undirected_connection_geometry(self):
        path = self.run_dir / 'connections.geojson'
        document = json.loads(path.read_text())
        feature = document['features'][0]
        props = feature['properties']
        props['from_splitter'], props['to_splitter'] = (
            props['to_splitter'], props['from_splitter']
        )
        feature['geometry']['coordinates'].reverse()
        path.write_text(json.dumps(document))
        metrics = MetricsService().analyse(self.run_dir)
        self.assertEqual(metrics['connectivity']['qualifying_links'], 1)

    def test_report_describes_explicit_selection_and_company_roads(self):
        metrics = MetricsService().analyse(self.run_dir)
        path = self.root / 'METRICS.md'
        write_report(path, metrics)
        report = path.read_text()
        self.assertIn('selection: explicit bbox', report)
        self.assertNotIn('densest eligible', report)
        self.assertNotIn('proximity to OSM', report)

    def test_exported_map_uses_folium_with_embedded_snapshot_data(self):
        html = (self.run_dir / 'map.html').read_text()
        self.assertNotIn('src="web/', html)
        self.assertNotIn('href="web/', html)
        self.assertNotIn('__MAP_DATA__', html)
        self.assertIn('L.map(', html)
        self.assertIn('L.geoJson(', html)
        self.assertIn('class ProviderSelection', html)
        self.assertIn('cdn.jsdelivr.net', html)

    def test_exports_use_selected_threshold_even_when_larger_threshold_runs_last(self):
        output = self.root / 'small-threshold'
        output.mkdir()
        data = InputData.read(self.root / 'splitters.csv', self.root / 'households.csv')
        settings = RunSettings(
            output=output, automatic=False, bbox=(76.999, 27.999, 77.002, 28.001),
            roads=self.root / 'roads.json', download=False, points_only=False,
            x_m=20, snap_m=30, ambiguity_m=2, compare_x=(100, 200),
        )
        summary = RegionalWorkflow().execute(data, settings)
        self.assertEqual(summary['connected_patches'], 2)
        features = json.loads((output / 'splitters.geojson').read_text())['features']
        self.assertEqual(len({row['properties']['patch'] for row in features}), 2)
        metrics = MetricsService().analyse(output)
        self.assertEqual(metrics['connectivity']['patches'], 2)

    def test_metric_csv_uses_shared_spreadsheet_escaping(self):
        path = self.root / 'metrics.csv'
        write_records(path, [{'owner': '=formula', 'road': '\tvalue', 'count': 3}])
        with path.open(newline='') as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row, {'owner': "'=formula", 'road': "'\tvalue", 'count': '3'})


class OverpassClientTests(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'roads.json'

    @staticmethod
    def response(payload):
        return lambda request, timeout: io.BytesIO(payload)

    def test_success_saves_the_original_response_without_source_records(self):
        data = {'elements': [{'type': 'node', 'id': 1, 'lat': 28, 'lon': 77}]}
        client = OverpassClient(opener=self.response(json.dumps(data).encode()))
        client.download([77, 28, 77.01, 28.01], 330, self.path)
        self.assertEqual(json.loads(self.path.read_text()), data)
        self.assertNotIn('partner_id', client.query([77, 28, 77.01, 28.01], 330))

    def test_incomplete_or_oversized_response_is_not_saved(self):
        payload = json.dumps({'remark': 'timeout', 'elements': []}).encode()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            OverpassClient(opener=self.response(payload)).download(
                [77, 28, 77.01, 28.01],
                330,
                self.path,
            )
        with patch('cspmap.road_download.MAX_RESPONSE_BYTES', 8):
            with self.assertRaisesRegex(ValueError, 'too large'):
                OverpassClient(opener=self.response(b'x' * 9)).download(
                    [77, 28, 77.01, 28.01],
                    330,
                    self.path,
                )
        self.assertFalse(self.path.exists())

    def test_network_failure_is_an_actionable_error(self):

        def unavailable(request, timeout):
            raise urllib.error.URLError('offline')
        with self.assertRaisesRegex(ValueError, 'Supply --roads'):
            OverpassClient(opener=unavailable).download(
                [77, 28, 77.01, 28.01], 330, self.path
            )
        self.assertFalse(self.path.exists())
if __name__ == '__main__':
    unittest.main()
