"""Pure table-row formatting for metric reports."""

from .markdown import format_number, markdown_text


def quality_rows(quality):
    """Format the same full-source indicators for both input populations."""
    specs = (
        ("Source records", "records", ","),
        ("Coordinates within numeric/geographic bounds",
         "coordinate_validity_pct", ".4f"),
        ("Missing or invalid coordinates", "missing_or_invalid_coordinates", ","),
        ("Unique coordinate pairs", "unique_coordinate_pairs", ","),
        ("Duplicate-coordinate excess records",
         "duplicate_coordinate_excess_records", ","),
        ("Duplicate-coordinate excess / valid records",
         "duplicate_coordinate_excess_pct_valid", ".4f"),
    )
    return [
        [label, *[
            (format(quality[name][key], spec) + ("%" if "pct" in key else ""))
            if quality[name][key] is not None else "N/A"
            for name in ("splitters", "households")
        ]]
        for label, key, spec in specs
    ]


def distribution_rows(matching, connectivity):
    """Apply one quantile-column order to every descriptive distribution."""
    return [
        [label, row["count"], *[
            format_number(row.get(key), 4)
            for key in ("min", "mean", "median", "p90", "p95", "p99", "max")
        ]]
        for label, row in (
            ("Matched road offsets (m)", matching["matched_offset_m"]),
            ("Ambiguous nearest candidate offsets (m)",
             matching["ambiguous_nearest_candidate_offset_m"]),
            ("Qualifying route lengths (m)", connectivity["qualifying_route_length_m"]),
            ("Patch sizes (splitters)", connectivity["patch_size_splitters"]),
            ("Link degree per matched splitter", connectivity["splitter_link_degree"]),
        )
    ]


def connectivity_rows(conn):
    """Format connectivity counts and measured lengths, keeping overlap explicit."""
    return [
        ["Patches / multi-splitter patches / singletons",
         f"{conn['patches']} / {conn['multi_splitter_patches']} / "
         f"{conn['singleton_patches']}"],
        ["Connected splitters (at least one same-CSP link)",
         conn["connected_splitters"]],
        ["Connected splitters / all pilot splitters",
         f"{conn['connected_pct_all_splitters']:.2f}%"],
        ["Connected splitters / matched splitters (%)",
         format_number(conn["connected_pct_of_matched_splitters"])],
        ["Singletons / patches (%)", format_number(conn["singleton_pct_of_patches"])],
        ["Qualifying links / zero-length links",
         f"{conn['qualifying_links']} / {conn['zero_length_links']}"],
        ["Links within 5 m below x", conn["links_within_5_m_of_threshold"]],
        ["Unique used physical road length",
         f"{conn['unique_used_road_length_m'] / 1000:.3f} km"],
        ["Sum of route lengths (includes shared stretches)",
         f"{conn['sum_route_lengths_m_including_overlap'] / 1000:.3f} km"],
    ]


def road_rows(road):
    """Format buffered graph measurements separately from splitter connectivity."""
    return [
        ["Buffered road nodes / segments / components",
         f"{road['nodes']} / {road['segments']} / {road['connected_components']}"],
        ["Largest buffered road component (nodes)", road["largest_component_nodes"]],
        ["Dead ends / junction nodes",
         f"{road['dead_end_nodes_degree_1']} / "
         f"{road['junction_nodes_degree_at_least_3']}"],
        ["Total buffered road length", f"{road['total_road_length_m'] / 1000:.3f} km"],
        ["Used / buffered road length (%)",
         format_number(road['used_road_length_pct'])],
    ]


def sensitivity_rows(rows):
    """Use the same comparison columns for each parameter sweep."""
    return [
        [
            f"{row['x_m']:g} / {row['snap_m']:g} / {row['ambiguity_m']:g}",
            row["matched"], row["ambiguous"], row["no_road_within_tolerance"],
            row["patches"], row["singleton_patches"], row["qualifying_links"],
            f"{row['unique_used_road_length_m'] / 1000:.3f}",
            format_number(row["qualifying_link_pair_jaccard_vs_baseline"], 4),
            format_number(row["partition_vs_baseline"]["adjusted_rand_index"], 4),
        ]
        for row in rows
    ]


def provider_rows(rows):
    """Display largest providers first and escape arbitrary identifier text."""
    return [
        [
            markdown_text(row["partner_id"]),
            row["splitters"], f"{row['match_rate_pct']:.2f}", row["unresolved"],
            row["patches"], row["singleton_patches"], row["qualifying_links"],
            format_number(row["mean_matched_offset_m"], 3),
        ]
        for row in sorted(rows, key=lambda value: -value["splitters"])
    ]
