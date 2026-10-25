"""Per-provider descriptive measurements; ownership is never inferred."""

from collections import Counter, defaultdict
from statistics import mean, median

from .analysis import used_road_length
from .statistics import percent


def provider_row(owner, points, patches, links, graph) -> dict:
    """Measure one provider's already-computed result."""
    matched = [point for point in points if point.status == "matched"]
    statuses = Counter(point.status for point in points)
    singletons = sum(patch["isolated"] for patch in patches)
    return {
        'partner_id': owner,
        'splitters': len(points),
        'matched': len(matched),
        'match_rate_pct': percent(len(matched), len(points)),
        'ambiguous': statuses['ambiguous_road_match'],
        'no_road_within_tolerance': statuses['no_road_within_tolerance'],
        'unresolved': len(points) - len(matched),
        'patches': len(patches),
        'singleton_patches': singletons,
        'connected_splitters': len(matched) - singletons,
        'connected_pct_all_csp_splitters': percent(
            len(matched) - singletons,
            len(points),
        ),
        'largest_patch_splitters': max(
            (patch['splitter_count'] for patch in patches),
            default=0,
        ),
        'qualifying_links': len(links),
        'unique_used_road_length_m': used_road_length(graph, links),
        'mean_matched_offset_m': (
            mean(point.offset_m for point in matched) if matched else None
        ),
        'median_matched_offset_m': (
            median(point.offset_m for point in matched) if matched else None
        ),
    }


def provider_metrics(result) -> list[dict]:
    """Produce a deterministic provider table, retaining each denominator."""
    points, patches, links = (defaultdict(list) for _ in range(3))
    for point in result.points:
        if point.partner:
            points[point.partner].append(point)
    for patch in result.patches:
        patches[patch['partner_id']].append(patch)
    for link in result.connections:
        links[link['partner_id']].append(link)
    return [
        provider_row(
            owner, points[owner], patches[owner], links[owner], result.graph,
        )
        for owner in sorted(points)
    ]
