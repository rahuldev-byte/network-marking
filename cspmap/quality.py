"""Source-quality flags and summaries; no road inference."""

from collections import Counter, defaultdict

from .regions import bounds, inside

SHARED_COORDINATE_FLAG = "coordinate_shared_by_csps"
OUTSIDE_EXTENT_FLAG = "outside_splitter_extent_review"


def shared_locations(splitters) -> set[tuple]:
    """Find coordinates recorded against multiple nonempty owner identifiers."""
    labels = defaultdict(set)
    for point in splitters:
        if point.valid and point.partner:
            labels[(point.lat, point.lon)].add(point.partner)
    return {location for location, owners in labels.items() if len(owners) > 1}


def flag_shared_locations(splitters, shared) -> None:
    """Recompute derived flags without accumulating flags across calls."""
    for point in splitters:
        point.flags[:] = [
            flag for flag in point.flags if flag != SHARED_COORDINATE_FLAG
        ]
        if point.valid and (point.lat, point.lon) in shared:
            point.flags.append(SHARED_COORDINATE_FLAG)


def flag_outside_extent(splitters, households) -> None:
    """Identify valid household positions outside the expanded splitter extent."""
    envelope = bounds(splitters)
    expanded = None
    if envelope:
        expanded = (
            envelope[0] - 0.25, envelope[1] - 0.25,
            envelope[2] + 0.25, envelope[3] + 0.25,
        )
    for point in households:
        point.flags[:] = [flag for flag in point.flags if flag != OUTSIDE_EXTENT_FLAG]
        if expanded and point.valid and not inside(point, expanded):
            point.flags.append(OUTSIDE_EXTENT_FLAG)


def point_quality(points) -> dict:
    """Count source records and flags without discarding duplicate locations."""
    return {
        "records": len(points),
        "valid_coordinates": sum(point.valid for point in points),
        "missing_or_invalid_coordinates": sum(not point.valid for point in points),
        "unique_coordinate_pairs": len({
            (point.lat, point.lon) for point in points if point.valid
        }),
        "bounds_west_south_east_north": bounds(points),
        "flags": dict(Counter(flag for point in points for flag in point.flags)),
    }


def profile(splitters, households) -> dict:
    """Combine full-source quality summaries and current derived review flags."""
    shared = shared_locations(splitters)
    flag_shared_locations(splitters, shared)
    flag_outside_extent(splitters, households)
    report = {
        "splitters": point_quality(splitters),
        "households": point_quality(households),
        "roads_available_in_inputs": False,
        "household_ownership_links_available": False,
    }
    report["splitters"]["distinct_csps"] = len({
        point.partner for point in splitters if point.partner
    })
    report["splitters"]["coordinates_shared_by_csps"] = len(shared)
    return report
