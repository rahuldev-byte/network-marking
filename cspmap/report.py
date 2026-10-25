"""Human-readable pilot results and traceable local-review examples."""

from collections import Counter
from dataclasses import dataclass

from .markdown import MarkdownDocument, markdown_text

REVIEW_ACTIONS = (
    "1. Confirm representative qualifying connections and true breaks with local "
    "network staff.",
    "2. Review ambiguous matches and distant points against actual roads and splitter "
    "locations. Keep unresolved records visible until there is evidence for a match.",
    "3. Confirm x, match tolerance and ambiguity margin using reviewed examples, "
    "then rerun into a new output directory.",
    "4. Obtain reliable household-to-CSP identifiers before assigning household "
    "ownership or deriving served-area boundaries.",
)
OUTPUT_DESCRIPTIONS = (
    "- map.html: a combined provider network on the supplied roads; browser assets "
    "and OSM basemap tiles require internet.",
    "- config.json, summary.json, sensitivity.json, patches.json: settings and "
    "machine-readable results.",
    "- splitter_review.csv: every regional splitter, including unresolved records.",
    "- splitters.geojson, households.geojson, roads.geojson, connections.geojson, "
    "road_matches.geojson: spatial exports.",
    "- data_quality.json: full source profiling; counts can exceed those "
    "for this region.",
)


@dataclass
class PilotReviewReport:
    """Present a regional result without modifying its computational state."""

    config: dict
    summary: dict
    sensitivity: list
    patches: list
    connections: list
    points: list

    def write(self, path):
        document = MarkdownDocument()
        self._introduction(document)
        self._matching(document)
        if self.summary["road_status"] == "available":
            self._distance(document)
            self._selected_result(document)
        self._providers(document)
        self._examples(document)
        self._actions(document)
        document.write(path, trailing_newline=False)

    def _introduction(self, document):
        summary = self.summary
        bbox = self.config["bbox_west_south_east_north"]
        document.lines.extend([
            "# Pilot results and review", "",
            f"Region (west, south, east, north): {bbox}", "",
            f"{summary['region_splitters']:,} splitters; "
            f"{summary['region_households']:,} household points; "
            f"{summary['distinct_csps']:,} CSPs. "
            f"Road status: {summary['road_status']}.",
            "", "Open [map.html](map.html) to view the combined road-network "
            "map with linked splitter nodes and inferred same-owner routes. "
            "Filter by CSP or inspect outlined splitters needing review.",
            "Recorded CSP ownership is retained. Household ownership is unassigned.",
            "All splitters appear once, together with inferred routes and dashed "
            "GPS-to-road snap offsets (not verified cables). The supplied road "
            "graph is visible; households are an optional owner-unknown layer. "
            "Expand About this map or inspect splitter and route popups.",
            "",
        ])

    def _matching(self, document):
        total = self.summary["region_splitters"]
        document.lines.extend(["## Road matching", ""])
        document.table(["Status", "Splitters", "Share"], [
            [status, f"{count:,}", f"{count / total:.1%}"]
            for status, count in sorted(self.summary["matching_status_counts"].items())
        ])

    def _distance(self, document):
        config = self.config
        matched = self.summary["matching_status_counts"].get("matched", 0)
        unresolved = self.summary["region_splitters"] - matched
        document.lines.extend([
            f"Match tolerance: {config['snap_m']:g} m; competing-match margin: "
            f"{config['ambiguity_m']:g} m. {unresolved:,} unresolved records are "
            "excluded from connected patches.", "", "## Distance sensitivity", "",
            "Each connection uses a successive same-CSP road route strictly shorter "
            "than x. Offsets from original points to roads are excluded from route "
            "length. Long chains are allowed.",
            "These comparisons use the same road data and matching settings; "
            "they do not select a business threshold.", "",
        ])
        document.table(
            ["x (m)", "Patches", "Singleton patches", "Qualifying links",
             "Unique road length (km)"],
            [[f"{row['x_m']:g}", f"{row['patches']:,}", f"{row['isolated_patches']:,}",
              f"{row['qualifying_links']:,}",
              f"{row['unique_road_length_m'] / 1000:.3f}"]
             for row in self.sensitivity],
        )

    def _selected_result(self, document):
        largest = max((p["splitter_count"] for p in self.patches), default=0)
        singletons = sum(patch["isolated"] for patch in self.patches)
        document.lines.extend([
            f"At the selected x = {self.config['x_m']:g} m: {len(self.patches):,} "
            f"patches, {singletons:,} singleton patches, {len(self.connections):,} "
            f"qualifying links. Largest patch: {largest:,} splitters.",
            "A singleton can reflect a real break, missing roads, location error "
            "or the selected threshold.", "",
        ])

    def _providers(self, document):
        ordered = sorted(
            self.summary["by_partner"].items(),
            key=lambda item: (-item[1]["splitters"], item[0]),
        )
        document.lines.extend(["## CSP results", ""])
        columns = ["CSP (partner_id)", "Splitters", "Matched", "Unresolved", "Patches"]
        document.table(columns, [
            [markdown_text(owner or "Missing CSP ID"), f"{row['splitters']:,}",
             f"{row['matched']:,}", f"{row['splitters'] - row['matched']:,}",
             f"{row['patches']:,}"]
            for owner, row in ordered
        ])

    def _examples(self, document):
        document.lines.extend([
            "## Traceable review examples", "",
            "Find these IDs in splitter_review.csv or the map's splitter details. "
            "Source row IDs count from the first data row and remain stable only "
            "while source CSV order stays fixed.", "",
        ])
        self._unresolved_examples(document)
        self._flag_counts(document)
        self._route_examples(document)

    def _unresolved_examples(self, document):
        for status in sorted(self.summary["matching_status_counts"]):
            if status == "matched":
                continue
            points = sorted(
                (point for point in self.points if point.status == status),
                key=lambda point: point.id,
            )[:5]
            document.lines.append(f"- {status}: " + ", ".join(p.id for p in points))

    def _flag_counts(self, document):
        flags = Counter(flag for point in self.points for flag in point.flags)
        if flags:
            document.lines.extend([
                "", "Source review flags (a record can have several):"
            ])
            document.lines.extend(
                f"- {flag}: {count:,} records" for flag, count in sorted(flags.items())
            )

    def _route_examples(self, document):
        if not self.connections:
            return
        ordered = sorted(
            self.connections,
            key=lambda link: (
                link["distance_m"], link["from_splitter"], link["to_splitter"]
            ),
        )
        document.lines.extend([
            "",
            "Sample qualifying routes (shortest, middle and longest by route length):",
            "",
        ])
        for link in (ordered[0], ordered[len(ordered) // 2], ordered[-1]):
            document.lines.append(
                f"- {link['from_splitter']} → {link['to_splitter']}: "
                f"{link['distance_m']:.3f} m. Inspect the exported connection "
                "geometry and confirm the physical route locally."
            )

    @staticmethod
    def _actions(document):
        document.lines.extend([
            "", "## Review before operational use", "", *REVIEW_ACTIONS, "",
            "Road topology approximates cable routes. Geometric crossings and "
            "nearby road endings do not establish junctions. Traffic one-way "
            "restrictions are ignored for physical connectivity. Parameters "
            "have not been field validated.", "", "## Files", "",
            *OUTPUT_DESCRIPTIONS, "",
        ])


def write_review(path, config, summary, sensitivity, patches, connections, points):
    """Compatibility entry point for regional review reports."""
    PilotReviewReport(
        config, summary, sensitivity, patches, connections, points
    ).write(path)
