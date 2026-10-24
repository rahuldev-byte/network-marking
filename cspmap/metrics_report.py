"""Present descriptive metrics as a readable report with focused sections."""

from .markdown import MarkdownDocument, format_number, markdown_text
from .metric_rows import (
    connectivity_rows,
    distribution_rows,
    provider_rows,
    quality_rows,
    road_rows,
    sensitivity_rows,
)


class MetricsReport:
    """Render existing measurements without changing or recalculating them."""

    def __init__(self, metrics):
        self.metrics = metrics
        self.document = MarkdownDocument()

    def write(self, path):
        self.document = MarkdownDocument()
        for section in (
            self._introduction, self._source_quality, self._matching,
            self._connectivity, self._sensitivity, self._providers, self._limitations,
        ):
            section()
        self.document.write(path)

    def _section(self, title, *paragraphs):
        self.document.lines.extend([f"## {title}", ""])
        for paragraph in paragraphs:
            self.document.lines.extend([paragraph, ""])

    def _introduction(self):
        scope, settings = self.metrics["scope"], self.metrics["settings"]
        self.document.lines.extend([
            "# Pilot metrics", "",
            "Real-world accuracy is unmeasured because no verified match, cable-route "
            "or ownership labels are supplied. Match rates and stability scores "
            "below are diagnostics, not accuracy scores.", "",
            f"Run: `{self.metrics['run_directory']}`. Pilot: "
            f"{scope['pilot_splitters']:,} splitters, {scope['pilot_households']:,} "
            f"households and {scope['pilot_csps']} CSPs. This is "
            f"{scope['pilot_pct_all_source_splitters']:.2f}% of source splitters, "
            f"with selection: {markdown_text(scope['selection'])}. "
            "This region is not a representative random sample.",
            "", f"Settings: x={settings['x_m']:g} m, matching tolerance="
            f"{settings['snap_m']:g} m, "
            f"ambiguity margin={settings['ambiguity_m']:g} m.",
            "",
        ])

    def _source_quality(self):
        quality = self.metrics["source_data_quality"]
        splitters, households = quality["splitters"], quality["households"]
        self._section("Source data quality")
        self.document.table(
            ["Metric", "Splitters", "Households"], quality_rows(quality)
        )
        self.document.lines.extend([
            "Valid coordinates only means finite values within latitude/longitude "
            "bounds. Duplicate-coordinate excess is valid records minus unique "
            "coordinate pairs; shared infrastructure can be legitimate.", "",
            "Cross-CSP shared coordinates: "
            f"{splitters['coordinates_shared_by_csps']:,} "
            f"locations; {splitters['shared_csp_coordinate_record_pct']:.2f}% of "
            "splitter records are flagged. Households outside the expanded splitter "
            f"extent: {households['flags'].get('outside_splitter_extent_review', 0)}. "
            "Household-to-CSP ownership is unavailable for all pilot households.", "",
        ])

    def _matching(self):
        match, conn = self.metrics["matching"], self.metrics["connectivity"]
        self._section("Road matching")
        self.document.table(["Status", "Count", "% of all pilot splitters"], [
            [status, count, f"{match['rate_pct_all_splitters'][status]:.2f}%"]
            for status, count in match["counts"].items()
        ])
        self.document.lines.extend([
            f"Total unresolved: {match['unresolved']:,} "
            f"({match['unresolved_pct']:.2f}%). "
            "Unweighted mean CSP match rate (%): "
            f"{format_number(match['macro_csp_match_rate_pct'])}. "
            f"Matched points more than 20 m from their assigned road: "
            f"{match['matched_offsets_above_20_m']}.", "",
        ])
        self.document.table(
            ["Distribution", "Count", "Min", "Mean", "Median",
             "P90", "P95", "P99", "Max"],
            distribution_rows(match, conn),
        )
        self.document.lines.extend([
            "Offsets measure proximity to the supplied roads, not error against "
            "surveyed ground truth. Quantiles use linear interpolation; full "
            "distributions also include population standard deviation in metrics.json.",
            "",
        ])

    def _connectivity(self):
        self._section("Connectivity and road graph")
        rows = connectivity_rows(self.metrics["connectivity"])
        rows.extend(road_rows(self.metrics["buffered_road_graph"]))
        self.document.table(["Metric", "Value"], rows)
        self.document.lines.extend([
            "Road graph figures describe all loaded roads, including any outside "
            "the pilot. "
            "Dead ends and components are topology statistics, not proof of data gaps. "
            "Zero-length links arise from distinct splitter records at a shared "
            "matched position. Per-CSP road lengths can overlap and must not be "
            "summed as unique physical road length.", "",
        ])

    def _sensitivity(self):
        self._section(
            "Parameter stability",
            "Each sweep changes only its stated parameter. More matches or links "
            "do not establish greater accuracy. Link Jaccard compares unordered "
            "qualifying splitter pairs to the baseline. Partition ARI measures "
            "patch agreement on records matched in both runs; it is a stability "
            "score, with 1 meaning identical partitions.",
        )
        for name, rows in self.metrics["parameter_sensitivity"].items():
            self.document.lines.extend([f"### {name.replace('_', ' ').title()}", ""])
            self.document.table(
                ["x / tolerance / margin (m)", "Matched", "Ambiguous", "No nearby road",
                 "Patches", "Singletons", "Links", "Road km",
                 "Link Jaccard", "Patch ARI"],
                sensitivity_rows(rows),
            )

    def _providers(self):
        self._section(
            "Per-CSP metrics",
            "Small CSP counts can produce extreme percentages; "
            "retain the denominators. "
            "Additional columns are in per_csp_metrics.csv.",
        )
        self.document.table(
            ["CSP", "Splitters", "Matched %", "Unresolved", "Patches", "Singletons",
             "Links", "Mean offset m"],
            provider_rows(self.metrics["per_csp"]),
        )

    def _limitations(self):
        consistency = self.metrics["internal_geometry_consistency"]
        self._section(
            "Internal consistency",
            "Baseline replay checks saved counts, splitter states, patch memberships, "
            "connection identities, distances and geometry. Route geometry length "
            "is compared against graph distance using the same road source; this "
            "checks arithmetic consistency only.",
            "Geometry/graph route-length RMSE: "
            f"{consistency['route_length_rmse_m']} m.",
        )
        self._section("Accuracy metrics requiring ground truth")
        self.document.table(["Metric", "Status / missing evidence"], [
            [name.replace("_", " "), row["reason"]]
            for name, row in self.metrics["unavailable_accuracy_metrics"].items()
        ])


def write_report(path, metrics):
    """Compatibility entry point for Markdown metric reports."""
    MetricsReport(metrics).write(path)
