import unittest
from types import SimpleNamespace

from cspmap.metric_rows import quality_rows, road_rows
from cspmap.metrics import distribution, overlap, partition_stability, percent
from cspmap.models import Point, RoadGraph
from cspmap.provider_metrics import provider_metrics


class MetricsTests(unittest.TestCase):

    def test_provider_metrics_preserve_counts_and_shared_road_lengths(self):
        class SinglePass(list):
            def __iter__(self):
                if getattr(self, "iterated", False):
                    raise AssertionError("Source collection scanned more than once")
                self.iterated = True
                return super().__iter__()

        result = SimpleNamespace(
            points=SinglePass([
                Point("b", 28, 77, "beta", status="no_road_within_tolerance"),
                Point("a1", 28, 77, "alpha", status="matched", offset_m=2),
                Point("a2", 28, 77, "alpha", status="matched", offset_m=4),
                Point("unknown", 28, 77),
            ]),
            patches=SinglePass([{
                "partner_id": "alpha", "isolated": False, "splitter_count": 2,
            }]),
            connections=SinglePass([
                {"partner_id": "alpha", "piece_ids": ["shared"]},
                {"partner_id": "alpha", "piece_ids": ["shared"]},
            ]),
            graph=RoadGraph({}, {}, {"shared": {"length_m": 10}}),
        )
        alpha, beta = provider_metrics(result)
        self.assertEqual([alpha["partner_id"], beta["partner_id"]], ["alpha", "beta"])
        self.assertEqual(alpha["splitters"], 2)
        self.assertEqual(alpha["match_rate_pct"], 100)
        self.assertEqual(alpha["mean_matched_offset_m"], 3)
        self.assertEqual(alpha["unique_used_road_length_m"], 10)
        self.assertEqual(alpha["connected_splitters"], 2)
        self.assertEqual(beta["unresolved"], 1)
        self.assertEqual(beta["qualifying_links"], 0)
        self.assertIsNone(beta["mean_matched_offset_m"])

    def test_quantiles_and_empty_distributions(self):
        self.assertEqual(distribution([]), {'count': 0})
        result = distribution([0, 10, 20])
        self.assertEqual(result['median'], 10)
        self.assertEqual(result['p90'], 18)
        self.assertEqual(result['p95'], 19)
        self.assertEqual(result['max'], 20)

    def test_rates_keep_unknown_denominators_unknown(self):
        self.assertEqual(percent(1, 4), 25)
        self.assertIsNone(percent(0, 0))
        self.assertIsNone(overlap(set(), set()))
        self.assertAlmostEqual(overlap({1, 2}, {2, 3}), 1 / 3)

    def test_report_tables_render_undefined_rates_without_crashing(self):
        invalid_population = {
            'records': 1, 'coordinate_validity_pct': 0,
            'missing_or_invalid_coordinates': 1, 'unique_coordinate_pairs': 0,
            'duplicate_coordinate_excess_records': 0,
            'duplicate_coordinate_excess_pct_valid': None,
        }
        rows = quality_rows({
            'splitters': invalid_population, 'households': invalid_population,
        })
        self.assertEqual(rows[-1][1:], ['N/A', 'N/A'])
        rows = road_rows({
            'nodes': 2, 'segments': 1, 'connected_components': 1,
            'largest_component_nodes': 2, 'dead_end_nodes_degree_1': 2,
            'junction_nodes_degree_at_least_3': 0, 'total_road_length_m': 0,
            'used_road_length_pct': None,
        })
        self.assertEqual(rows[-1][1], 'N/A')

    def test_partition_stability_ignores_label_names_and_noncommon_records(self):
        result = partition_stability(
            {'a': 'one', 'b': 'one', 'c': 'two', 'extra': 'three'},
            {'a': 'x', 'b': 'x', 'c': 'y'},
        )
        self.assertEqual(result['common_matched_records'], 3)
        self.assertEqual(result['adjusted_rand_index'], 1)
        self.assertEqual(result['co_cluster_pair_jaccard'], 1)

    def test_partition_stability_detects_changed_connections(self):
        result = partition_stability(
            {'a': 1, 'b': 1, 'c': 2, 'd': 2},
            {'a': 1, 'b': 2, 'c': 1, 'd': 2},
        )
        self.assertEqual(result['co_cluster_pair_jaccard'], 0)
        self.assertAlmostEqual(result['adjusted_rand_index'], -0.5)
        self.assertIsNone(partition_stability({}, {})['adjusted_rand_index'])
if __name__ == '__main__':
    unittest.main()
