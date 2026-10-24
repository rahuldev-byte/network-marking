"""Parameter sweeps and agreement with a verified reconstructed baseline."""

from collections import Counter

from .analysis import AnalysisResult, RoadAnalysis
from .matching import SegmentIndex
from .saved_run import SavedRun
from .snapshot_validation import SnapshotValidator
from .statistics import overlap, partition_stability, percent


def evaluation_counts(result: AnalysisResult) -> dict:
    """Describe one threshold evaluation using the existing metrics schema."""
    counts = Counter(point.status for point in result.points)
    matched = len(result.matches)
    total = len(result.points)
    isolated = sum(patch["isolated"] for patch in result.patches)
    return {
        "x_m": result.x_m, "snap_m": result.snap_m,
        "ambiguity_m": result.ambiguity_m,
        "matched": matched, "matched_pct_all_splitters": percent(matched, total),
        "ambiguous": counts["ambiguous_road_match"],
        "no_road_within_tolerance": counts["no_road_within_tolerance"],
        "patches": len(result.patches), "singleton_patches": isolated,
        "connected_splitters": matched - isolated,
        "connected_pct_all_splitters": percent(matched - isolated, total),
        "qualifying_links": len(result.connections),
        "unique_used_road_length_m": result.road_length_m,
    }


class ParameterEvaluator:
    """Reuse the application analysis service while isolating every sweep."""

    def __init__(self, saved: SavedRun):
        self.saved = saved
        self.points = saved.fresh_points()
        self.index = SegmentIndex(saved.roads)

    def evaluate(self, snap, ambiguity, thresholds) -> list[AnalysisResult]:
        analysis = RoadAnalysis(self.saved.roads, snap, ambiguity, self.index)
        return analysis.evaluate(self.points, thresholds)

    def baseline(self) -> tuple[AnalysisResult, list[AnalysisResult]]:
        config = self.saved.config
        thresholds = sorted({config["x_m"], *config["compare_x_m"]})
        results = self.evaluate(config["snap_m"], config["ambiguity_m"], thresholds)
        baseline = next(row for row in results if row.x_m == config["x_m"])
        SnapshotValidator(self.saved).validate(baseline)
        return baseline, results

    def sweeps(self, baseline, distance_results) -> dict:
        config = self.saved.config
        tolerance = [
            baseline if snap == config["snap_m"] else self.evaluate(
                snap, config["ambiguity_m"], [config["x_m"]]
            )[0]
            for snap in sorted({10.0, 20.0, 30.0, 50.0, config["snap_m"]})
        ]
        margins = [
            baseline if margin == config["ambiguity_m"] else self.evaluate(
                config["snap_m"], margin, [config["x_m"]]
            )[0]
            for margin in sorted({0.0, 1.0, 2.0, 5.0, config["ambiguity_m"]})
        ]
        return {
            name: [self._stability(row, baseline) for row in rows]
            for name, rows in (
                ("distance_threshold", distance_results),
                ("matching_tolerance", tolerance),
                ("ambiguity_margin", margins),
            )
        }

    @staticmethod
    def _stability(result: AnalysisResult, baseline: AnalysisResult) -> dict:
        return {
            **evaluation_counts(result),
            "matched_set_jaccard_vs_baseline": overlap(
                set(baseline.membership), set(result.membership)
            ),
            "qualifying_link_pair_jaccard_vs_baseline": overlap(
                baseline.link_pairs, result.link_pairs
            ),
            "partition_vs_baseline": partition_stability(
                baseline.membership, result.membership
            ),
        }
