"""Descriptive statistics and partition agreement, independent of file I/O."""

import math
from collections import Counter
from statistics import mean, median, pstdev


def percent(numerator, denominator):
    """Keep rates with an unknown denominator unavailable rather than zero."""
    return 100 * numerator / denominator if denominator else None


def distribution(values):
    """Linear-interpolated quantiles, including endpoints; population stddev."""
    values = sorted(values)
    if not values:
        return {"count": 0}

    def quantile(fraction):
        index = fraction * (len(values) - 1)
        lower = math.floor(index)
        return values[lower] + (
            values[math.ceil(index)] - values[lower]
        ) * (index - lower)

    return {
        "count": len(values), "min": values[0], "mean": mean(values),
        "median": median(values), "p90": quantile(0.9), "p95": quantile(0.95),
        "p99": quantile(0.99), "max": values[-1], "population_stddev": pstdev(values),
    }


def overlap(first, second):
    """Return set Jaccard, leaving an empty union undefined."""
    return len(first & second) / len(first | second) if first or second else None


def _pair_count(counts):
    return sum(math.comb(count, 2) for count in counts)


def partition_stability(first, second):
    """Compare partitions only over matched records shared by both analyses."""
    common = first.keys() & second.keys()
    count = len(common)
    if count < 2:
        return {
            "common_matched_records": count,
            "adjusted_rand_index": None, "co_cluster_pair_jaccard": None,
        }
    pairs_first = _pair_count(Counter(first[key] for key in common).values())
    pairs_second = _pair_count(Counter(second[key] for key in common).values())
    pairs_both = _pair_count(
        Counter((first[key], second[key]) for key in common).values()
    )
    expected = pairs_first * pairs_second / math.comb(count, 2)
    denominator = (pairs_first + pairs_second) / 2 - expected
    union = pairs_first + pairs_second - pairs_both
    return {
        "common_matched_records": count,
        "adjusted_rand_index": (
            (pairs_both - expected) / denominator if denominator else 1.0
        ),
        "co_cluster_pair_jaccard": pairs_both / union if union else 1.0,
    }
