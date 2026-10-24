"""Compose metrics from a saved run without mixing rendering and analysis."""

from datetime import datetime, timezone

from .measurements import (
    connectivity_metrics,
    matching_metrics,
    source_quality_metrics,
    unavailable_accuracy_metrics,
)
from .provider_metrics import provider_metrics
from .road_statistics import geometry_consistency, road_statistics
from .saved_run import SavedRun
from .sensitivity import ParameterEvaluator
from .statistics import percent


class MetricsService:
    """Validate a baseline, evaluate parameter changes, and assemble diagnostics."""

    def analyse(self, directory) -> dict:
        saved = SavedRun.read(directory)
        evaluator = ParameterEvaluator(saved)
        baseline, distance_results = evaluator.baseline()
        providers = provider_metrics(baseline)
        return {
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'run_directory': str(saved.directory),
            'scope': self._scope(saved, baseline),
            'settings': {
                key: saved.config[key]
                 for key in ('x_m', 'snap_m', 'ambiguity_m')
            },
            'source_data_quality': source_quality_metrics(saved.quality),
            'matching': matching_metrics(baseline, providers),
            'connectivity': connectivity_metrics(baseline),
            'buffered_road_graph': road_statistics(saved.roads, baseline.road_length_m),
            'internal_geometry_consistency': geometry_consistency(
                baseline,
                saved.roads.projection,
            ),
            'parameter_sensitivity': evaluator.sweeps(baseline, distance_results),
            'per_csp': providers,
            'unavailable_accuracy_metrics': unavailable_accuracy_metrics(),
        }

    @staticmethod
    def _scope(saved, result) -> dict:
        return {
            "pilot_splitters": len(result.points),
            "pilot_households": saved.summary["region_households"],
            "pilot_csps": saved.summary["distinct_csps"],
            "pilot_pct_all_source_splitters": percent(
                len(result.points), saved.quality["splitters"]["records"]
            ),
            "pilot_pct_all_source_households": percent(
                saved.summary["region_households"],
                saved.quality["households"]["records"],
            ),
            "selection": saved.config["selection"],
            "bbox": saved.config["bbox_west_south_east_north"],
        }
