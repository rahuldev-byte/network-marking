"""Regional counts and per-provider aggregation for exported summaries."""

from collections import Counter, defaultdict

LIMITATIONS = (
    "Household CSP ownership is unknown",
    "Parameters have not been field validated",
    "Road connectivity approximates cable routes",
    "A singleton patch can reflect missing roads or location errors",
)


def regional_summary(points, households, result=None) -> dict:
    """Summarize one region without performing matching or changing ownership."""
    patches = result.patches if result else []
    connections = result.connections if result else []
    per_partner = defaultdict(lambda: {"splitters": 0, "matched": 0, "patches": 0})
    for point in points:
        per_partner[point.partner]["splitters"] += 1
        per_partner[point.partner]["matched"] += point.status == "matched"
    for patch in patches:
        per_partner[patch["partner_id"]]["patches"] += 1
    return {
        "road_status": "available" if result else "unavailable",
        "region_splitters": len(points),
        "region_households": len(households),
        "distinct_csps": sum(bool(owner) for owner in per_partner),
        "matching_status_counts": dict(Counter(point.status for point in points)),
        "connected_patches": len(patches),
        "qualifying_connections": len(connections),
        "by_partner": dict(per_partner),
        "limitations": list(LIMITATIONS),
    }
