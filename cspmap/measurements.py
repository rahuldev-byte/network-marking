"""Descriptive matching, connectivity, and full-source quality measurements."""

from collections import Counter
from statistics import mean

from .sensitivity import evaluation_counts
from .statistics import distribution, percent

MISSING_ACCURACY_EVIDENCE = {
    "confusion_matrix_tp_fp_tn_fn": (
        "No labelled matches/connections or defined negative-pair evaluation set."
    ),
    "road_match_accuracy_precision_recall_f1": (
        "No independently verified road match labels."
    ),
    "connection_accuracy_precision_recall_f1_specificity": (
        "No verified true/false cable connections or defined negative-pair "
        "evaluation set."
    ),
    "roc_auc_pr_auc": (
        "No labelled evaluation set or defined prediction score for each "
        "evaluated case."
    ),
    "splitter_position_error_mae_rmse": "No surveyed reference coordinates.",
    "cable_route_distance_error_mae_rmse": "No measured cable-route distances.",
    "road_completeness_precision_recall": (
        "No authoritative road inventory for the region."
    ),
    "service_area_iou_or_coverage_accuracy": (
        "No verified service boundaries; the model generates road stretches, "
        "not service polygons."
    ),
    "household_to_csp_assignment_accuracy": (
        "The household input contains no ownership links and no assignments "
        "are inferred."
    ),
    "accuracy_confidence_intervals": (
        "No labelled evaluation sample; the selected pilot is not a representative "
        "random sample of all records."
    ),
}


def matching_metrics(result, per_csp) -> dict:
    """Measure acceptance and offsets, retaining unresolved cases."""
    points = result.points
    total = len(points)
    matched = [point for point in points if point.status == "matched"]
    ambiguous = [point for point in points if point.status == "ambiguous_road_match"]
    counts = Counter(point.status for point in points)
    return {
        "counts": dict(counts),
        "rate_pct_all_splitters": {
            status: percent(count, total) for status, count in counts.items()
        },
        "unresolved": total - len(matched),
        "unresolved_pct": percent(total - len(matched), total),
        "matched_offset_m": distribution(point.offset_m for point in matched),
        "ambiguous_nearest_candidate_offset_m": distribution(
            point.offset_m for point in ambiguous
        ),
        "matched_offsets_above_20_m": sum(point.offset_m > 20 for point in matched),
        "macro_csp_match_rate_pct": (
            mean(row["match_rate_pct"] for row in per_csp) if per_csp else None
        ),
    }


def connectivity_metrics(result) -> dict:
    """Measure the chosen result, counting each distinct road piece once."""
    base = evaluation_counts(result)
    matched = len(result.matches)
    singletons = base["singleton_patches"]
    degree = Counter()
    for link in result.connections:
        degree.update((link["from_splitter"], link["to_splitter"]))
    return {
        **base,
        "multi_splitter_patches": len(result.patches) - singletons,
        "singleton_pct_of_patches": percent(singletons, len(result.patches)),
        "singleton_pct_of_matched_splitters": percent(singletons, matched),
        "connected_pct_of_matched_splitters": percent(matched - singletons, matched),
        "patch_size_splitters": distribution(
            patch["splitter_count"] for patch in result.patches
        ),
        **route_metrics(result),
        "splitter_link_degree": distribution(
            degree[point.id] for point in result.points if point.id in result.matches
        ),
    }


def route_metrics(result) -> dict:
    """Measure emitted routes while distinguishing overlap from unique length."""
    links = result.connections
    return {
        "qualifying_route_length_m": distribution(link["distance_m"] for link in links),
        "zero_length_links": sum(link["distance_m"] == 0 for link in links),
        "links_within_5_m_of_threshold": sum(
            link["distance_m"] >= result.x_m - 5 for link in links
        ),
        "sum_route_lengths_m_including_overlap": sum(
            link["distance_m"] for link in links
        ),
    }


def source_quality_metrics(quality) -> dict:
    """Add explicit denominators and duplicate-coordinate diagnostics."""
    result = {}
    for name in ("splitters", "households"):
        row = quality[name]
        duplicates = row["valid_coordinates"] - row["unique_coordinate_pairs"]
        result[name] = {
            **row,
            "coordinate_validity_pct": percent(
                row["valid_coordinates"], row["records"]
            ),
            "duplicate_coordinate_excess_records": duplicates,
            "duplicate_coordinate_excess_pct_valid": percent(
                duplicates, row["valid_coordinates"]
            ),
        }
    result["splitters"]["shared_csp_coordinate_record_pct"] = percent(
        quality["splitters"]["flags"].get("coordinate_shared_by_csps", 0),
        quality["splitters"]["records"],
    )
    result["households"]["outside_expanded_splitter_extent_pct_valid"] = percent(
        quality["households"]["flags"].get("outside_splitter_extent_review", 0),
        quality["households"]["valid_coordinates"],
    )
    return result


def unavailable_accuracy_metrics() -> dict:
    """Record absent evidence instead of manufacturing accuracy scores."""
    return {
        name: {"value": None, "reason": reason}
        for name, reason in MISSING_ACCURACY_EVIDENCE.items()
    }
