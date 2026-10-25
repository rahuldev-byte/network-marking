"""Metrics CLI and compatibility API: python3 -m cspmap.metrics."""

import argparse
import json
import sys
from pathlib import Path

from .metric_service import MetricsService
from .metrics_report import write_report
from .run_output import staged_output
from .serialization import write_json
from .statistics import distribution, overlap, partition_stability, percent
from .tabular_output import write_records

__all__ = [
    "analyse", "distribution", "overlap", "partition_stability",
    "percent", "write_report", "main",
]


def analyse(run_dir):
    """Compute descriptive diagnostics from one completed saved road run."""
    return MetricsService().analyse(run_dir)


def main(argv=None):
    """Parse metric paths and export JSON, Markdown, and the provider table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        with staged_output(args.output) as output:
            metrics = analyse(args.run)
            write_json(output / "metrics.json", metrics)
            write_report(output / "METRICS.md", metrics)
            write_records(output / "per_csp_metrics.csv", metrics["per_csp"])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"cspmap.metrics: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "output": str(args.output),
        "matching": metrics["matching"]["rate_pct_all_splitters"],
        "real_world_accuracy": "unmeasured: no ground truth labels",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
